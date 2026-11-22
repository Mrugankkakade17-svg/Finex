from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.main import create_app


def test_portfolio_route_is_mounted_and_uses_authenticated_principal() -> None:
    app = create_app()
    client = TestClient(app)

    unauthenticated = client.get("/api/v1/portfolios")
    assert unauthenticated.status_code in (401, 403)

    token = create_access_token({"sub": "pa02-user", "user_id": "pa02-user"})
    response = client.get(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_cross_user_portfolio_access_is_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    token_a = create_access_token({"sub": "pa02-a", "user_id": "pa02-a"})
    token_b = create_access_token({"sub": "pa02-b", "user_id": "pa02-b"})
    created = client.post(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Private Portfolio", "currency": "USD"},
    )
    assert created.status_code == 201
    portfolio_id = created.json()["data"]["portfolio_id"]

    denied = client.get(
        f"/api/v1/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404
