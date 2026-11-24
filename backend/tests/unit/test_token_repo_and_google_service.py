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
    @pytest.fixture(autouse=True)
    def enable_mock_google_auth(self, monkeypatch):
        from app.config.settings import get_settings

        monkeypatch.setattr(get_settings(), "allow_mock_google_auth", True)

    def test_verify_google_identity_with_caller_supplied_fields_rejected(self):
        """Identity fields without a valid credential must be rejected (Security Fix 1)."""
        service = GoogleAuthService()
        req = GoogleAuthRequest(
            google_id="gid-test",
            email="test@finex.com",
            name="Test User",
            avatar_url="https://avatar.com/test.png",
        )
        with pytest.raises(BadRequestException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "MISSING_GOOGLE_CREDENTIAL"

    def test_verify_google_identity_with_mock_payload_rejected(self):
        """Mock payload dict without credential must be rejected (Security Fix 1)."""
        service = GoogleAuthService()
        req = GoogleAuthRequest(
            mock_payload={
                "email": "mockuser@finex.com",
                "name": "Mock User",
                "google_id": "gid-mock",
            }
        )
        with pytest.raises(BadRequestException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "MISSING_GOOGLE_CREDENTIAL"

    def test_verify_google_identity_missing_all(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest()
        with pytest.raises(BadRequestException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "MISSING_GOOGLE_CREDENTIAL"

    def test_verify_token_string_mock_email(self):
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token="mock-google-token-alice@finex.com")
        identity = service.verify_google_identity(req)
        assert identity["email"] == "alice@finex.com"
        assert identity["google_id"] == "google_alice@finex.com"
        assert identity["email_verified"] is True

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

    def test_verify_google_identity_unverified_email_in_jwt_claims_rejected(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from jose import jwk, jwt

        from app.ports.adapters.google_oauth_verifier import google_jwks_client

        # Generate test RSA key
        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        priv_jwk = jwk.RSAKey(algorithm="RS256", key=priv_key)
        pub_dict = {
            k: v for k, v in priv_jwk.to_dict().items() if k in ("kty", "alg", "use", "n", "e")
        }
        pub_dict["kid"] = "test-kid-unverified"
        google_jwks_client.add_key_override("test-kid-unverified", pub_dict)

        unverified_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": "test-aud",
                "sub": "gid-999",
                "email": "unverified@finex.com",
                "email_verified": False,
                "exp": 2000000000,
            },
            priv_pem,
            algorithm="RS256",
            headers={"kid": "test-kid-unverified"},
        )
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token=unverified_token)
        with pytest.raises(UnauthorizedException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "UNVERIFIED_GOOGLE_EMAIL"

    def test_verify_google_identity_expired_jwt_rejected(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from jose import jwk, jwt

        from app.ports.adapters.google_oauth_verifier import google_jwks_client

        # Generate test RSA key
        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        priv_jwk = jwk.RSAKey(algorithm="RS256", key=priv_key)
        pub_dict = {
            k: v for k, v in priv_jwk.to_dict().items() if k in ("kty", "alg", "use", "n", "e")
        }
        pub_dict["kid"] = "test-kid-expired"
        google_jwks_client.add_key_override("test-kid-expired", pub_dict)

        expired_token = jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": "test-aud",
                "sub": "gid-999",
                "email": "expired@finex.com",
                "email_verified": True,
                "exp": 1000000000,  # September 2001
            },
            priv_pem,
            algorithm="RS256",
            headers={"kid": "test-kid-expired"},
        )
        service = GoogleAuthService()
        req = GoogleAuthRequest(id_token=expired_token)
        with pytest.raises(UnauthorizedException) as exc_info:
            service.verify_google_identity(req)
        assert exc_info.value.error_code == "EXPIRED_GOOGLE_TOKEN"
