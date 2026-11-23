"""Market service implementing provider chain, circuit breaker, rate limiting, and DataFreshness."""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.adapters.yfinance_adapter import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    FixtureMarketDataProvider,
    RateLimiter,
    YFinanceMarketDataProvider,
)
from app.core.exceptions import (
    ProviderTimeoutException,
    ProviderUnavailableException,
    RateLimitExceededException,
    SymbolNotFoundException,
)
from app.ports.market_data_port import MarketDataProvider, MarketQuote
from app.schemas.market import (
    BatchQuotesResponse,
    CircuitState,
    DataFreshness,
    MarketQuoteResponse,
    ProviderHealth,
)

logger = logging.getLogger(__name__)


class ProviderChainEntry:
    """Wrapper encapsulating a provider, its circuit breaker, and rate limiter."""

    def __init__(
        self,
        name: str,
        provider: MarketDataProvider,
        circuit_breaker: Optional[CircuitBreaker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.name = name
        self.provider = provider
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name=name)
        self.rate_limiter = rate_limiter

        # Wire up the circuit breaker if the provider supports it.
        if hasattr(self.provider, "circuit_breaker"):
            self.provider.circuit_breaker = self.circuit_breaker


class MarketService(MarketDataProvider):
    """Authoritative market service coordinating the multi-provider fallback chain.

    Features:
    1. Provider Chain: Primary provider (yfinance) falls back to secondary (fixture).
    2. Fault Tolerance: Handles timeout, unavailable, and rate limits gracefully.
    3. Circuit Breaker: Prevents cascading failures on downstream outages.
    4. Rate Limiter: Protects third-party providers from quota exhaustion.
    5. Truthful Freshness: Strictly enforces that no yfinance path can emit LIVE.
    6. Graceful Degradation: Emits UNAVAILABLE state when entire chain is exhausted.
    """

    def __init__(
        self,
        chain: Optional[list[ProviderChainEntry]] = None,
        default_currency: str = "USD",
    ):
        self.default_currency = default_currency

        if chain is not None:
            self._chain = chain
        else:
            # Default production-like chain: yfinance (with limits) -> fixture fallback
            yf_cb = CircuitBreaker(name="yfinance", failure_threshold=3, recovery_timeout=30.0)
            yf_rl = RateLimiter(provider_name="yfinance", max_requests=30, window_seconds=60.0)
            yf_provider = YFinanceMarketDataProvider(
                timeout_seconds=3.0,
                circuit_breaker=yf_cb,
            )

            fix_cb = CircuitBreaker(name="fixture", failure_threshold=5, recovery_timeout=15.0)
            fix_provider = FixtureMarketDataProvider(
                timeout_seconds=2.0,
                circuit_breaker=fix_cb,
            )

            self._chain = [
                ProviderChainEntry("yfinance", yf_provider, yf_cb, yf_rl),
                ProviderChainEntry("fixture", fix_provider, fix_cb),
            ]

    @property
    def chain(self) -> list[ProviderChainEntry]:
        return self._chain

    async def get_quote_with_freshness(
        self,
        symbol: str,
        fallback_price: Optional[float] = None,
    ) -> MarketQuoteResponse:
        """Fetch quote traversing provider chain, returning rich schema with truthful freshness."""
        normalized = symbol.strip().upper()
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        errors: list[str] = []

        for entry in self._chain:
            # 1. Circuit Breaker Check
            if not await entry.circuit_breaker.allow_request():
                reset_sec = entry.circuit_breaker.get_reset_in_seconds()
                logger.warning(
                    "Skipping provider '%s' (circuit breaker is OPEN, resets in %.1fs)",
                    entry.name,
                    reset_sec,
                )
                errors.append(f"{entry.name}: circuit breaker is OPEN")
                continue

            # 2. Rate Limiter Check
            if entry.rate_limiter:
                try:
                    await entry.rate_limiter.acquire()
                except RateLimitExceededException as rle:
                    logger.warning("Provider '%s' rate limited: %s", entry.name, rle)
                    errors.append(f"{entry.name}: rate limit exceeded")
                    continue

            # 3. Attempt quote retrieval
            try:
                quote = await entry.provider.get_quote(normalized, fallback_price=fallback_price)

                # Determine and enforce truthful freshness
                if entry.name == "yfinance":
                    # LOCKED INVARIANT: No path can emit LIVE for yfinance
                    freshness = DataFreshness.DELAYED
                elif entry.name == "fixture":
                    freshness = DataFreshness.CACHED
                elif quote.is_stale:
                    freshness = DataFreshness.DELAYED
                else:
                    freshness = DataFreshness.DELAYED

                if getattr(entry.provider, "circuit_breaker", None) is not entry.circuit_breaker:
                    await entry.circuit_breaker.record_success()

                return MarketQuoteResponse(
                    symbol=normalized,
                    price=quote.price,
                    currency=self.default_currency,
                    change=quote.change,
                    change_pct=quote.change_pct,
                    source=entry.name,
                    as_of=now_iso,
                    fetched_at=now_iso,
                    freshness=freshness,
                    is_stale=quote.is_stale,
                    error=None,
                )

            except (
                ProviderTimeoutException,
                ProviderUnavailableException,
                RateLimitExceededException,
                CircuitBreakerOpenException,
                SymbolNotFoundException,
            ) as exc:
                provider_breaker = getattr(entry.provider, "circuit_breaker", None)
                if (
                    not isinstance(exc, SymbolNotFoundException)
                    and provider_breaker is not entry.circuit_breaker
                ):
                    await entry.circuit_breaker.record_failure(exc)
                logger.warning(
                    "Provider '%s' failed for '%s' (%s). Advancing to next provider.",
                    entry.name,
                    normalized,
                    exc,
                )
                errors.append(f"{entry.name}: {exc}")
                continue

            except Exception as unhandled:
                if getattr(entry.provider, "circuit_breaker", None) is not entry.circuit_breaker:
                    await entry.circuit_breaker.record_failure(unhandled)
                logger.error(
                    "Unexpected error from provider '%s' for '%s': %s",
                    entry.name,
                    normalized,
                    unhandled,
                )
                errors.append(f"{entry.name}: {unhandled}")
                continue

        # 4. Entire chain exhausted -> return truthful UNAVAILABLE response
        logger.error(
            "All providers in chain failed for symbol '%s'. Errors: %s",
            normalized,
            "; ".join(errors),
        )
        return MarketQuoteResponse(
            symbol=normalized,
            price=fallback_price if (fallback_price is not None and fallback_price > 0) else None,
            currency=self.default_currency,
            change=0.0,
            change_pct=0.0,
            source="none",
            as_of=None,
            fetched_at=now_iso,
            freshness=DataFreshness.UNAVAILABLE,
            is_stale=True,
            error=f"All market providers in chain failed or unavailable: {'; '.join(errors)}",
        )

    async def get_quote(
        self,
        symbol: str,
        fallback_price: Optional[float] = None,
    ) -> MarketQuote:
        """Port implementation: returns MarketQuote or raises typed exception."""
        response = await self.get_quote_with_freshness(symbol, fallback_price=fallback_price)

        if response.freshness == DataFreshness.UNAVAILABLE:
            if response.price is not None and response.price > 0:
                return MarketQuote(
                    symbol=response.symbol,
                    price=response.price,
                    change=0.0,
                    change_pct=0.0,
                    timestamp=datetime.now(timezone.utc),
                    is_stale=True,
                )
            raise ProviderUnavailableException(
                "market_chain",
                response.error or "All market providers in chain failed or unavailable",
            )

        return MarketQuote(
            symbol=response.symbol,
            price=response.price if response.price is not None else 0.0,
            change=response.change,
            change_pct=response.change_pct,
            timestamp=datetime.now(timezone.utc),
            is_stale=response.is_stale,
        )

    async def get_quotes(
        self,
        symbols: list[str],
        fallback_prices: Optional[dict[str, float]] = None,
    ) -> dict[str, MarketQuote]:
        """Batch fetch quotes across symbols satisfying MarketDataProvider port."""
        fallback_map = fallback_prices or {}
        results: dict[str, MarketQuote] = {}

        for sym in symbols:
            clean = sym.strip().upper()
            fb = fallback_map.get(clean)
            results[clean] = await self.get_quote(clean, fallback_price=fb)

        return results

    async def get_batch_quotes(
        self,
        symbols: list[str],
        fallback_prices: Optional[dict[str, float]] = None,
    ) -> BatchQuotesResponse:
        """Batch fetch quotes returning rich schema response."""
        fallback_map = fallback_prices or {}
        quotes: dict[str, MarketQuoteResponse] = {}

        for sym in symbols:
            clean = sym.strip().upper()
            fb = fallback_map.get(clean)
            quotes[clean] = await self.get_quote_with_freshness(clean, fallback_price=fb)

        resolved = sum(1 for q in quotes.values() if q.freshness != DataFreshness.UNAVAILABLE)
        status = DataFreshness.DELAYED if resolved > 0 else DataFreshness.UNAVAILABLE

        return BatchQuotesResponse(
            quotes=quotes,
            requested_count=len(symbols),
            resolved_count=resolved,
            data_status=status,
        )

    async def search_securities(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        """Search securities across the provider chain."""
        for entry in self._chain:
            if not await entry.circuit_breaker.allow_request():
                continue
            if hasattr(entry.provider, "search_securities"):
                try:
                    results = await entry.provider.search_securities(query, limit=limit)
                    if results:
                        return results
                except Exception as exc:
                    logger.warning("Provider '%s' search failed: %s", entry.name, exc)
                    continue
        return []

    def get_health(self) -> list[ProviderHealth]:
        """Return diagnostic health and circuit breaker states for all chain providers."""
        records: list[ProviderHealth] = []
        for entry in self._chain:
            state = entry.circuit_breaker.state
            records.append(
                ProviderHealth(
                    provider_name=entry.name,
                    circuit_state=state,
                    failure_count=entry.circuit_breaker.failure_count,
                    failure_threshold=entry.circuit_breaker.failure_threshold,
                    recovery_timeout_seconds=entry.circuit_breaker.recovery_timeout,
                    last_failure_time=(
                        entry.circuit_breaker.last_failure_time.isoformat()
                        if entry.circuit_breaker.last_failure_time
                        else None
                    ),
                    is_available=(state != CircuitState.OPEN),
                )
            )
        return records


# Global default instance
market_service = MarketService()
