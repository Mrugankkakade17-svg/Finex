"""
market_data_provider.py

WHAT THIS FILE IS FOR
----------------------
Today, market quotes come from a free `yfinance` adapter with a
15-minute cache. Later, this may be replaced with a licensed market
data provider.

This interface defines the contract for accessing market data while
keeping the application independent of any specific provider.

Nobody outside the concrete adapter should ever import `yfinance` (or any
future provider's SDK) directly -- always go through this interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

DataStatus = Literal["LIVE", "DELAYED", "END_OF_DAY", "CACHED", "UNAVAILABLE"]


@dataclass(frozen=True)
class Quote:
    """Canonical quote shape every part of FinEx agrees on."""

    symbol: str
    price: float
    currency: str
    change_value: float
    change_percent: float
    source: str
    as_of: str  # ISO-8601 timestamp of the price itself
    fetched_at: str  # ISO-8601 timestamp of when FinEx retrieved it
    status: DataStatus


@runtime_checkable
class MarketDataProvider(Protocol):
    """Abstract contract for fetching security prices/metadata."""

    async def get_quote(self, symbol: str) -> Quote:
        """
        Return the current (possibly cached, possibly delayed) quote for a
        symbol. Must always set `status` honestly -- never claim LIVE
        unless the provider contract actually supports that.
        """
        ...

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Batch version of get_quote, keyed by symbol."""
        ...

    async def search_securities(self, query: str, limit: int = 10) -> list[dict]:
        """Search the canonical symbol master (market.securities) by name
        or ticker fragment."""
        ...
