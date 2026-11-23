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
