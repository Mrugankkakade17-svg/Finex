from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app

client = TestClient(app)


def test_onboarding_requires_authentication():
    response = client.post(
        "/api/v1/onboarding/complete",
        json={"consent_given": True},
    )

    assert response.status_code in (401, 403)


def test_onboarding_complete_success(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.post(
        "/api/v1/onboarding/complete",
        json={"consent_given": True},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["data"]["user_id"] == 1
    assert body["data"]["onboarding_completed"] is True
    assert body["data"]["consent_given"] is True

    assert "meta" in body
    assert body["meta"]["correlationId"]

    app.dependency_overrides.clear()


def test_onboarding_rejects_missing_consent(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1}

    response = client.post(
        "/api/v1/onboarding/complete",
        json={"consent_given": False},
    )

    assert response.status_code == 400

    body = response.json()

    assert body["error"]["code"] == "CONSENT_REQUIRED"

    app.dependency_overrides.clear()
