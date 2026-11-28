from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.auth.principal import Principal, get_current_principal
from app.main import create_app
from app.routers.twin import get_twin_service
from app.services.twin_service import TwinService


class OwnedPortfolioSource:
    async def list_portfolios(self, user_id: str):
        if user_id != "twin-user-a":
            return []
        return [SimpleNamespace(currency="USD", total_value=Decimal("2500.00"))]


class OwnedPaperSource:
    def get_account(self, user_id: str):
        if user_id != "twin-user-a":
            return {
                "cash_balance": Decimal("0.00"),
                "total_equity": Decimal("0.00"),
                "currency": "USD",
            }
        return {
            "cash_balance": Decimal("1000.00"),
            "total_equity": Decimal("1200.00"),
            "currency": "USD",
        }


class OwnedSpendingSource:
    def list_transactions(self, user_id: str):
        if user_id != "twin-user-a":
            return []
        return [SimpleNamespace(date="2026-11-28", amount=Decimal("100.00"))]


def _test_principal(request: Request) -> Principal:
    user_id = request.headers.get("X-Test-User")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return Principal(user_id=user_id)


def _test_twin_service() -> TwinService:
    return TwinService(
        portfolio_source=OwnedPortfolioSource(),
        paper_source=OwnedPaperSource(),
        spending_source=OwnedSpendingSource(),
    )


def test_twin_route_requires_authentication():
    application = create_app()
    application.dependency_overrides[get_twin_service] = _test_twin_service

    with TestClient(application) as client:
        response = client.get("/api/v1/twin")

    assert response.status_code == 401


def test_twin_route_returns_authenticated_user_snapshot_contract():
    application = create_app()
    application.dependency_overrides[get_current_principal] = _test_principal
    application.dependency_overrides[get_twin_service] = _test_twin_service

    with TestClient(application) as client:
        response = client.get(
            "/api/v1/twin?as_of_date=2026-11-28",
            headers={"X-Test-User": "twin-user-a"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["data"]["as_of_date"] == "2026-11-28"
    assert body["data"]["figures"] == [
        {
            "label": "manual investment assets",
            "source": "manual_portfolios",
            "currency": "USD",
            "amount": "2500.00",
            "kind": "assets",
        },
        {
            "label": "paper account equity (cash plus paper positions)",
            "source": "paper_account",
            "currency": "USD",
            "amount": "1200.00",
            "kind": "simulated_assets",
        },
    ]
    assert body["data"]["combined_net_worth"] is None
    assert body["data"]["liabilities"]["complete"] is False
    assert body["meta"]["dataStatus"] == "CACHED"


def test_twin_route_does_not_return_another_users_figures():
    application = create_app()
    application.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="different-user"
    )
    application.dependency_overrides[get_twin_service] = _test_twin_service

    with TestClient(application) as client:
        response = client.get("/api/v1/twin")

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["figures"] == [
        {
            "label": "paper account equity (cash plus paper positions)",
            "source": "paper_account",
            "currency": "USD",
            "amount": "0.00",
            "kind": "simulated_assets",
        }
    ]
