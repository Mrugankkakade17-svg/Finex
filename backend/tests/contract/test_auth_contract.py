"""
Contract tests for the Authentication API.

These tests verify the SHAPE of responses — that all fields the frontend
depends on are present and correctly typed, regardless of specific values.

Uses TestClient against the live FastAPI app (no mocking).
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.token_store import TokenRevocationStore
from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)

MOCK_TOKEN = "mock:contract@finex.com:Contract User"


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Fresh repo and revocation store for each contract test."""
    fresh_repo = UserRepository()
    fresh_store = TokenRevocationStore()
    monkeypatch.setattr("app.services.auth_service.user_repository", fresh_repo)
    monkeypatch.setattr("app.services.auth_service.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.auth.dependencies.token_revocation_store", fresh_store)
    monkeypatch.setattr("app.routers.users.user_repository", fresh_repo)


# ─────────────────────────────────────────────
# Success response envelope shape
# ─────────────────────────────────────────────


class TestSuccessEnvelope:
    def test_google_callback_success_shape(self):
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": MOCK_TOKEN})
        assert resp.status_code == 200
        body = resp.json()
        # Top-level envelope
        assert "success" in body
        assert "message" in body
        assert "data" in body
        assert body["success"] is True
        # Token fields
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        # User object
        user = data["user"]
        assert "id" in user
        assert "email" in user
        assert "name" in user

    def test_register_success_shape(self):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Contract User",
                "email": "contract_reg@finex.com",
                "password": "Password@123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_success_shape(self):
        client.post(
            "/api/v1/auth/register",
            json={
                "name": "Contract User",
                "email": "contract_login@finex.com",
                "password": "Password@123",
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "contract_login@finex.com",
                "password": "Password@123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "refresh_token" in data

    def test_logout_success_shape(self):
        cb = client.post("/api/v1/auth/google/callback", json={"id_token": MOCK_TOKEN})
        tokens = cb.json()["data"]
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "message" in body

    def test_refresh_success_shape(self):
        cb = client.post("/api/v1/auth/google/callback", json={"id_token": MOCK_TOKEN})
        tokens = cb.json()["data"]
        resp = client.post(f"/api/v1/auth/refresh?token={tokens['refresh_token']}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert "token_type" in data

    def test_users_me_success_shape(self):
        cb = client.post("/api/v1/auth/google/callback", json={"id_token": MOCK_TOKEN})
        tokens = cb.json()["data"]
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "id" in data
        assert "email" in data
        assert "name" in data
        assert "role" in data
        assert "is_active" in data


# ─────────────────────────────────────────────
# Error response envelope shape
# ─────────────────────────────────────────────


class TestErrorEnvelope:
    def test_invalid_google_token_error_shape(self):
        resp = client.post("/api/v1/auth/google/callback", json={"id_token": "bad-token"})
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert "message" in body
        assert "error_code" in body

    def test_invalid_credentials_error_shape(self):
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@finex.com",
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert "error_code" in body

    def test_missing_auth_header_error_shape(self):
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 403

    def test_invalid_token_error_shape(self):
        resp = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer this.is.invalid"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["success"] is False
        assert "error_code" in body
