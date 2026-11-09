import asyncio
from datetime import datetime

import pytest

from app.adapters.market_data_adapter import MockMarketDataProvider
from app.core.exceptions import FinExException
from app.repositories.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    AssetClass,
    HoldingCreate,
    PortfolioCreate,
    PortfolioType,
    PortfolioUpdate,
)
from app.services.portfolio_math import (
    calculate_allocations,
    calculate_holding_metrics,
    compute_portfolio_valuations,
)
from app.services.portfolio_service import PortfolioService


@pytest.fixture
def repo():
    r = PortfolioRepository()
    r.clear()
    return r


@pytest.fixture
def mock_market():
    return MockMarketDataProvider(
        {
            "AAPL": {"price": 200.0, "change": 5.0, "change_pct": 2.56},
            "MSFT": {"price": 400.0, "change": -2.0, "change_pct": -0.50},
            "BND": {"price": 80.0, "change": 0.2, "change_pct": 0.25},
        }
    )


@pytest.fixture
def service(repo, mock_market):
    return PortfolioService(repository=repo, market_data_provider=mock_market)


# ---------------------------------------------------------------------------
# Unit Tests: Portfolio Math Engine
# ---------------------------------------------------------------------------


def test_holding_metrics_gain():
    raw = {
        "holding_id": "h-1",
        "portfolio_id": "p-1",
        "user_id": "u-1",
        "symbol": "AAPL",
        "asset_class": AssetClass.EQUITY,
        "sector": "Technology",
        "quantity": 10.0,
        "avg_buy_price": 150.0,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    # Current price = 200 -> Cost = 1500, Value = 2000, Gain = +500 (+33.33%)
    metrics = calculate_holding_metrics(raw, current_price=200.0, portfolio_total_value=5000.0)

    assert metrics.total_cost == 1500.0
    assert metrics.current_value == 2000.0
    assert metrics.unrealized_gain_loss == 500.0
    assert metrics.unrealized_gain_loss_pct == 33.33
    assert metrics.weight_pct == 40.0  # 2000 / 5000 * 100


def test_holding_metrics_loss():
    raw = {
        "holding_id": "h-2",
        "portfolio_id": "p-1",
        "user_id": "u-1",
        "symbol": "MSFT",
        "asset_class": AssetClass.EQUITY,
        "sector": "Technology",
        "quantity": 5.0,
        "avg_buy_price": 500.0,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    # Current price = 400 -> Cost = 2500, Value = 2000, Loss = -500 (-20.00%)
    metrics = calculate_holding_metrics(raw, current_price=400.0, portfolio_total_value=4000.0)

    assert metrics.total_cost == 2500.0
    assert metrics.current_value == 2000.0
    assert metrics.unrealized_gain_loss == -500.0
    assert metrics.unrealized_gain_loss_pct == -20.0
    assert metrics.weight_pct == 50.0


def test_portfolio_valuations_deterministic():
    raw_holdings = [
        {
            "holding_id": "h-1",
            "portfolio_id": "p-1",
            "user_id": "u-1",
            "symbol": "AAPL",
            "asset_class": AssetClass.EQUITY,
            "sector": "Technology",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "holding_id": "h-2",
            "portfolio_id": "p-1",
            "user_id": "u-1",
            "symbol": "BND",
            "asset_class": AssetClass.FIXED_INCOME,
            "sector": "Government",
            "quantity": 25.0,
            "avg_buy_price": 80.0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
    ]
    quotes = {"AAPL": 200.0, "BND": 80.0}

    total_val, total_cost, gain_loss, gain_loss_pct, evaluated = compute_portfolio_valuations(
        raw_holdings, quotes
    )

    # AAPL: Cost 1500, Val 2000
    # BND: Cost 2000, Val 2000
    # Total Cost = 3500, Total Val = 4000, Gain = +500 (+14.29%)
    assert total_cost == 3500.0
    assert total_val == 4000.0
    assert gain_loss == 500.0
    assert gain_loss_pct == 14.29
    assert len(evaluated) == 2

    # Verify weights sum to 100%
    assert evaluated[0].weight_pct == 50.0
    assert evaluated[1].weight_pct == 50.0


def test_calculate_allocations_asset_class():
    raw_holdings = [
        {
            "holding_id": "h-1",
            "portfolio_id": "p-1",
            "user_id": "u-1",
            "symbol": "AAPL",
            "asset_class": AssetClass.EQUITY,
            "sector": "Technology",
            "quantity": 10.0,
            "avg_buy_price": 150.0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
        {
            "holding_id": "h-2",
            "portfolio_id": "p-1",
            "user_id": "u-1",
            "symbol": "BND",
            "asset_class": AssetClass.FIXED_INCOME,
            "sector": "Fixed Income",
            "quantity": 25.0,
            "avg_buy_price": 80.0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        },
    ]
    quotes = {"AAPL": 200.0, "BND": 80.0}
    total_val, _, _, _, evaluated = compute_portfolio_valuations(raw_holdings, quotes)

    allocations = calculate_allocations(evaluated, "asset_class", total_val)

    assert len(allocations) == 2
    assert allocations[0].category == "EQUITY"
    assert allocations[0].percentage == 50.0
    assert allocations[1].category == "FIXED_INCOME"
    assert allocations[1].percentage == 50.0


# ---------------------------------------------------------------------------
# Unit Tests: Portfolio Service & Multi-Tenancy Isolation
# ---------------------------------------------------------------------------


def test_create_and_get_portfolio(service):
    async def run():
        user_id = "usr_alpha"
        create_req = PortfolioCreate(
            name="Retirement Nest",
            description="Long term 401k",
            portfolio_type=PortfolioType.RETIREMENT,
            currency="USD",
        )

        created = await service.create_portfolio(user_id, create_req)
        assert created.name == "Retirement Nest"
        assert created.user_id == user_id
        assert created.total_value == 0.0
        assert created.holdings_count == 0

        fetched = await service.get_portfolio(created.portfolio_id, user_id)
        assert fetched.portfolio_id == created.portfolio_id
        assert fetched.name == "Retirement Nest"

    asyncio.run(run())


def test_multi_tenant_isolation(service):
    async def run():
        user_a = "user_A"
        user_b = "user_B"

        # User A creates a portfolio
        port_a = await service.create_portfolio(
            user_a,
            PortfolioCreate(name="User A Secret Wealth", portfolio_type=PortfolioType.GROWTH),
        )

        # User B tries to view User A's portfolio -> 404 / Access Denied
        with pytest.raises(FinExException) as exc_info:
            await service.get_portfolio(port_a.portfolio_id, user_b)
        assert exc_info.value.status_code == 404

        # User B tries to delete User A's portfolio -> 404 / Access Denied
        with pytest.raises(FinExException) as exc_info:
            await service.delete_portfolio(port_a.portfolio_id, user_b)
        assert exc_info.value.status_code == 404

        # User B tries to add a holding into User A's portfolio -> 404 / Access Denied
        with pytest.raises(FinExException) as exc_info:
            await service.add_holding(
                port_a.portfolio_id,
                user_b,
                HoldingCreate(symbol="AAPL", quantity=10, avg_buy_price=150),
            )
        assert exc_info.value.status_code == 404

    asyncio.run(run())


def test_add_holding_and_summary_calculation(service):
    async def run():
        user_id = "user_investor"

        # 1. Create portfolio
        p = await service.create_portfolio(
            user_id,
            PortfolioCreate(name="Core Growth", portfolio_type=PortfolioType.GROWTH),
        )

        # 2. Add AAPL (Equity) - 10 shares @ $150 (Market Price in mock = $200)
        await service.add_holding(
            p.portfolio_id,
            user_id,
            HoldingCreate(
                symbol="AAPL",
                asset_class=AssetClass.EQUITY,
                sector="Technology",
                quantity=10,
                avg_buy_price=150,
            ),
        )

        # 3. Add BND (Fixed Income) - 25 shares @ $80 (Market Price in mock = $80)
        await service.add_holding(
            p.portfolio_id,
            user_id,
            HoldingCreate(
                symbol="BND",
                asset_class=AssetClass.FIXED_INCOME,
                sector="Fixed Income",
                quantity=25,
                avg_buy_price=80,
            ),
        )

        # 4. Fetch Summary
        summary = await service.get_portfolio_summary(p.portfolio_id, user_id)

        assert summary.portfolio_id == p.portfolio_id
        assert summary.total_cost == 3500.0
        assert summary.total_value == 4000.0
        assert summary.total_gain_loss == 500.0
        assert summary.total_gain_loss_pct == 14.29
        assert summary.holdings_count == 2
        assert summary.data_status == "LIVE"

        # Verify Asset Allocation Breakdown
        assert len(summary.asset_allocation) == 2
        assert summary.asset_allocation[0].category == "EQUITY"
        assert summary.asset_allocation[0].percentage == 50.0
        assert summary.asset_allocation[1].category == "FIXED_INCOME"
        assert summary.asset_allocation[1].percentage == 50.0

        # Verify Top Performers
        assert len(summary.top_performers) == 2
        assert summary.top_performers[0].symbol == "AAPL"
        assert summary.top_performers[0].unrealized_gain_loss_pct == 33.33

    asyncio.run(run())


def test_update_and_delete_portfolio(service):
    async def run():
        user_id = "user_test_lifecycle"

        p = await service.create_portfolio(
            user_id,
            PortfolioCreate(name="Initial Name", portfolio_type=PortfolioType.TRADING),
        )

        updated = await service.update_portfolio(
            p.portfolio_id,
            user_id,
            PortfolioUpdate(name="Renamed Portfolio", description="Updated Description"),
        )
        assert updated.name == "Renamed Portfolio"
        assert updated.description == "Updated Description"

        deleted = await service.delete_portfolio(p.portfolio_id, user_id)
        assert deleted is True

        # After delete, get should fail
        with pytest.raises(FinExException):
            await service.get_portfolio(p.portfolio_id, user_id)

    asyncio.run(run())


def test_missing_quote_safe_fallback(service):
    async def run():
        user_id = "user_obscure_asset"

        p = await service.create_portfolio(
            user_id,
            PortfolioCreate(name="Alternative Assets", portfolio_type=PortfolioType.INDIVIDUAL),
        )

        # UNKNOWN_TICKER is not in mock market prices
        # System should fallback to avg_buy_price without setting price to 0.0
        holding = await service.add_holding(
            p.portfolio_id,
            user_id,
            HoldingCreate(
                symbol="UNKNOWN_FUND",
                asset_class=AssetClass.COMMODITY,
                quantity=10,
                avg_buy_price=50.0,
            ),
        )

        assert holding.current_price == 50.0
        assert holding.current_value == 500.0
        assert holding.unrealized_gain_loss == 0.0

        summary = await service.get_portfolio_summary(p.portfolio_id, user_id)
        assert summary.data_status == "DELAYED"
        assert summary.total_value == 500.0

    asyncio.run(run())
