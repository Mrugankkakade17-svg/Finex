"""
Unit tests for TokenRepository and GoogleAuthService.
Ensures high test coverage across repositories and services.
"""

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.repositories.token_repository import TokenRepository
from app.schemas.auth import GoogleAuthRequest
from app.services.google_auth_service import GoogleAuthService


class TestTokenRepository:
    def test_store_and_validate_refresh_token(self):
        repo = TokenRepository()
        expires = datetime.utcnow() + timedelta(days=7)
        repo.store_refresh_token(user_id=1, token_jti="jti-123", expires_at=expires)

        assert repo.is_refresh_token_valid("jti-123") is True
        assert repo.is_token_revoked("jti-123") is False

    def test_revoke_token(self):
        repo = TokenRepository()
        repo.store_refresh_token(user_id=1, token_jti="jti-123")
        repo.revoke_token("jti-123")

        assert repo.is_token_revoked("jti-123") is True
        assert repo.is_refresh_token_valid("jti-123") is False

    def test_revoke_empty_token(self):
        repo = TokenRepository()
        assert repo.revoke_token("") is False
        assert repo.is_token_revoked("") is False
        assert repo.is_refresh_token_valid("") is False

    def test_revoke_user_tokens(self):
        repo = TokenRepository()
        repo.store_refresh_token(user_id=1, token_jti="jti-1")
        repo.store_refresh_token(user_id=1, token_jti="jti-2")
        repo.store_refresh_token(user_id=2, token_jti="jti-3")

        revoked_count = repo.revoke_user_tokens(1)
        assert revoked_count == 2
        assert repo.is_token_revoked("jti-1") is True
        assert repo.is_token_revoked("jti-2") is True
        assert repo.is_token_revoked("jti-3") is False

    def test_expired_token(self):
        repo = TokenRepository()
        expired = datetime.utcnow() - timedelta(days=1)
        repo.store_refresh_token(user_id=1, token_jti="jti-exp", expires_at=expired)
        assert repo.is_refresh_token_valid("jti-exp") is False

    def test_clear_repository(self):
        repo = TokenRepository()
        repo.store_refresh_token(user_id=1, token_jti="jti-1")
        repo.clear()
        assert repo.is_refresh_token_valid("jti-1") is False


class TestGoogleAuthService:
    def test_verify_google_identity_with_fields(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(
            google_id="gid-test",
            email="test@finex.com",
            name="Test User",
            avatar_url="https://avatar.com/test.png",
        )
        identity = service.verify_google_identity(req)
        assert identity["google_id"] == "gid-test"
        assert identity["email"] == "test@finex.com"
        assert identity["name"] == "Test User"

    def test_verify_google_identity_with_mock_payload(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(
            mock_payload={
                "email": "mockuser@finex.com",
                "name": "Mock User",
                "google_id": "gid-mock",
            }
        )
        identity = service.verify_google_identity(req)
        assert identity["email"] == "mockuser@finex.com"
        assert identity["google_id"] == "gid-mock"

    def test_verify_google_identity_mock_payload_missing_email(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(mock_payload={"name": "No Email"})
        with pytest.raises(BadRequestException):
            service.verify_google_identity(req)

    def test_verify_google_identity_missing_all(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest()
        with pytest.raises(BadRequestException):
            service.verify_google_identity(req)

    def test_verify_token_string_mock_email(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token="mock-google-token-alice@finex.com")
        identity = service.verify_google_identity(req)
        assert identity["email"] == "alice@finex.com"
        assert identity["google_id"] == "google_alice@finex.com"

    def test_verify_token_string_empty(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token="   ")
        with pytest.raises(BadRequestException):
            service.verify_google_identity(req)

    def test_verify_token_string_invalid(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token="invalid_no_at_sign")
        with pytest.raises(UnauthorizedException):
            service.verify_google_identity(req)
