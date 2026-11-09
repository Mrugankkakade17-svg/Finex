"""S3 bounded synthetic cache, denial ordering and failure/privacy assertions.

Only in-process requests and owned temporary SQLite files are used. Fake clocks
prove domain boundaries, not real elapsed expiry or native-process acceptance.
"""

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import AppEnv
from app.domain.local_portfolio import LocalPortfolioQuoteSnapshot
from tests.support.local_s3_client import (
    CONSENT,
    FIXTURE_TIME,
    LISTS,
    MARKET,
    ONBOARDING,
    OPERATIONS,
    Clock,
    ControlledCatalogue,
    ControlledQuotes,
    application,
    completed,
    created,
    data,
    error,
    utc,
)


@pytest.mark.parametrize(
    "environment,enabled",
    [(AppEnv.LOCAL, False), (AppEnv.DEV, True), (AppEnv.UAT, True), (AppEnv.PROD, True)],
)
def test_all_s3_boundaries_deny_before_malformed_body_provider_or_storage(
    tmp_path: Path, environment: AppEnv, enabled: bool
) -> None:
    path = tmp_path / "never-opened.sqlite3"
    catalogue, quotes = ControlledCatalogue(), ControlledQuotes()
    application_under_test = application(
        path, enabled=enabled, environment=environment, catalogue=catalogue, quotes=quotes
    )
    client = TestClient(application_under_test)
    for method, endpoint, _ in OPERATIONS:
        response = client.request(
            method, endpoint, content="{malformed", headers={"Content-Type": "application/json"}
        )
        error(response, 403, "LOCAL_APPLICATION_ONLY")
    assert not path.exists()
    assert catalogue.calls == 0 and quotes.calls == []


def test_forged_forwarded_headers_cannot_authorize_nonloopback_s3_peer(tmp_path: Path) -> None:
    path = tmp_path / "nonloopback.sqlite3"
    client = TestClient(application(path), client=("192.0.2.25", 12345))
    response = client.post(
        LISTS,
        content="{malformed",
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-For": "127.0.0.1",
            "Host": "127.0.0.1:8000",
            "Origin": "http://127.0.0.1:3000",
        },
    )
    error(response, 403, "LOCAL_APPLICATION_ONLY")
    assert not path.exists()


@pytest.mark.parametrize("failed,invalid", [(True, False), (False, True)])
def test_catalogue_fault_is_not_an_empty_or_default_fallback(
    tmp_path: Path, failed: bool, invalid: bool
) -> None:
    catalogue = ControlledCatalogue()
    catalogue.failed, catalogue.invalid = failed, invalid
    client = TestClient(application(tmp_path / "catalogue-fault.sqlite3", catalogue=catalogue))
    headers = completed(client)
    response = client.get(MARKET + "/instruments", headers=headers)
    error(response, 503, "LOCAL_CATALOG_UNAVAILABLE")
    reflected = "Opaque synthetic catalogue failure" in response.text
    assert not reflected


def test_quote_cache_hit_and_exact_sixty_second_refresh_preserve_fixture_time(
    tmp_path: Path,
) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "cache.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    first = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    assert quotes.calls == [("SYN:AAPL",)]
    clock.now += timedelta(seconds=59, microseconds=999999)
    assert data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)) == first
    assert quotes.calls == [("SYN:AAPL",)]
    clock.now += timedelta(microseconds=1)
    refreshed = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    assert quotes.calls == [("SYN:AAPL",), ("SYN:AAPL",)]
    assert refreshed["unit_price"] == first["unit_price"]
    assert refreshed["quote_as_of"] == refreshed["fixture_as_of"] == FIXTURE_TIME
    assert utc(refreshed["fetched_at"]) == clock.now
    assert utc(refreshed["cache_expires_at"]) == clock.now + timedelta(seconds=60)


@pytest.mark.parametrize("invalid", [False, True])
def test_failed_or_invalid_refresh_stale_until_exact_three_hundred_then_null(
    tmp_path: Path, invalid: bool
) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "stale.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    first = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    quotes.failed, quotes.invalid = not invalid, invalid
    clock.now += timedelta(seconds=60)
    stale_response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    stale = data(stale_response)
    assert stale["status"] == "STALE" and stale["reason"] == "SYNTHETIC_PROVIDER_STALE"
    assert stale["unit_price"] == first["unit_price"] and stale["quote_as_of"] == FIXTURE_TIME
    assert (
        stale["fetched_at"] == first["fetched_at"]
        and stale["cache_expires_at"] == first["cache_expires_at"]
    )
    assert stale_response.json()["meta"]["dataStatus"] == "CACHED"
    assert stale_response.json()["meta"]["dataAsOf"] == FIXTURE_TIME
    clock.now += timedelta(seconds=239, microseconds=999999)
    assert data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))["status"] == "STALE"
    clock.now += timedelta(microseconds=1)
    unavailable_response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    unavailable = data(unavailable_response)
    assert (
        unavailable["status"] == "UNAVAILABLE"
        and unavailable["reason"] == "SYNTHETIC_PROVIDER_UNAVAILABLE"
    )
    assert unavailable["unit_price"] is None and unavailable["quote_as_of"] is None
    assert (
        unavailable["fetched_at"] == first["fetched_at"]
        and unavailable["cache_expires_at"] == first["cache_expires_at"]
    )
    assert unavailable["fixture_as_of"] == FIXTURE_TIME
    assert unavailable_response.json()["meta"]["dataStatus"] == "UNAVAILABLE"
    assert unavailable_response.json()["meta"]["dataAsOf"] is None
    quotes.failed = quotes.invalid = False
    clock.now += timedelta(seconds=1)
    recovered = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    assert recovered["status"] == "CACHED" and recovered["unit_price"] == "200.0000"
    assert recovered["fixture_as_of"] == recovered["quote_as_of"] == FIXTURE_TIME
    assert utc(recovered["fetched_at"]) == clock.now


def test_failed_first_quote_is_safe_unavailable_without_invented_retrieval(tmp_path: Path) -> None:
    quotes = ControlledQuotes()
    quotes.failed = True
    client = TestClient(application(tmp_path / "no-cache.sqlite3", quotes=quotes))
    headers = completed(client)
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    result = data(response)
    assert (
        result["status"] == "UNAVAILABLE" and result["reason"] == "SYNTHETIC_PROVIDER_UNAVAILABLE"
    )
    assert (
        result["fetched_at"]
        is result["cache_expires_at"]
        is result["unit_price"]
        is result["quote_as_of"]
        is None
    )
    assert result["source_type"] == "SYNTHETIC" and result["source"] == "finex.synthetic.portfolio"
    assert result["fixture_as_of"] == FIXTURE_TIME
    assert response.json()["meta"]["dataStatus"] == "UNAVAILABLE"


@pytest.mark.parametrize(
    "price", ["0.0000", "-1.0000", "NaN", "Infinity", "1000000.0001", "1.00", "01.0000", 2.0, True]
)
def test_invalid_provider_price_is_never_supplied_as_a_quote(tmp_path: Path, price: object) -> None:
    class InvalidPriceQuotes(ControlledQuotes):
        def snapshot(self, identifiers: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
            snapshot = super().snapshot(identifiers)
            return replace(snapshot, quotes=(replace(snapshot.quotes[0], unit_price=price),))

    client = TestClient(
        application(tmp_path / "invalid-price.sqlite3", quotes=InvalidPriceQuotes())
    )
    headers = completed(client)
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    result = data(response)
    assert result["status"] == "UNAVAILABLE" and result["unit_price"] is None
    assert result["reason"] == "SYNTHETIC_PROVIDER_UNAVAILABLE" and result["quote_as_of"] is None
    assert result["fetched_at"] is None and result["cache_expires_at"] is None


def test_backwards_clock_denies_without_rejuvenating_or_altering_cache(tmp_path: Path) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "backwards.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    first = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    clock.now -= timedelta(microseconds=1)
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    error(response, 503, "LOCAL_QUOTE_UNAVAILABLE")
    assert quotes.calls == [("SYN:AAPL",)]
    clock.now = utc(first["fetched_at"]) + timedelta(seconds=1)
    assert data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)) == first


def test_invalid_shared_clock_is_safe_authorization_failure_before_provider(tmp_path: Path) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "invalid-clock.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    clock.now = datetime(2026, 10, 12, 1)
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert quotes.calls == []


def test_expanded_cache_lru_is_four_entries_hit_does_not_refresh_time(tmp_path: Path) -> None:
    clock, quotes = Clock(), ControlledQuotes(expanded=True)
    client = TestClient(
        application(
            tmp_path / "lru.sqlite3",
            clock,
            catalogue=ControlledCatalogue(expanded=True),
            quotes=quotes,
        )
    )
    headers = completed(client)
    saved: dict[str, dict] = {}
    for index in range(1, 5):
        identifier = f"SYN:TEST{index:03d}"
        saved[identifier] = data(client.get(MARKET + "/quotes/" + identifier, headers=headers))
    clock.now += timedelta(seconds=1)
    assert data(client.get(MARKET + "/quotes/SYN:TEST001", headers=headers)) == saved["SYN:TEST001"]
    data(client.get(MARKET + "/quotes/SYN:TEST005", headers=headers))
    assert len(quotes.calls) == 5
    assert data(client.get(MARKET + "/quotes/SYN:TEST003", headers=headers)) == saved["SYN:TEST003"]
    refreshed = data(client.get(MARKET + "/quotes/SYN:TEST002", headers=headers))
    assert len(quotes.calls) == 6 and quotes.calls[-1] == ("SYN:TEST002",)
    assert utc(refreshed["fetched_at"]) == clock.now
    assert refreshed["quote_as_of"] == saved["SYN:TEST002"]["quote_as_of"] == FIXTURE_TIME


def test_withdrawal_blocks_market_provider_even_when_cache_already_exists(tmp_path: Path) -> None:
    catalogue, quotes = ControlledCatalogue(), ControlledQuotes()
    client = TestClient(
        application(tmp_path / "provider-authorization.sqlite3", catalogue=catalogue, quotes=quotes)
    )
    headers = completed(client)
    data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
    before = catalogue.calls, len(quotes.calls)
    response = client.post(
        ONBOARDING + "/consent", headers=headers, json={**CONSENT, "consent_given": False}
    )
    assert response.status_code == 200
    error(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers), 409, "ONBOARDING_REQUIRED")
    error(client.get(MARKET + "/instruments", headers=headers), 409, "ONBOARDING_REQUIRED")
    assert (catalogue.calls, len(quotes.calls)) == before


@pytest.mark.parametrize(
    "method,suffix", [("DELETE", ""), ("PUT", "/items/SYN:AAPL"), ("DELETE", "/items/SYN:AAPL")]
)
@pytest.mark.parametrize("payload", [{"owner_id": "learner-b"}, [], True, "not-an-object"])
def test_empty_body_only_mutations_reject_client_authority_and_wrong_types(
    tmp_path: Path, method: str, suffix: str, payload: object
) -> None:
    client = TestClient(application(tmp_path / "empty-body.sqlite3"))
    headers = completed(client)
    watchlist = created(client, headers)
    response = client.request(
        method, LISTS + "/" + watchlist["watchlist_id"] + suffix, headers=headers, json=payload
    )
    error(response, 422, "VALIDATION_ERROR")
    result = data(client.get(LISTS + "/" + watchlist["watchlist_id"], headers=headers))
    assert result["items"] == [] and result["item_count"] == 0


def test_default_watchlist_items_do_not_enable_test_catalogue_or_unknown_instruments(
    tmp_path: Path,
) -> None:
    client = TestClient(application(tmp_path / "default-items.sqlite3"))
    headers = completed(client)
    watchlist = created(client, headers)
    path = LISTS + "/" + watchlist["watchlist_id"]
    for identifier in ("SYN:OTHER", "SYN:TEST001", "SYN:TEST101"):
        error(
            client.put(path + "/items/" + identifier, headers=headers), 404, "INSTRUMENT_NOT_FOUND"
        )
        error(
            client.delete(path + "/items/" + identifier, headers=headers),
            404,
            "INSTRUMENT_NOT_FOUND",
        )
    assert data(client.get(path, headers=headers))["items"] == []


def test_s3_does_not_mount_order_execution_or_historical_global_authority(tmp_path: Path) -> None:
    client = TestClient(application(tmp_path / "no-orders.sqlite3"))
    headers = completed(client)
    for endpoint in (
        "/api/v1/local-paper/orders",
        "/api/v1/market/quotes/AAPL",
        "/api/v1/watchlists",
        "/api/v1/paper-trading/account",
        "/api/v1/portfolios",
    ):
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 404
