"""Unit and contract tests for S1-LI02: Real registration/login on Postgres.

Covers:
- Criterion 1: Existing response structure and contract preservation.
- Criterion 2: 11th failed login in the window is throttled (HTTP 429).
- Criterion 3: Password hashes and secrets are never logged.
- PostgreSQL user repository operations and bcrypt hashing.
"""

import logging
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.auth.password import hash_password, verify_password
from app.core.exceptions import (
    BadRequestException,
    LoginRateLimitExceededException,
    UnauthorizedException,
)
from app.main import app
from app.repositories.postgres_user_repository import PostgresUserRepository
from app.services import auth_service
from app.services.auth_service import login_tracker

client = TestClient(app)


class TestFailedLoginThrottling:
    """Verifies that the 11th failed login attempt within the window is throttled."""

    def setup_method(self):
        login_tracker.clear()
        if hasattr(auth_service.user_repository, "_memory_users"):
            auth_service.user_repository._memory_users.clear()

    def test_first_10_failures_return_401_and_11th_returns_429(self):
        email = f"throttle_{uuid.uuid4().hex[:8]}@finex.com"
        password = "CorrectPassword@123"
        wrong_pass = "WrongPassword@123"
        auth_service.register(name="Throttle User", email=email, password=password)

        # Attempts 1 through 10 must raise UnauthorizedException (HTTP 401)
        for i in range(1, 11):
            with pytest.raises(UnauthorizedException) as exc_info:
                auth_service.login(email=email, password=wrong_pass)
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == "INVALID_CREDENTIALS"

        # Attempt 11 must be throttled with LoginRateLimitExceededException (HTTP 429)
        with pytest.raises(LoginRateLimitExceededException) as exc_info:
            auth_service.login(email=email, password=wrong_pass)
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "RATE_LIMIT_EXCEEDED"

    def test_endpoint_returns_http_429_on_11th_failed_login(self):
        email = f"endpoint_throttle_{uuid.uuid4().hex[:8]}@finex.com"
        client.post(
            "/api/v1/auth/register",
            json={"name": "EP User", "email": email, "password": "Correct@123"},
        )

        # 10 failed login requests via API
        for _ in range(10):
            res = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPassword"},
            )
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "INVALID_CREDENTIALS"

        # 11th request must return HTTP 429
        res_11 = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword"},
        )
        assert res_11.status_code == 429
        body = res_11.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_successful_login_resets_failed_attempt_counter(self):
        email = f"throttle_reset_{uuid.uuid4().hex[:8]}@finex.com"
        password = "GoodPassword@123"
        auth_service.register(name="Reset User", email=email, password=password)

        # 5 failed attempts
        for _ in range(5):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email, password="BadPassword")

        # 1 successful login
        res = auth_service.login(email=email, password=password)
        assert "access_token" in res

        # Counter is reset, so 10 more failed attempts can occur before throttling
        for _ in range(10):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email, password="BadPassword")

        # 11th after reset is throttled
        with pytest.raises(LoginRateLimitExceededException):
            auth_service.login(email=email, password="BadPassword")

    def test_window_expiration_clears_throttle(self, monkeypatch):
        email = f"window_expire_{uuid.uuid4().hex[:8]}@finex.com"
        auth_service.register(name="Window User", email=email, password="GoodPassword@123")

        # Simulate 10 failed logins
        for _ in range(10):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email, password="BadPassword")

        # Confirm 11th is throttled
        with pytest.raises(LoginRateLimitExceededException):
            auth_service.login(email=email, password="BadPassword")

        # Advance time by 901 seconds (past the 900s window)
        current_time = time.time()
        monkeypatch.setattr(time, "time", lambda: current_time + 901)

        # Now attempt should be allowed through to credentials check (returning 401 instead of 429)
        with pytest.raises(UnauthorizedException) as exc_info:
            auth_service.login(email=email, password="BadPassword")
        assert exc_info.value.status_code == 401

    def test_different_emails_have_isolated_counters(self):
        email_a = f"user_a_{uuid.uuid4().hex[:8]}@finex.com"
        email_b = f"user_b_{uuid.uuid4().hex[:8]}@finex.com"
        auth_service.register(name="User A", email=email_a, password="PasswordA@123")
        auth_service.register(name="User B", email=email_b, password="PasswordB@123")

        # 10 failures for User A
        for _ in range(10):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email_a, password="WrongPassword")

        # User A is throttled
        with pytest.raises(LoginRateLimitExceededException):
            auth_service.login(email=email_a, password="WrongPassword")

        # User B is NOT throttled and can log in successfully
        login_b = auth_service.login(email=email_b, password="PasswordB@123")
        assert "access_token" in login_b


class TestPasswordHashNotLogged:
    """Verifies that plaintext passwords, password hashes, and tokens are never logged."""

    def test_registration_does_not_log_passwords_or_hashes(self, caplog):
        caplog.set_level(logging.DEBUG)
        raw_password = "SuperSecretPlaintextPassword!987"
        email = f"logging_test_reg_{uuid.uuid4().hex[:8]}@finex.com"

        res = auth_service.register(name="Log Test", email=email, password=raw_password)
        user = auth_service.user_repository.get_user_by_email(email)
        assert user is not None
        pw_hash = user.hashed_password

        # Assert no sensitive strings appear in captured log output
        assert raw_password not in caplog.text
        assert pw_hash not in caplog.text
        assert res["access_token"] not in caplog.text
        assert res["refresh_token"] not in caplog.text

    def test_login_success_does_not_log_passwords_or_hashes(self, caplog):
        caplog.set_level(logging.DEBUG)
        raw_password = "LoginSecretPass@123"
        email = f"logging_test_login_{uuid.uuid4().hex[:8]}@finex.com"
        auth_service.register(name="Log Login", email=email, password=raw_password)

        caplog.clear()
        res = auth_service.login(email=email, password=raw_password)
        user = auth_service.user_repository.get_user_by_email(email)
        assert user is not None
        pw_hash = user.hashed_password

        assert raw_password not in caplog.text
        assert pw_hash not in caplog.text
        assert res["access_token"] not in caplog.text
        assert res["refresh_token"] not in caplog.text

    def test_failed_login_does_not_log_raw_password(self, caplog):
        caplog.set_level(logging.DEBUG)
        wrong_password = "AttemptedWrongPassword!456"
        email = f"logging_test_fail_{uuid.uuid4().hex[:8]}@finex.com"

        caplog.clear()
        with pytest.raises(UnauthorizedException):
            auth_service.login(email=email, password=wrong_password)

        assert wrong_password not in caplog.text


class TestPostgresUserRepositoryUnit:
    """Unit tests for PostgresUserRepository operations."""

    def setup_method(self):
        self.repo = PostgresUserRepository()
        self.repo._memory_users.clear()
        self.repo._db_available = False  # Test in-memory unit fallback

    def test_create_and_retrieve_user(self):
        raw_pw = "BcryptPass@123"
        hashed = hash_password(raw_pw)
        user = self.repo.create_user(
            name="Unit User",
            email="UnitUser@Finex.Com",
            hashed_password=hashed,
            role="analyst",
        )
        assert user.name == "Unit User"
        assert user.email == "unituser@finex.com"
        assert user.role == "analyst"
        assert verify_password(raw_pw, user.hashed_password)

        # Retrieve by normalized email
        found = self.repo.get_user_by_email("unituser@finex.com")
        assert found is not None
        assert found.id == user.id

        # Retrieve by upper-case email (case-insensitive)
        found_upper = self.repo.get_user_by_email("UNITUSER@FINEX.COM")
        assert found_upper is not None
        assert found_upper.id == user.id

        # Retrieve by ID
        found_id = self.repo.get_user_by_id(user.id)
        assert found_id is not None
        assert found_id.email == "unituser@finex.com"

    def test_duplicate_email_registration_rejected(self):
        hashed = hash_password("Password@123")
        self.repo.create_user(name="User 1", email="dup@finex.com", hashed_password=hashed)
        with pytest.raises(BadRequestException) as exc_info:
            self.repo.create_user(name="User 2", email="DUP@FINEX.COM", hashed_password=hashed)
        assert exc_info.value.error_code == "EMAIL_EXISTS"

    def test_update_user_login(self):
        hashed = hash_password("Password@123")
        user = self.repo.create_user(
            name="Login User", email="login_upd@finex.com", hashed_password=hashed
        )
        old_updated = user.updated_at
        self.repo.update_user_login(user.id)
        updated_user = self.repo.get_user_by_id(user.id)
        assert updated_user is not None
        assert updated_user.updated_at >= old_updated

    @pytest.mark.asyncio
    async def test_async_repository_methods_with_mock_session(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row._mapping = {
            "user_id": "mock-uuid-1",
            "email": "async@finex.com",
            "password_hash": "$2b$12$mockhash",
            "name": "Async User",
            "role": "user",
            "risk_profile": "low",
            "is_active": True,
            "created_at": None,
            "updated_at": None,
        }
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        async_repo = PostgresUserRepository(session=mock_session)
        user = await async_repo.get_user_by_email_async("async@finex.com")
        assert user is not None
        assert user.id == "mock-uuid-1"
        assert user.email == "async@finex.com"
        assert user.hashed_password == "$2b$12$mockhash"
