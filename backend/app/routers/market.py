"""Exchange instrument search, OHLCV history, and market-session endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.config.database import execute_query
from app.core.responses import APIResponse
from app.schemas.envelope import DataStatus
from app.services.market_calendar import market_session

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class Instrument(BaseModel):
    symbol: str
    name: str
    exchange: str
    asset_class: str | None = None
    currency: str


class Candle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)


# A deterministic bootstrap catalogue. Search can still be used when the market
# warehouse is not configured; seed_instruments.py persists this same master.
INSTRUMENTS = (
    Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        exchange="NSE",
        asset_class="EQUITY",
        currency="INR",
    ),
    Instrument(
        symbol="RELIANCE",
        name="Reliance Industries Limited",
        exchange="BSE",
        asset_class="EQUITY",
        currency="INR",
    ),
    Instrument(
        symbol="TCS",
        name="Tata Consultancy Services Limited",
        exchange="NSE",
        asset_class="EQUITY",
        currency="INR",
    ),
    Instrument(
        symbol="TCS",
        name="Tata Consultancy Services Limited",
        exchange="BSE",
        asset_class="EQUITY",
        currency="INR",
    ),
    Instrument(
        symbol="AAPL", name="Apple Inc.", exchange="NASDAQ", asset_class="EQUITY", currency="USD"
    ),
    Instrument(
        symbol="MSFT",
        name="Microsoft Corporation",
        exchange="NASDAQ",
        asset_class="EQUITY",
        currency="USD",
    ),
    Instrument(
        symbol="GOOGL",
        name="Alphabet Inc.",
        exchange="NASDAQ",
        asset_class="EQUITY",
        currency="USD",
    ),
    Instrument(
        symbol="NVDA",
        name="NVIDIA Corporation",
        exchange="NASDAQ",
        asset_class="EQUITY",
        currency="USD",
    ),
    Instrument(
        symbol="SPY",
        name="SPDR S&P 500 ETF Trust",
        exchange="NYSE",
        asset_class="ETF",
        currency="USD",
    ),
)
_CURRENCY_BY_EXCHANGE = {"NSE": "INR", "BSE": "INR", "NYSE": "USD", "NASDAQ": "USD"}


def _respond(
    request: Request,
    data: object,
    message: str,
    status: DataStatus = "CACHED",
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    return APIResponse.success(
        message=message,
        data=data,
        correlation_id=correlation,
        data_status=status,
    )


@router.get("/instruments")
async def search_instruments(
    request: Request,
    query: str = Query(default="", max_length=80),
    exchange: str | None = Query(default=None, pattern="^(NSE|BSE|NYSE|NASDAQ)$"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Search the bundled cross-market master by symbol or company name."""
    needle = query.strip().casefold()
    found: list[dict[str, object]]
    try:
        sql = """SELECT symbol, name, exchange, instrument_type AS asset_class
                 FROM finex_dev.market.instruments
                 WHERE coalesce(is_active, true) = true
                   AND (:exchange IS NULL OR upper(exchange) = :exchange)
                   AND (:query = '' OR lower(symbol) LIKE :pattern OR lower(name) LIKE :pattern)
                 ORDER BY upper(symbol), upper(exchange) LIMIT :limit"""
        records = execute_query(
            sql,
            {"exchange": exchange, "query": needle, "pattern": f"%{needle}%", "limit": limit},
        )
        found = [
            {
                "symbol": str(row["symbol"]).upper(),
                "name": str(row["name"]),
                "exchange": str(row["exchange"]).upper(),
                "asset_class": row.get("asset_class"),
                "currency": _CURRENCY_BY_EXCHANGE[str(row["exchange"]).upper()],
            }
            for row in records
            if str(row.get("exchange", "")).upper() in _CURRENCY_BY_EXCHANGE
        ]
    except Exception:
        found = [
            row.model_dump()
            for row in INSTRUMENTS
            if (not needle or needle in row.symbol.casefold() or needle in row.name.casefold())
            and (exchange is None or row.exchange == exchange)
        ][:limit]
    return _respond(request, {"items": found, "count": len(found)}, "Instrument search completed")


@router.get("/instruments/{symbol}/ohlcv")
async def historical_ohlcv(
    request: Request,
    symbol: str,
    exchange: str = Query(..., pattern="^(NSE|BSE|NYSE|NASDAQ)$"),
    start: date = Query(...),
    end: date = Query(...),
    interval: Literal["1d"] = Query(default="1d"),
):
    """Return daily candles from the canonical market.prices warehouse table."""
    if end < start or (end - start).days > 3650:
        raise HTTPException(
            status_code=422, detail="Date range must be ordered and at most ten years"
        )
    normalized = symbol.strip().upper()
    if not any(item.symbol == normalized and item.exchange == exchange for item in INSTRUMENTS):
        raise HTTPException(status_code=404, detail="Instrument not found")
    try:
        rows = execute_query(
            """SELECT p.price_date AS timestamp, p.open_price AS open,
                      p.high_price AS high, p.low_price AS low,
                      p.close_price AS close, p.volume AS volume
               FROM finex_dev.market.prices p
               JOIN finex_dev.market.instruments i ON i.instrument_id = p.instrument_id
               WHERE upper(i.symbol) = :symbol AND upper(i.exchange) = :exchange
                 AND p.price_date >= :start_date AND p.price_date <= :end_date
               ORDER BY p.price_date ASC""",
            {
                "symbol": normalized,
                "exchange": exchange,
                "start_date": start,
                "end_date": end,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Market history is unavailable") from exc
    candles: list[dict[str, object]] = []
    try:
        for row in rows:
            candle = Candle(
                timestamp=row["timestamp"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            if candle.high < max(candle.open, candle.close, candle.low):
                raise ValueError("Invalid OHLC high")
            if candle.low > min(candle.open, candle.close, candle.high):
                raise ValueError("Invalid OHLC low")
            candles.append(candle.model_dump(mode="json"))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Market history data is invalid") from exc
    if not candles:
        raise HTTPException(
            status_code=404, detail="No market history found for the requested range"
        )
    return APIResponse.success(
        message="Historical OHLCV loaded",
        data={"symbol": normalized, "exchange": exchange, "interval": interval, "items": candles},
        correlation_id=getattr(request.state, "correlation_id", "unknown"),
        data_status="END_OF_DAY",
    )


@router.get("/calendar/{exchange}")
async def calendar(exchange: str, request: Request):
    try:
        session = market_session(exchange)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Exchange not found") from exc
    return _respond(
        request,
        {
            "exchange": session.exchange,
            "timezone": session.timezone,
            "market_status": "OPEN" if session.is_open else "MARKET_CLOSED",
            "session_date": session.session_date.isoformat(),
            "opens_at": session.opens_at.isoformat() if session.opens_at else None,
            "closes_at": session.closes_at.isoformat() if session.closes_at else None,
        },
        "Market calendar status",
    )
