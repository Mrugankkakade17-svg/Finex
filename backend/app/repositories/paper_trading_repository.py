"""Transactional PostgreSQL persistence for paper orders, cash ledger, and positions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from app.config.settings import Settings, get_settings
from app.ports.adapters.postgres_local_store import postgres_dsn

_CENT = Decimal("0.01")
_UNIT = Decimal("0.000001")


def _stored_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Persisted paper order integer has an invalid type.")
    return value


def _stored_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError("Persisted paper order decimal has an invalid type.")
    return value


@dataclass(frozen=True)
class PaperOrderRecord:
    order_id: str
    account_id: str
    user_id: str
    idempotency_key: str
    request_fingerprint: str
    instrument_id: str
    exchange: str
    side: str
    quantity: int
    executed_price: Decimal
    notional_cents: int
    fee_cents: int
    cash_delta_cents: int
    balance_after_cents: int
    quote_freshness: str
    quote_as_of: str | None
    created_at: datetime


class PaperPositionRow(TypedDict):
    instrument_id: str
    exchange: str
    quantity: int
    average_cost: Decimal
    last_price: Decimal


class PaperAccountSnapshot(TypedDict):
    account_id: str
    cash_balance_cents: int
    positions: list[PaperPositionRow]
    recent_orders: list[PaperOrderRecord]


class PaperTradingConflict(Exception):
    """An order conflicts with the user's current paper account state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PaperTradingStoreUnavailable(Exception):
    """The durable paper trading store is not configured or unavailable."""


class PostgresPaperTradingRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _connect(self):
        database_url = self._settings.app_database_url or os.getenv("DATABASE_URL", "")
        if not database_url:
            raise PaperTradingStoreUnavailable("Paper trading persistence is not configured.")
        try:
            return psycopg.connect(postgres_dsn(database_url), row_factory=dict_row)
        except (psycopg.Error, ValueError) as exc:
            raise PaperTradingStoreUnavailable("Paper trading persistence is unavailable.") from exc

    @staticmethod
    def _to_record(row: dict[str, object], balance_after_cents: int = 0) -> PaperOrderRecord:
        return PaperOrderRecord(
            order_id=str(row["order_id"]),
            account_id=str(row["account_id"]),
            user_id=str(row["user_id"]),
            idempotency_key=str(row["idempotency_key"]),
            request_fingerprint=str(row["request_fingerprint"]),
            instrument_id=str(row["instrument_id"]),
            exchange=str(row["exchange"]),
            side=str(row["side"]),
            quantity=_stored_int(row["quantity"]),
            executed_price=_stored_decimal(row["executed_price"]),
            notional_cents=_stored_int(row["notional_cents"]),
            fee_cents=_stored_int(row["fee_cents"]),
            cash_delta_cents=_stored_int(row["cash_delta_cents"]),
            balance_after_cents=balance_after_cents,
            quote_freshness=str(row["quote_freshness"]),
            quote_as_of=str(row["quote_as_of"]) if row["quote_as_of"] is not None else None,
            created_at=row["created_at"],  # type: ignore[arg-type]
        )

    def find_order(self, user_id: str, idempotency_key: str) -> PaperOrderRecord | None:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM finex.paper_orders WHERE user_id=%s AND idempotency_key=%s",
                    (user_id, idempotency_key),
                ).fetchone()
                if row is None:
                    return None
                return self._to_record(row)
        except PaperTradingStoreUnavailable:
            raise
        except psycopg.Error as exc:
            raise PaperTradingStoreUnavailable("Paper trading persistence is unavailable.") from exc

    def execute_order(
        self,
        order: PaperOrderRecord,
        *,
        initial_cash_cents: int,
    ) -> tuple[PaperOrderRecord, bool]:
        """Lock the account and atomically persist exactly one fill and its ledger effect."""
        try:
            with self._connect() as connection:
                inserted = connection.execute(
                    "INSERT INTO finex.paper_accounts(account_id,user_id,currency) "
                    "VALUES(%s,%s,'USD') ON CONFLICT(user_id) DO NOTHING "
                    "RETURNING account_id",
                    (order.account_id, order.user_id),
                ).fetchone()
                if inserted is not None:
                    connection.execute(
                        "INSERT INTO finex.paper_ledger "
                        "(ledger_id,account_id,user_id,cash_delta_cents) VALUES(%s,%s,%s,%s)",
                        (
                            f"ledger-{uuid4().hex}",
                            order.account_id,
                            order.user_id,
                            initial_cash_cents,
                        ),
                    )

                account = connection.execute(
                    "SELECT account_id FROM finex.paper_accounts WHERE user_id=%s FOR UPDATE",
                    (order.user_id,),
                ).fetchone()
                if account is None:
                    raise PaperTradingStoreUnavailable("Paper account could not be initialized.")
                account_id = str(account["account_id"])

                existing = connection.execute(
                    "SELECT * FROM finex.paper_orders WHERE user_id=%s AND idempotency_key=%s",
                    (order.user_id, order.idempotency_key),
                ).fetchone()
                if existing is not None:
                    saved = self._to_record(existing)
                    if saved.request_fingerprint != order.request_fingerprint:
                        raise PaperTradingConflict(
                            "IDEMPOTENCY_KEY_REUSED",
                            "The idempotency key was already used for a different order.",
                        )
                    balance = self._balance(connection, account_id)
                    return self._to_record(existing, balance), False

                balance_before = self._balance(connection, account_id)
                balance_after = balance_before + order.cash_delta_cents
                if balance_after < 0:
                    raise PaperTradingConflict(
                        "INSUFFICIENT_CASH", "The order would make paper cash negative."
                    )

                position = connection.execute(
                    "SELECT quantity,average_cost FROM finex.paper_positions "
                    "WHERE account_id=%s AND instrument_id=%s AND exchange=%s FOR UPDATE",
                    (account_id, order.instrument_id, order.exchange),
                ).fetchone()
                old_quantity = int(position["quantity"]) if position is not None else 0
                old_average = (
                    Decimal(position["average_cost"]) if position is not None else Decimal(0)
                )
                if order.side == "SELL" and old_quantity < order.quantity:
                    raise PaperTradingConflict(
                        "INSUFFICIENT_POSITION", "There are not enough shares to sell."
                    )

                if order.side == "BUY":
                    new_quantity = old_quantity + order.quantity
                    total_cost = (
                        old_average * old_quantity
                        + Decimal(order.notional_cents + order.fee_cents) / 100
                    )
                    average_cost = (total_cost / new_quantity).quantize(
                        _UNIT, rounding=ROUND_HALF_UP
                    )
                    connection.execute(
                        "INSERT INTO finex.paper_positions "
                        "(account_id,user_id,instrument_id,exchange,quantity,"
                        "average_cost,last_price) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT(account_id,instrument_id,exchange) DO UPDATE SET "
                        "quantity=EXCLUDED.quantity,average_cost=EXCLUDED.average_cost, "
                        "last_price=EXCLUDED.last_price,updated_at=NOW()",
                        (
                            account_id,
                            order.user_id,
                            order.instrument_id,
                            order.exchange,
                            new_quantity,
                            average_cost,
                            order.executed_price,
                        ),
                    )
                else:
                    new_quantity = old_quantity - order.quantity
                    if new_quantity == 0:
                        connection.execute(
                            "DELETE FROM finex.paper_positions WHERE account_id=%s "
                            "AND instrument_id=%s AND exchange=%s",
                            (account_id, order.instrument_id, order.exchange),
                        )
                    else:
                        connection.execute(
                            "UPDATE finex.paper_positions SET quantity=%s,last_price=%s,"
                            "updated_at=NOW() "
                            "WHERE account_id=%s AND instrument_id=%s AND exchange=%s",
                            (
                                new_quantity,
                                order.executed_price,
                                account_id,
                                order.instrument_id,
                                order.exchange,
                            ),
                        )

                saved_order = connection.execute(
                    "INSERT INTO finex.paper_orders "
                    "(order_id,account_id,user_id,idempotency_key,request_fingerprint,"
                    "instrument_id,exchange,side,quantity,executed_price,notional_cents,fee_cents,"
                    "cash_delta_cents,quote_freshness,quote_as_of) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (
                        order.order_id,
                        account_id,
                        order.user_id,
                        order.idempotency_key,
                        order.request_fingerprint,
                        order.instrument_id,
                        order.exchange,
                        order.side,
                        order.quantity,
                        order.executed_price,
                        order.notional_cents,
                        order.fee_cents,
                        order.cash_delta_cents,
                        order.quote_freshness,
                        order.quote_as_of,
                    ),
                ).fetchone()
                if saved_order is None:
                    raise PaperTradingStoreUnavailable("Paper order was not persisted.")
                connection.execute(
                    "INSERT INTO finex.paper_ledger "
                    "(ledger_id,account_id,user_id,cash_delta_cents) VALUES(%s,%s,%s,%s)",
                    (
                        f"ledger-{uuid4().hex}",
                        account_id,
                        order.user_id,
                        order.cash_delta_cents,
                    ),
                )
                return self._to_record(saved_order, balance_after), True
        except (PaperTradingConflict, PaperTradingStoreUnavailable):
            raise
        except psycopg.Error as exc:
            raise PaperTradingStoreUnavailable("Paper order could not be committed.") from exc

    @staticmethod
    def _balance(connection, account_id: str) -> int:
        row = connection.execute(
            "SELECT COALESCE(SUM(cash_delta_cents),0) AS balance "
            "FROM finex.paper_ledger WHERE account_id=%s",
            (account_id,),
        ).fetchone()
        if row is None:
            return 0
        return int(row["balance"])

    def account_snapshot(self, user_id: str, *, initial_cash_cents: int) -> PaperAccountSnapshot:
        account_id = f"paper-{uuid4().hex}"
        try:
            with self._connect() as connection:
                inserted = connection.execute(
                    "INSERT INTO finex.paper_accounts(account_id,user_id,currency) "
                    "VALUES(%s,%s,'USD') ON CONFLICT(user_id) DO NOTHING "
                    "RETURNING account_id",
                    (account_id, user_id),
                ).fetchone()
                if inserted is not None:
                    connection.execute(
                        "INSERT INTO finex.paper_ledger "
                        "(ledger_id,account_id,user_id,cash_delta_cents) VALUES(%s,%s,%s,%s)",
                        (f"ledger-{uuid4().hex}", account_id, user_id, initial_cash_cents),
                    )
                account = connection.execute(
                    "SELECT account_id FROM finex.paper_accounts WHERE user_id=%s",
                    (user_id,),
                ).fetchone()
                if account is None:
                    raise PaperTradingStoreUnavailable("Paper account could not be initialized.")
                account_id = str(account["account_id"])
                positions = connection.execute(
                    "SELECT instrument_id,exchange,quantity,average_cost,last_price "
                    "FROM finex.paper_positions WHERE account_id=%s "
                    "ORDER BY instrument_id,exchange",
                    (account_id,),
                ).fetchall()
                orders = connection.execute(
                    "SELECT * FROM finex.paper_orders WHERE account_id=%s "
                    "ORDER BY created_at DESC,order_id DESC LIMIT 10",
                    (account_id,),
                ).fetchall()
                return {
                    "account_id": account_id,
                    "cash_balance_cents": self._balance(connection, account_id),
                    "positions": [
                        PaperPositionRow(
                            instrument_id=str(row["instrument_id"]),
                            exchange=str(row["exchange"]),
                            quantity=_stored_int(row["quantity"]),
                            average_cost=_stored_decimal(row["average_cost"]),
                            last_price=_stored_decimal(row["last_price"]),
                        )
                        for row in positions
                    ],
                    "recent_orders": [self._to_record(row) for row in orders],
                }
        except PaperTradingStoreUnavailable:
            raise
        except psycopg.Error as exc:
            raise PaperTradingStoreUnavailable("Paper account could not be loaded.") from exc

    def list_orders(self, user_id: str, *, limit: int) -> list[PaperOrderRecord]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM finex.paper_orders WHERE user_id=%s "
                    "ORDER BY created_at DESC,order_id DESC LIMIT %s",
                    (user_id, limit),
                ).fetchall()
                return [self._to_record(row) for row in rows]
        except PaperTradingStoreUnavailable:
            raise
        except psycopg.Error as exc:
            raise PaperTradingStoreUnavailable("Paper orders could not be loaded.") from exc
