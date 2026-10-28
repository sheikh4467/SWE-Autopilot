"""FastAPI authentication service for SWE Autopilot."""

from __future__ import annotations

import os
import re
import socket
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlencode

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse

from .db import (
    UserExistsError,
    consume_oauth_state,
    create_or_reuse_local_user,
    ensure_default_workspace,
    find_or_create_oauth_user,
    get_workspace_stats,
    get_user_by_email,
    get_user_by_id,
    invalidate_latest_verification_code,
    init_db,
    issue_verification_code,
    mark_user_email_verified,
    record_workspace_event,
    save_oauth_state,
    VerificationCodeCooldownError,
    verify_email_code,
)
from . import email_validation
from . import mail
from .security import hash_password, verify_password


load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
SESSION_SECRET = os.getenv(
    "SESSION_SECRET", "local-development-session-secret-change-me"
).strip()
MAX_FULL_NAME_LENGTH = 24


class SignupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_FULL_NAME_LENGTH)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)


class LoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class VerifyEmailPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    code: str = Field(min_length=1, max_length=32)


class ResendVerificationPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)


_EMAIL_LOCAL_PART_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_EMAIL_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _normalize_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if not normalized:
        raise HTTPException(status_code=422, detail="Full name must not be blank.")
    if len(normalized) > MAX_FULL_NAME_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Full name must be {MAX_FULL_NAME_LENGTH} characters or fewer.",
        )
    if any(ord(character) < 32 for character in normalized):
        raise HTTPException(status_code=422, detail="Full name contains invalid characters.")
    return normalized


def _check_email_domain(domain: str) -> None:
    if not _env_bool("EMAIL_DOMAIN_CHECK", True):
        return
    try:
        # This confirms that the domain can resolve. It does not claim that a
        # particular mailbox exists; only the OTP can prove mailbox access.
        socket.getaddrinfo(domain, 25, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise HTTPException(
            status_code=422,
            detail="The email domain could not be reached. Check the address and try again.",
        ) from exc


def _normalize_email(email: str, *, check_domain: bool = True) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 320 or any(ord(character) < 33 or character.isspace() for character in normalized):
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")

    if normalized.count("@") != 1:
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")

    local_part, domain = normalized.rsplit("@", 1)
    if (
        not local_part
        or len(local_part) > 64
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or not _EMAIL_LOCAL_PART_RE.fullmatch(local_part)
        or len(domain) > 253
        or "." not in domain
    ):
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")

    labels = domain.split(".")
    if (
        len(labels) < 2
        or len(labels[-1]) < 2
        or any(not _EMAIL_DOMAIN_LABEL_RE.fullmatch(label) for label in labels)
    ):
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")

    if check_domain:
        _check_email_domain(domain)
    return normalized


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "created_at": user["created_at"],
    }


def _set_authenticated_user(request: Request, user: dict[str, Any]) -> None:
    # OAuth state is kept server-side in SQLite. The signed session cookie only
    # needs this one value for every authenticated request.
    request.session.clear()
    request.session["user_id"] = int(user["id"])


def _current_user(request: Request) -> dict[str, Any]:
    user_id = request.session.get("user_id")
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Authentication required.")

    user = get_user_by_id(user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _provider_config(provider: str) -> dict[str, str]:
    provider = provider.lower()
    if provider == "google":
        client_id_name = "GOOGLE_CLIENT_ID"
        client_secret_name = "GOOGLE_CLIENT_SECRET"
        config = {
            "name": "Google",
            "client_id": os.getenv(client_id_name, "").strip(),
            "client_secret": os.getenv(client_secret_name, "").strip(),
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
            "scope": "openid email profile",
            "client_id_name": client_id_name,
            "client_secret_name": client_secret_name,
        }
    elif provider == "github":
        client_id_name = "GITHUB_CLIENT_ID"
        client_secret_name = "GITHUB_CLIENT_SECRET"
        config = {
            "name": "GitHub",
            "client_id": os.getenv(client_id_name, "").strip(),
            "client_secret": os.getenv(client_secret_name, "").strip(),
            "authorization_endpoint": "https://github.com/login/oauth/authorize",
            "token_endpoint": "https://github.com/login/oauth/access_token",
            "userinfo_endpoint": "https://api.github.com/user",
            "email_endpoint": "https://api.github.com/user/emails",
            "scope": "read:user user:email",
            "client_id_name": client_id_name,
            "client_secret_name": client_secret_name,
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="Unsupported OAuth provider. Use google or github.",
        )

    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{config['name']} OAuth is not configured. Set "
                f"{config['client_id_name']} and {config['client_secret_name']}."
            ),
        )
    return config


def _redirect_uri(provider: str) -> str:
    return f"{BACKEND_URL}/auth/{provider}/callback"


def _success_redirect(provider: str) -> str:
    query = urlencode({"auth": "success", "provider": provider})
    return f"{FRONTEND_URL}/workspace?{query}"


def _verification_redirect(provider: str, email: str) -> str:
    query = urlencode({"auth": "verify", "provider": provider, "email": email})
    return f"{FRONTEND_URL}/?{query}"


def send_verification_email(recipient: str, code: str) -> None:
    """Patchable application boundary around the SMTP helper."""

    mail.send_verification_email(recipient, code)


def _send_verification_code(
    user: dict[str, Any], *, enforce_cooldown: bool = True
) -> None:
    code = issue_verification_code(
        int(user["id"]),
        str(user["email"]),
        enforce_cooldown=enforce_cooldown,
    )
    try:
        send_verification_email(str(user["email"]), code)
    except mail.MailConfigurationError as exc:
        invalidate_latest_verification_code(int(user["id"]))
        raise HTTPException(
            status_code=503,
            detail="Email verification is not configured.",
        ) from exc
    except mail.MailDeliveryError as exc:
        invalidate_latest_verification_code(int(user["id"]))
        raise HTTPException(
            status_code=503,
            detail="Unable to send verification email.",
        ) from exc


async def _validate_signup_email(email: str, request: Request) -> None:
    """Require a confirmed ZeroBounce result before creating a local user."""

    client_host = request.client.host if request.client is not None else ""
    try:
        result = await email_validation.validate_email(
            email,
            ip_address=client_host,
        )
    except email_validation.EmailValidationConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Email validation is not configured.",
        ) from exc
    except email_validation.EmailValidationServiceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Email validation is temporarily unavailable. Please try again.",
        ) from exc

    if result.status == "valid" and result.sub_status not in {
        "alias_address",
        "accept_all",
        "role_based_accept_all",
        "role_based_catch_all",
    }:
        return

    if result.status == "invalid" and result.sub_status == "possible_typo" and result.did_you_mean:
        raise HTTPException(
            status_code=422,
            detail=f"This email address appears invalid. Did you mean {result.did_you_mean}?",
        )

    if result.status in {"invalid", "spamtrap", "abuse", "do_not_mail"}:
        raise HTTPException(
            status_code=422,
            detail="This email address could not be verified. Please use a valid email address.",
        )

    # catch-all and unknown cannot prove that this specific mailbox exists.
    raise HTTPException(
        status_code=422,
        detail="We could not confirm that this mailbox exists. Please use a different email address.",
    )


def _oauth_client(config: dict[str, str], redirect_uri: str) -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token_endpoint_auth_method=(
            "client_secret_post" if config["name"] == "GitHub" else "client_secret_basic"
        ),
        scope=config["scope"],
        redirect_uri=redirect_uri,
    )


async def _google_identity(
    client: AsyncOAuth2Client, config: dict[str, str]
) -> tuple[str, str, str]:
    response = await client.get(config["userinfo_endpoint"])
    response.raise_for_status()
    profile = response.json()
    provider_account_id = str(profile.get("sub") or "").strip()
    email = str(profile.get("email") or "").strip()
    email_verified = profile.get("email_verified") is True
    if not provider_account_id or not email or not email_verified:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a verified email address.",
        )
    name = str(profile.get("name") or email.split("@", 1)[0]).strip()
    return provider_account_id, email, name[:MAX_FULL_NAME_LENGTH]


async def _github_identity(
    client: AsyncOAuth2Client, config: dict[str, str]
) -> tuple[str, str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    response = await client.get(config["userinfo_endpoint"], headers=headers)
    response.raise_for_status()
    profile = response.json()
    provider_account_id = str(profile.get("id") or "").strip()
    email_response = await client.get(config["email_endpoint"], headers=headers)
    email_response.raise_for_status()
    addresses = email_response.json()
    email = ""
    if isinstance(addresses, list):
        preferred = next(
            (
                item.get("email")
                for item in addresses
                if isinstance(item, dict)
                and item.get("primary")
                and item.get("verified")
                and item.get("email")
            ),
            None,
        )
        verified = next(
            (
                item.get("email")
                for item in addresses
                if isinstance(item, dict)
                and item.get("verified")
                and item.get("email")
            ),
            None,
        )
        email = str(preferred or verified or "").strip()

    if not provider_account_id or not email:
        raise HTTPException(
            status_code=400,
            detail="GitHub did not return a verified email address.",
        )
    name = str(profile.get("name") or profile.get("login") or email.split("@", 1)[0]).strip()
    return provider_account_id, email, name[:MAX_FULL_NAME_LENGTH]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="SWE Autopilot Auth API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="swe_autopilot_session",
    same_site="lax",
    https_only=BACKEND_URL.startswith("https://"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/{provider}/login")
async def oauth_login(provider: str) -> RedirectResponse:
    provider = provider.lower()
    config = _provider_config(provider)
    redirect_uri = _redirect_uri(provider)
    client = _oauth_client(config, redirect_uri)
    try:
        authorization_url, state = client.create_authorization_url(
            config["authorization_endpoint"],
            redirect_uri=redirect_uri,
            prompt="select_account",
        )
        save_oauth_state(state, provider, redirect_uri)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to start {config['name']} OAuth.",
        ) from exc
    finally:
        await client.aclose()
    return RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)


@app.get("/auth/{provider}/callback")
async def oauth_callback(provider: str, request: Request) -> RedirectResponse:
    provider = provider.lower()
    config = _provider_config(provider)
    state = request.query_params.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="OAuth state is missing.")

    state_record = consume_oauth_state(state)
    if state_record is None or state_record["provider"] != provider:
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired.")
    if request.query_params.get("error"):
        error_description = request.query_params.get("error_description") or "authorization was denied"
        raise HTTPException(status_code=400, detail=f"OAuth {error_description}.")
    if not request.query_params.get("code"):
        raise HTTPException(status_code=400, detail="OAuth authorization code is missing.")

    client = _oauth_client(config, str(state_record["redirect_uri"]))
    try:
        token_headers = {"Accept": "application/json"} if provider == "github" else None
        await client.fetch_token(
            config["token_endpoint"],
            authorization_response=str(request.url),
            redirect_uri=str(state_record["redirect_uri"]),
            headers=token_headers,
        )
        if provider == "google":
            provider_account_id, email, name = await _google_identity(client, config)
        else:
            provider_account_id, email, name = await _github_identity(client, config)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{config['name']} OAuth request failed.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{config['name']} OAuth request failed.",
        ) from exc
    finally:
        await client.aclose()

    email = _normalize_email(email, check_domain=False)
    user = find_or_create_oauth_user(provider, provider_account_id, email, name)

    if not user.get("email_verified_at"):
        if not mail.email_verification_required():
            verified_user = mark_user_email_verified(int(user["id"]))
            if verified_user is not None:
                user = verified_user
        else:
            try:
                _send_verification_code(user)
            except VerificationCodeCooldownError:
                # A valid, recently sent code remains usable. Do not issue a
                # second message while the resend cooldown is active.
                pass
            return RedirectResponse(
                _verification_redirect(provider, str(user["email"])),
                status_code=status.HTTP_302_FOUND,
            )

    ensure_default_workspace(int(user["id"]), str(user["name"]))
    record_workspace_event(int(user["id"]), "oauth_login")
    _set_authenticated_user(request, user)
    return RedirectResponse(_success_redirect(provider), status_code=status.HTTP_302_FOUND)


@app.post("/auth/signup")
async def signup(payload: SignupPayload, request: Request) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    name = _normalize_name(payload.name)

    await _validate_signup_email(email, request)

    try:
        user = create_or_reuse_local_user(email, name, hash_password(payload.password))
    except UserExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="An account with that email already exists.",
        ) from exc

    try:
        _send_verification_code(user)
    except VerificationCodeCooldownError as exc:
        raise HTTPException(
            status_code=429,
            detail="Please wait before requesting another verification email.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    return {
        "verification_required": True,
        "email": email,
        "message": "If this address can receive email, check it for a verification code.",
    }


@app.post("/auth/login")
async def login(payload: LoginPayload, request: Request) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    user = get_user_by_email(email)
    if user is None or not verify_password(payload.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.get("email_verified_at"):
        try:
            _send_verification_code(user)
        except VerificationCodeCooldownError:
            # A recently issued code is still valid; do not send a duplicate.
            pass
        raise HTTPException(
            status_code=403,
            detail={
                "verification_required": True,
                "email": email,
                "message": "Email verification is required before login.",
            },
        )

    ensure_default_workspace(int(user["id"]), str(user["name"]))
    record_workspace_event(int(user["id"]), "login")
    _set_authenticated_user(request, user)
    return _public_user(user)


@app.post("/auth/verify-email")
async def verify_email(payload: VerifyEmailPayload, request: Request) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    user = verify_email_code(email, payload.code)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    ensure_default_workspace(int(user["id"]), str(user["name"]))
    record_workspace_event(int(user["id"]), "email_verified")
    _set_authenticated_user(request, user)
    return _public_user(user)


@app.post("/auth/resend-verification")
async def resend_verification(payload: ResendVerificationPayload) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    user = get_user_by_email(email)
    if user is not None and not user.get("email_verified_at"):
        try:
            _send_verification_code(user)
        except VerificationCodeCooldownError:
            # Keep the response identical for unknown, verified, and
            # cooldown-limited addresses.
            pass
    return {
        "ok": True,
        "message": "If an unverified account exists, a verification email has been sent.",
    }


@app.get("/auth/me")
async def me(request: Request) -> dict[str, Any]:
    return _public_user(_current_user(request))


@app.get("/workspace/stats")
async def workspace_stats(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    ensure_default_workspace(int(user["id"]), str(user["name"]))
    return get_workspace_stats(int(user["id"]))


@app.post("/auth/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}
