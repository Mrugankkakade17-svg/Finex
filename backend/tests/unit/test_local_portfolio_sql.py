"""Real physical manual-table constraints; application type validation is separate.

SQLite affinity may turn an exactly integral binding into stored INTEGER. These
tests claim only the stored-type and bound checks, never original JSON typing.
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.local_application import LocalUser
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
OWNER = "synthetic-owner-a"
OTHER = "synthetic-owner-b"


def prepare_owners(path: Path) -> None:
    with SQLiteLocalApplicationStore(path).transaction(write=True) as transaction:
        transaction.create_user(LocalUser(OWNER, "learner-a"), "profile.v1", NOW)
        transaction.create_user(LocalUser(OTHER, "learner-b"), "profile.v1", NOW)


def insert_portfolio(connection: sqlite3.Connection, owner: str, portfolio_id: str) -> None:
    connection.execute(
        "INSERT INTO local_manual_portfolios VALUES(?,?,?,NULL,'USD',?,?)",
        (portfolio_id, owner, "Synthetic portfolio", NOW.isoformat(), NOW.isoformat()),
    )


def insert_holding(
    connection: sqlite3.Connection,
    owner: str,
    portfolio_id: str,
    *,
    holding_id: str | None = None,
    instrument: str = "SYN:AAPL",
    quantity: object = 1,
    cost: object = 0,
) -> None:
    connection.execute(
        "INSERT INTO local_manual_holdings VALUES(?,?,?,?,?,?,'USD',?,?)",
        (
            holding_id or str(uuid4()),
            owner,
            portfolio_id,
            instrument,
            quantity,
            cost,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def test_composite_owner_parent_fk_and_owned_instrument_uniqueness_are_physical(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manual-fk-unique.sqlite3"
    prepare_owners(path)
    first_parent, second_parent = str(uuid4()), str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        insert_portfolio(connection, OWNER, first_parent)
        insert_portfolio(connection, OTHER, second_parent)
        insert_holding(connection, OWNER, first_parent)
        with pytest.raises(sqlite3.IntegrityError):
            insert_holding(connection, OTHER, first_parent)
        with pytest.raises(sqlite3.IntegrityError):
            insert_holding(connection, OWNER, str(uuid4()))
        with pytest.raises(sqlite3.IntegrityError):
            insert_holding(connection, OWNER, first_parent)
        insert_holding(connection, OTHER, second_parent)
        insert_holding(connection, OWNER, first_parent, instrument="SYN:BND")
        connection.commit()
        assert connection.execute("SELECT COUNT(*) FROM local_manual_holdings").fetchone()[0] == 3


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", 0),
        ("quantity", -1),
        ("quantity", 1_000_000_000_001),
        ("quantity", 0.5),
        ("quantity", "invalid"),
        ("cost", -1),
        ("cost", 10_000_000_001),
        ("cost", 0.5),
        ("cost", "invalid"),
    ],
)
def test_stored_micro_and_cost_values_enforce_integer_type_and_bounds(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "manual-unit-check.sqlite3"
    prepare_owners(path)
    parent = str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        insert_portfolio(connection, OWNER, parent)
        with pytest.raises(sqlite3.IntegrityError):
            insert_holding(
                connection,
                OWNER,
                parent,
                quantity=value if field == "quantity" else 1,
                cost=value if field == "cost" else 0,
            )


def test_exact_maximum_units_remain_integers_without_sql_multiplication(tmp_path: Path) -> None:
    path = tmp_path / "manual-max-units.sqlite3"
    prepare_owners(path)
    parent = str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        insert_portfolio(connection, OWNER, parent)
        insert_holding(connection, OWNER, parent, quantity=1_000_000_000_000, cost=10_000_000_000)
        row = connection.execute(
            "SELECT quantity_micro_units,typeof(quantity_micro_units),"
            "average_cost_units,typeof(average_cost_units) FROM local_manual_holdings"
        ).fetchone()
        assert row == (1_000_000_000_000, "integer", 10_000_000_000, "integer")


def test_manual_cascade_never_deletes_other_owners_or_immutable_risk_history(
    tmp_path: Path,
) -> None:
    path = tmp_path / "manual-owned-cascade.sqlite3"
    prepare_owners(path)
    first_parent, second_parent = str(uuid4()), str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        insert_portfolio(connection, OWNER, first_parent)
        insert_portfolio(connection, OTHER, second_parent)
        insert_holding(connection, OWNER, first_parent)
        insert_holding(connection, OTHER, second_parent)
        connection.execute(
            "INSERT INTO local_risk_assessments(assessment_id,user_id,idempotency_key,"
            "request_fingerprint,document_json,created_at) VALUES(?,?,?,?,?,?)",
            (
                str(uuid4()),
                OWNER,
                str(uuid4()),
                "b" * 64,
                '{"synthetic_sql":"opaque"}',
                NOW.isoformat(),
            ),
        )
        connection.commit()
        connection.execute(
            "DELETE FROM local_manual_portfolios WHERE user_id=? AND portfolio_id=?",
            (OWNER, first_parent),
        )
        connection.commit()
        assert connection.execute("SELECT user_id FROM local_manual_holdings").fetchall() == [
            (OTHER,)
        ]
        assert connection.execute("SELECT user_id FROM local_manual_portfolios").fetchall() == [
            (OTHER,)
        ]
        assert connection.execute("SELECT COUNT(*) FROM local_risk_assessments").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM local_users").fetchone()[0] == 2
