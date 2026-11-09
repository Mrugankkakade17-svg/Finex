"""Narrow S3 corruption/runtime-injection controls; no real credentials or DB."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.local_foundation import PaperOpeningRecord, WatchlistRecord
from app.ports.adapters.sqlite_local_foundation import SQLiteLocalFoundationTransaction
from tests.support.local_s3_client import (
    LISTS,
    MARKET,
    PAPER,
    Clock,
    ControlledCatalogue,
    ControlledQuotes,
    application,
    completed,
    created,
    data,
    error,
    opened,
)


@pytest.mark.parametrize("value", [None, True, "not-a-datetime"])
def test_invalid_shared_clock_type_is_safe_503_without_provider_or_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    clock, quotes = Clock(), ControlledQuotes()
    client = TestClient(
        application(tmp_path / "bad-clock.sqlite3", clock, quotes=quotes),
        raise_server_exceptions=False,
    )
    headers = completed(client)
    monkeypatch.setattr(clock, "now", value)
    response = client.get(MARKET + "/quotes/SYN:AAPL", headers=headers)
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert quotes.calls == []


@pytest.mark.parametrize("resource", ["watchlist", "account"])
@pytest.mark.parametrize(
    "stamp",
    ["2026-10-12T01:00:00.0000001+00:00", "2026-10-12T01:00:00", "2026-10-12T01:00:00+01:00"],
)
def test_invalid_persisted_s3_times_are_not_truncated_or_guessed_as_saved(
    tmp_path: Path, resource: str, stamp: str
) -> None:
    path = tmp_path / "bad-stored-time.sqlite3"
    client = TestClient(application(path))
    headers = completed(client)
    if resource == "watchlist":
        watchlist = created(client, headers)
        endpoint = LISTS + "/" + watchlist["watchlist_id"]
        with closing(sqlite3.connect(path)) as connection:
            connection.execute(
                "UPDATE local_watchlists SET created_at=?,updated_at=?", (stamp, stamp)
            )
            connection.commit()
    else:
        opened(client, headers)
        endpoint = PAPER
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("UPDATE local_paper_accounts SET created_at=?", (stamp,))
            connection.commit()
    response = client.get(endpoint, headers=headers)
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")


def test_falsey_valid_injected_provider_capabilities_are_not_replaced(tmp_path: Path) -> None:
    class FalseyCatalogue(ControlledCatalogue):
        def __bool__(self) -> bool:
            return False

    class FalseyQuotes(ControlledQuotes):
        def __bool__(self) -> bool:
            return False

    catalogue, quotes = FalseyCatalogue(expanded=True), FalseyQuotes(expanded=True)
    client = TestClient(
        application(tmp_path / "falsey-provider.sqlite3", catalogue=catalogue, quotes=quotes)
    )
    headers = completed(client)
    quote = data(client.get(MARKET + "/quotes/SYN:TEST001", headers=headers))
    assert quote["unit_price"] == "1.0000" and quote["instrument_id"] == "SYN:TEST001"
    assert quotes.calls == [("SYN:TEST001",)]


@pytest.mark.parametrize("fault", ["duplicate", "reversed"])
def test_corrupt_owned_list_projection_cannot_confirm_a_new_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    path = tmp_path / "bad-list-projection.sqlite3"
    clock = Clock()
    client = TestClient(application(path, clock))
    headers = completed(client)
    created(client, headers, "Synthetic original list")
    clock.now += timedelta(seconds=1)
    created(client, headers, "Synthetic second list")
    original = SQLiteLocalFoundationTransaction.watchlists

    def corrupted(
        transaction: SQLiteLocalFoundationTransaction, owner: str, limit: int
    ) -> list[WatchlistRecord]:
        rows = original(transaction, owner, limit)
        return rows + rows[:1] if fault == "duplicate" else list(reversed(rows))

    monkeypatch.setattr(SQLiteLocalFoundationTransaction, "watchlists", corrupted)
    response = client.post(LISTS, headers=headers, json={"name": "Synthetic unconfirmed list"})
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_watchlists").fetchone()[0] == 2


@pytest.mark.parametrize("fault", ["timestamp", "sequence"])
def test_corrupt_ledger_projection_cannot_invent_a_different_opening_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    path = tmp_path / "bad-ledger-projection.sqlite3"
    client = TestClient(application(path))
    headers = completed(client)
    opened(client, headers)
    original = SQLiteLocalFoundationTransaction.ledger

    def corrupted(
        transaction: SQLiteLocalFoundationTransaction,
        owner: str,
        account_id: str,
        after_sequence: int,
        limit: int,
    ) -> list[PaperOpeningRecord]:
        rows = original(transaction, owner, account_id, after_sequence, limit)
        if rows:
            rows[0] = (
                replace(rows[0], created_at=rows[0].created_at + timedelta(seconds=1))
                if fault == "timestamp"
                else replace(rows[0], sequence=rows[0].sequence + 1)
            )
        return rows

    monkeypatch.setattr(SQLiteLocalFoundationTransaction, "ledger", corrupted)
    response = client.get(PAPER + "/ledger", headers=headers)
    error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_paper_ledger").fetchone()[0] == 1
