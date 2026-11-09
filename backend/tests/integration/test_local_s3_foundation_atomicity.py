"""Native temporary SQLite S3 mutation atomicity and real lock ordering.

The API transport is in process; no real TCP/process-expiry/UAT claim is made.
Thread events observe only BEGIN IMMEDIATE, never expanded SQL or credentials.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient

from app.ports.adapters.sqlite_local_store import SQLiteTransactionStore
from tests.support.local_s3_client import (
    CONSENT,
    LISTS,
    ONBOARDING,
    OPEN,
    PAPER,
    application,
    completed,
    created,
    data,
    error,
)


@pytest.mark.parametrize("operation", ["watchlist-create", "account-open"])
def test_failed_domain_commit_has_no_half_saved_state_and_retry_is_deliberate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    path = tmp_path / "rollback.sqlite3"
    client = TestClient(application(path))
    headers = completed(client)
    armed = True

    def fail_once(self: object, connection: sqlite3.Connection) -> None:
        nonlocal armed
        if armed:
            armed = False
            raise sqlite3.OperationalError("Synthetic unconfirmed domain commit")

    monkeypatch.setattr(SQLiteTransactionStore, "_before_commit", fail_once)
    endpoint, payload = (
        (LISTS, {"name": "Synthetic rollback list"})
        if operation == "watchlist-create"
        else (PAPER + "/open", OPEN)
    )
    response = client.post(endpoint, headers=headers, json=payload)
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert data(client.get(LISTS, headers=headers))["items"] == []
    assert data(client.get(PAPER, headers=headers))["account"] is None
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_watchlists").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM local_paper_accounts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM local_paper_ledger").fetchone()[0] == 0
    retry = client.post(endpoint, headers=headers, json=payload)
    data(retry, status=201 if operation == "watchlist-create" else 200)


def test_concurrent_openings_have_one_account_one_integer_opening_and_immutable_ledger(
    tmp_path: Path,
) -> None:
    path = tmp_path / "concurrent-open.sqlite3"
    app = application(path)
    client = TestClient(app)
    headers = completed(client)
    initial = data(client.get(PAPER, headers=headers))
    assert initial["account"] is None
    ready = Barrier(2)

    def explicit_open() -> dict:
        ready.wait(3)
        response = TestClient(app).post(PAPER + "/open", headers=headers, json=OPEN)
        return data(response)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(explicit_open), pool.submit(explicit_open)
        a, b = first.result(timeout=6), second.result(timeout=6)
    assert a == b
    ledger = data(client.get(PAPER + "/ledger", headers=headers))
    assert ledger["count"] == 1
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_paper_accounts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM local_paper_ledger").fetchone()[0] == 1
        row = connection.execute(
            "SELECT typeof(opening_cash_cents),opening_cash_cents,"
            "typeof(cash_balance_cents),cash_balance_cents FROM local_paper_accounts"
        ).fetchone()
        assert row == ("integer", 1000000, "integer", 1000000)
        for statement in (
            "UPDATE local_paper_ledger SET cash_after_cents=cash_after_cents",
            "DELETE FROM local_paper_ledger",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)


def test_concurrent_last_watchlist_slot_cannot_exceed_owner_capacity(tmp_path: Path) -> None:
    app = application(tmp_path / "concurrent-quota.sqlite3")
    client = TestClient(app)
    headers = completed(client)
    for index in range(9):
        created(client, headers, f"Synthetic saved list {index}")
    ready = Barrier(2)

    def create_last(index: int) -> int:
        ready.wait(3)
        response = TestClient(app).post(
            LISTS, headers=headers, json={"name": f"Synthetic competing list {index}"}
        )
        if response.status_code == 409:
            error(response, 409, "WATCHLIST_LIMIT")
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(create_last, 1), pool.submit(create_last, 2)
        assert sorted([first.result(timeout=6), second.result(timeout=6)]) == [201, 409]
    assert data(client.get(LISTS, headers=headers))["count"] == 10
    other = completed(client, "learner-b")
    created(client, other, "Synthetic independent owner")
    assert data(client.get(LISTS, headers=other))["count"] == 1


def test_duplicate_concurrent_item_put_returns_same_saved_item_once(tmp_path: Path) -> None:
    app = application(tmp_path / "duplicate-item.sqlite3")
    client = TestClient(app)
    headers = completed(client)
    watchlist = created(client, headers)
    endpoint = LISTS + "/" + watchlist["watchlist_id"] + "/items/SYN:AAPL"
    ready = Barrier(2)

    def add_item() -> dict:
        ready.wait(3)
        return data(TestClient(app).put(endpoint, headers=headers))

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(add_item), pool.submit(add_item)
        assert first.result(timeout=6) == second.result(timeout=6)
    assert (
        data(client.get(LISTS + "/" + watchlist["watchlist_id"], headers=headers))["item_count"]
        == 1
    )


@pytest.mark.parametrize("order", ["withdrawal-first", "domain-first"])
def test_real_withdrawal_and_domain_write_lock_order_is_not_a_replayed_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: str
) -> None:
    app = application(tmp_path / "consent-write-race.sqlite3")
    client = TestClient(app)
    headers = completed(client)
    watchlist = created(client, headers)
    item_path = LISTS + "/" + watchlist["watchlist_id"] + "/items/SYN:AAPL"
    first_ready, release_first, second_attempted = Event(), Event(), Event()
    armed = True
    original_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and first_ready.is_set():
                second_attempted.set()
            return super().execute(sql, parameters)

    def observed_connect(*args, **kwargs):
        kwargs["factory"] = ObservedConnection
        return original_connect(*args, **kwargs)

    def pause_first(self: object, connection: sqlite3.Connection) -> None:
        nonlocal armed
        if armed:
            armed = False
            first_ready.set()
            if not release_first.wait(3):
                raise RuntimeError("Synthetic race release was not received")

    monkeypatch.setattr(sqlite3, "connect", observed_connect)
    monkeypatch.setattr(SQLiteTransactionStore, "_before_commit", pause_first)

    def withdraw() -> int:
        response = TestClient(app).post(
            ONBOARDING + "/consent", headers=headers, json={**CONSENT, "consent_given": False}
        )
        assert response.status_code == 200
        return response.status_code

    def add() -> int:
        response = TestClient(app).put(item_path, headers=headers)
        if order == "withdrawal-first":
            error(response, 409, "ONBOARDING_REQUIRED")
        else:
            data(response)
        return response.status_code

    first_operation, second_operation = (
        (withdraw, add) if order == "withdrawal-first" else (add, withdraw)
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_operation)
        try:
            assert first_ready.wait(2)
            second = pool.submit(second_operation)
            assert second_attempted.wait(2)
        finally:
            release_first.set()
        assert first.result(timeout=5) == 200
        assert second.result(timeout=5) == (409 if order == "withdrawal-first" else 200)
    error(client.get(LISTS, headers=headers), 409, "ONBOARDING_REQUIRED")
    with closing(original_connect(tmp_path / "consent-write-race.sqlite3")) as connection:
        count = connection.execute("SELECT COUNT(*) FROM local_watchlist_items").fetchone()[0]
    assert count == (0 if order == "withdrawal-first" else 1)
