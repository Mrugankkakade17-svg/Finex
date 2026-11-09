"""A deterministic, vendor-isolated market-data adapter for future portfolio work.

The adapter deliberately uses synthetic fixture data in this prototype. It never
imports a vendor SDK or makes a remote request, so local development and tests
remain free-tier and reproducible.
"""

from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import (
    ProviderTimeoutException,
    ProviderUnavailableException,
    RateLimitExceededException,
    SymbolNotFoundException,
)
from app.ports.market_data_port import MarketDataProvider, MarketQuote


class YFinanceMarketDataProvider(MarketDataProvider):
    """Map deterministic provider outcomes to the shared market-data port."""

    def __init__(self, timeout_seconds: float = 3.0, fail_mode: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.fail_mode = fail_mode

    async def get_quote(
        self,
        symbol: str,
        fallback_price: Optional[float] = None,
    ) -> MarketQuote:
        normalized = symbol.strip().upper()

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
            return MarketQuote(
                symbol=normalized,
                price=known_prices[normalized],
                change=1.50,
                change_pct=0.75,
                timestamp=now,
                is_stale=True,
            )

        if fallback_price is not None and fallback_price > 0:
            return MarketQuote(
                symbol=normalized,
                price=fallback_price,
                change=0.0,
                change_pct=0.0,
                timestamp=now,
                is_stale=True,
            )

        raise SymbolNotFoundException(symbol=normalized)

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
