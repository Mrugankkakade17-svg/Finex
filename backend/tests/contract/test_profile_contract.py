"""
Contract tests for the Profile API.

These tests verify the response structure and authentication
behavior expected by API consumers.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)

MOCK_TOKEN = "mock:contract@finex.com:Contract User"


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Use a fresh repository for every contract test."""
    fresh_repo = UserRepository()

    monkeypatch.setattr(
        "app.services.auth_service.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.services.profile_service.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.routers.users.user_repository",
        fresh_repo,
    )


def create_authenticated_user():
    """Create a test user and return authentication tokens."""
    response = client.post(
        "/api/v1/auth/google/callback",
        json={"id_token": MOCK_TOKEN},
    )

    assert response.status_code == 200

    return response.json()["data"]


class TestProfileSuccessEnvelope:
    def test_get_profile_success_shape(self):
        tokens = create_authenticated_user()

        response = client.get(
            "/api/v1/users/me/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True
        assert "message" in body
        assert "data" in body
        assert "meta" in body

        meta = body["meta"]

        assert "correlationId" in meta
        assert "apiVersion" in meta
        assert "dataAsOf" in meta
        assert "dataStatus" in meta

        data = body["data"]

        assert "user_id" in data
        assert "name" in data
        assert "email" in data
        assert "risk_profile" in data

    def test_update_profile_success_shape(self):
        tokens = create_authenticated_user()

        response = client.put(
            "/api/v1/users/me/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "name": "Updated Contract User",
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True
        assert "message" in body
        assert "data" in body
        assert "meta" in body

        meta = body["meta"]

        assert "correlationId" in meta
        assert "apiVersion" in meta
        assert "dataAsOf" in meta
        assert "dataStatus" in meta

        data = body["data"]

        assert "user_id" in data
        assert "name" in data
        assert "email" in data
        assert "risk_profile" in data


class TestProfileErrorEnvelope:
    def test_get_profile_without_authentication(self):
        response = client.get("/api/v1/users/me/profile")

        assert response.status_code == 403

        body = response.json()

        assert "detail" in body
        assert body["detail"] == "Authorization header missing"

    def test_get_profile_with_invalid_token(self):
        response = client.get(
            "/api/v1/users/me/profile",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401

        body = response.json()

        assert body["success"] is False
        assert "message" in body
        assert "error_code" in body

    def test_update_profile_without_authentication(self):
        response = client.put(
            "/api/v1/users/me/profile",
            json={
                "name": "Unauthorized User",
            },
        )

        assert response.status_code == 403

        body = response.json()

        assert "detail" in body
        assert body["detail"] == "Authorization header missing"
