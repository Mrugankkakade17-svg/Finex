"""
Unit tests for jwt_handler.py

Tests JWT creation, decoding, expiry, and jti presence.
No FastAPI, no HTTP — pure function-level testing.
"""

from datetime import timedelta

from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.auth.token_store import TokenRevocationStore


class TestCreateAccessToken:
    def test_creates_valid_token(self):
        token = create_access_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "alice@finex.com"
        assert payload["user_id"] == 1

    def test_type_is_access(self):
        token = create_access_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert payload["type"] == "access"

    def test_includes_jti(self):
        token = create_access_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) == 36  # UUID4 format

    def test_two_tokens_have_different_jti(self):
        token1 = create_access_token(data={"sub": "alice@finex.com", "user_id": 1})
        token2 = create_access_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload1 = decode_token(token1)
        payload2 = decode_token(token2)
        assert payload1["jti"] != payload2["jti"]

    def test_expired_token_returns_none(self):
        token = create_access_token(
            data={"sub": "alice@finex.com"},
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        payload = decode_token(token)
        assert payload is None


class TestCreateRefreshToken:
    def test_creates_valid_token(self):
        token = create_refresh_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "alice@finex.com"

    def test_type_is_refresh(self):
        token = create_refresh_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert payload["type"] == "refresh"

    def test_includes_jti(self):
        token = create_refresh_token(data={"sub": "alice@finex.com", "user_id": 1})
        payload = decode_token(token)
        assert "jti" in payload


class TestDecodeToken:
    def test_returns_none_for_garbage(self):
        assert decode_token("this.is.garbage") is None

    def test_returns_none_for_empty_string(self):
        assert decode_token("") is None

    def test_returns_payload_for_valid_token(self):
        token = create_access_token(data={"sub": "bob@finex.com"})
        payload = decode_token(token)
        assert payload["sub"] == "bob@finex.com"


class TestTokenRevocationStore:
    def setup_method(self):
        self.store = TokenRevocationStore()

    def test_new_store_has_no_revoked_tokens(self):
        assert not self.store.is_revoked("some-jti")

    def test_revoke_marks_token_as_revoked(self):
        self.store.revoke("jti-abc")
        assert self.store.is_revoked("jti-abc")

    def test_non_revoked_jti_is_not_affected(self):
        self.store.revoke("jti-abc")
        assert not self.store.is_revoked("jti-xyz")

    def test_clear_removes_all_revocations(self):
        self.store.revoke("jti-abc")
        self.store.revoke("jti-xyz")
        self.store.clear()
        assert not self.store.is_revoked("jti-abc")
        assert not self.store.is_revoked("jti-xyz")

    def test_revoking_same_jti_twice_is_idempotent(self):
        self.store.revoke("jti-abc")
        self.store.revoke("jti-abc")
        assert self.store.is_revoked("jti-abc")
