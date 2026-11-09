import pytest

from app.adapters.yfinance_adapter import YFinanceMarketDataProvider
from app.core.exceptions import (
    ProviderTimeoutException,
    RateLimitExceededException,
    SymbolNotFoundException,
)


@pytest.mark.asyncio
async def test_known_quote_is_deterministic_and_stale() -> None:
    provider = YFinanceMarketDataProvider()

    quote = await provider.get_quote(" aapl ")

    assert quote.symbol == "AAPL"
    assert quote.price == 227.16
    assert quote.is_stale is True
    assert quote.timestamp.tzinfo is not None


@pytest.mark.asyncio
async def test_unknown_quote_uses_explicit_fallback_or_fails() -> None:
    provider = YFinanceMarketDataProvider()

    fallback_quote = await provider.get_quote("unknown", fallback_price=12.5)

    assert fallback_quote.price == 12.5
    assert fallback_quote.is_stale is True

    with pytest.raises(SymbolNotFoundException):
        await provider.get_quote("unknown")


@pytest.mark.asyncio
async def test_configured_failure_modes_have_typed_errors() -> None:
    with pytest.raises(ProviderTimeoutException):
        await YFinanceMarketDataProvider(fail_mode="timeout").get_quote("AAPL")

    with pytest.raises(RateLimitExceededException):
        await YFinanceMarketDataProvider(fail_mode="rate_limit").get_quote("AAPL")
