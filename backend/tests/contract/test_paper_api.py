from datetime import datetime, timezone
from decimal import Decimal

from fastapi import Request
from fastapi.testclient import TestClient

from app.auth.principal import Principal, get_current_principal
from app.config.settings import Settings
from app.main import create_app
from app.routers.paper import get_paper_trading_service
from app.services.paper_trading_service import PaperTradingService
from tests.support.paper_trading import FixedPaperQuotes, MemoryPaperTradingRepository


def test_paper_order_contract_idempotency_and_user_isolation():
    repository = MemoryPaperTradingRepository()
    service = PaperTradingService(
        repository,
        FixedPaperQuotes(price=125.5),
        Settings(paper_trading_initial_cash=Decimal("1000.00"), paper_trading_fee_bps=10),
        clock=lambda: datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc),
        market_open=lambda _exchange, _now: True,
    )
    app = create_app()

    def resolve_test_principal(request: Request):
        user_id = request.headers.get("X-Test-User")
        if not user_id:
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="Authorization header missing")
        return Principal(user_id=user_id)

    app.dependency_overrides[get_current_principal] = resolve_test_principal
    app.dependency_overrides[get_paper_trading_service] = lambda: service

    with TestClient(app) as client:
        headers = {"X-Test-User": "paper-user-a"}
        payload = {
            "instrument_id": "aapl",
            "exchange": "NASDAQ",
            "side": "BUY",
            "quantity": 2,
            "idempotency_key": "contract-order-001",
        }
        first = client.post("/api/v1/paper/orders", json=payload, headers=headers)
        replay = client.post("/api/v1/paper/orders", json=payload, headers=headers)
        account = client.get("/api/v1/paper/account", headers=headers)
        positions = client.get("/api/v1/paper/positions", headers=headers)
        other_account = client.get("/api/v1/paper/account", headers={"X-Test-User": "paper-user-b"})
        other_orders = client.get("/api/v1/paper/orders", headers={"X-Test-User": "paper-user-b"})
        unauthenticated = client.get("/api/v1/paper/account")

    assert first.status_code == 201, first.text
    assert first.json()["success"] is True
    assert first.json()["data"]["status"] == "FILLED"
    assert first.json()["data"]["fee"] == "0.25"
    assert replay.status_code == 200
    assert replay.json()["data"]["order_id"] == first.json()["data"]["order_id"]
    assert account.json()["data"]["cash_balance"] == "748.75"
    assert account.json()["data"]["positions"][0]["quantity"] == 2
    assert len(positions.json()["data"]) == 1
    assert other_account.json()["data"]["cash_balance"] == "1000.00"
    assert other_account.json()["data"]["positions"] == []
    assert other_orders.json()["data"] == []
    assert unauthenticated.status_code == 401


def test_paper_routes_are_registered_without_replacing_existing_router():
    paths = create_app().openapi()["paths"]
    assert "/api/v1/paper/orders" in paths
    assert "/api/v1/paper/account" in paths
