from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.schemas.market import DataFreshness
from app.schemas.paper import PaperOrderRequest
from app.services.paper_trading_service import PaperTradingService
from tests.support.paper_trading import FixedPaperQuotes, MemoryPaperTradingRepository

NOW = datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc)


def make_service(
    *,
    cash: str = "50000.00",
    fee_bps: int = 10,
    quotes: FixedPaperQuotes | None = None,
    open_market: bool = True,
):
    repo = MemoryPaperTradingRepository()
    quote_source = quotes or FixedPaperQuotes()
    service = PaperTradingService(
        repo,
        quote_source,
        Settings(
            paper_trading_initial_cash=Decimal(cash),
            paper_trading_fee_bps=fee_bps,
        ),
        clock=lambda: NOW,
        market_open=lambda _exchange, _now: open_market,
    )
    return service, repo, quote_source


def request(key: str, *, side: str = "BUY", quantity: int = 2):
    return PaperOrderRequest(
        instrument_id="aapl",
        exchange="NASDAQ",
        side=side,
        quantity=quantity,
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_buy_is_idempotent_and_posts_fee_adjusted_ledger_effect():
    service, repo, quotes = make_service()

    filled, created = await service.submit_order("user-1", request("client-order-001"))
    replay, replay_created = await service.submit_order("user-1", request("client-order-001"))

    assert created is True and replay_created is False
    assert replay.order_id == filled.order_id
    assert len(repo.orders) == 1
    assert repo.cash["user-1"] == 4_979_980
    assert quotes.calls == ["AAPL"]
    account = service.get_account("user-1")
    assert account["cash_balance"] == Decimal("49799.8")
    assert account["positions"][0]["quantity"] == 2
    assert account["positions"][0]["average_cost"] == Decimal("100.10")


@pytest.mark.asyncio
async def test_reusing_key_for_different_request_is_rejected():
    service, _, _ = make_service()
    await service.submit_order("user-1", request("client-order-002"))

    with pytest.raises(FinExException) as error:
        await service.submit_order("user-1", request("client-order-002", quantity=3))

    assert error.value.error_code == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.asyncio
async def test_closed_market_rejects_without_fetching_quote_or_creating_order():
    service, repo, quotes = make_service(open_market=False)

    with pytest.raises(FinExException) as error:
        await service.submit_order("user-1", request("client-order-003"))

    assert error.value.error_code == "MARKET_CLOSED"
    assert quotes.calls == []
    assert repo.orders == {}


@pytest.mark.parametrize(
    ("price", "freshness", "stale"),
    [
        (None, DataFreshness.UNAVAILABLE, True),
        (100.0, DataFreshness.STALE, True),
        (100.0, DataFreshness.CACHED, True),
    ],
)
@pytest.mark.asyncio
async def test_ineligible_quote_rejects_without_creating_order(price, freshness, stale):
    service, repo, _ = make_service(
        quotes=FixedPaperQuotes(price=price, freshness=freshness, stale=stale)
    )

    with pytest.raises(FinExException) as error:
        await service.submit_order("user-1", request("client-order-004"))

    assert error.value.error_code == "QUOTE_INELIGIBLE"
    assert repo.orders == {}


@pytest.mark.asyncio
async def test_concurrent_buys_cannot_overdraw_paper_cash():
    import asyncio

    service, repo, _ = make_service(cash="100.00", fee_bps=10, quotes=FixedPaperQuotes(price=80))
    results = await asyncio.gather(
        service.submit_order("user-1", request("client-order-005", quantity=1)),
        service.submit_order("user-1", request("client-order-006", quantity=1)),
        return_exceptions=True,
    )

    successful = [result for result in results if not isinstance(result, Exception)]
    rejected = [result for result in results if isinstance(result, FinExException)]
    assert len(successful) == 1, repr(results)
    assert len(rejected) == 1
    assert rejected[0].error_code == "INSUFFICIENT_CASH"
    assert repo.cash["user-1"] == 1_992
    assert len(repo.orders) == 1


@pytest.mark.asyncio
async def test_sell_requires_owned_quantity_and_updates_position():
    service, repo, _ = make_service()
    await service.submit_order("user-1", request("client-order-007", quantity=4))

    with pytest.raises(FinExException) as error:
        await service.submit_order("user-1", request("client-order-008", side="SELL", quantity=5))
    assert error.value.error_code == "INSUFFICIENT_POSITION"

    sold, created = await service.submit_order(
        "user-1", request("client-order-009", side="SELL", quantity=1)
    )
    assert created is True
    assert sold.cash_delta_cents == 9_990
    assert repo.positions[("user-1", "AAPL", "NASDAQ")]["quantity"] == 3
