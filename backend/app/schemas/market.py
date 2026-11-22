"""Market data and freshness schemas per FinEx architectural contracts."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DataFreshness(str, Enum):
    """Truthful data freshness states for market data feeds.

    - LIVE: Real-time tick or streaming quote from an authorized exchange feed.
            NOTE: Under the locked contract, yfinance is strictly prohibited from emitting LIVE.
    - DELAYED: 15-20 min delayed exchange feed.
    - END_OF_DAY: Daily closing price from previous trading session.
    - CACHED: Served from in-memory or persisted local cache within TTL.
    - UNAVAILABLE: Upstream provider failed, timed out, or symbol is unquoted.
    """

    LIVE = "LIVE"
    DELAYED = "DELAYED"
    END_OF_DAY = "END_OF_DAY"
    CACHED = "CACHED"
    UNAVAILABLE = "UNAVAILABLE"


class CircuitState(str, Enum):
    """States of a provider circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class MarketQuoteResponse(BaseModel):
    """Standardized market quote response model."""

    symbol: str = Field(..., description="Normalized ticker symbol (e.g. AAPL)")
    price: Optional[float] = Field(None, description="Current quote price, or None if unavailable")
    currency: str = Field("USD", description="Currency ISO code")
    change: float = Field(0.0, description="Absolute price change")
    change_pct: float = Field(0.0, description="Percentage price change")
    source: str = Field(..., description="Provider source identifier (e.g. yfinance, fixture)")
    as_of: Optional[str] = Field(None, description="ISO-8601 timestamp of market price")
    fetched_at: str = Field(..., description="ISO-8601 timestamp when quote was retrieved")
    freshness: DataFreshness = Field(..., description="Truthful freshness indicator")
    is_stale: bool = Field(False, description="Flag indicating if quote is stale")
    error: Optional[str] = Field(None, description="Error reason if quote is UNAVAILABLE")

    @field_validator("freshness")
    @classmethod
    def validate_no_live_yfinance(cls, v: DataFreshness, info) -> DataFreshness:
        source = str(info.data.get("source", "")).lower()
        if "yfinance" in source and v == DataFreshness.LIVE:
            raise ValueError(
                "Contract violation: yfinance provider is never permitted to emit LIVE data."
            )
        return v


class BatchQuotesResponse(BaseModel):
    """Batch quote response keyed by normalized symbol."""

    quotes: dict[str, MarketQuoteResponse] = Field(default_factory=dict)
    requested_count: int = Field(0)
    resolved_count: int = Field(0)
    data_status: DataFreshness = Field(DataFreshness.DELAYED)


class ProviderHealth(BaseModel):
    """Health and circuit breaker status for a market data provider."""

    provider_name: str
    circuit_state: CircuitState
    failure_count: int
    failure_threshold: int
    recovery_timeout_seconds: float
    last_failure_time: Optional[str] = None
    is_available: bool


class SecuritySearchResult(BaseModel):
    """Catalogue security lookup result."""

    symbol: str
    name: str
    exchange: str
    asset_class: Optional[str] = None
