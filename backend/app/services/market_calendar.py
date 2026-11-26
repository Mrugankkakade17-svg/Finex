"""Deterministic exchange calendar helpers for market API responses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MarketSession:
    exchange: str
    timezone: str
    is_open: bool
    session_date: date
    opens_at: datetime | None
    closes_at: datetime | None


# Regular weekday sessions only. Exchange holidays and exceptional closures
# are not represented by the current DDL and require an authoritative calendar.
_SESSIONS = {
    "NSE": ("Asia/Kolkata", time(9, 15), time(15, 30)),
    "BSE": ("Asia/Kolkata", time(9, 15), time(15, 30)),
    "NYSE": ("America/New_York", time(9, 30), time(16, 0)),
    "NASDAQ": ("America/New_York", time(9, 30), time(16, 0)),
}


def market_session(exchange: str, now: datetime | None = None) -> MarketSession:
    """Return whether an exchange is in its regular weekday session.

    ``now`` must be timezone-aware when supplied. This deterministic rule
    excludes weekends but does not model exchange holidays or early closes.
    """
    normalized = exchange.strip().upper()
    if normalized not in _SESSIONS:
        raise ValueError(f"Unsupported exchange: {exchange}")
    zone_name, opening, closing = _SESSIONS[normalized]
    zone = ZoneInfo(zone_name)
    instant = now or datetime.now(zone)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = instant.astimezone(zone)
    opens_at = datetime.combine(local.date(), opening, zone)
    closes_at = datetime.combine(local.date(), closing, zone)
    is_open = local.weekday() < 5 and opens_at <= local < closes_at
    return MarketSession(
        exchange=normalized,
        timezone=zone_name,
        is_open=is_open,
        session_date=local.date(),
        opens_at=opens_at if local.weekday() < 5 else None,
        closes_at=closes_at if local.weekday() < 5 else None,
    )


def next_session_date(exchange: str, on_or_after: date) -> date:
    """Return the next weekday on or after the supplied date."""
    if exchange.strip().upper() not in _SESSIONS:
        raise ValueError(f"Unsupported exchange: {exchange}")
    result = on_or_after
    while result.weekday() >= 5:
        result += timedelta(days=1)
    return result
