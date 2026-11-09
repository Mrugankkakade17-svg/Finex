"""
Integration tests for the Consent / Onboarding API.

These tests exercise the real router -> service -> repository flow.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def google_login(email: str, name: str):
    response = client.post(
        "/api/v1/auth/google/callback",
        json={
            "id_token": f"mock:{email}:{name}",
        },
    )

    assert response.status_code == 200

    return response.json()["data"]


class TestConsentFlow:
    def test_complete_onboarding_with_consent(self):
        tokens = google_login(
            "consent_flow@finex.com",
            "Consent Flow User",
        )

        response = client.post(
            "/api/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "consent_given": True,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True

        data = body["data"]

        assert data["user_id"] == 1
        assert data["onboarding_completed"] is True
        assert data["consent_given"] is True

    def test_complete_onboarding_without_consent(self):
        tokens = google_login(
            "no_consent@finex.com",
            "No Consent User",
        )

        response = client.post(
            "/api/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "consent_given": False,
            },
        )

        assert response.status_code == 400

        body = response.json()

        assert body["success"] is False
        assert body["error_code"] == "CONSENT_REQUIRED"

    def test_complete_onboarding_without_authentication(self):
        response = client.post(
            "/api/v1/onboarding/complete",
            json={
                "consent_given": True,
            },
        )

        assert response.status_code == 403

    def test_complete_onboarding_with_invalid_token(self):
        response = client.post(
            "/api/v1/onboarding/complete",
            headers={
                "Authorization": "Bearer invalid-token",
            },
            json={
                "consent_given": True,
            },
        )

        assert response.status_code == 401

    def test_complete_onboarding_missing_consent_field(self):
        tokens = google_login(
            "missing_consent@finex.com",
            "Missing Consent User",
        )

        response = client.post(
            "/api/v1/onboarding/complete",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={},
        )

        assert response.status_code == 422
