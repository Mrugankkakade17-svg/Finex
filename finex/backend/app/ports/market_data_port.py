from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MarketQuote:
    """Represents a market quote snapshot for an asset."""

    symbol: str
    price: float
    change: float
    change_pct: float
    timestamp: datetime
    is_stale: bool = False


class MarketDataProvider(ABC):
    """Abstract port interface for fetching live/delayed market data quotes."""

    @abstractmethod
    async def get_quote(self, symbol: str, fallback_price: Optional[float] = None) -> MarketQuote:
        """Fetch current quote for a given symbol."""
        pass

    @abstractmethod
    async def get_quotes(
        self,
        symbols: List[str],
        fallback_prices: Optional[Dict[str, float]] = None,
    ) -> Dict[str, MarketQuote]:
        """Batch fetch quotes for multiple instruments."""
        pass
