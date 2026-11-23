from datetime import datetime, timezone

import pytest

from app.services.market_calendar import market_session


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
