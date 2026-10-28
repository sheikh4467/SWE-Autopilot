"""Standard-library SMTP delivery for email verification codes."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


class MailConfigurationError(Exception):
    """Raised when SMTP settings are missing or invalid."""


class MailDeliveryError(Exception):
    """Raised when an SMTP server cannot accept the message."""


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_tls: bool


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def email_verification_required() -> bool:
    """Return whether OAuth users must complete email verification."""

    return _env_bool("EMAIL_VERIFICATION_REQUIRED", True)


def smtp_config() -> SMTPConfig:
    """Read SMTP configuration from the environment without exposing secrets."""

    host = os.getenv("SMTP_HOST", "").strip()
    port_text = os.getenv("SMTP_PORT", "587").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    use_tls = _env_bool("SMTP_USE_TLS", True)

    if not host or not from_email:
        raise MailConfigurationError(
            "SMTP_HOST and SMTP_FROM_EMAIL must be configured for verification email."
        )
    try:
        port = int(port_text)
    except (TypeError, ValueError) as exc:
        raise MailConfigurationError("SMTP_PORT must be a valid port number.") from exc
    if not 1 <= port <= 65535:
        raise MailConfigurationError("SMTP_PORT must be a valid port number.")
    if bool(username) != bool(password):
        raise MailConfigurationError(
            "SMTP_USERNAME and SMTP_PASSWORD must be configured together."
        )

    return SMTPConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        from_email=from_email,
        use_tls=use_tls,
    )


def send_verification_email(recipient: str, code: str) -> None:
    """Send a verification code without returning or logging the code."""

    config = smtp_config()
    message = EmailMessage()
    message["Subject"] = "Verify your SWE Autopilot email"
    message["From"] = config.from_email
    message["To"] = recipient
    message.set_content(
        "Your SWE Autopilot verification code is "
        f"{code}. It expires in 10 minutes.\n\n"
        "If you did not create this account, you can ignore this email."
    )

    try:
        with smtplib.SMTP(config.host, config.port, timeout=15) as server:
            if config.use_tls:
                server.starttls()
            if config.username:
                server.login(config.username, config.password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("Verification email could not be sent.") from exc
