import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


def test_instrument_search_returns_exchange_currency_and_matches_tickers() -> None:
    client = TestClient(create_app())
    for query, expected_exchange, expected_currency in (
        ("RELIANCE", "NSE", "INR"),
        ("TCS", "NSE", "INR"),
        ("AAPL", "NASDAQ", "USD"),
    ):
        response = client.get(
            "/api/v1/market/instruments", params={"query": query, "exchange": expected_exchange}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["items"]
        item = body["data"]["items"][0]
        assert item["exchange"] == expected_exchange
        assert item["currency"] == expected_currency


def test_market_calendar_reports_status_and_ohlcv_uses_database(monkeypatch) -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/market/calendar/NSE")
    assert response.status_code == 200
    assert response.json()["data"]["market_status"] in {"OPEN", "MARKET_CLOSED"}

    from app.routers import market

    monkeypatch.setattr(
        market,
        "execute_query",
        lambda *_args, **_kwargs: [
            {
                "timestamp": "2026-11-02",
                "open": 100,
                "high": 110,
                "low": 90,
                "close": 105,
                "volume": 2500,
            }
        ],
    )
    history = client.get(
        "/api/v1/market/instruments/AAPL/ohlcv",
        params={"exchange": "NASDAQ", "start": "2026-11-01", "end": "2026-11-10"},
    )
    assert history.status_code == 200
    assert history.json()["meta"]["dataStatus"] == "END_OF_DAY"
    assert history.json()["data"]["items"][0]["close"] == "105"


def test_market_endpoints_do_not_change_existing_local_market_route() -> None:
    paths = create_app().openapi()["paths"]
    assert "/api/v1/local-market/instruments" in paths
    assert "/api/v1/market/instruments" in paths


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-11-10", "2026-11-09"),
        ("2016-11-01", "2026-11-02"),
    ],
)
def test_ohlcv_rejects_invalid_date_ranges(start: str, end: str) -> None:
    client = TestClient(create_app())
    response = client.get(
        "/api/v1/market/instruments/AAPL/ohlcv",
        params={"exchange": "NASDAQ", "start": start, "end": end},
    )
    assert response.status_code == 422


def test_ohlcv_accepts_instrument_outside_bootstrap_catalog_when_database_returns_history(
    monkeypatch,
) -> None:
    from app.routers import market

    queries: list[str] = []

    def query(sql, _params):
        queries.append(sql)
        return [
            {
                "timestamp": "2026-11-02",
                "open": 100,
                "high": 110,
                "low": 90,
                "close": 105,
                "volume": 2500,
            }
        ]

    monkeypatch.setattr(market, "execute_query", query)
    response = TestClient(create_app()).get(
        "/api/v1/market/instruments/NEWCO/ohlcv",
        params={
            "exchange": "NASDAQ",
            "start": "2026-11-01",
            "end": "2026-11-10",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["symbol"] == "NEWCO"
    assert any("JOIN finex_dev.market.instruments" in sql for sql in queries)


@pytest.mark.parametrize(
    "row",
    [
        {"open": 0, "high": 110, "low": 90, "close": 105, "volume": 2500},
        {"open": 100, "high": 99, "low": 90, "close": 105, "volume": 2500},
        {"open": 100, "high": 110, "low": 106, "close": 105, "volume": 2500},
        {"open": 100, "high": 110, "low": 90, "close": 105, "volume": -1},
    ],
)
def test_ohlcv_rejects_invalid_candle_values(monkeypatch, row) -> None:
    from app.routers import market

    monkeypatch.setattr(
        market,
        "execute_query",
        lambda *_args, **_kwargs: [{"timestamp": "2026-11-02", **row}],
    )
    response = TestClient(create_app()).get(
        "/api/v1/market/instruments/AAPL/ohlcv",
        params={
            "exchange": "NASDAQ",
            "start": "2026-11-01",
            "end": "2026-11-10",
        },
    )
    assert response.status_code == 503


def test_market_api_rejects_unsupported_exchanges() -> None:
    client = TestClient(create_app())
    assert client.get("/api/v1/market/instruments", params={"exchange": "LSE"}).status_code == 422
    assert (
        client.get(
            "/api/v1/market/instruments/AAPL/ohlcv",
            params={"exchange": "LSE", "start": "2026-11-01", "end": "2026-11-10"},
        ).status_code
        == 422
    )
    assert client.get("/api/v1/market/calendar/LSE").status_code == 404


def test_instrument_search_logs_safe_warning_when_warehouse_falls_back(monkeypatch, caplog) -> None:
    from app.routers import market

    monkeypatch.setattr(
        market,
        "execute_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("secret-token-must-not-be-logged")
        ),
    )
    with caplog.at_level(logging.WARNING):
        response = TestClient(create_app()).get("/api/v1/market/instruments")

    assert response.status_code == 200
    assert "Market instrument query failed; using bundled fallback catalog" in caplog.text
    assert "secret-token-must-not-be-logged" not in caplog.text

