"""Contract tests for the S2-PA02 secondary-provider and last-good cache."""

from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.yfinance_adapter import (
    FixtureMarketDataProvider,
    SecondaryMarketDataProvider,
    YFinanceMarketDataProvider,
)
from app.core.exceptions import ProviderUnavailableException
from app.ports.market_data_port import MarketQuote
from app.schemas.market import DataFreshness
from app.services.market_service import MarketService, ProviderChainEntry


def make_quote(
    symbol: str = "AAPL",
    *,
    price: float = 100.0,
    is_stale: bool = False,
    timestamp: datetime | None = None,
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        price=price,
        change=0.0,
        change_pct=0.0,
        timestamp=timestamp or datetime.now(timezone.utc),
        is_stale=is_stale,
    )


@pytest.mark.asyncio
async def test_secondary_provider_reports_its_own_name() -> None:
    provider = SecondaryMarketDataProvider(fail_mode="unavailable")

    assert provider.provider_name == "secondary"
    with pytest.raises(ProviderUnavailableException, match="secondary"):
        await provider.get_quote("AAPL")


@pytest.mark.asyncio
async def test_cache_is_cached_at_exact_sixty_second_boundary() -> None:
    service = MarketService(cache_ttl_seconds=60.0, stale_ttl_seconds=300.0)
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service._last_good["AAPL"] = (make_quote(timestamp=fetched_at), fetched_at)

    response = await service._get_last_good_response("AAPL", fetched_at + timedelta(seconds=60.0))

    assert response is not None
    assert response.freshness == DataFreshness.CACHED


@pytest.mark.asyncio
async def test_cache_is_stale_after_sixty_seconds_and_at_exact_three_hundred() -> None:
    service = MarketService(cache_ttl_seconds=60.0, stale_ttl_seconds=300.0)
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service._last_good["AAPL"] = (make_quote(timestamp=fetched_at), fetched_at)

    just_after_cache_ttl = await service._get_last_good_response(
        "AAPL", fetched_at + timedelta(seconds=60.0001)
    )
    at_stale_ttl = await service._get_last_good_response(
        "AAPL", fetched_at + timedelta(seconds=300.0)
    )

    assert just_after_cache_ttl is not None
    assert just_after_cache_ttl.freshness == DataFreshness.STALE
    assert at_stale_ttl is not None
    assert at_stale_ttl.freshness == DataFreshness.STALE


@pytest.mark.asyncio
async def test_cache_entry_is_evicted_after_three_hundred_seconds() -> None:
    service = MarketService(cache_ttl_seconds=60.0, stale_ttl_seconds=300.0)
    fetched_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service._last_good["AAPL"] = (make_quote(timestamp=fetched_at), fetched_at)

    response = await service._get_last_good_response(
        "AAPL", fetched_at + timedelta(seconds=300.0001)
    )

    assert response is None
    assert "AAPL" not in service._last_good


@pytest.mark.asyncio
async def test_first_request_with_both_providers_failing_is_unavailable() -> None:
    service = MarketService(
        chain=[
            ProviderChainEntry("yfinance", YFinanceMarketDataProvider(fail_mode="timeout")),
            ProviderChainEntry("secondary", SecondaryMarketDataProvider(fail_mode="unavailable")),
        ]
    )

    response = await service.get_quote_with_freshness("AAPL")

    assert response.freshness == DataFreshness.UNAVAILABLE
    assert response.price is None
    assert service._last_good == {}


@pytest.mark.asyncio
async def test_last_good_cache_is_isolated_per_symbol() -> None:
    provider = FixtureMarketDataProvider(
        custom_quotes={"AAPL": {"price": 100.0, "change": 0.0, "change_pct": 0.0}}
    )
    service = MarketService(chain=[ProviderChainEntry("fixture", provider)])

    assert (await service.get_quote_with_freshness("AAPL")).price == 100.0
    provider.fail_mode = "unavailable"

    cached_aapl = await service.get_quote_with_freshness("AAPL")
    missing_msft = await service.get_quote_with_freshness("MSFT")

    assert cached_aapl.freshness == DataFreshness.CACHED
    assert cached_aapl.price == 100.0
    assert missing_msft.freshness == DataFreshness.UNAVAILABLE
    assert missing_msft.price is None


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [0.0, -25.0, float("nan"), float("inf")])
async def test_invalid_prices_are_not_added_to_last_good_cache(price: float) -> None:
    service = MarketService()

    await service._record_last_good("AAPL", make_quote(price=price))

    assert "AAPL" not in service._last_good


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [0.0, -25.0, float("nan"), float("inf")])
async def test_provider_invalid_prices_are_unavailable_not_returned(price: float) -> None:
    provider = FixtureMarketDataProvider(
        custom_quotes={"AAPL": {"price": price, "change": 0.0, "change_pct": 0.0}}
    )
    service = MarketService(chain=[ProviderChainEntry("fixture", provider)])

    response = await service.get_quote_with_freshness("AAPL")

    assert response.freshness == DataFreshness.UNAVAILABLE
    assert response.price is None
    assert "AAPL" not in service._last_good


@pytest.mark.asyncio
async def test_stale_quote_cannot_overwrite_fresh_last_good_value() -> None:
    service = MarketService()
    fresh = make_quote(price=100.0)
    await service._record_last_good("AAPL", fresh)
    saved_fresh, saved_at = service._last_good["AAPL"]

    await service._record_last_good("AAPL", make_quote(price=90.0, is_stale=True))

    cached_quote, cached_at = service._last_good["AAPL"]
    assert cached_quote is saved_fresh
    assert cached_at == saved_at


@pytest.mark.asyncio
async def test_port_quote_preserves_cached_observation_timestamp() -> None:
    provider = FixtureMarketDataProvider(
        custom_quotes={"AAPL": {"price": 100.0, "change": 1.0, "change_pct": 1.0}}
    )
    service = MarketService(chain=[ProviderChainEntry("fixture", provider)])

    first = await service.get_quote("AAPL")
    provider.fail_mode = "unavailable"
    cached = await service.get_quote("AAPL")

    assert cached.timestamp == first.timestamp
    assert cached.price == first.price
    assert cached.is_stale is False


@pytest.mark.asyncio
async def test_port_quote_raises_instead_of_returning_zero_price() -> None:
    service = MarketService(
        chain=[
            ProviderChainEntry("yfinance", YFinanceMarketDataProvider(fail_mode="unavailable")),
            ProviderChainEntry("secondary", SecondaryMarketDataProvider(fail_mode="unavailable")),
        ]
    )

    with pytest.raises(ProviderUnavailableException):
        await service.get_quote("AAPL")
