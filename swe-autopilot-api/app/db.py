"""Small SQLite data layer for users, OAuth identities, and OAuth state."""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_DATABASE_PATH = "./auth.db"


class UserExistsError(Exception):
    """Raised when a local user is created for an email that already exists."""


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
                updated_at TEXT NOT NULL
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
            """
        )


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
                INSERT INTO users (email, name, password_hash, created_at, updated_at)
                VALUES (?, ?, NULL, ?, ?)
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
