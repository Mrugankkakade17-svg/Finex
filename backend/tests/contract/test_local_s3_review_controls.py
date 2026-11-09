"""Additional independent-review S3 controls, written before implementation."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.ports.adapters.sqlite_local_store import SQLiteTransactionStore
from tests.contract.test_local_s3_foundation_api import QUOTE_FIELDS
from tests.support.local_s3_client import (
    CONSENT,
    FIXTURE_TIME,
    LISTS,
    MARKET,
    ONBOARDING,
    OPEN,
    PAPER,
    SCOPE,
    Clock,
    ControlledQuotes,
    application,
    completed,
    created,
    data,
    error,
)


def test_review_literal_versions_parent_item_binding_and_actual_time_order(tmp_path: Path) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "binding.sqlite3", clock))
    headers = completed(client)
    watchlist = created(client, headers)
    assert watchlist["watchlist_version"] == "watchlist.v1"
    path = LISTS + "/" + watchlist["watchlist_id"]
    expected = (
        ("SYN:MSFT", "Synthetic Microsoft example", "EQUITY", "TECHNOLOGY"),
        ("SYN:AAPL", "Synthetic Apple example", "EQUITY", "TECHNOLOGY"),
        ("SYN:BND", "Synthetic bond-fund example", "BOND", "FIXED_INCOME"),
    )
    for identifier, name, asset, sector in expected:
        added = data(client.put(path + "/items/" + identifier, headers=headers))
        assert added["watchlist_id"] == watchlist["watchlist_id"]
        assert added["watchlist_version"] == "watchlist.v1"
        assert added["item"] == {
            "instrument_id": identifier,
            "display_name": name,
            "asset_class": asset,
            "sector": sector,
            "currency": "USD",
            "added_at": clock.now.isoformat(),
        }
        clock.now += timedelta(seconds=1)
    full = data(client.get(path, headers=headers))
    assert full["watchlist_version"] == "watchlist.v1"
    assert type(full["item_count"]) is int and full["item_count"] == 3
    assert [item["instrument_id"] for item in full["items"]] == [row[0] for row in expected]
    updated = data(client.put(path, headers=headers, json={"name": "Synthetic updated"}))
    assert updated["watchlist_version"] == "watchlist.v1"
    collection = data(client.get(LISTS, headers=headers))
    assert type(collection["limit"]) is int and type(collection["count"]) is int
    assert type(collection["items"][0]["item_count"]) is int


@pytest.mark.parametrize("state", ["stale", "fault-first", "fault-old"])
def test_review_quote_fault_and_stale_exact_literals_keys_and_metadata(
    tmp_path: Path, state: str
) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "quote-review.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    previous = None
    if state != "fault-first":
        previous = data(client.get(MARKET + "/quotes/SYN:AAPL", headers=headers))
        clock.now += timedelta(seconds=60 if state == "stale" else 300)
    quotes.failed = True
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    result = data(response)
    assert set(result) == QUOTE_FIELDS
    assert result == {
        **SCOPE,
        "catalog_version": "synthetic_catalog.v1",
        "quote_snapshot_version": "synthetic_quotes.v1",
        "source": "finex.synthetic.portfolio",
        "source_type": "SYNTHETIC",
        "fixture_as_of": FIXTURE_TIME,
        "instrument_id": "SYN:AAPL",
        "currency": "USD",
        "status": "STALE" if state == "stale" else "UNAVAILABLE",
        "unit_price": "200.0000" if state == "stale" else None,
        "quote_as_of": FIXTURE_TIME if state == "stale" else None,
        "fetched_at": previous["fetched_at"] if previous else None,
        "cache_expires_at": previous["cache_expires_at"] if previous else None,
        "reason": "SYNTHETIC_PROVIDER_STALE"
        if state == "stale"
        else "SYNTHETIC_PROVIDER_UNAVAILABLE",
    }
    assert response.json()["meta"]["dataStatus"] == (
        "CACHED" if state == "stale" else "UNAVAILABLE"
    )
    assert response.json()["meta"]["dataAsOf"] == (FIXTURE_TIME if state == "stale" else None)


def test_review_idempotent_metadata_preserves_times_but_not_request_correlation(
    tmp_path: Path,
) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "idempotency-metadata.sqlite3", clock))
    headers = completed(client)

    def trace(name: str) -> dict[str, str]:
        return {**headers, "X-Correlation-ID": name}

    first_open = client.post(PAPER + "/open", headers=trace("s3-open-first"), json=OPEN)
    first = data(first_open)
    clock.now += timedelta(seconds=1)
    again_open = client.post(PAPER + "/open", headers=trace("s3-open-again"), json=OPEN)
    assert data(again_open) == first
    assert again_open.json()["meta"]["dataAsOf"] == first_open.json()["meta"]["dataAsOf"]
    assert first_open.json()["meta"]["correlationId"] == "s3-open-first"
    assert again_open.json()["meta"]["correlationId"] == "s3-open-again"
    watchlist = created(client, headers)
    item_path = LISTS + "/" + watchlist["watchlist_id"] + "/items/SYN:AAPL"
    added = client.put(item_path, headers=trace("s3-add-first"))
    first_item = data(added)
    clock.now += timedelta(seconds=1)
    repeated = client.put(item_path, headers=trace("s3-add-again"))
    assert data(repeated) == first_item
    assert added.json()["meta"]["dataAsOf"] == repeated.json()["meta"]["dataAsOf"]
    assert repeated.json()["meta"]["correlationId"] == "s3-add-again"
    removed = client.delete(item_path, headers=trace("s3-remove-first"))
    first_removal = data(removed)
    clock.now += timedelta(seconds=1)
    repeated_remove = client.delete(item_path, headers=trace("s3-remove-again"))
    assert data(repeated_remove) == first_removal
    assert removed.json()["meta"]["dataAsOf"] == repeated_remove.json()["meta"]["dataAsOf"]
    assert repeated_remove.json()["meta"]["correlationId"] == "s3-remove-again"
    ledger = data(client.get(PAPER + "/ledger", headers=headers))
    empty_response = client.get(
        PAPER + f"/ledger?after_sequence={ledger['items'][0]['sequence']}", headers=headers
    )
    empty = data(empty_response)
    assert empty["items"] == [] and empty_response.json()["meta"]["dataAsOf"] is None


def test_review_unavailable_success_cache_hit_then_refresh_failure_retains_retrieval(
    tmp_path: Path,
) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(application(tmp_path / "unavailable-cache.sqlite3", clock, quotes=quotes))
    headers = completed(client)
    first = data(client.get(MARKET + "/quotes/SYN:UNAVAILABLE", headers=headers))
    assert first["fetched_at"] is not None and first["cache_expires_at"] is not None
    clock.now += timedelta(seconds=59)
    assert data(client.get(MARKET + "/quotes/SYN:UNAVAILABLE", headers=headers)) == first
    assert quotes.calls == [("SYN:UNAVAILABLE",)]
    clock.now += timedelta(seconds=1)
    quotes.failed = True
    response = client.get(MARKET + "/quotes/SYN:UNAVAILABLE", headers=headers)
    failed = data(response)
    assert (
        failed["status"] == "UNAVAILABLE"
        and failed["unit_price"] is None
        and failed["quote_as_of"] is None
    )
    assert failed["reason"] == "SYNTHETIC_PROVIDER_UNAVAILABLE"
    assert (
        failed["fetched_at"] == first["fetched_at"]
        and failed["cache_expires_at"] == first["cache_expires_at"]
    )
    assert failed["fixture_as_of"] == FIXTURE_TIME and response.json()["meta"]["dataAsOf"] is None


@pytest.mark.parametrize("order", ["withdrawal-first", "domain-first"])
def test_review_real_account_open_withdrawal_lock_orders_save_zero_or_one_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: str
) -> None:
    path = tmp_path / "account-withdrawal-race.sqlite3"
    app = application(path)
    client = TestClient(app)
    headers = completed(client)
    assert data(client.get(PAPER, headers=headers))["account"] is None
    ready, released, attempted = Event(), Event(), Event()
    original_connect = sqlite3.connect
    armed = True

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and ready.is_set():
                attempted.set()
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        kwargs["factory"] = ObservedConnection
        return original_connect(*args, **kwargs)

    def pause(self: object, connection: sqlite3.Connection) -> None:
        nonlocal armed
        if armed:
            armed = False
            ready.set()
            if not released.wait(3):
                raise RuntimeError("Synthetic account race was not released")

    monkeypatch.setattr(sqlite3, "connect", connect)
    monkeypatch.setattr(SQLiteTransactionStore, "_before_commit", pause)

    def withdraw() -> int:
        response = TestClient(app).post(
            ONBOARDING + "/consent", headers=headers, json={**CONSENT, "consent_given": False}
        )
        assert response.status_code == 200
        return response.status_code

    def open_account() -> int:
        response = TestClient(app).post(PAPER + "/open", headers=headers, json=OPEN)
        if order == "withdrawal-first":
            error(response, 409, "ONBOARDING_REQUIRED")
        else:
            data(response)
        return response.status_code

    first_operation, second_operation = (
        (withdraw, open_account) if order == "withdrawal-first" else (open_account, withdraw)
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_operation)
        try:
            assert ready.wait(2)
            second = pool.submit(second_operation)
            assert attempted.wait(2)
        finally:
            released.set()
        assert first.result(timeout=5) == 200
        assert second.result(timeout=5) == (409 if order == "withdrawal-first" else 200)
    error(client.get(PAPER, headers=headers), 409, "ONBOARDING_REQUIRED")
    with closing(original_connect(path)) as connection:
        accounts = connection.execute("SELECT COUNT(*) FROM local_paper_accounts").fetchone()[0]
        ledger = connection.execute("SELECT COUNT(*) FROM local_paper_ledger").fetchone()[0]
    assert accounts == ledger == (0 if order == "withdrawal-first" else 1)
