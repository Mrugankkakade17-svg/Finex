"""
Unit tests for auth_service.py

Uses a fresh in-memory UserRepository and MockGoogleVerifier for each test.
No HTTP, no FastAPI — pure service-layer testing.
"""

import pytest

from app.auth.jwt_handler import decode_token
from app.auth.token_store import TokenRevocationStore
from app.core.exceptions import (
    AuthenticationException,
    BadRequestException,
    UnauthorizedException,
)
from app.ports.adapters.mock_google_verifier import MockGoogleVerifier
from app.repositories.user_repository import UserRepository
from app.services import auth_service


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch):
    """
    Replace the shared singletons with fresh instances for each test.
    This prevents state leaking between tests.
    """
    fresh_repo = UserRepository()
    fresh_store = TokenRevocationStore()

    monkeypatch.setattr("app.services.auth_service.user_repository", fresh_repo)
    monkeypatch.setattr("app.services.auth_service.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.auth.dependencies.token_revocation_store", fresh_store)

    return fresh_repo, fresh_store


@pytest.fixture
def verifier():
    return MockGoogleVerifier()


# ─────────────────────────────────────────────
# register()
# ─────────────────────────────────────────────


class TestRegister:
    def test_register_new_user_returns_tokens(self):
        result = auth_service.register("Alice", "alice@finex.com", "Password@123")
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    def test_register_duplicate_email_raises(self):
        auth_service.register("Alice", "alice@finex.com", "Password@123")
        with pytest.raises(BadRequestException) as exc:
            auth_service.register("Alice2", "alice@finex.com", "Password@456")
        assert exc.value.error_code == "EMAIL_EXISTS"

    def test_access_token_payload(self):
        result = auth_service.register("Alice", "alice@finex.com", "Password@123")
        payload = decode_token(result["access_token"])
        assert payload["sub"] == "alice@finex.com"
        assert payload["type"] == "access"
        assert "jti" in payload


# ─────────────────────────────────────────────
# login()
# ─────────────────────────────────────────────


class TestLogin:
    def setup_method(self):
        pass  # reset_singletons fixture handles state

    def test_login_with_valid_credentials(self, reset_singletons):
        repo, _ = reset_singletons
        auth_service.register("Alice", "alice@finex.com", "Password@123")
        result = auth_service.login("alice@finex.com", "Password@123")
        assert "access_token" in result

    def test_login_with_wrong_password_raises(self, reset_singletons):
        auth_service.register("Alice", "alice@finex.com", "Password@123")
        with pytest.raises(UnauthorizedException) as exc:
            auth_service.login("alice@finex.com", "WrongPassword")
        assert exc.value.error_code == "INVALID_CREDENTIALS"

    def test_login_with_unknown_email_raises(self):
        with pytest.raises(UnauthorizedException):
            auth_service.login("nobody@finex.com", "Password@123")


# ─────────────────────────────────────────────
# google_callback()
# ─────────────────────────────────────────────


class TestGoogleCallback:
    def test_new_google_user_returns_tokens(self, verifier):
        result = auth_service.google_callback(
            id_token="mock:alice@finex.com:Alice Smith",
            google_verifier=verifier,
        )
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["user"]["email"] == "alice@finex.com"
        assert result["user"]["name"] == "Alice Smith"

    def test_existing_google_user_is_loaded(self, verifier):
        """Same Google token twice should return the same user id."""
        result1 = auth_service.google_callback("mock:alice@finex.com:Alice", verifier)
        result2 = auth_service.google_callback("mock:alice@finex.com:Alice", verifier)
        assert result1["user"]["id"] == result2["user"]["id"]

    def test_invalid_google_token_raises(self, verifier):
        with pytest.raises(AuthenticationException):
            auth_service.google_callback("not-a-valid-token", verifier)

    def test_malformed_mock_token_raises(self, verifier):
        with pytest.raises(AuthenticationException):
            auth_service.google_callback("mock:onlyonepart", verifier)

    def test_access_token_contains_user_id(self, verifier):
        result = auth_service.google_callback("mock:bob@finex.com:Bob", verifier)
        payload = decode_token(result["access_token"])
        assert payload["sub"] == "bob@finex.com"
        assert payload["user_id"] is not None


# ─────────────────────────────────────────────
# refresh()
# ─────────────────────────────────────────────


class TestRefresh:
    def test_valid_refresh_token_returns_new_access_token(self):
        reg = auth_service.register("Alice", "alice@finex.com", "Password@123")
        result = auth_service.refresh(reg["refresh_token"])
        assert "access_token" in result

    def test_access_token_passed_as_refresh_raises(self):
        reg = auth_service.register("Alice", "alice@finex.com", "Password@123")
        with pytest.raises(UnauthorizedException) as exc:
            auth_service.refresh(reg["access_token"])
        assert exc.value.error_code == "INVALID_REFRESH_TOKEN"

    def test_revoked_refresh_token_raises(self, reset_singletons):
        _, fresh_store = reset_singletons
        reg = auth_service.register("Alice", "alice@finex.com", "Password@123")
        refresh_payload = decode_token(reg["refresh_token"])
        fresh_store.revoke(refresh_payload["jti"])

        with pytest.raises(UnauthorizedException) as exc:
            auth_service.refresh(reg["refresh_token"])
        assert exc.value.error_code == "TOKEN_REVOKED"

    def test_garbage_token_raises(self):
        with pytest.raises(UnauthorizedException):
            auth_service.refresh("garbage.token.here")


# ─────────────────────────────────────────────
# logout()
# ─────────────────────────────────────────────


class TestLogout:
    def test_logout_revokes_refresh_token(self, reset_singletons):
        _, fresh_store = reset_singletons
        reg = auth_service.register("Alice", "alice@finex.com", "Password@123")
        auth_service.logout(reg["refresh_token"])

        refresh_payload = decode_token(reg["refresh_token"])
        assert fresh_store.is_revoked(refresh_payload["jti"])

    def test_refresh_after_logout_raises(self, reset_singletons):
        auth_service.register("Alice", "alice@finex.com", "Password@123")
        reg = auth_service.login("alice@finex.com", "Password@123")
        auth_service.logout(reg["refresh_token"])

        with pytest.raises(UnauthorizedException) as exc:
            auth_service.refresh(reg["refresh_token"])
        assert exc.value.error_code == "TOKEN_REVOKED"

    def test_logout_with_access_token_raises(self):
        reg = auth_service.register("Alice", "alice@finex.com", "Password@123")
        with pytest.raises(UnauthorizedException):
            auth_service.logout(reg["access_token"])
