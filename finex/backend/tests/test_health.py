from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()

    # Standard FinEx v1 success envelope
    assert "data" in body
    assert "meta" in body

    # Health data
    assert body["data"]["status"] == "healthy"
    assert body["data"]["service"] == "FinEx Backend"
    assert body["data"]["version"] == "0.1.0"
    assert body["data"]["environment"] == "development"

    # Response metadata
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["dataStatus"] == "LIVE"

    # Correlation ID
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]


def test_liveness_health():
    response = client.get("/api/v1/health/live")

    # Expected HTTP status
    assert response.status_code == 200

    # Response schema
    body = response.json()
    assert "data" in body
    assert "meta" in body

    # Liveness health data
    assert body["data"]["status"] == "healthy"

    # Response metadata
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["dataStatus"] == "LIVE"

    # Correlation ID
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]


def test_readiness_health():
    response = client.get("/api/v1/health/ready")

    # Expected HTTP status
    assert response.status_code == 200

    # Response schema
    body = response.json()
    assert "data" in body
    assert "meta" in body

    # Readiness health data
    assert body["data"]["status"] == "healthy"

    # Response metadata
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["dataStatus"] == "LIVE"

    # Correlation ID
    assert body["meta"]["correlationId"]
    assert response.headers["x-correlation-id"] == body["meta"]["correlationId"]
