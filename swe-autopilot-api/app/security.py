"""Password hashing helpers for local email/password authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LENGTH = 64
_SALT_LENGTH = 16


def hash_password(password: str) -> str:
    """Return a self-contained scrypt password hash.

    The encoded value contains only the scrypt parameters, a random salt, and
    the derived key. The original password is never persisted.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    salt = secrets.token_bytes(_SALT_LENGTH)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_LENGTH,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_key = base64.b64encode(derived_key).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${encoded_salt}${encoded_key}"


def verify_password(password: str, encoded_hash: str | None) -> bool:
    """Verify a password against a hash produced by :func:`hash_password`."""

    if not isinstance(password, str) or not isinstance(encoded_hash, str):
        return False

    try:
        algorithm, n_text, r_text, p_text, salt_text, key_text = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False

        n = int(n_text)
        r = int(r_text)
        p = int(p_text)
        salt = base64.b64decode(salt_text.encode("ascii"), validate=True)
        expected_key = base64.b64decode(key_text.encode("ascii"), validate=True)

        # Only accept the parameters emitted by this service. This keeps a
        # malformed database value from requesting unbounded work at login.
        if (n, r, p) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P):
            return False
        if len(salt) != _SALT_LENGTH or len(expected_key) != _KEY_LENGTH:
            return False

        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_key),
        )
        return hmac.compare_digest(actual_key, expected_key)
    except (TypeError, ValueError, UnicodeError):
        return False
