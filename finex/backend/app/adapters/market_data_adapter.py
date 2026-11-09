import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.ports.market_data_port import MarketDataProvider, MarketQuote

logger = logging.getLogger(__name__)

# Default deterministic mock fixtures for Sprint 3 demo/testing
DEFAULT_MOCK_QUOTES: Dict[str, Dict[str, float]] = {
    "AAPL": {"price": 188.50, "change": 1.25, "change_pct": 0.67},
    "MSFT": {"price": 415.20, "change": -0.80, "change_pct": -0.19},
    "GOOGL": {"price": 175.40, "change": 2.10, "change_pct": 1.21},
    "AMZN": {"price": 182.30, "change": 0.95, "change_pct": 0.52},
    "NVDA": {"price": 125.60, "change": 4.50, "change_pct": 3.72},
    "TSLA": {"price": 210.80, "change": -3.20, "change_pct": -1.50},
    "SPY": {"price": 545.00, "change": 1.50, "change_pct": 0.28},
    "QQQ": {"price": 475.20, "change": 3.00, "change_pct": 0.63},
    "BND": {"price": 69.10, "change": -0.05, "change_pct": -0.07},
    "AGG": {"price": 95.80, "change": 0.10, "change_pct": 0.10},
    "CASH": {"price": 1.00, "change": 0.00, "change_pct": 0.00},
    "BTC": {"price": 64500.00, "change": 1200.00, "change_pct": 1.90},
    "ETH": {"price": 3450.00, "change": -45.00, "change_pct": -1.29},
    "GLD": {"price": 215.30, "change": 1.10, "change_pct": 0.51},
}


class MockMarketDataProvider(MarketDataProvider):
    """
    Mock adapter supplying deterministic quotes for portfolio valuation.
    Can be configured with custom fixture prices for tests.
    """

    def __init__(self, custom_quotes: Optional[Dict[str, Dict[str, float]]] = None):
        self._quotes = DEFAULT_MOCK_QUOTES.copy()
        if custom_quotes:
            self._quotes.update(custom_quotes)

    async def get_quote(self, symbol: str, fallback_price: Optional[float] = None) -> MarketQuote:
        clean_sym = symbol.strip().upper()
        now = datetime.now()

        if clean_sym in self._quotes:
            q = self._quotes[clean_sym]
            return MarketQuote(
                symbol=clean_sym,
                price=q["price"],
                change=q.get("change", 0.0),
                change_pct=q.get("change_pct", 0.0),
                timestamp=now,
                is_stale=False,
            )

        # Fallback handling: Never convert missing prices to zero
        if fallback_price is not None and fallback_price > 0:
            logger.warning(
                "Quote for %s not found in market feed. Falling back to purchase price: %s",
                clean_sym,
                fallback_price,
            )
            return MarketQuote(
                symbol=clean_sym,
                price=fallback_price,
                change=0.0,
                change_pct=0.0,
                timestamp=now,
                is_stale=True,
            )

        # Default fallback for unknown symbols without cost basis
        logger.warning(
            "Quote for %s not found and no fallback provided. Defaulting to 100.0 (stale)",
            clean_sym,
        )
        return MarketQuote(
            symbol=clean_sym,
            price=100.0,
            change=0.0,
            change_pct=0.0,
            timestamp=now,
            is_stale=True,
        )

    async def get_quotes(
        self,
        symbols: List[str],
        fallback_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, MarketQuote]:
        fallback_prices = fallback_prices or {}
        results: Dict[str, MarketQuote] = {}

        for sym in symbols:
            clean_sym = sym.strip().upper()
            fb = fallback_prices.get(clean_sym)
            results[clean_sym] = await self.get_quote(clean_sym, fallback_price=fb)

        return results
