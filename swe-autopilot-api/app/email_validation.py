"""ZeroBounce-backed email validation for account signup."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx


DEFAULT_ZEROBOUNCE_API_URL = "https://api-us.zerobounce.net/v2/validate"
DEFAULT_ZEROBOUNCE_TIMEOUT_SECONDS = 30


class EmailValidationConfigurationError(Exception):
    """Raised when the ZeroBounce integration is not configured."""


class EmailValidationServiceError(Exception):
    """Raised when ZeroBounce cannot return a usable validation result."""


@dataclass(frozen=True)
class EmailValidationResult:
    address: str
    status: str
    sub_status: str = ""
    did_you_mean: str | None = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _timeout_seconds() -> int:
    raw_value = os.getenv(
        "ZEROBOUNCE_TIMEOUT_SECONDS",
        str(DEFAULT_ZEROBOUNCE_TIMEOUT_SECONDS),
    ).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise EmailValidationConfigurationError(
            "ZEROBOUNCE_TIMEOUT_SECONDS must be a whole number between 3 and 60."
        ) from exc
    if not 3 <= value <= 60:
        raise EmailValidationConfigurationError(
            "ZEROBOUNCE_TIMEOUT_SECONDS must be a whole number between 3 and 60."
        )
    return value


def is_required() -> bool:
    """Return whether signup must pass ZeroBounce validation."""

    return _env_bool("ZEROBOUNCE_REQUIRED", True)


async def validate_email(
    email: str,
    *,
    ip_address: str = "",
) -> EmailValidationResult:
    """Validate one address using ZeroBounce's v2 single-email endpoint."""

    api_key = os.getenv("ZEROBOUNCE_API_KEY", "").strip()
    if not api_key:
        if is_required():
            raise EmailValidationConfigurationError(
                "ZEROBOUNCE_API_KEY is not configured."
            )
        return EmailValidationResult(address=email, status="valid")

    api_url = os.getenv("ZEROBOUNCE_API_URL", DEFAULT_ZEROBOUNCE_API_URL).strip()
    if not api_url.startswith("https://"):
        raise EmailValidationConfigurationError(
            "ZEROBOUNCE_API_URL must use HTTPS."
        )

    timeout_seconds = _timeout_seconds()
    payload = {
        "api_key": api_key,
        "email": email,
        "ip_address": ip_address,
        "timeout": str(timeout_seconds),
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(api_url, data=payload)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise EmailValidationServiceError(
            "The email validation service could not be reached."
        ) from exc

    if not isinstance(body, dict):
        raise EmailValidationServiceError(
            "The email validation service returned an invalid response."
        )

    if body.get("error"):
        # Do not expose provider details such as API-key or credit errors to
        # the browser, and never include the secret in an exception message.
        raise EmailValidationServiceError(
            "The email validation service rejected the request."
        )

    status = str(body.get("status") or "").strip().lower()
    if not status:
        raise EmailValidationServiceError(
            "The email validation service returned no status."
        )

    return EmailValidationResult(
        address=str(body.get("address") or email),
        status=status,
        sub_status=str(body.get("sub_status") or "").strip().lower(),
        did_you_mean=(
            str(body["did_you_mean"]).strip()
            if body.get("did_you_mean")
            else None
        ),
    )
