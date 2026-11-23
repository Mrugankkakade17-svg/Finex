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

    def test_concurrent_failed_logins_cannot_bypass_throttle(self):
        """Simultaneous failed logins across multiple threads must be throttled atomically."""
        import concurrent.futures

        email = f"concurrent_throttle_{uuid.uuid4().hex[:8]}@finex.com"
        password = "GoodPassword@123"
        auth_service.register(name="Concurrent User", email=email, password=password)

        results = []

        def attempt_login():
            try:
                auth_service.login(email=email, password="BadPassword@123")
                return 200
            except UnauthorizedException:
                return 401
            except LoginRateLimitExceededException:
                return 429
            except Exception as e:
                return str(e)

        # Launch 20 concurrent failed login attempts
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attempt_login) for _ in range(20)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        count_401 = results.count(401)
        count_429 = results.count(429)

        assert count_401 == 10, f"Expected exactly 10 401s, got {count_401}"
        assert count_429 == 10, f"Expected exactly 10 429s, got {count_429}"
        assert len(results) == 20


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
        self.repo = PostgresUserRepository(require_db=False)
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


class TestDatabaseUrlConsistencyAndNoSilentFallback:
    """Verifies that database URL adheres to Settings and no silent fallback in DB mode."""

    def test_database_url_sourced_from_settings_or_env(self, monkeypatch):
        from app.config.settings import get_settings

        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("APP_DATABASE_URL", raising=False)

        repo = PostgresUserRepository()
        assert repo._database_url == get_settings().app_database_url

    def test_database_url_explicit_override(self):
        custom_url = "postgresql://user:pass@dbhost:5432/custom_db"
        repo = PostgresUserRepository(database_url=custom_url)
        assert repo._database_url == custom_url

    def test_no_silent_fallback_in_postgres_mode(self):
        from app.core.exceptions import DatabaseUnavailableException

        repo = PostgresUserRepository(
            database_url="postgresql://invalid_host:5432/finex",
            require_db=True,
        )
        repo._db_available = False

        # create_user must raise DatabaseUnavailableException
        with pytest.raises(DatabaseUnavailableException):
            repo.create_user(
                name="Fail User",
                email="fail@finex.com",
                hashed_password="hash",
            )
        # Ensure user was NOT silently saved into memory
        assert "fail@finex.com" not in repo._memory_users

        # get_user_by_email must raise DatabaseUnavailableException
        with pytest.raises(DatabaseUnavailableException):
            repo.get_user_by_email("fail@finex.com")

        # get_user_by_id must raise DatabaseUnavailableException
        with pytest.raises(DatabaseUnavailableException):
            repo.get_user_by_id("some-uuid")


class TestGoogleSignInCompatibility:
    """Verifies that google_id and picture survive Google sign-in and retrieval."""

    def setup_method(self):
        login_tracker.clear()
        auth_service.user_repository = PostgresUserRepository(require_db=False)
        auth_service.user_repository._db_available = False

    def test_google_sign_in_preserves_google_id_and_picture(self):
        email = f"google_user_{uuid.uuid4().hex[:8]}@example.com"
        google_id = f"g_{uuid.uuid4().hex[:12]}"
        picture_url = "https://lh3.googleusercontent.com/a/test_avatar.jpg"
        name = "Google Test User"

        # 1. Login or create google user
        res = auth_service.login_or_create_google_user(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=picture_url,
        )
        assert res["user"]["email"] == email
        assert res["user"]["picture"] == picture_url

        repo = auth_service.get_user_repository()
        # 2. Subsequent retrieval by email preserves google_id and picture
        user_by_email = repo.get_user_by_email(email)
        assert user_by_email is not None
        assert user_by_email.google_id == google_id
        assert user_by_email.picture == picture_url

        # 3. Subsequent retrieval by id preserves google_id and picture
        user_by_id = repo.get_user_by_id(user_by_email.id)
        assert user_by_id is not None
        assert user_by_id.google_id == google_id
        assert user_by_id.picture == picture_url

        # 4. Subsequent retrieval by google_id preserves google_id and picture
        user_by_gid = repo.get_user_by_google_id(google_id)
        assert user_by_gid is not None
        assert user_by_gid.google_id == google_id
        assert user_by_gid.picture == picture_url

        # 5. Calling get_or_create_google_user again returns same user
        second_res = auth_service.login_or_create_google_user(
            google_id=google_id,
            email=email,
            name=name,
            avatar_url=picture_url,
        )
        assert second_res["user"]["id"] == res["user"]["id"]
        assert second_res["user"]["picture"] == picture_url

    def test_google_id_conflict_with_different_email_rejected(self):
        email_original = f"google_orig_{uuid.uuid4().hex[:8]}@example.com"
        email_attacker = f"google_attack_{uuid.uuid4().hex[:8]}@example.com"
        google_id = f"g_conflict_{uuid.uuid4().hex[:12]}"
        repo = auth_service.get_user_repository()

        # Create original user with this google_id
        repo.get_or_create_google_user(
            google_id=google_id,
            email=email_original,
            name="Original User",
        )

        # Attempt to link same google_id with a different email must raise GOOGLE_ACCOUNT_CONFLICT
        with pytest.raises(BadRequestException) as exc_info:
            repo.get_or_create_google_user(
                google_id=google_id,
                email=email_attacker,
                name="Attacker",
            )
        assert exc_info.value.error_code == "GOOGLE_ACCOUNT_CONFLICT"

    def test_google_linking_to_existing_email_password_user(self):
        email = f"link_user_{uuid.uuid4().hex[:8]}@example.com"
        google_id = f"g_link_{uuid.uuid4().hex[:12]}"
        avatar = "https://example.com/avatar.png"

        # 1. Register with email and password first
        reg = auth_service.register(name="Email User", email=email, password="InitialPassword@123")
        orig_id = reg["user"]["id"]

        # 2. Later, user logs in via Google with the same email
        google_res = auth_service.login_or_create_google_user(
            google_id=google_id,
            email=email,
            name="Email User",
            avatar_url=avatar,
        )
        assert google_res["user"]["id"] == orig_id
        assert google_res["user"]["picture"] == avatar

        # 3. User is now retrievable by google_id
        repo = auth_service.get_user_repository()
        by_gid = repo.get_user_by_google_id(google_id)
        assert by_gid is not None
        assert by_gid.id == orig_id
        assert by_gid.google_id == google_id
        assert by_gid.picture == avatar


class TestUserRoutesUuidCompatibility:
    """Verifies that user routes support both UUID string IDs and integer IDs."""

    def setup_method(self):
        login_tracker.clear()
        auth_service.user_repository = PostgresUserRepository(require_db=False)
        auth_service.user_repository._db_available = False

    def test_users_me_and_get_user_with_uuid(self):
        from app.auth.jwt_handler import create_access_token

        repo = auth_service.get_user_repository()
        user_uuid = str(uuid.uuid4())
        email = f"uuid_user_{uuid.uuid4().hex[:8]}@example.com"
        repo.create_user(
            name="UUID User",
            email=email,
            hashed_password=hash_password("Pass@123"),
            user_id=user_uuid,
        )

        token = create_access_token(data={"sub": email, "user_id": user_uuid})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. GET /api/v1/users/me with UUID
        res_me = client.get("/api/v1/users/me", headers=headers)
        assert res_me.status_code == 200
        data_me = res_me.json()["data"]
        assert str(data_me["id"]) == user_uuid
        assert data_me["email"] == email

        # 2. GET /api/v1/users/{user_id} with UUID
        res_uid = client.get(f"/api/v1/users/{user_uuid}", headers=headers)
        assert res_uid.status_code == 200
        data_uid = res_uid.json()["data"]
        assert str(data_uid["id"]) == user_uuid
        assert data_uid["email"] == email

        # 3. GET /api/v1/users/{other_uuid} returns 404 (user isolation)
        other_uuid = str(uuid.uuid4())
        res_other = client.get(f"/api/v1/users/{other_uuid}", headers=headers)
        assert res_other.status_code == 404

    def test_users_me_and_get_user_with_int_id(self):
        from app.auth.jwt_handler import create_access_token
        from app.repositories.user_repository import user_repository as mem_repo

        auth_service.user_repository = mem_repo
        email = f"int_user_{uuid.uuid4().hex[:8]}@example.com"
        user = mem_repo.create_user(
            name="Int User",
            email=email,
            hashed_password=hash_password("Pass@123"),
        )
        int_id = user.id
        token = create_access_token(data={"sub": email, "user_id": int_id})
        headers = {"Authorization": f"Bearer {token}"}

        # 1. GET /api/v1/users/me with int id
        res_me = client.get("/api/v1/users/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["data"]["id"] == int_id

        # 2. GET /api/v1/users/{user_id} with int id
        res_uid = client.get(f"/api/v1/users/{int_id}", headers=headers)
        assert res_uid.status_code == 200
        assert res_uid.json()["data"]["id"] == int_id
