from datetime import date, datetime, timezone

import pytest

from app.services.market_calendar import market_session, next_session_date


@pytest.mark.parametrize(
    ("exchange", "instant", "expected"),
    [
        ("NSE", datetime(2026, 11, 23, 4, 0, tzinfo=timezone.utc), True),
        ("BSE", datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc), False),
        ("NASDAQ", datetime(2026, 11, 23, 15, 0, tzinfo=timezone.utc), True),
        ("NYSE", datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc), False),
    ],
)
def test_market_session_handles_exchange_timezone_and_weekend(
    exchange: str, instant: datetime, expected: bool
) -> None:
    assert market_session(exchange, instant).is_open is expected


def test_market_session_rejects_naive_clock_and_unknown_exchange() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        market_session("NSE", datetime(2026, 11, 23, 10))
    with pytest.raises(ValueError, match="Unsupported exchange"):
        market_session("LSE", datetime(2026, 11, 23, tzinfo=timezone.utc))



@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 11, 23, 3, 45, tzinfo=timezone.utc), True),
        (datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc), False),
    ],
)
def test_market_session_opening_inclusive_and_closing_exclusive(
    instant: datetime, expected: bool
) -> None:
    assert market_session("NSE", instant).is_open is expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 11, 27), date(2026, 11, 27)),
        (date(2026, 11, 28), date(2026, 11, 30)),
        (date(2026, 11, 29), date(2026, 11, 30)),
    ],
)
def test_next_session_date_skips_weekends(day: date, expected: date) -> None:
    assert next_session_date("NASDAQ", day) == expected


def test_next_session_date_rejects_unsupported_exchange() -> None:
    with pytest.raises(ValueError, match="Unsupported exchange"):
        next_session_date("LSE", date(2026, 11, 27))
