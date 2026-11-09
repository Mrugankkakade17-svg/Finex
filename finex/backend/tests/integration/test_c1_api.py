# backend/tests/integration/test_c1_api.py
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.c1 import router

# Create a mini FastAPI app just for testing our router
app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_create_portfolio_fails_without_user_id():
    """
    Proves that the API strictly requires the X-User-ID header for authorization,
    acting as a boundary/security test.
    """
    # We are intentionally NOT sending the X-User-ID header
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "My Retirement Fund", "type": "MANUAL", "base_currency": "USD"},
    )

    # 422 is the standard FastAPI error code for missing/invalid required data
    assert response.status_code == 422
    assert "X-User-ID" in response.text
