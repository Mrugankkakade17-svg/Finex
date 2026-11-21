"""PostgreSQL implementation of manual portfolio persistence."""

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
from app.ports.adapters.postgres_local_store import (
    PostgresAuthorizationTransaction,
    PostgresTransactionStore,
    stored_integer,
    stored_text,
    stored_time,
)
from app.ports.local_portfolio_store import LocalPortfolioTransaction


def _portfolio(row: dict, user_id: str) -> LocalPortfolioRecord:
    return validate_portfolio_record(
        LocalPortfolioRecord(
            user_id=stored_text(row["user_id"]),
            portfolio_id=stored_text(row["portfolio_id"]),
            name=stored_text(row["name"]),
            description=row["description"],
            currency=stored_text(row["currency"]),
            created_at=stored_time(row["created_at"]),
            updated_at=stored_time(row["updated_at"]),
        ),
        user_id=user_id,
    )


def _holding(row: dict, user_id: str, portfolio_id: str) -> LocalHoldingRecord:
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


class PostgresLocalPortfolioTransaction(PostgresAuthorizationTransaction):
    def get_portfolio(self, user_id: str, portfolio_id: str) -> LocalPortfolioRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_manual_portfolios WHERE user_id=%s AND portfolio_id=%s",
            (user_id, portfolio_id),
        ).fetchone()
        return _portfolio(row, user_id) if row else None

    def list_portfolios(self, user_id: str, *, limit: int) -> list[LocalPortfolioRecord]:
        if type(limit) is not int or not 1 <= limit <= PORTFOLIO_LIMIT + 1:
            raise ValueError("The manual collection query is not bounded.")
        rows = self._connection.execute(
            "SELECT * FROM finex.local_manual_portfolios WHERE user_id=%s "
            "ORDER BY created_at,portfolio_id LIMIT %s",
            (user_id, limit),
        ).fetchall()
        return [_portfolio(row, user_id) for row in rows]

    def count_portfolios(self, user_id: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM finex.local_manual_portfolios WHERE user_id=%s",
            (user_id,),
        ).fetchone()
        return stored_integer(row["count"])

    def insert_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        validate_portfolio_record(record)
        self._connection.execute(
            "INSERT INTO finex.local_manual_portfolios"
            "(portfolio_id,user_id,name,description,currency,created_at,updated_at)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                record.portfolio_id,
                record.user_id,
                record.name,
                record.description,
                record.currency,
                record.created_at,
                record.updated_at,
            ),
        )
        return record

    def update_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        validate_portfolio_record(record)
        previous = self.get_portfolio(record.user_id, record.portfolio_id)
        if previous is None or record.created_at != previous.created_at:
            raise ValueError("The manual update is not an existing immutable resource.")
        changed = self._connection.execute(
            "UPDATE finex.local_manual_portfolios "
            "SET name=%s,description=%s,currency=%s,updated_at=%s "
            "WHERE user_id=%s AND portfolio_id=%s",
            (
                record.name,
                record.description,
                record.currency,
                record.updated_at,
                record.user_id,
                record.portfolio_id,
            ),
        )
        if changed.rowcount != 1:
            raise ValueError("The manual update did not change an owned resource.")
        return record

    def delete_portfolio(self, user_id: str, portfolio_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM finex.local_manual_portfolios WHERE user_id=%s AND portfolio_id=%s",
            (user_id, portfolio_id),
        )
        return changed.rowcount == 1

    def get_holding(
        self, user_id: str, portfolio_id: str, holding_id: str
    ) -> LocalHoldingRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_manual_holdings "
            "WHERE user_id=%s AND portfolio_id=%s AND holding_id=%s",
            (user_id, portfolio_id, holding_id),
        ).fetchone()
        return _holding(row, user_id, portfolio_id) if row else None

    def list_holdings(
        self, user_id: str, portfolio_id: str, *, limit: int
    ) -> list[LocalHoldingRecord]:
        if type(limit) is not int or not 1 <= limit <= HOLDING_LIMIT + 1:
            raise ValueError("The manual collection query is not bounded.")
        rows = self._connection.execute(
            "SELECT * FROM finex.local_manual_holdings WHERE user_id=%s AND portfolio_id=%s "
            "ORDER BY created_at,holding_id LIMIT %s",
            (user_id, portfolio_id, limit),
        ).fetchall()
        return [_holding(row, user_id, portfolio_id) for row in rows]

    def count_holdings(self, user_id: str, portfolio_id: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM finex.local_manual_holdings "
            "WHERE user_id=%s AND portfolio_id=%s",
            (user_id, portfolio_id),
        ).fetchone()
        return stored_integer(row["count"])

    def get_holding_by_instrument(
        self, user_id: str, portfolio_id: str, instrument_id: str
    ) -> LocalHoldingRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_manual_holdings "
            "WHERE user_id=%s AND portfolio_id=%s AND instrument_id=%s",
            (user_id, portfolio_id, instrument_id),
        ).fetchone()
        return _holding(row, user_id, portfolio_id) if row else None

    def insert_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord:
        validate_holding_record(record)
        self._connection.execute(
            "INSERT INTO finex.local_manual_holdings"
            "(holding_id,user_id,portfolio_id,instrument_id,quantity_micro_units,average_cost_units,currency,created_at,updated_at)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                record.holding_id,
                record.user_id,
                record.portfolio_id,
                record.instrument_id,
                quantity_units(record.quantity),
                cost_units(record.average_cost),
                record.currency,
                record.created_at,
                record.updated_at,
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
        changed = self._connection.execute(
            "UPDATE finex.local_manual_holdings SET quantity_micro_units=%s,average_cost_units=%s,"
            "currency=%s,updated_at=%s WHERE user_id=%s AND portfolio_id=%s AND holding_id=%s",
            (
                quantity_units(record.quantity),
                cost_units(record.average_cost),
                record.currency,
                record.updated_at,
                record.user_id,
                record.portfolio_id,
                record.holding_id,
            ),
        )
        if changed.rowcount != 1:
            raise ValueError("The manual update did not change an owned holding.")
        return record

    def delete_holding(self, user_id: str, portfolio_id: str, holding_id: str) -> bool:
        changed = self._connection.execute(
            "DELETE FROM finex.local_manual_holdings "
            "WHERE user_id=%s AND portfolio_id=%s AND holding_id=%s",
            (user_id, portfolio_id, holding_id),
        )
        return changed.rowcount == 1


class PostgresLocalPortfolioStore(PostgresTransactionStore[LocalPortfolioTransaction]):
    def __init__(self, database_url: str) -> None:
        super().__init__(database_url, PostgresLocalPortfolioTransaction)
