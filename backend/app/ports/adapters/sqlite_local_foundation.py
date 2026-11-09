"""S3 owned SQLite capability; all mutations share the authorization connection."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.local_foundation import (
    PaperAccountRecord,
    PaperOpeningRecord,
    WatchlistItemRecord,
    WatchlistRecord,
    utc_record,
    validate_account,
    validate_item,
    validate_opening,
    validate_watchlist,
)
from app.ports.adapters.sqlite_local_store import (
    SQLiteAuthorizationTransaction,
    SQLiteTransactionStore,
    stored_integer,
    stored_text,
    utc_text,
)
from app.ports.local_foundation_store import LocalFoundationTransaction


def _stored_foundation_time(value: object) -> datetime:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|\+00:00)",
            value,
        )
        is None
    ):
        raise ValueError("Invalid owned UTC time")
    parsed = datetime.fromisoformat(value)
    utc_record(parsed)
    return parsed


def _watchlist(row: sqlite3.Row) -> WatchlistRecord:
    return validate_watchlist(
        WatchlistRecord(
            stored_text(row["user_id"]),
            stored_text(row["watchlist_id"]),
            stored_text(row["name"]),
            _stored_foundation_time(row["created_at"]),
            _stored_foundation_time(row["updated_at"]),
        )
    )


def _item(row: sqlite3.Row) -> WatchlistItemRecord:
    return validate_item(
        WatchlistItemRecord(
            stored_text(row["user_id"]),
            stored_text(row["watchlist_id"]),
            stored_text(row["instrument_id"]),
            _stored_foundation_time(row["added_at"]),
        )
    )


def _account(row: sqlite3.Row) -> PaperAccountRecord:
    return validate_account(
        PaperAccountRecord(
            stored_text(row["user_id"]),
            stored_text(row["account_id"]),
            stored_text(row["opening_ledger_id"]),
            stored_text(row["currency"]),
            stored_integer(row["opening_cash_cents"]),
            stored_integer(row["cash_balance_cents"]),
            _stored_foundation_time(row["created_at"]),
        )
    )


def _opening(row: sqlite3.Row) -> PaperOpeningRecord:
    if stored_text(row["entry_type"]) != "OPENING" or any(
        row[field] is not None
        for field in (
            "instrument_id",
            "quantity_delta_micro_units",
            "position_after_micro_units",
            "order_id",
            "trade_id",
            "corrects_ledger_id",
        )
    ):
        raise ValueError("Invalid simulated opening record")
    return validate_opening(
        PaperOpeningRecord(
            stored_text(row["user_id"]),
            stored_text(row["account_id"]),
            stored_text(row["ledger_id"]),
            stored_integer(row["sequence"]),
            stored_integer(row["cash_delta_cents"]),
            stored_integer(row["cash_after_cents"]),
            _stored_foundation_time(row["created_at"]),
        )
    )


def _bound(value: int, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("Invalid owned query bound")
    return value


class SQLiteLocalFoundationTransaction(SQLiteAuthorizationTransaction):
    def watchlists(self, user_id: str, limit: int) -> list[WatchlistRecord]:
        rows = self._connection.execute(
            "SELECT * FROM local_watchlists WHERE user_id=? "
            "ORDER BY julianday(created_at),watchlist_id LIMIT ?",
            (user_id, _bound(limit, 11)),
        ).fetchall()
        return sorted(
            (_watchlist(row) for row in rows), key=lambda row: (row.created_at, row.watchlist_id)
        )

    def watchlist(self, user_id: str, watchlist_id: str) -> WatchlistRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_watchlists WHERE user_id=? AND watchlist_id=?",
            (user_id, watchlist_id),
        ).fetchone()
        return _watchlist(row) if row is not None else None

    def insert_watchlist(self, record: WatchlistRecord) -> None:
        validate_watchlist(record)
        self._connection.execute(
            "INSERT INTO local_watchlists(watchlist_id,user_id,name,created_at,updated_at) "
            "VALUES(?,?,?,?,?)",
            (
                record.watchlist_id,
                record.user_id,
                record.name,
                utc_text(record.created_at),
                utc_text(record.updated_at),
            ),
        )

    def update_watchlist(self, record: WatchlistRecord) -> bool:
        validate_watchlist(record)
        changed = self._connection.execute(
            "UPDATE local_watchlists SET name=?,updated_at=? WHERE user_id=? AND watchlist_id=?",
            (record.name, utc_text(record.updated_at), record.user_id, record.watchlist_id),
        )
        return changed.rowcount == 1

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM local_watchlists WHERE user_id=? AND watchlist_id=?",
            (user_id, watchlist_id),
        )
        return changed.rowcount == 1

    def items(self, user_id: str, watchlist_id: str, limit: int) -> list[WatchlistItemRecord]:
        rows = self._connection.execute(
            "SELECT * FROM local_watchlist_items WHERE user_id=? AND watchlist_id=? "
            "ORDER BY julianday(added_at),instrument_id LIMIT ?",
            (user_id, watchlist_id, _bound(limit, 101)),
        ).fetchall()
        return sorted(
            (_item(row) for row in rows), key=lambda row: (row.added_at, row.instrument_id)
        )

    def item(
        self, user_id: str, watchlist_id: str, instrument_id: str
    ) -> WatchlistItemRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_watchlist_items WHERE user_id=? AND watchlist_id=? "
            "AND instrument_id=?",
            (user_id, watchlist_id, instrument_id),
        ).fetchone()
        return _item(row) if row is not None else None

    def insert_item(self, record: WatchlistItemRecord) -> None:
        validate_item(record)
        self._connection.execute(
            "INSERT INTO local_watchlist_items(user_id,watchlist_id,instrument_id,added_at) "
            "VALUES(?,?,?,?)",
            (record.user_id, record.watchlist_id, record.instrument_id, utc_text(record.added_at)),
        )

    def delete_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM local_watchlist_items WHERE user_id=? AND watchlist_id=? "
            "AND instrument_id=?",
            (user_id, watchlist_id, instrument_id),
        )
        return changed.rowcount == 1

    def account(self, user_id: str) -> PaperAccountRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_paper_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        return _account(row) if row is not None else None

    def opening(self, user_id: str, account_id: str, ledger_id: str) -> PaperOpeningRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_paper_ledger WHERE user_id=? AND account_id=? AND ledger_id=?",
            (user_id, account_id, ledger_id),
        ).fetchone()
        return _opening(row) if row is not None else None

    def insert_account_with_opening(
        self, account: PaperAccountRecord, entry: PaperOpeningRecord
    ) -> None:
        validate_account(account)
        validate_opening(entry, account.user_id, new=True)
        if (
            account.account_id != entry.account_id
            or account.opening_ledger_id != entry.ledger_id
            or account.created_at != entry.created_at
        ):
            raise ValueError("Invalid simulated opening binding")
        self._connection.execute(
            "INSERT INTO local_paper_accounts(account_id,user_id,opening_ledger_id,currency,"
            "opening_cash_cents,cash_balance_cents,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                account.account_id,
                account.user_id,
                account.opening_ledger_id,
                account.currency,
                account.opening_cash_cents,
                account.cash_balance_cents,
                utc_text(account.created_at),
            ),
        )
        self._connection.execute(
            "INSERT INTO local_paper_ledger(ledger_id,user_id,account_id,entry_type,"
            "cash_delta_cents,cash_after_cents,created_at) VALUES(?,?,?,'OPENING',?,?,?)",
            (
                entry.ledger_id,
                entry.user_id,
                entry.account_id,
                entry.cash_delta_cents,
                entry.cash_after_cents,
                utc_text(entry.created_at),
            ),
        )

    def ledger(
        self, user_id: str, account_id: str, after_sequence: int, limit: int
    ) -> list[PaperOpeningRecord]:
        if type(after_sequence) is not int or not 0 <= after_sequence <= 9007199254740991:
            raise ValueError("Invalid simulated cursor")
        rows = self._connection.execute(
            "SELECT * FROM local_paper_ledger WHERE user_id=? AND account_id=? AND sequence>? "
            "ORDER BY sequence LIMIT ?",
            (user_id, account_id, after_sequence, _bound(limit, 101)),
        ).fetchall()
        return [_opening(row) for row in rows]


class SQLiteLocalFoundationStore(SQLiteTransactionStore[LocalFoundationTransaction]):
    def __init__(self, path: Path) -> None:
        super().__init__(path, SQLiteLocalFoundationTransaction)
