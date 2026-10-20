"""FastAPI authentication service for SWE Autopilot."""

from __future__ import annotations

import os
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
    create_local_user,
    find_or_create_oauth_user,
    get_user_by_email,
    get_user_by_id,
    init_db,
    save_oauth_state,
)
from .security import hash_password, verify_password


load_dotenv()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").strip().rstrip("/")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").strip().rstrip("/")
SESSION_SECRET = os.getenv(
    "SESSION_SECRET", "local-development-session-secret-change-me"
).strip()


class SignupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)


class LoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if (
        len(normalized) > 320
        or normalized.count("@") != 1
        or not normalized.split("@", 1)[0]
        or not normalized.split("@", 1)[1]
        or " " in normalized
    ):
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")
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
    return f"{FRONTEND_URL}/?{query}"


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
    if not provider_account_id or not email:
        raise HTTPException(
            status_code=400,
            detail="Google did not return a usable account id and email address.",
        )
    name = str(profile.get("name") or email.split("@", 1)[0]).strip()
    return provider_account_id, email, name[:120]


async def _github_identity(
    client: AsyncOAuth2Client, config: dict[str, str]
) -> tuple[str, str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    response = await client.get(config["userinfo_endpoint"], headers=headers)
    response.raise_for_status()
    profile = response.json()
    provider_account_id = str(profile.get("id") or "").strip()
    email = str(profile.get("email") or "").strip()

    # GitHub may omit the public email from /user. The user:email scope lets us
    # retrieve the account's verified/primary addresses from /user/emails.
    if not email:
        email_response = await client.get(config["email_endpoint"], headers=headers)
        email_response.raise_for_status()
        addresses = email_response.json()
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
            fallback = next(
                (
                    item.get("email")
                    for item in addresses
                    if isinstance(item, dict) and item.get("email")
                ),
                None,
            )
            email = str(preferred or verified or fallback or "").strip()

    if not provider_account_id or not email:
        raise HTTPException(
            status_code=400,
            detail="GitHub did not return a usable account id and email address.",
        )
    name = str(profile.get("name") or profile.get("login") or email.split("@", 1)[0]).strip()
    return provider_account_id, email, name[:120]


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

    email = _normalize_email(email)
    user = find_or_create_oauth_user(provider, provider_account_id, email, name)
    _set_authenticated_user(request, user)
    return RedirectResponse(_success_redirect(provider), status_code=status.HTTP_302_FOUND)


@app.post("/auth/signup")
async def signup(payload: SignupPayload, request: Request) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be blank.")

    try:
        user = create_local_user(email, name, hash_password(payload.password))
    except UserExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="An account with that email already exists.",
        ) from exc

    _set_authenticated_user(request, user)
    return _public_user(user)


@app.post("/auth/login")
async def login(payload: LoginPayload, request: Request) -> dict[str, Any]:
    email = _normalize_email(payload.email)
    user = get_user_by_email(email)
    if user is None or not verify_password(payload.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _set_authenticated_user(request, user)
    return _public_user(user)


@app.get("/auth/me")
async def me(request: Request) -> dict[str, Any]:
    return _public_user(_current_user(request))


@app.post("/auth/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}
