from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_demo_error():
    response = client.get("/api/v1/demo/error")

    assert response.status_code == 400

    body = response.json()

    assert "error" in body
    assert body["error"]["code"] == "DEMO_ERROR"
    assert body["error"]["message"] == "This is a demo exception."
    assert body["error"]["fieldErrors"] == []
    assert body["error"]["correlationId"]
