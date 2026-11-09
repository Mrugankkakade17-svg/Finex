"""Narrow native manual portfolios; no quotes, math, broker data or S1 writes."""

import sqlite3
from pathlib import Path

from app.domain.local_portfolio import (
    HOLDING_LIMIT,
    PORTFOLIO_LIMIT,
    LocalHoldingRecord,
    LocalPortfolioRecord,
    cost_text,
    cost_units,
    quantity_text,
    quantity_units,
    validate_holding_record,
    validate_portfolio_record,
)
from app.ports.adapters.sqlite_local_store import (
    SQLiteAuthorizationTransaction,
    SQLiteTransactionStore,
    optional_text,
    stored_integer,
    stored_text,
    stored_time,
    utc_text,
)
from app.ports.local_portfolio_store import LocalPortfolioTransaction


def _portfolio(row: sqlite3.Row, user_id: str) -> LocalPortfolioRecord:
    return validate_portfolio_record(
        LocalPortfolioRecord(
            user_id=stored_text(row["user_id"]),
            portfolio_id=stored_text(row["portfolio_id"]),
            name=stored_text(row["name"]),
            description=optional_text(row["description"]),
            currency=stored_text(row["currency"]),
            created_at=stored_time(row["created_at"]),
            updated_at=stored_time(row["updated_at"]),
        ),
        user_id=user_id,
    )


def _holding(row: sqlite3.Row, user_id: str, portfolio_id: str) -> LocalHoldingRecord:
    return validate_holding_record(
        LocalHoldingRecord(
            user_id=stored_text(row["user_id"]),
            portfolio_id=stored_text(row["portfolio_id"]),
            holding_id=stored_text(row["holding_id"]),
            instrument_id=stored_text(row["instrument_id"]),
            quantity=quantity_text(row["quantity_micro_units"]),
            average_cost=cost_text(row["average_cost_units"]),
            currency=stored_text(row["currency"]),
            created_at=stored_time(row["created_at"]),
            updated_at=stored_time(row["updated_at"]),
        ),
        user_id=user_id,
        portfolio_id=portfolio_id,
    )


def _limit(value: int, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError("The manual collection query is not bounded.")


class SQLiteLocalPortfolioTransaction(SQLiteAuthorizationTransaction):
    def get_portfolio(self, user_id: str, portfolio_id: str) -> LocalPortfolioRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_manual_portfolios WHERE user_id=? AND portfolio_id=?",
            (user_id, portfolio_id),
        ).fetchone()
        return _portfolio(row, user_id) if row is not None else None

    def list_portfolios(self, user_id: str, *, limit: int) -> list[LocalPortfolioRecord]:
        _limit(limit, PORTFOLIO_LIMIT + 1)
        rows = self._connection.execute(
            "SELECT * FROM local_manual_portfolios WHERE user_id=? "
            "ORDER BY created_at,portfolio_id LIMIT ?",
            (user_id, PORTFOLIO_LIMIT + 1),
        ).fetchall()
        records = [_portfolio(row, user_id) for row in rows]
        # UTC strings may use equivalent Z/+00:00 forms. Compare real instants
        # before slicing the bounded owned collection, not raw timestamp text.
        records.sort(key=lambda record: (record.created_at, record.portfolio_id))
        return records[:limit]

    def _count(self, statement: str, parameters: tuple[str, ...]) -> int:
        row = self._connection.execute(statement, parameters).fetchone()
        if row is None:
            raise ValueError("The manual collection count is missing.")
        count = stored_integer(row[0])
        if count < 0:
            raise ValueError("The manual collection count is invalid.")
        return count

    def count_portfolios(self, user_id: str) -> int:
        return self._count(
            "SELECT COUNT(*) FROM local_manual_portfolios WHERE user_id=?", (user_id,)
        )

    def insert_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        validate_portfolio_record(record)
        self._connection.execute(
            """INSERT INTO local_manual_portfolios(
            portfolio_id,user_id,name,description,currency,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                record.portfolio_id,
                record.user_id,
                record.name,
                record.description,
                record.currency,
                utc_text(record.created_at),
                utc_text(record.updated_at),
            ),
        )
        return record

    def update_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        validate_portfolio_record(record)
        previous = self.get_portfolio(record.user_id, record.portfolio_id)
        if previous is None or record.created_at != previous.created_at:
            raise ValueError("The manual update is not an existing immutable resource.")
        if (record.name, record.description, record.currency) == (
            previous.name,
            previous.description,
            previous.currency,
        ):
            return previous
        changed = self._connection.execute(
            "UPDATE local_manual_portfolios SET name=?,description=?,currency=?,updated_at=? "
            "WHERE user_id=? AND portfolio_id=?",
            (
                record.name,
                record.description,
                record.currency,
                utc_text(record.updated_at),
                record.user_id,
                record.portfolio_id,
            ),
        )
        if changed.rowcount != 1:
            raise ValueError("The manual update did not change an owned resource.")
        return record

    def delete_portfolio(self, user_id: str, portfolio_id: str) -> bool:
        deleted = self._connection.execute(
            "DELETE FROM local_manual_portfolios WHERE user_id=? AND portfolio_id=?",
            (user_id, portfolio_id),
        )
        return deleted.rowcount == 1

    def get_holding(
        self, user_id: str, portfolio_id: str, holding_id: str
    ) -> LocalHoldingRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_manual_holdings "
            "WHERE user_id=? AND portfolio_id=? AND holding_id=?",
            (user_id, portfolio_id, holding_id),
        ).fetchone()
        return _holding(row, user_id, portfolio_id) if row is not None else None

    def list_holdings(
        self, user_id: str, portfolio_id: str, *, limit: int
    ) -> list[LocalHoldingRecord]:
        _limit(limit, HOLDING_LIMIT + 1)
        rows = self._connection.execute(
            "SELECT * FROM local_manual_holdings WHERE user_id=? AND portfolio_id=? "
            "ORDER BY created_at,holding_id LIMIT ?",
            (user_id, portfolio_id, HOLDING_LIMIT + 1),
        ).fetchall()
        records = [_holding(row, user_id, portfolio_id) for row in rows]
        records.sort(key=lambda record: (record.created_at, record.holding_id))
        return records[:limit]

    def count_holdings(self, user_id: str, portfolio_id: str) -> int:
        return self._count(
            "SELECT COUNT(*) FROM local_manual_holdings WHERE user_id=? AND portfolio_id=?",
            (user_id, portfolio_id),
        )

    def get_holding_by_instrument(
        self, user_id: str, portfolio_id: str, instrument_id: str
    ) -> LocalHoldingRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_manual_holdings "
            "WHERE user_id=? AND portfolio_id=? AND instrument_id=?",
            (user_id, portfolio_id, instrument_id),
        ).fetchone()
        return _holding(row, user_id, portfolio_id) if row is not None else None

    def insert_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord:
        validate_holding_record(record)
        self._connection.execute(
            """INSERT INTO local_manual_holdings(
            holding_id,user_id,portfolio_id,instrument_id,quantity_micro_units,average_cost_units,
            currency,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                record.holding_id,
                record.user_id,
                record.portfolio_id,
                record.instrument_id,
                quantity_units(record.quantity),
                cost_units(record.average_cost),
                record.currency,
                utc_text(record.created_at),
                utc_text(record.updated_at),
            ),
        )
        return record

    def update_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord:
        validate_holding_record(record)
        previous = self.get_holding(record.user_id, record.portfolio_id, record.holding_id)
        if (
            previous is None
            or record.created_at != previous.created_at
            or record.instrument_id != previous.instrument_id
        ):
            raise ValueError("The manual update changed an immutable holding field.")
        if (record.quantity, record.average_cost, record.currency) == (
            previous.quantity,
            previous.average_cost,
            previous.currency,
        ):
            return previous
        changed = self._connection.execute(
            "UPDATE local_manual_holdings SET quantity_micro_units=?,average_cost_units=?,"
            "currency=?,updated_at=? WHERE user_id=? AND portfolio_id=? AND holding_id=?",
            (
                quantity_units(record.quantity),
                cost_units(record.average_cost),
                record.currency,
                utc_text(record.updated_at),
                record.user_id,
                record.portfolio_id,
                record.holding_id,
            ),
        )
        if changed.rowcount != 1:
            raise ValueError("The manual update did not change an owned holding.")
        return record

    def delete_holding(self, user_id: str, portfolio_id: str, holding_id: str) -> bool:
        deleted = self._connection.execute(
            "DELETE FROM local_manual_holdings WHERE user_id=? AND portfolio_id=? AND holding_id=?",
            (user_id, portfolio_id, holding_id),
        )
        return deleted.rowcount == 1


class SQLiteLocalPortfolioStore(SQLiteTransactionStore[LocalPortfolioTransaction]):
    """Lazily constructs the shared schema and only this manual capability."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, SQLiteLocalPortfolioTransaction)
