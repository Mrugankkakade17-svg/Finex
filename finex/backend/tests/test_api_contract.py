from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_success_response_envelope():
    response = client.get("/api/v1/health")

    assert response.status_code == 200

    body = response.json()

    assert "data" in body
    assert "meta" in body

    assert "correlationId" in body["meta"]
    assert body["meta"]["apiVersion"] == "v1"
    assert "dataAsOf" in body["meta"]
    assert body["meta"]["dataStatus"] in {
        "LIVE",
        "DELAYED",
        "END_OF_DAY",
        "CACHED",
        "UNAVAILABLE",
    }


def test_error_response_envelope():
    response = client.get("/api/v1/demo/error")

    assert response.status_code == 400

    body = response.json()

    assert "error" in body
    assert body["error"]["code"] == "DEMO_ERROR"
    assert body["error"]["message"] == "This is a demo exception."
    assert body["error"]["fieldErrors"] == []
    assert "correlationId" in body["error"]


def test_validation_error_response_envelope():
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User"},
    )

    assert response.status_code == 422

    body = response.json()

    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"
    assert isinstance(body["error"]["fieldErrors"], list)
    assert len(body["error"]["fieldErrors"]) > 0
    assert "correlationId" in body["error"]

    for field_error in body["error"]["fieldErrors"]:
        assert "field" in field_error
        assert "code" in field_error
        assert field_error["code"] in {
            "REQUIRED",
            "INVALID_FORMAT",
            "TOO_SHORT",
            "TOO_LONG",
        }


def test_internal_server_error_response_envelope():
    response = client.get("/api/v1/demo/error500")

    assert response.status_code == 500

    body = response.json()

    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["message"] == "An unexpected error occurred."
    assert body["error"]["fieldErrors"] == []
    assert "correlationId" in body["error"]


def test_correlation_id_is_generated():
    response = client.get("/api/v1/demo/error")

    correlation_id = response.json()["error"]["correlationId"]

    assert correlation_id
    assert len(correlation_id) > 0
    assert response.headers["X-Correlation-ID"] == correlation_id


def test_correlation_id_is_preserved():
    correlation_id = "finex-contract-test-123"

    response = client.get(
        "/api/v1/demo/error",
        headers={"X-Correlation-ID": correlation_id},
    )

    assert response.status_code == 400

    body = response.json()

    assert body["error"]["correlationId"] == correlation_id
    assert response.headers["X-Correlation-ID"] == correlation_id
