"""
Integration tests for the Google OAuth → JWT → logout flow.

These are end-to-end HTTP tests through the full FastAPI stack.
They verify that the pieces work together correctly — not just individually.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.token_store import TokenRevocationStore
from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Isolate each integration test with a fresh repo and store."""
    fresh_repo = UserRepository()
    fresh_store = TokenRevocationStore()
    monkeypatch.setattr("app.services.auth_service.user_repository", fresh_repo)
    monkeypatch.setattr("app.services.auth_service.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.auth.dependencies.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.routers.users.user_repository", fresh_repo)


def _google_login(email: str = "alice@finex.com", name: str = "Alice") -> dict:
    """Helper: perform Google callback and return token dict."""
    resp = client.post(
        "/api/v1/auth/google/callback",
        json={"id_token": f"mock:{email}:{name}"},
    )
    assert resp.status_code == 200
    return resp.json()["data"]


# ─────────────────────────────────────────────
# Google OAuth callback
# ─────────────────────────────────────────────


class TestGoogleCallback:
    def test_valid_mock_token_returns_200(self):
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"id_token": "mock:alice@finex.com:Alice"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_invalid_token_returns_401(self):
        resp = client.post(
            "/api/v1/auth/google/callback",
            json={"id_token": "totally-invalid"},
        )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_same_user_returned_on_second_login(self):
        tokens1 = _google_login("alice@finex.com")
        tokens2 = _google_login("alice@finex.com")
        assert tokens1["user"]["id"] == tokens2["user"]["id"]

    def test_different_emails_create_different_users(self):
        tokens1 = _google_login("alice@finex.com")
        tokens2 = _google_login("bob@finex.com")
        assert tokens1["user"]["id"] != tokens2["user"]["id"]


# ─────────────────────────────────────────────
# JWT access — GET /api/v1/users/me
# ─────────────────────────────────────────────


class TestUsersMe:
    def test_authenticated_user_gets_full_profile(self):
        tokens = _google_login("alice@finex.com", "Alice Smith")
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == "alice@finex.com"
        assert data["name"] == "Alice Smith"
        assert data["id"] == tokens["user"]["id"]

    def test_missing_token_returns_403(self):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 403

    def test_invalid_token_returns_401(self):
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert "error_code" in body

    def test_refresh_token_used_as_access_returns_401(self):
        tokens = _google_login()
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# Refresh token flow
# ─────────────────────────────────────────────


class TestRefreshFlow:
    def test_valid_refresh_returns_new_access_token(self):
        tokens = _google_login()
        resp = client.post(f"/api/v1/auth/refresh?token={tokens['refresh_token']}")
        assert resp.status_code == 200
        new_token = resp.json()["data"]["access_token"]
        assert new_token != tokens["access_token"]

    def test_new_access_token_works_on_protected_route(self):
        tokens = _google_login()
        refresh_resp = client.post(f"/api/v1/auth/refresh?token={tokens['refresh_token']}")
        new_access = refresh_resp.json()["data"]["access_token"]

        me_resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert me_resp.status_code == 200

    def test_access_token_as_refresh_returns_401(self):
        tokens = _google_login()
        resp = client.post(f"/api/v1/auth/refresh?token={tokens['access_token']}")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_REFRESH_TOKEN"

    def test_garbage_refresh_token_returns_401(self):
        resp = client.post("/api/v1/auth/refresh?token=garbage")
        assert resp.status_code == 401


# ─────────────────────────────────────────────
# Logout + revocation
# ─────────────────────────────────────────────


class TestLogoutRevocation:
    def test_logout_returns_200(self):
        tokens = _google_login()
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_refresh_after_logout_returns_401(self):
        """The DONE condition: logout invalidates the refresh token."""
        tokens = _google_login()
        # Logout
        client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        # Try to use the revoked refresh token
        resp = client.post(f"/api/v1/auth/refresh?token={tokens['refresh_token']}")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "TOKEN_REVOKED"

    def test_logout_without_auth_header_returns_403(self):
        tokens = _google_login()
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 403

    def test_two_separate_sessions_independent_revocation(self):
        """Logging out session 1 should not affect session 2."""
        tokens1 = _google_login("alice@finex.com")
        tokens2 = _google_login("alice@finex.com")  # second login, different tokens

        # Logout session 1
        client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens1["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens1['access_token']}"},
        )

        # Session 2's refresh token should still work
        resp = client.post(f"/api/v1/auth/refresh?token={tokens2['refresh_token']}")
        assert resp.status_code == 200


# ─────────────────────────────────────────────
# Full end-to-end flow
# ─────────────────────────────────────────────


class TestFullGoogleAuthFlow:
    def test_complete_flow(self):
        """
        Google callback → get profile → refresh → use new token → logout → 401 on refresh
        """
        # 1. Google OAuth callback
        cb_resp = client.post(
            "/api/v1/auth/google/callback",
            json={"id_token": "mock:flow@finex.com:Flow User"},
        )
        assert cb_resp.status_code == 200
        tokens = cb_resp.json()["data"]
        access = tokens["access_token"]
        refresh = tokens["refresh_token"]

        # 2. Get full profile
        me_resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert me_resp.status_code == 200
        profile = me_resp.json()["data"]
        assert profile["email"] == "flow@finex.com"

        # 3. Refresh → new access token
        refresh_resp = client.post(f"/api/v1/auth/refresh?token={refresh}")
        assert refresh_resp.status_code == 200
        new_access = refresh_resp.json()["data"]["access_token"]

        # 4. Use new access token
        me_resp2 = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert me_resp2.status_code == 200

        # 5. Logout (revoke refresh token)
        logout_resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert logout_resp.status_code == 200

        # 6. Verify refresh token is now dead
        retry_resp = client.post(f"/api/v1/auth/refresh?token={refresh}")
        assert retry_resp.status_code == 401
        assert retry_resp.json()["error_code"] == "TOKEN_REVOKED"
