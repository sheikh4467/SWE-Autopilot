from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse


_database_path = Path(tempfile.gettempdir()) / "swe-autopilot-auth-tests.db"
_database_path.unlink(missing_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(
    {
        "DATABASE_PATH": str(_database_path),
        "FRONTEND_URL": "http://frontend.test",
        "BACKEND_URL": "http://backend.test",
        "SESSION_SECRET": "test-session-secret",
        "GOOGLE_CLIENT_ID": "test-google-client",
        "GOOGLE_CLIENT_SECRET": "test-google-secret",
        "GITHUB_CLIENT_ID": "test-github-client",
        "GITHUB_CLIENT_SECRET": "test-github-secret",
        "EMAIL_VERIFICATION_REQUIRED": "true",
        "EMAIL_DOMAIN_CHECK": "false",
        "ZEROBOUNCE_REQUIRED": "false",
        "ZEROBOUNCE_API_KEY": "",
    }
)

import httpx

from app import db, main


class AuthRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        db.init_db()

    async def asyncTearDown(self) -> None:
        with db.connection() as conn:
            conn.execute("DELETE FROM verification_codes")
            conn.execute("DELETE FROM oauth_accounts")
            conn.execute("DELETE FROM oauth_states")
            conn.execute("DELETE FROM users")

    async def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://backend.test",
        )

    async def test_oauth_authorization_selects_provider_account(self) -> None:
        async with await self._client() as client:
            for provider in ("google", "github"):
                response = await client.get(f"/auth/{provider}/login", follow_redirects=False)
                self.assertEqual(response.status_code, 302)
                query = parse_qs(urlparse(response.headers["location"]).query)
                self.assertEqual(query["prompt"], ["select_account"])
                self.assertIn("state", query)

    async def test_oauth_verification_redirect_and_optional_bypass(self) -> None:
        class FakeResponse:
            def __init__(self, profile: dict[str, str]) -> None:
                self.profile = profile

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, str]:
                return self.profile

        class FakeOAuthClient:
            def __init__(self, profile: dict[str, str]) -> None:
                self.profile = profile

            async def fetch_token(self, *args: object, **kwargs: object) -> None:
                return None

            async def get(self, *args: object, **kwargs: object) -> FakeResponse:
                return FakeResponse(self.profile)

            async def aclose(self) -> None:
                return None

        async with await self._client() as client:
            profile = {
                "sub": "google-verify",
                "email": "oauth@example.com",
                "email_verified": True,
                "name": "OAuth User",
            }
            with patch.object(main, "_oauth_client", return_value=FakeOAuthClient(profile)):
                db.save_oauth_state(
                    "verify-state",
                    "google",
                    "http://backend.test/auth/google/callback",
                )
                with patch.object(main, "send_verification_email") as sender:
                    response = await client.get(
                        "/auth/google/callback?state=verify-state&code=test-code",
                        follow_redirects=False,
                    )
                self.assertEqual(response.status_code, 302)
                query = parse_qs(urlparse(response.headers["location"]).query)
                self.assertEqual(query["auth"], ["verify"])
                self.assertEqual(query["provider"], ["google"])
                self.assertEqual(query["email"], ["oauth@example.com"])
                sender.assert_called_once()
                self.assertEqual((await client.get("/auth/me")).status_code, 401)

            db.save_oauth_state(
                "bypass-state",
                "google",
                "http://backend.test/auth/google/callback",
            )
            with patch.dict(os.environ, {"EMAIL_VERIFICATION_REQUIRED": "false"}):
                with patch.object(main, "_oauth_client", return_value=FakeOAuthClient(profile)):
                    response = await client.get(
                        "/auth/google/callback?state=bypass-state&code=test-code",
                        follow_redirects=False,
                    )
            self.assertEqual(response.status_code, 302)
            redirect = urlparse(response.headers["location"])
            self.assertEqual(redirect.path, "/workspace")
            query = parse_qs(redirect.query)
            self.assertEqual(query["auth"], ["success"])
            self.assertEqual((await client.get("/auth/me")).status_code, 200)

    async def test_provider_email_must_be_verified(self) -> None:
        class FakeResponse:
            def __init__(self, profile: object) -> None:
                self.profile = profile

            def raise_for_status(self) -> None:
                return None

            def json(self) -> object:
                return self.profile

        class FakeGoogleClient:
            async def get(self, *args: object, **kwargs: object) -> FakeResponse:
                return FakeResponse(
                    {"sub": "unverified-google", "email": "unverified@example.com", "email_verified": False}
                )

            async def fetch_token(self, *args: object, **kwargs: object) -> None:
                return None

            async def aclose(self) -> None:
                return None

        class FakeGithubClient:
            async def get(self, url: str, *args: object, **kwargs: object) -> FakeResponse:
                if url.endswith("/user"):
                    return FakeResponse({"id": 123, "login": "unverified-github"})
                return FakeResponse([{"email": "unverified@example.com", "primary": True, "verified": False}])

            async def fetch_token(self, *args: object, **kwargs: object) -> None:
                return None

            async def aclose(self) -> None:
                return None

        async with await self._client() as client:
            db.save_oauth_state("unverified-google-state", "google", "http://backend.test/auth/google/callback")
            with patch.object(main, "_oauth_client", return_value=FakeGoogleClient()):
                response = await client.get(
                    "/auth/google/callback?state=unverified-google-state&code=test-code",
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn("verified email", response.json()["detail"])

            db.save_oauth_state("unverified-github-state", "github", "http://backend.test/auth/github/callback")
            with patch.object(main, "_oauth_client", return_value=FakeGithubClient()):
                response = await client.get(
                    "/auth/github/callback?state=unverified-github-state&code=test-code",
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 400)
            self.assertIn("verified email", response.json()["detail"])

    async def test_signup_requires_verification_and_successful_code_authenticates(self) -> None:
        sent: list[tuple[str, str]] = []

        def fake_sender(recipient: str, code: str) -> None:
            sent.append((recipient, code))

        async with await self._client() as client:
            with patch.object(main.mail, "send_verification_email", side_effect=fake_sender):
                output = StringIO()
                error_output = StringIO()
                with redirect_stdout(output), redirect_stderr(error_output):
                    response = await client.post(
                        "/auth/signup",
                        json={
                            "name": "Alice",
                            "email": " Alice@Example.COM ",
                            "password": "password123",
                        },
                    )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json(),
                    {
                        "verification_required": True,
                        "email": "alice@example.com",
                        "message": "If this address can receive email, check it for a verification code.",
                    },
                )
                self.assertEqual(sent[0][0], "alice@example.com")
                code = sent[0][1]
                self.assertEqual(len(code), 6)
                self.assertNotIn(code, response.text)
                self.assertNotIn(code, output.getvalue() + error_output.getvalue())

                response = await client.get("/auth/me")
                self.assertEqual(response.status_code, 401)

                response = await client.post(
                    "/auth/login",
                    json={"email": "alice@example.com", "password": "password123"},
                )
                self.assertEqual(response.status_code, 403)
                self.assertTrue(response.json()["detail"]["verification_required"])
                self.assertEqual(len(sent), 1)

                response = await client.post(
                    "/auth/verify-email",
                    json={"email": "alice@example.com", "code": "000000"},
                )
                self.assertEqual(response.status_code, 400)

                response = await client.post(
                    "/auth/verify-email",
                    json={"email": "alice@example.com", "code": code},
                )
                self.assertEqual(response.status_code, 200)

                stats_response = await client.get("/workspace/stats")
                self.assertEqual(stats_response.status_code, 200)
                stats = stats_response.json()
                self.assertEqual(stats["metrics"][0]["label"], "Workspaces")
                self.assertEqual(stats["metrics"][0]["value"], 1)
                self.assertGreaterEqual(sum(point["value"] for point in stats["activity"]), 1)
                self.assertNotIn("password_hash", response.json())
                self.assertNotIn("email_verified_at", response.json())

                response = await client.get("/auth/me")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("password_hash", response.json())

                await client.post("/auth/logout")
                response = await client.post(
                    "/auth/login",
                    json={"email": "alice@example.com", "password": "password123"},
                )
                self.assertEqual(response.status_code, 200)

    async def test_signup_rejects_invalid_name_and_email_before_sending(self) -> None:
        async with await self._client() as client:
            with patch.object(main.mail, "send_verification_email") as sender:
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "N" * (main.MAX_FULL_NAME_LENGTH + 1),
                        "email": "valid@example.com",
                        "password": "password123",
                    },
                )
                self.assertEqual(response.status_code, 422)
                self.assertIn(
                    f"at most {main.MAX_FULL_NAME_LENGTH} characters",
                    response.json()["detail"][0]["msg"],
                )

                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Valid Name",
                        "email": "not-an-email",
                        "password": "password123",
                    },
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(sender.call_count, 0)

            with patch.dict(os.environ, {"EMAIL_DOMAIN_CHECK": "true"}):
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Valid Name",
                        "email": "user@example.invalid",
                        "password": "password123",
                    },
                )
            self.assertEqual(response.status_code, 422)
            self.assertIn("email domain", response.json()["detail"])

    async def test_zerobounce_rejects_invalid_email_before_user_creation(self) -> None:
        async with await self._client() as client:
            with patch.object(
                main.email_validation,
                "validate_email",
                return_value=main.email_validation.EmailValidationResult(
                    address="fake@gmail.com",
                    status="invalid",
                    sub_status="mailbox_not_found",
                ),
            ) as validator, patch.object(main.mail, "send_verification_email") as sender:
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Fake User",
                        "email": "fake@gmail.com",
                        "password": "password123",
                    },
                )

            self.assertEqual(response.status_code, 422)
            self.assertIn("could not be verified", response.json()["detail"])
            validator.assert_awaited_once()
            sender.assert_not_called()
            with db.connection() as conn:
                self.assertIsNone(
                    conn.execute(
                        "SELECT id FROM users WHERE email = ?",
                        ("fake@gmail.com",),
                    ).fetchone()
                )

    async def test_zerobounce_accepts_valid_email_before_otp(self) -> None:
        sent: list[str] = []

        async with await self._client() as client:
            with patch.object(
                main.email_validation,
                "validate_email",
                return_value=main.email_validation.EmailValidationResult(
                    address="valid@gmail.com",
                    status="valid",
                ),
            ), patch.object(
                main.mail,
                "send_verification_email",
                side_effect=lambda _, code: sent.append(code),
            ):
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Valid User",
                        "email": "valid@gmail.com",
                        "password": "password123",
                    },
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(sent), 1)

    async def test_zerobounce_rejects_valid_but_non_mailbox_result(self) -> None:
        async with await self._client() as client:
            with patch.object(
                main.email_validation,
                "validate_email",
                return_value=main.email_validation.EmailValidationResult(
                    address="alias@gmail.com",
                    status="valid",
                    sub_status="alias_address",
                ),
            ), patch.object(main.mail, "send_verification_email") as sender:
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Alias User",
                        "email": "alias@gmail.com",
                        "password": "password123",
                    },
                )

            self.assertEqual(response.status_code, 422)
            self.assertIn("could not confirm", response.json()["detail"])
            sender.assert_not_called()

    async def test_missing_zerobounce_configuration_blocks_signup(self) -> None:
        async with await self._client() as client:
            with patch.object(
                main.email_validation,
                "validate_email",
                side_effect=main.email_validation.EmailValidationConfigurationError,
            ), patch.object(main.mail, "send_verification_email") as sender:
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "No Validator",
                        "email": "novalidator@gmail.com",
                        "password": "password123",
                    },
                )

            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "Email validation is not configured.")
            sender.assert_not_called()

    async def test_resend_is_generic_and_cooldown_does_not_send_again(self) -> None:
        sent: list[str] = []

        async with await self._client() as client:
            with patch.object(main.mail, "send_verification_email", side_effect=lambda _, code: sent.append(code)):
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "Bob",
                        "email": "bob@example.com",
                        "password": "password123",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(sent), 1)

                response = await client.post(
                    "/auth/resend-verification",
                    json={"email": "bob@example.com"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(sent), 1)
                generic_message = response.json()["message"]

                response = await client.post(
                    "/auth/resend-verification",
                    json={"email": "nobody@example.com"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["message"], generic_message)

    async def test_missing_mail_delivery_returns_503_without_authenticating(self) -> None:
        async with await self._client() as client:
            with patch.object(
                main,
                "send_verification_email",
                side_effect=main.mail.MailConfigurationError("not configured"),
            ):
                response = await client.post(
                    "/auth/signup",
                    json={
                        "name": "No Mail",
                        "email": "no-mail@example.com",
                        "password": "password123",
                    },
                )
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"], "Email verification is not configured.")
            self.assertEqual((await client.get("/auth/me")).status_code, 401)

    def test_existing_database_is_migrated_without_losing_users(self) -> None:
        with db.connection() as conn:
            conn.executescript(
                """
                DROP TABLE IF EXISTS verification_codes;
                DROP TABLE IF EXISTS oauth_accounts;
                DROP TABLE IF EXISTS oauth_states;
                DROP TABLE IF EXISTS users;
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    name TEXT NOT NULL,
                    password_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO users (email, name, password_hash, created_at, updated_at)
                VALUES ('legacy@example.com', 'Legacy', NULL, '2026-01-01', '2026-01-01');
                """
            )

        db.init_db()
        with db.connection() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            tables = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            legacy = conn.execute(
                "SELECT email FROM users WHERE email = 'legacy@example.com'"
            ).fetchone()
        self.assertIn("email_verified_at", columns)
        self.assertIn("verification_codes", tables)
        self.assertEqual(legacy["email"], "legacy@example.com")


if __name__ == "__main__":
    unittest.main()
