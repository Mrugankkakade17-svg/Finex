from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_capabilities_endpoint_uses_finex_envelope_and_is_public() -> None:
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["dataStatus"] == "LIVE"
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]
    assert set(body["data"]) == {"capabilities"}


def test_capabilities_follow_current_full_sprint_acceptance_boundary() -> None:
    response = client.get("/api/v1/capabilities")
    capabilities = response.json()["data"]["capabilities"]

    assert capabilities == {
        "login": True,
        "onboarding": True,
        "dashboard": True,
        "risk": True,
        "portfolio": True,
        "market": False,
        "watchlist": False,
        "paper_trading": False,
        "goals": False,
        "spending": False,
        "ai_assistant": False,
        "alerts": False,
        "operations": False,
        "release": False,
    }


def test_capabilities_are_public_flags_and_contain_no_user_credentials() -> None:
    body = client.get("/api/v1/capabilities").json()
    capabilities = body["data"]["capabilities"]

    assert all(type(available) is bool for available in capabilities.values())
    assert "user_id" not in body["data"]
    assert "access_token" not in body["data"]
