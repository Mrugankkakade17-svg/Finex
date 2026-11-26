"""Unit and contract tests for S2-PA01: DataFreshness schema, provider chain,

circuit breaker, rate limiter, and yfinance strict non-LIVE invariant.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.adapters.yfinance_adapter import (
    CircuitBreaker,
    FixtureMarketDataProvider,
    RateLimiter,
    SecondaryMarketDataProvider,
    YFinanceMarketDataProvider,
)
from app.core.exceptions import (
    ProviderUnavailableException,
    RateLimitExceededException,
)
from app.schemas.market import (
    CircuitState,
    DataFreshness,
    MarketQuoteResponse,
)
from app.services.market_service import (
    MarketService,
    ProviderChainEntry,
)

# ===========================================================================
# 1. Circuit Breaker Unit Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_closed_to_open_transition() -> None:
    cb = CircuitBreaker(name="test_cb", failure_threshold=3, recovery_timeout=0.1)

    assert cb.state == CircuitState.CLOSED
    assert await cb.allow_request() is True

    # First failure
    await cb.record_failure(ValueError("err1"))
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 1
    assert await cb.allow_request() is True

    # Second failure
    await cb.record_failure(ValueError("err2"))
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 2
    assert await cb.allow_request() is True

    # Third failure -> trips to OPEN
    await cb.record_failure(ValueError("err3"))
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 3
    assert await cb.allow_request() is False


@pytest.mark.asyncio
async def test_circuit_breaker_open_to_half_open_and_recovery() -> None:
    cb = CircuitBreaker(
        name="test_cb",
        failure_threshold=2,
        recovery_timeout=0.05,
        success_threshold=1,
    )

    # Trip to OPEN
    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert await cb.allow_request() is False

    # Wait for recovery timeout
    await asyncio.sleep(0.06)

    # Should transition to HALF_OPEN
    assert cb.state == CircuitState.HALF_OPEN
    assert await cb.allow_request() is True

    # Successful call in HALF_OPEN recovers to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_re_trips_to_open() -> None:
    cb = CircuitBreaker(name="test_cb", failure_threshold=2, recovery_timeout=0.05)

    await cb.record_failure()
    await cb.record_failure()
    assert cb.state == CircuitState.OPEN

    await asyncio.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    # Failure in HALF_OPEN immediately trips back to OPEN
    await cb.record_failure(ValueError("relapse"))
    assert cb.state == CircuitState.OPEN


# ===========================================================================
# 2. Rate Limiter Unit Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_rate_limiter_permits_within_limit_and_blocks_when_exceeded() -> None:
    rl = RateLimiter(provider_name="test_provider", max_requests=2, window_seconds=60.0)

    # 1st and 2nd requests allowed
    assert await rl.acquire() is True
    assert await rl.acquire() is True
    assert rl.remaining_requests == 0

    # 3rd request exceeds limit
    with pytest.raises(RateLimitExceededException) as exc_info:
        await rl.acquire()

    assert "rate limit was exceeded" in str(exc_info.value)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_market_service_acquires_provider_rate_limit_once_per_quote() -> None:
    service = MarketService()
    limiter = service.chain[0].rate_limiter

    assert limiter is not None
    assert limiter.remaining_requests == 30

    response = await service.get_quote_with_freshness("AAPL")

    assert response.source == "yfinance"
    assert limiter.remaining_requests == 29


@pytest.mark.asyncio
async def test_unknown_symbols_do_not_trip_provider_circuit_breakers() -> None:
    chain = [
        ProviderChainEntry("yfinance", YFinanceMarketDataProvider()),
        ProviderChainEntry("fixture", FixtureMarketDataProvider()),
    ]
    service = MarketService(chain=chain)

    for _ in range(3):
        response = await service.get_quote_with_freshness("UNSUPPORTED")
        assert response.freshness == DataFreshness.UNAVAILABLE

    assert all(entry.circuit_breaker.failure_count == 0 for entry in chain)
    assert all(entry.circuit_breaker.state == CircuitState.CLOSED for entry in chain)


@pytest.mark.asyncio
async def test_secondary_provider_adapter_returns_cached_fixture_quote() -> None:
    secondary = SecondaryMarketDataProvider()
    quote = await secondary.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == 227.16
    assert quote.is_stale is False


@pytest.mark.asyncio
async def test_last_good_value_is_returned_cached_when_all_providers_fail() -> None:
    chain = [
        ProviderChainEntry("fixture", FixtureMarketDataProvider()),
    ]
    service = MarketService(
        chain=chain,
        cache_ttl_seconds=60,
        stale_ttl_seconds=300,
    )

    live = await service.get_quote_with_freshness("AAPL")
    assert live.freshness == DataFreshness.CACHED

    chain[0].provider.fail_mode = "timeout"
    cached = await service.get_quote_with_freshness("AAPL")

    assert cached.freshness == DataFreshness.CACHED
    assert cached.source == "cache"
    assert cached.price == 227.16
    assert cached.is_stale is False


@pytest.mark.asyncio
async def test_last_good_value_becomes_stale_after_cache_ttl() -> None:
    chain = [ProviderChainEntry("fixture", FixtureMarketDataProvider())]
    service = MarketService(
        chain=chain,
        cache_ttl_seconds=60,
        stale_ttl_seconds=300,
    )
    quote = await service.get_quote_with_freshness("AAPL")
    assert quote.freshness == DataFreshness.CACHED
    cached_quote, _ = service._last_good["AAPL"]
    service._last_good["AAPL"] = (
        cached_quote,
        datetime.now(timezone.utc) - timedelta(seconds=61),
    )

    fixture = service.chain[0]
    fixture.provider.fail_mode = "unavailable"
    stale = await service.get_quote_with_freshness("AAPL")

    assert stale.freshness == DataFreshness.STALE
    assert stale.source == "cache"
    assert stale.is_stale is True
    assert stale.price == 227.16


# ===========================================================================
# 3. Acceptance Criteria: Strict Invariant — No Path Can Emit LIVE for yfinance
# ===========================================================================


@pytest.mark.asyncio
async def test_yfinance_adapter_never_emits_live_freshness() -> None:
    """Invariant test: Any quote returned from yfinance is strictly non-LIVE."""
    adapter = YFinanceMarketDataProvider()

    quote = await adapter.get_quote("AAPL")
    assert quote.symbol == "AAPL"
    assert quote.is_stale is True  # Always marked stale/delayed in yfinance adapter

    fallback_quote = await adapter.get_quote("UNKNOWN", fallback_price=50.0)
    assert fallback_quote.is_stale is True


@pytest.mark.asyncio
async def test_market_service_yfinance_quotes_emit_delayed_never_live() -> None:
    """Invariant test: MarketService maps yfinance responses to DELAYED, never LIVE."""
    yf = YFinanceMarketDataProvider()
    service = MarketService(chain=[ProviderChainEntry("yfinance", yf)])

    response = await service.get_quote_with_freshness("AAPL")

    assert response.symbol == "AAPL"
    assert response.source == "yfinance"
    assert response.freshness == DataFreshness.DELAYED
    assert response.freshness != DataFreshness.LIVE


def test_schema_validator_rejects_live_freshness_for_yfinance() -> None:
    """Schema invariant: MarketQuoteResponse field_validator strictly rejects LIVE for yfinance."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # Allowed: DELAYED, CACHED, UNAVAILABLE for yfinance
    valid_resp = MarketQuoteResponse(
        symbol="AAPL",
        price=227.16,
        source="yfinance",
        fetched_at=now_iso,
        freshness=DataFreshness.DELAYED,
    )
    assert valid_resp.freshness == DataFreshness.DELAYED

    # Prohibited: LIVE for yfinance
    with pytest.raises(ValidationError) as exc_info:
        MarketQuoteResponse(
            symbol="AAPL",
            price=227.16,
            source="yfinance",
            fetched_at=now_iso,
            freshness=DataFreshness.LIVE,
        )

    expected_msg = "Contract violation: yfinance provider is never permitted to emit LIVE data."
    assert expected_msg in str(exc_info.value)

    # Case-insensitive check: "YFinance"
    with pytest.raises(ValidationError):
        MarketQuoteResponse(
            symbol="AAPL",
            price=227.16,
            source="YFinance",
            fetched_at=now_iso,
            freshness=DataFreshness.LIVE,
        )


# ===========================================================================
# 4. Acceptance Criteria: Timeout, Next Provider, UNAVAILABLE with Recorded Responses
# ===========================================================================


@pytest.mark.asyncio
async def test_acceptance_timeout_falls_back_to_next_provider() -> None:
    """Acceptance Test: Primary provider times out -> Chain advances to next provider."""
    # Primary provider configured to simulate timeout
    yf_primary = YFinanceMarketDataProvider(fail_mode="timeout", timeout_seconds=1.5)
    # Secondary fixture provider with valid fixture quote
    fixture_secondary = FixtureMarketDataProvider(
        custom_quotes={"AAPL": {"price": 227.16, "change": 1.50, "change_pct": 0.75}}
    )

    chain = [
        ProviderChainEntry("yfinance", yf_primary),
        ProviderChainEntry("fixture", fixture_secondary),
    ]
    service = MarketService(chain=chain)

    # Execute request
    response = await service.get_quote_with_freshness("AAPL")

    # Recorded response assertions
    assert response.symbol == "AAPL"
    assert response.price == 227.16
    assert response.source == "fixture"  # Proven fallback to next provider
    assert response.freshness == DataFreshness.CACHED
    assert response.error is None
    assert response.is_stale is False

    # Verify primary circuit breaker recorded the failure exactly once
    assert chain[0].circuit_breaker.failure_count == 1


@pytest.mark.asyncio
async def test_acceptance_provider_unavailable_falls_back_to_next_provider() -> None:
    """Acceptance Test: Primary provider unavailable -> Chain advances to next provider."""
    yf_primary = YFinanceMarketDataProvider(fail_mode="unavailable")
    fixture_secondary = FixtureMarketDataProvider()

    chain = [
        ProviderChainEntry("yfinance", yf_primary),
        ProviderChainEntry("fixture", fixture_secondary),
    ]
    service = MarketService(chain=chain)

    response = await service.get_quote_with_freshness("MSFT")

    assert response.symbol == "MSFT"
    assert response.price == 505.12
    assert response.source == "fixture"
    assert response.freshness == DataFreshness.CACHED


@pytest.mark.asyncio
async def test_acceptance_all_providers_fail_returns_unavailable_recorded_response() -> None:
    """Acceptance Test: All providers fail -> Chain returns truthful UNAVAILABLE response."""
    yf_primary = YFinanceMarketDataProvider(fail_mode="timeout")
    fixture_secondary = FixtureMarketDataProvider(fail_mode="unavailable")

    chain = [
        ProviderChainEntry("yfinance", yf_primary),
        ProviderChainEntry("fixture", fixture_secondary),
    ]
    service = MarketService(chain=chain)

    # 1. When no fallback price is provided
    response = await service.get_quote_with_freshness("AAPL")

    assert response.symbol == "AAPL"
    assert response.price is None
    assert response.freshness == DataFreshness.UNAVAILABLE
    assert response.is_stale is True
    assert response.source == "none"
    assert response.error is not None
    assert "All market providers in chain failed or unavailable" in response.error

    # 2. When positive fallback price is provided
    fallback_response = await service.get_quote_with_freshness("AAPL", fallback_price=150.0)

    assert fallback_response.symbol == "AAPL"
    assert fallback_response.price == 150.0
    assert fallback_response.freshness == DataFreshness.UNAVAILABLE
    assert fallback_response.is_stale is True


@pytest.mark.asyncio
async def test_market_service_port_contract_raises_on_unavailable_without_fallback() -> None:
    """Contract Test: get_quote raises ProviderUnavailableException when all fail."""
    yf_primary = YFinanceMarketDataProvider(fail_mode="unavailable")
    fixture_secondary = FixtureMarketDataProvider(fail_mode="unavailable")

    service = MarketService(
        chain=[
            ProviderChainEntry("yfinance", yf_primary),
            ProviderChainEntry("fixture", fixture_secondary),
        ]
    )

    with pytest.raises(ProviderUnavailableException) as exc_info:
        await service.get_quote("AAPL")

    assert "All market providers in chain failed" in str(exc_info.value)
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_market_service_batch_quotes_and_health() -> None:
    """Integration Test: Batch quotes and provider diagnostic health reporting."""
    service = MarketService()

    batch = await service.get_batch_quotes(["AAPL", "MSFT"])
    assert batch.requested_count == 2
    assert batch.resolved_count == 2
    assert "AAPL" in batch.quotes
    assert "MSFT" in batch.quotes
    assert batch.quotes["AAPL"].freshness == DataFreshness.DELAYED

    health = service.get_health()
    assert len(health) == 2
    assert health[0].provider_name == "yfinance"
    assert health[0].circuit_state == CircuitState.CLOSED
    assert health[0].is_available is True
