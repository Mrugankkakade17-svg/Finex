"""A deterministic, vendor-isolated market-data adapter for future portfolio work.

The adapter deliberately uses synthetic fixture data in this prototype. It never
imports a vendor SDK or makes a remote request, so local development and tests
remain free-tier and reproducible.

Extends yfinance adapter with rate limiter, circuit breaker, and fixture provider.
Enforces that under NO circumstances can yfinance emit LIVE data freshness.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    ProviderTimeoutException,
    ProviderUnavailableException,
    RateLimitExceededException,
    SymbolNotFoundException,
)
from app.ports.market_data_port import MarketDataProvider, MarketQuote
from app.schemas.market import CircuitState

logger = logging.getLogger(__name__)


class CircuitBreakerOpenException(ProviderUnavailableException):
    """Raised when request is rejected because provider's circuit breaker is OPEN."""

    def __init__(self, provider: str, reset_in_seconds: float):
        super().__init__(
            provider=provider,
            reason=f"Circuit breaker is OPEN. Retry in {reset_in_seconds:.1f}s.",
        )
        self.reset_in_seconds = reset_in_seconds


class CircuitBreaker:
    """Three-state circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        success_threshold: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        now = datetime.now(timezone.utc)
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if (now - self._last_failure_time).total_seconds() >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def last_failure_time(self) -> Optional[datetime]:
        return self._last_failure_time

    async def allow_request(self) -> bool:
        async with self._lock:
            state = self.state
            if state == CircuitState.OPEN:
                return False
            return True

    def get_reset_in_seconds(self) -> float:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            now = datetime.now(timezone.utc)
            elapsed = (now - self._last_failure_time).total_seconds()
            return max(0.0, self.recovery_timeout - elapsed)
        return 0.0

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._last_failure_time = None
                    logger.info("Circuit breaker for %s reset to CLOSED", self.name)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def record_failure(self, exc: Optional[Exception] = None) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)
            if (
                self._state == CircuitState.HALF_OPEN
                or self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker for %s tripped to OPEN (failures=%d, exc=%s)",
                    self.name,
                    self._failure_count,
                    exc,
                )

    async def reset(self) -> None:
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None


class RateLimiter:
    """Sliding-window rate limiter for provider protection."""

    def __init__(self, provider_name: str, max_requests: int = 30, window_seconds: float = 60.0):
        self.provider_name = provider_name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[datetime] = []
        self._lock = asyncio.Lock()

    @property
    def remaining_requests(self) -> int:
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - self.window_seconds
        active = [ts for ts in self._timestamps if ts.timestamp() > cutoff]
        return max(0, self.max_requests - len(active))

    async def acquire(self) -> bool:
        async with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now.timestamp() - self.window_seconds
            self._timestamps = [ts for ts in self._timestamps if ts.timestamp() > cutoff]

            if len(self._timestamps) >= self.max_requests:
                oldest = self._timestamps[0].timestamp()
                retry_after = max(1, int(oldest + self.window_seconds - now.timestamp()))
                raise RateLimitExceededException(
                    provider=self.provider_name,
                    retry_after_seconds=retry_after,
                )

            self._timestamps.append(now)
            return True

    async def reset(self) -> None:
        async with self._lock:
            self._timestamps.clear()


class YFinanceMarketDataProvider(MarketDataProvider):
    """Map deterministic provider outcomes to the shared market-data port.

    Contract invariant: Under no circumstances can yfinance emit LIVE freshness.
    """

    def __init__(
        self,
        timeout_seconds: float = 3.0,
        fail_mode: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.fail_mode = fail_mode
        self.circuit_breaker = circuit_breaker
        self.provider_name = "yfinance"

    async def get_quote(
        self,
        symbol: str,
        fallback_price: Optional[float] = None,
    ) -> MarketQuote:
        normalized = symbol.strip().upper()

        if self.circuit_breaker and not await self.circuit_breaker.allow_request():
            raise CircuitBreakerOpenException(
                self.provider_name,
                reset_in_seconds=self.circuit_breaker.get_reset_in_seconds(),
            )

        try:
            if self.fail_mode == "timeout":
                raise ProviderTimeoutException("yfinance", self.timeout_seconds)
            if self.fail_mode == "unavailable":
                raise ProviderUnavailableException(
                    "yfinance",
                    "upstream Yahoo Finance API is unreachable",
                )
            if self.fail_mode == "rate_limit":
                raise RateLimitExceededException("yfinance", retry_after_seconds=30)

            known_prices: dict[str, float] = {
                "AAPL": 227.16,
                "MSFT": 505.12,
                "GOOGL": 178.40,
                "NVDA": 128.50,
                "SPY": 560.25,
            }
            now = datetime.now(timezone.utc)

            if normalized in known_prices:
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success()
                return MarketQuote(
                    symbol=normalized,
                    price=known_prices[normalized],
                    change=1.50,
                    change_pct=0.75,
                    timestamp=now,
                    is_stale=True,
                )

            if fallback_price is not None and fallback_price > 0:
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success()
                return MarketQuote(
                    symbol=normalized,
                    price=fallback_price,
                    change=0.0,
                    change_pct=0.0,
                    timestamp=now,
                    is_stale=True,
                )

            raise SymbolNotFoundException(symbol=normalized)

        except SymbolNotFoundException:
            raise
        except Exception as exc:
            if self.circuit_breaker:
                await self.circuit_breaker.record_failure(exc)
            raise

    async def get_quotes(
        self,
        symbols: list[str],
        fallback_prices: dict[str, float] | None = None,
    ) -> dict[str, MarketQuote]:
        fallback_map = fallback_prices or {}
        results: dict[str, MarketQuote] = {}

        for symbol in symbols:
            normalized = symbol.strip().upper()
            results[normalized] = await self.get_quote(
                normalized,
                fallback_price=fallback_map.get(normalized),
            )

        return results

    async def search_securities(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        """Return deterministic catalogue matches without a vendor-network dependency."""
        query_upper = query.strip().upper()
        sample_catalog = [
            {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
            {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ"},
            {"symbol": "NVDA", "name": "NVIDIA Corp.", "exchange": "NASDAQ"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "exchange": "NYSE"},
        ]
        return [
            security
            for security in sample_catalog
            if query_upper in security["symbol"] or query_upper in security["name"].upper()
        ][:limit]


DEFAULT_FIXTURE_QUOTES: dict[str, dict[str, float]] = {
    "AAPL": {"price": 227.16, "change": 1.50, "change_pct": 0.75},
    "MSFT": {"price": 505.12, "change": 2.30, "change_pct": 0.46},
    "GOOGL": {"price": 178.40, "change": -0.80, "change_pct": -0.45},
    "NVDA": {"price": 128.50, "change": 3.20, "change_pct": 2.55},
    "SPY": {"price": 560.25, "change": 1.10, "change_pct": 0.20},
    "TSLA": {"price": 242.84, "change": -4.20, "change_pct": -1.70},
    "AMZN": {"price": 186.40, "change": 0.90, "change_pct": 0.49},
}


class FixtureMarketDataProvider(MarketDataProvider):
    """Reliable secondary/fallback fixture provider in the provider chain."""

    def __init__(
        self,
        custom_quotes: Optional[dict[str, dict[str, float]]] = None,
        timeout_seconds: float = 2.0,
        fail_mode: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self._quotes = DEFAULT_FIXTURE_QUOTES.copy()
        if custom_quotes:
            self._quotes.update(custom_quotes)
        self.timeout_seconds = timeout_seconds
        self.fail_mode = fail_mode
        self.circuit_breaker = circuit_breaker
        self.provider_name = "fixture"

    async def get_quote(
        self,
        symbol: str,
        fallback_price: Optional[float] = None,
    ) -> MarketQuote:
        normalized = symbol.strip().upper()

        if self.circuit_breaker and not await self.circuit_breaker.allow_request():
            raise CircuitBreakerOpenException(
                self.provider_name,
                reset_in_seconds=self.circuit_breaker.get_reset_in_seconds(),
            )

        try:
            if self.fail_mode == "timeout":
                raise ProviderTimeoutException("fixture", self.timeout_seconds)
            if self.fail_mode == "unavailable":
                raise ProviderUnavailableException("fixture", "fixture provider is unavailable")
            if self.fail_mode == "rate_limit":
                raise RateLimitExceededException("fixture", retry_after_seconds=30)

            now = datetime.now(timezone.utc)

            if normalized in self._quotes:
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success()
                q = self._quotes[normalized]
                return MarketQuote(
                    symbol=normalized,
                    price=q["price"],
                    change=q.get("change", 0.0),
                    change_pct=q.get("change_pct", 0.0),
                    timestamp=now,
                    is_stale=False,
                )

            if fallback_price is not None and fallback_price > 0:
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success()
                return MarketQuote(
                    symbol=normalized,
                    price=fallback_price,
                    change=0.0,
                    change_pct=0.0,
                    timestamp=now,
                    is_stale=True,
                )

            raise SymbolNotFoundException(symbol=normalized)

        except SymbolNotFoundException:
            raise
        except Exception as exc:
            if self.circuit_breaker:
                await self.circuit_breaker.record_failure(exc)
            raise

    async def get_quotes(
        self,
        symbols: list[str],
        fallback_prices: dict[str, float] | None = None,
    ) -> dict[str, MarketQuote]:
        fallback_map = fallback_prices or {}
        results: dict[str, MarketQuote] = {}

        for symbol in symbols:
            normalized = symbol.strip().upper()
            results[normalized] = await self.get_quote(
                normalized,
                fallback_price=fallback_map.get(normalized),
            )

        return results

    async def search_securities(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        query_upper = query.strip().upper()
        catalog = [
            {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"},
            {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ"},
            {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ"},
            {"symbol": "NVDA", "name": "NVIDIA Corp.", "exchange": "NASDAQ"},
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "exchange": "NYSE"},
            {"symbol": "TSLA", "name": "Tesla Inc.", "exchange": "NASDAQ"},
            {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ"},
        ]
        return [
            sec
            for sec in catalog
            if query_upper in sec["symbol"] or query_upper in sec["name"].upper()
        ][:limit]


class SecondaryMarketDataProvider(FixtureMarketDataProvider):
    """Named second-provider adapter for the resilient market-data chain."""

    provider_name = "secondary"
