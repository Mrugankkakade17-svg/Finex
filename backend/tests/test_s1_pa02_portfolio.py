import os
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import app.repositories.portfolio_repository as portfolio_repository_module
from app.auth.jwt_handler import create_access_token
from app.config.settings import Settings
from app.main import create_app
from app.ports.adapters.postgres_local_store import postgres_dsn
from app.repositories.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    AssetClass,
    HoldingCreate,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioType,
    PortfolioUpdate,
)
from app.services.portfolio_service import PortfolioService


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


def test_analytics_endpoint_is_owner_scoped_and_reports_missing_history(monkeypatch) -> None:
    from app.routers import portfolio as portfolio_router

    monkeypatch.setattr(portfolio_router, "fetch_close_price_history", lambda *args, **kwargs: {})
    app = create_app()
    client = TestClient(app)
    token_a = create_access_token({"sub": "analytics-a", "user_id": "analytics-a"})
    token_b = create_access_token({"sub": "analytics-b", "user_id": "analytics-b"})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    created = client.post(
        "/api/v1/portfolios",
        headers=headers_a,
        json={"name": "Analytics fixture", "currency": "USD"},
    )
    assert created.status_code == 201
    portfolio_id = created.json()["data"]["portfolio_id"]
    added = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers=headers_a,
        json={"symbol": "AAPL", "quantity": 1, "avg_buy_price": 100},
    )
    assert added.status_code == 201

    analytics = client.get(f"/api/v1/portfolios/{portfolio_id}/analytics", headers=headers_a)
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["success"] is True
    assert body["meta"]["dataStatus"] == "UNAVAILABLE"
    assert body["data"]["status"] == "INSUFFICIENT_DATA"
    assert body["data"]["hhi"] == 1.0
    assert body["data"]["top_holdings"][0]["symbol"] == "AAPL"

    denied = client.get(
        f"/api/v1/portfolios/{portfolio_id}/analytics",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert denied.status_code == 404


@pytest.mark.postgres
@pytest.mark.asyncio
async def test_postgres_portfolio_fields_round_trip_through_create_read_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_dotenv()
    database_url = os.getenv("APP_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("APP_DATABASE_URL or DATABASE_URL is required for PostgreSQL coverage")

    monkeypatch.setenv("APP_PERSISTENCE", "postgresql")
    settings = Settings(app_persistence="postgresql", app_database_url=database_url)
    monkeypatch.setattr(portfolio_repository_module, "get_settings", lambda: settings)
    repository = PortfolioRepository()
    postgres_store = repository._postgres_store
    assert postgres_store is not None
    with postgres_store.transaction():
        pass

    user_id = f"pa02-metadata-{uuid4()}"
    portfolio_id: str | None = None
    service = PortfolioService(repository=repository)
    try:
        created = await service.create_portfolio(
            user_id,
            PortfolioCreate(
                name="Retirement Portfolio",
                portfolio_type=PortfolioType.RETIREMENT,
                currency="EUR",
            ),
        )
        portfolio_id = created.portfolio_id
        read_created = await service.get_portfolio(portfolio_id, user_id)
        assert read_created.portfolio_type == PortfolioType.RETIREMENT
        assert read_created.currency == "EUR"

        updated = await service.update_portfolio(
            portfolio_id,
            user_id,
            PortfolioUpdate(
                name="Growth Portfolio",
                portfolio_type=PortfolioType.GROWTH,
                currency="GBP",
            ),
        )
        assert updated.portfolio_type == PortfolioType.GROWTH
        assert updated.currency == "GBP"

        created_holding = await service.add_holding(
            portfolio_id,
            user_id,
            HoldingCreate(
                symbol="AAPL",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Municipal Bonds",
                quantity=2.5,
                avg_buy_price=120.0,
                notes="Created with custom metadata",
            ),
        )
        assert created_holding.asset_class == AssetClass.FIXED_INCOME
        assert created_holding.sector == "Municipal Bonds"
        assert created_holding.notes == "Created with custom metadata"
        holding_id = created_holding.holding_id
        read_created_holding = (await service.list_holdings(portfolio_id, user_id))[0]
        assert read_created_holding.asset_class == AssetClass.FIXED_INCOME
        assert read_created_holding.sector == "Municipal Bonds"
        assert read_created_holding.notes == "Created with custom metadata"
        created_raw = await repository.get_holding(holding_id, portfolio_id, user_id)
        assert created_raw is not None
        assert created_raw["currency"] == "GBP"

        await service.update_portfolio(
            portfolio_id,
            user_id,
            PortfolioUpdate(currency="CAD", portfolio_type=PortfolioType.CONSERVATIVE),
        )
        currency_updated_holding = await repository.get_holding(holding_id, portfolio_id, user_id)
        assert currency_updated_holding is not None
        assert currency_updated_holding["currency"] == "CAD"
        updated_holding = await service.update_holding(
            holding_id,
            portfolio_id,
            user_id,
            HoldingUpdate(
                quantity=3.0,
                avg_buy_price=125.0,
                asset_class=AssetClass.COMMODITY,
                sector="Precious Metals",
                notes="Updated metadata",
            ),
        )
        assert updated_holding.asset_class == AssetClass.COMMODITY
        assert updated_holding.sector == "Precious Metals"
        assert updated_holding.notes == "Updated metadata"

        read_updated = await service.get_portfolio(portfolio_id, user_id)
        assert read_updated.portfolio_type == PortfolioType.CONSERVATIVE
        assert read_updated.currency == "CAD"
        read_holding = await repository.get_holding(holding_id, portfolio_id, user_id)
        assert read_holding is not None
        assert read_holding["asset_class"] == AssetClass.COMMODITY.value
        assert read_holding["sector"] == "Precious Metals"
        assert read_holding["notes"] == "Updated metadata"
        assert read_holding["currency"] == "CAD"
    finally:
        if portfolio_id is not None:
            await repository.delete_portfolio(portfolio_id, user_id)
        with psycopg.connect(postgres_dsn(database_url)) as connection:
            connection.execute("DELETE FROM finex.local_users WHERE user_id=%s", (user_id,))
