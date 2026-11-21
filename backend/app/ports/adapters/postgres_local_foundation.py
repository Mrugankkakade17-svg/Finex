"""PostgreSQL implementation of foundation watchlist and paper-account persistence."""

from app.domain.local_foundation import (
    PaperAccountRecord,
    PaperOpeningRecord,
    WatchlistItemRecord,
    WatchlistRecord,
    validate_account,
    validate_item,
    validate_opening,
    validate_watchlist,
)
from app.ports.adapters.postgres_local_store import (
    PostgresAuthorizationTransaction,
    PostgresTransactionStore,
    stored_integer,
    stored_text,
    stored_time,
)
from app.ports.local_foundation_store import LocalFoundationTransaction


def _watchlist(row: dict) -> WatchlistRecord:
    return validate_watchlist(
        WatchlistRecord(
            stored_text(row["user_id"]),
            stored_text(row["watchlist_id"]),
            stored_text(row["name"]),
            stored_time(row["created_at"]),
            stored_time(row["updated_at"]),
        )
    )


def _item(row: dict) -> WatchlistItemRecord:
    return validate_item(
        WatchlistItemRecord(
            stored_text(row["user_id"]),
            stored_text(row["watchlist_id"]),
            stored_text(row["instrument_id"]),
            stored_time(row["added_at"]),
        )
    )


def _account(row: dict) -> PaperAccountRecord:
    return validate_account(
        PaperAccountRecord(
            stored_text(row["user_id"]),
            stored_text(row["account_id"]),
            stored_text(row["opening_ledger_id"]),
            stored_text(row["currency"]),
            stored_integer(row["opening_cash_cents"]),
            stored_integer(row["cash_balance_cents"]),
            stored_time(row["created_at"]),
        )
    )


def _opening(row: dict) -> PaperOpeningRecord:
    return validate_opening(
        PaperOpeningRecord(
            stored_text(row["user_id"]),
            stored_text(row["account_id"]),
            stored_text(row["ledger_id"]),
            stored_integer(row["sequence"]),
            stored_integer(row["cash_delta_cents"]),
            stored_integer(row["cash_after_cents"]),
            stored_time(row["created_at"]),
        )
    )


class PostgresLocalFoundationTransaction(PostgresAuthorizationTransaction):
    def watchlists(self, user_id: str, limit: int) -> list[WatchlistRecord]:
        if type(limit) is not int or not 1 <= limit <= 11:
            raise ValueError("Invalid owned query bound")
        rows = self._connection.execute(
            "SELECT * FROM finex.local_watchlists WHERE user_id=%s "
            "ORDER BY created_at,watchlist_id LIMIT %s",
            (user_id, limit),
        ).fetchall()
        return [_watchlist(row) for row in rows]

    def watchlist(self, user_id: str, watchlist_id: str) -> WatchlistRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_watchlists WHERE user_id=%s AND watchlist_id=%s",
            (user_id, watchlist_id),
        ).fetchone()
        return _watchlist(row) if row else None

    def insert_watchlist(self, record: WatchlistRecord) -> None:
        validate_watchlist(record)
        self._connection.execute(
            "INSERT INTO finex.local_watchlists(watchlist_id,user_id,name,created_at,updated_at)"
            " VALUES(%s,%s,%s,%s,%s)",
            (
                record.watchlist_id,
                record.user_id,
                record.name,
                record.created_at,
                record.updated_at,
            ),
        )

    def update_watchlist(self, record: WatchlistRecord) -> bool:
        validate_watchlist(record)
        changed = self._connection.execute(
            "UPDATE finex.local_watchlists SET name=%s,updated_at=%s "
            "WHERE user_id=%s AND watchlist_id=%s",
            (record.name, record.updated_at, record.user_id, record.watchlist_id),
        )
        return changed.rowcount == 1

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM finex.local_watchlists WHERE user_id=%s AND watchlist_id=%s",
            (user_id, watchlist_id),
        )
        return changed.rowcount == 1

    def items(self, user_id: str, watchlist_id: str, limit: int) -> list[WatchlistItemRecord]:
        if type(limit) is not int or not 1 <= limit <= 101:
            raise ValueError("Invalid owned query bound")
        rows = self._connection.execute(
            "SELECT * FROM finex.local_watchlist_items WHERE user_id=%s AND watchlist_id=%s "
            "ORDER BY added_at,instrument_id LIMIT %s",
            (user_id, watchlist_id, limit),
        ).fetchall()
        return [_item(row) for row in rows]

    def item(
        self, user_id: str, watchlist_id: str, instrument_id: str
    ) -> WatchlistItemRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_watchlist_items "
            "WHERE user_id=%s AND watchlist_id=%s AND instrument_id=%s",
            (user_id, watchlist_id, instrument_id),
        ).fetchone()
        return _item(row) if row else None

    def insert_item(self, record: WatchlistItemRecord) -> None:
        validate_item(record)
        self._connection.execute(
            "INSERT INTO finex.local_watchlist_items(user_id,watchlist_id,instrument_id,added_at)"
            " VALUES(%s,%s,%s,%s)",
            (record.user_id, record.watchlist_id, record.instrument_id, record.added_at),
        )

    def delete_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM finex.local_watchlist_items "
            "WHERE user_id=%s AND watchlist_id=%s AND instrument_id=%s",
            (user_id, watchlist_id, instrument_id),
        )
        return changed.rowcount == 1

    def account(self, user_id: str) -> PaperAccountRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_paper_accounts WHERE user_id=%s", (user_id,)
        ).fetchone()
        return _account(row) if row else None

    def opening(self, user_id: str, account_id: str, ledger_id: str) -> PaperOpeningRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_paper_ledger "
            "WHERE user_id=%s AND account_id=%s AND ledger_id=%s",
            (user_id, account_id, ledger_id),
        ).fetchone()
        return _opening(row) if row else None

    def insert_account_with_opening(
        self, account: PaperAccountRecord, entry: PaperOpeningRecord
    ) -> None:
        validate_account(account)
        validate_opening(entry, account.user_id, new=True)
        self._connection.execute(
            "INSERT INTO finex.local_paper_accounts(account_id,user_id,opening_ledger_id,currency,"
            "opening_cash_cents,cash_balance_cents,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                account.account_id,
                account.user_id,
                account.opening_ledger_id,
                account.currency,
                account.opening_cash_cents,
                account.cash_balance_cents,
                account.created_at,
            ),
        )
        self._connection.execute(
            "INSERT INTO finex.local_paper_ledger(ledger_id,user_id,account_id,entry_type,"
            "cash_delta_cents,cash_after_cents,created_at) VALUES(%s,%s,%s,'OPENING',%s,%s,%s)",
            (
                entry.ledger_id,
                entry.user_id,
                entry.account_id,
                entry.cash_delta_cents,
                entry.cash_after_cents,
                entry.created_at,
            ),
        )

    def ledger(
        self, user_id: str, account_id: str, after_sequence: int, limit: int
    ) -> list[PaperOpeningRecord]:
        if type(after_sequence) is not int or not 0 <= after_sequence <= 9007199254740991:
            raise ValueError("Invalid simulated cursor")
        if type(limit) is not int or not 1 <= limit <= 101:
            raise ValueError("Invalid owned query bound")
        rows = self._connection.execute(
            "SELECT * FROM finex.local_paper_ledger "
            "WHERE user_id=%s AND account_id=%s AND sequence>%s "
            "ORDER BY sequence LIMIT %s",
            (user_id, account_id, after_sequence, limit),
        ).fetchall()
        return [_opening(row) for row in rows]


class PostgresLocalFoundationStore(PostgresTransactionStore[LocalFoundationTransaction]):
    def __init__(self, database_url: str) -> None:
        super().__init__(database_url, PostgresLocalFoundationTransaction)
