"""Unit tests for current_principal dependency (S1-LI01).

Tests both local bearer tokens (learner-a and learner-b) and real JWT sessions,
covering credential extraction, identity resolution, isolation, expiry, revocation,
and HTTP 401 error handling.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.auth.principal import CurrentPrincipal, Principal, get_current_principal, get_principal
from app.auth.token_store import token_revocation_store
from app.domain.local_application import LocalSession, LocalUser
from app.services.local_authorization import digest_token

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
TOKEN_A = "a" * 43
TOKEN_B = "b" * 43


class MockTransaction:
    """Mock local authorization transaction."""

    def __init__(self, sessions: dict[str, LocalSession]) -> None:
        self.sessions = sessions

    def get_session(self, digest: str) -> LocalSession | None:
        return self.sessions.get(digest)


class MockStore:
    """Mock store providing transaction context."""

    def __init__(self, sessions: dict[str, LocalSession]) -> None:
        self.sessions = sessions

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[MockTransaction]:
        yield MockTransaction(self.sessions)


def create_mock_request(
    auth_header: str | None = None,
    store: MockStore | None = None,
    clock_fn=None,
) -> Request:
    """Helper to construct a mock Starlette Request with app state."""
    headers = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode("utf-8")))

    app = FastAPI()
    app.state.local_application_store = store
    app.state.local_clock = clock_fn or (lambda: NOW)
    app.state.local_application_service = None

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": headers,
        "app": app,
    }
    return Request(scope)


class TestPrincipalDataModel:
    def test_principal_attributes(self):
        p = Principal(user_id="user-123", is_synthetic=False, roles=["admin", "user"])
        assert p.user_id == "user-123"
        assert p.is_synthetic is False
        assert p.roles == ["admin", "user"]

    def test_principal_dict_access(self):
        p = Principal(user_id="synth-1", is_synthetic=True, roles=["learner"])
        assert p["user_id"] == "synth-1"
        assert p["is_synthetic"] is True
        assert p["roles"] == ["learner"]
        assert p.get("user_id") == "synth-1"
        assert p.get("nonexistent", "default") == "default"

    def test_principal_to_dict(self):
        p = Principal(user_id="u1", is_synthetic=True, roles=["user", "learner"])
        d = p.to_dict()
        assert d == {
            "user_id": "u1",
            "is_synthetic": True,
            "roles": ["user", "learner"],
        }

    def test_principal_immutable(self):
        p = Principal(user_id="u1")
        with pytest.raises(Exception):
            p.user_id = "u2"  # type: ignore[misc]


class TestLocalBearerAuthentication:
    def setup_method(self):
        self.user_a = LocalUser(id="uuid-learner-a", alias="learner-a")
        self.user_b = LocalUser(id="uuid-learner-b", alias="learner-b")
        self.session_a = LocalSession(
            digest=digest_token(TOKEN_A),
            user=self.user_a,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=None,
        )
        self.session_b = LocalSession(
            digest=digest_token(TOKEN_B),
            user=self.user_b,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=None,
        )
        self.sessions = {
            self.session_a.digest: self.session_a,
            self.session_b.digest: self.session_b,
        }
        self.store = MockStore(self.sessions)

    @pytest.mark.asyncio
    async def test_learner_a_success(self):
        req = create_mock_request(f"Bearer {TOKEN_A}", store=self.store)
        principal = await get_principal(req)
        assert principal.user_id == "uuid-learner-a"
        assert principal.is_synthetic is True
        assert "learner" in principal.roles

    @pytest.mark.asyncio
    async def test_learner_b_success(self):
        req = create_mock_request(f"Bearer {TOKEN_B}", store=self.store)
        principal = await get_principal(req)
        assert principal.user_id == "uuid-learner-b"
        assert principal.is_synthetic is True
        assert "learner" in principal.roles

    @pytest.mark.asyncio
    async def test_learner_a_and_b_cross_isolation(self):
        req_a = create_mock_request(f"Bearer {TOKEN_A}", store=self.store)
        req_b = create_mock_request(f"Bearer {TOKEN_B}", store=self.store)
        principal_a = await get_principal(req_a)
        principal_b = await get_principal(req_b)
        assert principal_a.user_id != principal_b.user_id
        assert principal_a.user_id == "uuid-learner-a"
        assert principal_b.user_id == "uuid-learner-b"

    @pytest.mark.asyncio
    async def test_local_session_expired_raises_401(self):
        expired_token = "e" * 43
        expired_session = LocalSession(
            digest=digest_token(expired_token),
            user=self.user_a,
            expires_at=NOW - timedelta(seconds=1),
            revoked_at=None,
        )
        self.sessions[expired_session.digest] = expired_session
        req = create_mock_request(f"Bearer {expired_token}", store=self.store)
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_local_session_revoked_raises_401(self):
        revoked_token = "r" * 43
        revoked_session = LocalSession(
            digest=digest_token(revoked_token),
            user=self.user_a,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=NOW - timedelta(minutes=5),
        )
        self.sessions[revoked_session.digest] = revoked_session
        req = create_mock_request(f"Bearer {revoked_token}", store=self.store)
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unknown_local_session_raises_401(self):
        unknown_token = "u" * 43
        req = create_mock_request(f"Bearer {unknown_token}", store=self.store)
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_local_token_format_raises_401(self):
        bad_token = "too_short"
        req = create_mock_request(f"Bearer {bad_token}", store=self.store)
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401


class TestRealJWTSession:
    def setup_method(self):
        token_revocation_store.clear()

    @pytest.mark.asyncio
    async def test_valid_real_jwt_session(self):
        token = create_access_token(
            data={"sub": "user@finex.com", "user_id": "42", "role": "trader"}
        )
        req = create_mock_request(f"Bearer {token}")
        principal = await get_principal(req)
        assert principal.user_id == "42"
        assert principal.is_synthetic is False
        assert "trader" in principal.roles

    @pytest.mark.asyncio
    async def test_valid_jwt_with_sub_fallback(self):
        token = create_access_token(data={"sub": "alice_sub"})
        req = create_mock_request(f"Bearer {token}")
        principal = await get_principal(req)
        assert principal.user_id == "alice_sub"
        assert principal.is_synthetic is False
        assert principal.roles == ["user"]

    @pytest.mark.asyncio
    async def test_valid_jwt_with_roles_list(self):
        token = create_access_token(data={"user_id": "99", "roles": ["admin", "analyst"]})
        req = create_mock_request(f"Bearer {token}")
        principal = await get_principal(req)
        assert principal.user_id == "99"
        assert principal.roles == ["admin", "analyst"]

    @pytest.mark.asyncio
    async def test_expired_jwt_raises_401(self):
        token = create_access_token(
            data={"user_id": "42"},
            expires_delta=timedelta(seconds=-10),
        )
        req = create_mock_request(f"Bearer {token}")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_jwt_raises_401(self):
        token = create_access_token(data={"user_id": "42"})
        from app.auth.jwt_handler import decode_token

        payload = decode_token(token)
        assert payload is not None
        jti = payload["jti"]
        token_revocation_store.revoke(jti)

        req = create_mock_request(f"Bearer {token}")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token(data={"user_id": "42"})
        req = create_mock_request(f"Bearer {token}")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "type" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_tampered_jwt_raises_401(self):
        token = create_access_token(data={"user_id": "42"})
        tampered = token[:-5] + "XXXXX"
        req = create_mock_request(f"Bearer {tampered}")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401


class TestCredentialExtractionErrors:
    @pytest.mark.asyncio
    async def test_missing_auth_header_raises_401(self):
        req = create_mock_request(None)
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "missing" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_scheme_raises_401(self):
        req = create_mock_request("Basic user:password")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401
        assert "bearer" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_malformed_header_parts_raises_401(self):
        req = create_mock_request("Bearer token extra_part")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token_raises_401(self):
        req = create_mock_request("Bearer   ")
        with pytest.raises(HTTPException) as exc_info:
            await get_principal(req)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_explicit_token_param(self):
        token = create_access_token(data={"user_id": "explicit_user"})
        req = create_mock_request(None)
        principal = await get_principal(req, token=token)
        assert principal.user_id == "explicit_user"


class TestFastAPIDependencyIntegration:
    """Test CurrentPrincipal dependency in an end-to-end FastAPI application."""

    def setup_method(self):
        token_revocation_store.clear()
        self.app = FastAPI()

        self.user_a = LocalUser(id="synth-a-uuid", alias="learner-a")
        self.session_a = LocalSession(
            digest=digest_token(TOKEN_A),
            user=self.user_a,
            expires_at=NOW + timedelta(hours=1),
            revoked_at=None,
        )
        self.store = MockStore({self.session_a.digest: self.session_a})
        self.app.state.local_application_store = self.store
        self.app.state.local_clock = lambda: NOW
        self.app.state.local_application_service = None

        @self.app.get("/api/v1/protected-me")
        async def protected_me(principal: Principal = CurrentPrincipal):
            return {
                "user_id": principal.user_id,
                "is_synthetic": principal.is_synthetic,
                "roles": principal.roles,
            }

        @self.app.get("/api/v1/protected-alias")
        async def protected_alias(principal: Principal = Depends(get_current_principal)):
            return {"user_id": principal.user_id}

        self.client = TestClient(self.app)

    def test_endpoint_with_local_learner(self):
        response = self.client.get(
            "/api/v1/protected-me",
            headers={"Authorization": f"Bearer {TOKEN_A}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "synth-a-uuid"
        assert data["is_synthetic"] is True
        assert data["roles"] == ["user", "learner"]

    def test_endpoint_with_real_jwt(self):
        jwt_token = create_access_token(data={"user_id": "real-user-77", "roles": ["pro"]})
        response = self.client.get(
            "/api/v1/protected-me",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "real-user-77"
        assert data["is_synthetic"] is False
        assert data["roles"] == ["pro"]

    def test_endpoint_without_auth_header_returns_401(self):
        response = self.client.get("/api/v1/protected-me")
        assert response.status_code == 401

    def test_endpoint_with_invalid_token_returns_401(self):
        response = self.client.get(
            "/api/v1/protected-me",
            headers={"Authorization": "Bearer invalid_garbage_token"},
        )
        assert response.status_code == 401
