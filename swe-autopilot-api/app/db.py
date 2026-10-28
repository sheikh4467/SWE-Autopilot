"""Small SQLite data layer for users, OAuth identities, and OAuth state."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_DATABASE_PATH = "./auth.db"


class UserExistsError(Exception):
    """Raised when a local user is created for an email that already exists."""


class VerificationCodeCooldownError(Exception):
    """Raised when a verification code was requested too recently."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Verification code resend cooldown is active.")
        self.retry_after = retry_after


VERIFICATION_CODE_PURPOSE = "email_verification"
VERIFICATION_CODE_TTL_SECONDS = 10 * 60
VERIFICATION_CODE_RESEND_COOLDOWN_SECONDS = 60
VERIFICATION_CODE_MAX_ATTEMPTS = 5
_VERIFICATION_CODE_SALT_BYTES = 16


def database_path() -> Path:
    """Return the configured SQLite path, creating its parent when needed."""

    configured_path = os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH).strip()
    path = Path(configured_path or DEFAULT_DATABASE_PATH).expanduser()
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                email_verified_at TEXT
            );

            CREATE TABLE IF NOT EXISTS oauth_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_account_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE (provider, provider_account_id),
                UNIQUE (provider, user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_oauth_accounts_user_id
                ON oauth_accounts(user_id);

            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                code_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                used_at REAL,
                purpose TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_verification_codes_user_purpose
                ON verification_codes(user_id, purpose, created_at);

            CREATE TABLE IF NOT EXISTS workspaces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workspace_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_workspace_events_user_created
                ON workspace_events(user_id, created_at);
            """
        )

        # Existing auth.db files predate email verification. Keep their rows
        # and add the column in place rather than replacing the table.
        user_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email_verified_at" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    init_db()
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _as_dict(row)


def get_user_by_email(email: str) -> dict[str, Any] | None:
    init_db()
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _as_dict(row)


def ensure_default_workspace(user_id: int, user_name: str) -> dict[str, Any]:
    """Create the user's initial workspace once and return it."""

    init_db()
    now = _now_iso()
    with connection() as conn:
        existing = conn.execute(
            "SELECT * FROM workspaces WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                """
                INSERT INTO workspaces (user_id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, f"{user_name}'s Workspace", now, now),
            )
            row = conn.execute(
                "SELECT * FROM workspaces WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        else:
            row = existing
    result = _as_dict(row)
    if result is None:  # pragma: no cover - guarded by insert/select
        raise RuntimeError("Default workspace could not be loaded.")
    return result


def record_workspace_event(user_id: int, event_type: str) -> None:
    """Record a small auditable event used by the live workspace telemetry."""

    init_db()
    with connection() as conn:
        conn.execute(
            "INSERT INTO workspace_events (user_id, event_type, created_at) VALUES (?, ?, ?)",
            (user_id, event_type, _now_iso()),
        )


def get_workspace_stats(user_id: int) -> dict[str, Any]:
    """Return current workspace telemetry for one authenticated user."""

    init_db()
    now = datetime.now(timezone.utc)
    day_keys = []
    for offset in range(6, -1, -1):
        day = now.date() - timedelta(days=offset)
        day_keys.append((day.isoformat(), day.strftime("%a")))

    with connection() as conn:
        workspace_count = int(
            conn.execute(
                "SELECT COUNT(*) AS count FROM workspaces WHERE user_id = ?", (user_id,)
            ).fetchone()["count"]
        )
        event_rows = conn.execute(
            """
            SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count
            FROM workspace_events
            WHERE user_id = ? AND created_at >= ?
            GROUP BY substr(created_at, 1, 10)
            """,
            (user_id, (now - timedelta(days=6)).isoformat()),
        ).fetchall()
        event_counts = {str(row["day"]): int(row["count"]) for row in event_rows}
        work_counts = {
            str(row["event_type"]): int(row["count"])
            for row in conn.execute(
                """
                SELECT event_type, COUNT(*) AS count
                FROM workspace_events
                WHERE user_id = ?
                GROUP BY event_type
                """,
                (user_id,),
            ).fetchall()
        }

    requirements = work_counts.get("requirement_created", 0)
    artifacts = work_counts.get("artifact_created", 0)
    agent_runs = work_counts.get("agent_run_started", 0)
    verifications = work_counts.get("verification_completed", 0)
    return {
        "metrics": [
            {"key": "workspaces", "label": "Workspaces", "value": workspace_count, "tone": "cyan"},
            {"key": "requirements", "label": "Requirements", "value": requirements, "tone": "violet"},
            {"key": "artifacts", "label": "Artifacts", "value": artifacts, "tone": "lime"},
            {"key": "agent_runs", "label": "Agent runs", "value": agent_runs, "tone": "orange"},
        ],
        "distribution": [
            {"label": "Requirements", "value": requirements, "tone": "cyan"},
            {"label": "Artifacts", "value": artifacts, "tone": "violet"},
            {"label": "Agent runs", "value": agent_runs, "tone": "lime"},
            {"label": "Verification", "value": verifications, "tone": "orange"},
        ],
        "activity": [
            {"label": label, "value": event_counts.get(day, 0)}
            for day, label in day_keys
        ],
        "last_updated": now.isoformat(),
        "note": "Live workspace telemetry. Work counters populate as project actions are added.",
    }


def create_local_user(email: str, name: str, password_hash: str) -> dict[str, Any]:
    init_db()
    now = _now_iso()
    try:
        with connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (email, name, password_hash, now, now),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as exc:
        raise UserExistsError from exc

    result = _as_dict(row)
    if result is None:  # pragma: no cover - guarded by the insert above
        raise RuntimeError("Created user could not be loaded.")
    return result


def create_or_reuse_local_user(email: str, name: str, password_hash: str) -> dict[str, Any]:
    """Create a local user or refresh an existing unverified local account."""

    init_db()
    now = _now_iso()
    with connection() as conn:
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            if existing["email_verified_at"] is not None:
                raise UserExistsError
            conn.execute(
                """
                UPDATE users
                SET name = ?, password_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, password_hash, now, existing["id"]),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (existing["id"],)).fetchone()
        else:
            cursor = conn.execute(
                """
                INSERT INTO users
                    (email, name, password_hash, created_at, updated_at, email_verified_at)
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (email, name, password_hash, now, now),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()

    result = _as_dict(row)
    if result is None:  # pragma: no cover - guarded by the insert/update above
        raise RuntimeError("Local user could not be loaded.")
    return result


def find_or_create_oauth_user(
    provider: str,
    provider_account_id: str,
    email: str,
    name: str,
) -> dict[str, Any]:
    """Find an OAuth identity, or link it to/create the matching email user."""

    init_db()
    now = _now_iso()
    with connection() as conn:
        account = conn.execute(
            """
            SELECT user_id
            FROM oauth_accounts
            WHERE provider = ? AND provider_account_id = ?
            """,
            (provider, provider_account_id),
        ).fetchone()

        if account is not None:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (account["user_id"],)).fetchone()
            result = _as_dict(row)
            if result is None:  # pragma: no cover - foreign key protects this
                raise RuntimeError("OAuth account points to a missing user.")
            return result

        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None:
            cursor = conn.execute(
                """
                INSERT INTO users
                    (email, name, password_hash, created_at, updated_at, email_verified_at)
                VALUES (?, ?, NULL, ?, ?, NULL)
                """,
                (email, name, now, now),
            )
            user_id = cursor.lastrowid
        else:
            user_id = user["id"]

        conn.execute(
            """
            INSERT INTO oauth_accounts
                (user_id, provider, provider_account_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, provider, provider_account_id, now),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    result = _as_dict(row)
    if result is None:  # pragma: no cover - guarded by the insert above
        raise RuntimeError("OAuth user could not be loaded.")
    return result


def mark_user_email_verified(user_id: int) -> dict[str, Any] | None:
    """Mark a user verified and return the current row."""

    init_db()
    now = _now_iso()
    with connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET email_verified_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, user_id),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _as_dict(row)


def issue_verification_code(
    user_id: int,
    email: str,
    *,
    purpose: str = VERIFICATION_CODE_PURPOSE,
    ttl_seconds: int = VERIFICATION_CODE_TTL_SECONDS,
    enforce_cooldown: bool = True,
) -> str:
    """Create a short-lived code while persisting only its salted hash."""

    init_db()
    now = time.time()
    with connection() as conn:
        latest = conn.execute(
            """
            SELECT created_at
            FROM verification_codes
            WHERE user_id = ? AND purpose = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, purpose),
        ).fetchone()
        if enforce_cooldown and latest is not None:
            elapsed = max(0.0, now - float(latest["created_at"]))
            if elapsed < VERIFICATION_CODE_RESEND_COOLDOWN_SECONDS:
                retry_after = int(VERIFICATION_CODE_RESEND_COOLDOWN_SECONDS - elapsed) + 1
                raise VerificationCodeCooldownError(retry_after)

        # A newly issued code supersedes any older active code for this user.
        conn.execute(
            """
            UPDATE verification_codes
            SET used_at = ?
            WHERE user_id = ? AND purpose = ? AND used_at IS NULL
            """,
            (now, user_id, purpose),
        )

        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_bytes(_VERIFICATION_CODE_SALT_BYTES)
        digest = hashlib.sha256(salt + code.encode("ascii")).hexdigest()
        code_hash = f"{salt.hex()}${digest}"
        conn.execute(
            """
            INSERT INTO verification_codes
                (user_id, email, code_hash, expires_at, attempts, used_at, purpose, created_at)
            VALUES (?, ?, ?, ?, 0, NULL, ?, ?)
            """,
            (user_id, email, code_hash, now + ttl_seconds, purpose, now),
        )
    return code


def invalidate_latest_verification_code(
    user_id: int,
    *,
    purpose: str = VERIFICATION_CODE_PURPOSE,
) -> None:
    """Invalidate the newest code when delivery did not complete."""

    init_db()
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM verification_codes
            WHERE user_id = ? AND purpose = ? AND used_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id, purpose),
        ).fetchone()
        if row is not None:
            conn.execute(
                "UPDATE verification_codes SET used_at = ? WHERE id = ?",
                (time.time(), row["id"]),
            )


def verify_email_code(
    email: str,
    code: str,
    *,
    purpose: str = VERIFICATION_CODE_PURPOSE,
) -> dict[str, Any] | None:
    """Validate the latest code, counting failed attempts atomically."""

    if not isinstance(code, str):
        return None

    init_db()
    now = time.time()
    with connection() as conn:
        row = conn.execute(
            """
            SELECT vc.*
            FROM verification_codes AS vc
            JOIN users AS u ON u.id = vc.user_id
            WHERE u.email = ? AND vc.purpose = ? AND vc.used_at IS NULL
            ORDER BY vc.created_at DESC
            LIMIT 1
            """,
            (email, purpose),
        ).fetchone()
        if row is None:
            return None

        attempts = int(row["attempts"])
        if row["expires_at"] <= now or attempts >= VERIFICATION_CODE_MAX_ATTEMPTS:
            conn.execute(
                "UPDATE verification_codes SET used_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            return None

        next_attempts = attempts + 1
        conn.execute(
            "UPDATE verification_codes SET attempts = ? WHERE id = ?",
            (next_attempts, row["id"]),
        )

        try:
            salt_hex, expected_digest = str(row["code_hash"]).split("$", 1)
            salt = bytes.fromhex(salt_hex)
            actual_digest = hashlib.sha256(salt + code.encode("ascii")).hexdigest()
        except (ValueError, UnicodeError):
            actual_digest = ""
            expected_digest = "!"

        if not hmac.compare_digest(actual_digest, expected_digest):
            if next_attempts >= VERIFICATION_CODE_MAX_ATTEMPTS:
                conn.execute(
                    "UPDATE verification_codes SET used_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
            return None

        conn.execute(
            "UPDATE verification_codes SET used_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        verified_at = _now_iso()
        conn.execute(
            """
            UPDATE users
            SET email_verified_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (verified_at, verified_at, row["user_id"]),
        )
        user = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
    return _as_dict(user)


def save_oauth_state(state: str, provider: str, redirect_uri: str) -> None:
    init_db()
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO oauth_states (state, provider, redirect_uri, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (state, provider, redirect_uri, time.time()),
        )


def consume_oauth_state(state: str, max_age_seconds: int = 600) -> dict[str, Any] | None:
    init_db()
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM oauth_states WHERE state = ?", (state,)
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))

    if time.time() - float(row["created_at"]) > max_age_seconds:
        return None
    return _as_dict(row)
