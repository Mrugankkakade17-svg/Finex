"""Typed manual persistence behavior, written before the dedicated adapter.

The preceding schema/SQL tests supply genuine RED. No missing-module failure is
claimed as RED evidence for this new adapter's import. All fixtures are owned
temporary synthetic records; there are no tokens, developer files or providers.
"""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.local_application import LocalStoreUnavailable, LocalUser
from app.domain.local_portfolio import LocalHoldingRecord, LocalPortfolioRecord
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_portfolio_store import SQLiteLocalPortfolioStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
LATER = NOW + timedelta(seconds=2)
OWNER = "synthetic-owner-a"
OTHER = "synthetic-owner-b"


def portfolio(
    owner: str = OWNER, *, resource_id: str | None = None, stamp: datetime = NOW
) -> LocalPortfolioRecord:
    return LocalPortfolioRecord(
        owner, resource_id or str(uuid4()), "Synthetic", None, "USD", stamp, stamp
    )


def holding(
    parent: LocalPortfolioRecord, *, instrument: str = "SYN:AAPL", stamp: datetime = NOW
) -> LocalHoldingRecord:
    return LocalHoldingRecord(
        parent.user_id,
        parent.portfolio_id,
        str(uuid4()),
        instrument,
        "1.000001",
        "0.0000",
        "USD",
        stamp,
        stamp,
    )


def owned_store(path: Path) -> SQLiteLocalPortfolioStore:
    with SQLiteLocalApplicationStore(path).transaction(write=True) as transaction:
        transaction.create_user(LocalUser(OWNER, "learner-a"), "profile.v1", NOW)
        transaction.create_user(LocalUser(OTHER, "learner-b"), "profile.v1", NOW)
    return SQLiteLocalPortfolioStore(path)


def seeded_store(
    path: Path,
) -> tuple[SQLiteLocalPortfolioStore, LocalPortfolioRecord, LocalHoldingRecord]:
    store = owned_store(path)
    parent = portfolio()
    child = holding(parent)
    with store.transaction(write=True) as transaction:
        assert transaction.insert_portfolio(parent) == parent
        assert transaction.insert_holding(child) == child
    return store, parent, child


def test_constructor_is_lazy_and_capability_has_only_auth_and_manual_operations(
    tmp_path: Path,
) -> None:
    path = tmp_path / "absent" / "lazy.sqlite3"
    store = SQLiteLocalPortfolioStore(path)
    assert not path.parent.exists()
    with store.transaction() as transaction:
        for name in (
            "get_session",
            "get_onboarding",
            "latest_consent",
            "get_portfolio",
            "list_portfolios",
            "count_portfolios",
            "insert_portfolio",
            "update_portfolio",
            "delete_portfolio",
            "get_holding",
            "list_holdings",
            "count_holdings",
            "get_holding_by_instrument",
            "insert_holding",
            "update_holding",
            "delete_holding",
        ):
            assert callable(getattr(transaction, name))
        for name in ("create_user", "revoke_session", "save_onboarding", "insert_risk_assessment"):
            assert not hasattr(transaction, name)


def test_owned_crud_restart_and_independent_parent_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "owned-manual.sqlite3"
    store, parent, child = seeded_store(path)
    updated_parent = replace(parent, name="Renamed", description="", updated_at=LATER)
    updated_child = replace(
        child, quantity="1000000.000000", average_cost="1000000.0000", updated_at=LATER
    )
    with store.transaction(write=True) as transaction:
        assert transaction.update_portfolio(updated_parent) == updated_parent
        assert transaction.update_holding(updated_child) == updated_child
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == updated_parent
    with SQLiteLocalPortfolioStore(path).transaction() as transaction:
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == updated_parent
        assert (
            transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == updated_child
        )
        assert (
            transaction.get_holding_by_instrument(OWNER, parent.portfolio_id, "SYN:AAPL")
            == updated_child
        )
        assert transaction.list_portfolios(OWNER, limit=21) == [updated_parent]
        assert transaction.list_holdings(OWNER, parent.portfolio_id, limit=101) == [updated_child]
        assert transaction.count_portfolios(OWNER) == 1
        assert transaction.count_holdings(OWNER, parent.portfolio_id) == 1
    with store.transaction(write=True) as transaction:
        assert transaction.delete_holding(OWNER, parent.portfolio_id, child.holding_id)
        assert not transaction.delete_holding(OWNER, parent.portfolio_id, child.holding_id)
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == updated_parent
        assert transaction.delete_portfolio(OWNER, parent.portfolio_id)
        assert not transaction.delete_portfolio(OWNER, parent.portfolio_id)


def test_identical_put_is_a_physical_noop_and_retains_original_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "no-op.sqlite3"
    store, parent, child = seeded_store(path)
    updates: list[bool] = []

    class ObservedStore(SQLiteLocalPortfolioStore):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()

            def observe(statement: str) -> None:
                if statement.startswith("UPDATE local_manual_"):
                    updates.append(True)  # Never retain expanded SQL/values.

            connection.set_trace_callback(observe)
            return connection

    with ObservedStore(path).transaction(write=True) as transaction:
        assert transaction.update_portfolio(replace(parent, updated_at=LATER)) == parent
        assert transaction.update_holding(replace(child, updated_at=LATER)) == child
    assert updates == []
    with store.transaction() as transaction:
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == parent
        assert transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == child


def test_null_and_empty_description_are_distinct_mutations(tmp_path: Path) -> None:
    path = tmp_path / "nullable-description.sqlite3"
    store, parent, _ = seeded_store(path)
    empty = replace(parent, description="", updated_at=LATER)
    with store.transaction(write=True) as transaction:
        assert transaction.update_portfolio(empty) == empty
    with store.transaction() as transaction:
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == empty


def test_all_holding_crud_leaves_parent_timestamp_unchanged(tmp_path: Path) -> None:
    store = owned_store(tmp_path / "independent-parent-time.sqlite3")
    parent = portfolio()
    child = holding(parent, stamp=LATER)
    with store.transaction(write=True) as transaction:
        transaction.insert_portfolio(parent)
        transaction.insert_holding(child)
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == parent
    with store.transaction(write=True) as transaction:
        transaction.update_holding(
            replace(child, quantity="2.000000", updated_at=LATER + timedelta(seconds=2))
        )
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == parent
    with store.transaction(write=True) as transaction:
        assert transaction.delete_holding(OWNER, parent.portfolio_id, child.holding_id)
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == parent


@pytest.mark.parametrize(
    "column,value",
    [
        ("quantity_micro_units", 0),
        ("quantity_micro_units", 0.5),
        ("average_cost_units", -1),
        ("average_cost_units", 0.5),
        ("holding_id", "not-a-canonical-resource"),
        ("instrument_id", "guessed-symbol"),
    ],
)
def test_corrupt_stored_units_and_resource_fields_fail_closed_on_bounded_read(
    tmp_path: Path, column: str, value: object
) -> None:
    path = tmp_path / "corrupt-stored-manual.sqlite3"
    store, parent, _ = seeded_store(path)
    with closing(sqlite3.connect(path)) as connection:
        # Fault injection is confined to this owned fixture and this separate
        # connection. The production store never disables CHECK enforcement.
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"UPDATE local_manual_holdings SET {column}=?", (value,))
        connection.commit()
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.list_holdings(OWNER, parent.portfolio_id, limit=101)


def test_every_owned_read_and_delete_includes_owner_and_parent(tmp_path: Path) -> None:
    path = tmp_path / "owner-parent.sqlite3"
    store, parent, child = seeded_store(path)
    second = portfolio()
    with store.transaction(write=True) as transaction:
        transaction.insert_portfolio(second)
        assert transaction.get_portfolio(OTHER, parent.portfolio_id) is None
        assert transaction.get_holding(OTHER, parent.portfolio_id, child.holding_id) is None
        assert transaction.get_holding(OWNER, second.portfolio_id, child.holding_id) is None
        assert transaction.get_holding_by_instrument(OTHER, parent.portfolio_id, "SYN:AAPL") is None
        assert transaction.list_portfolios(OTHER, limit=21) == []
        assert transaction.list_holdings(OTHER, parent.portfolio_id, limit=101) == []
        assert transaction.count_portfolios(OTHER) == 0
        assert transaction.count_holdings(OTHER, parent.portfolio_id) == 0
        assert not transaction.delete_portfolio(OTHER, parent.portfolio_id)
        assert not transaction.delete_holding(OTHER, parent.portfolio_id, child.holding_id)
        assert not transaction.delete_holding(OWNER, second.portfolio_id, child.holding_id)
    with store.transaction() as transaction:
        assert transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == child


@pytest.mark.parametrize("operation", ["portfolio", "holding"])
def test_cross_owner_update_cannot_replace_a_record(tmp_path: Path, operation: str) -> None:
    store, parent, child = seeded_store(tmp_path / "owner-update.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            if operation == "portfolio":
                transaction.update_portfolio(replace(parent, user_id=OTHER, name="Not owned"))
            else:
                transaction.update_holding(replace(child, user_id=OTHER, quantity="2.000000"))
    with store.transaction() as transaction:
        assert transaction.get_portfolio(OWNER, parent.portfolio_id) == parent
        assert transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == child


@pytest.mark.parametrize("mutation", ["instrument", "parent", "created"])
def test_holding_update_rejects_immutable_field_changes(tmp_path: Path, mutation: str) -> None:
    store, parent, child = seeded_store(tmp_path / "immutable-child.sqlite3")
    replacement = (
        replace(child, instrument_id="SYN:BND")
        if mutation == "instrument"
        else replace(child, portfolio_id=str(uuid4()))
        if mutation == "parent"
        else replace(child, created_at=NOW - timedelta(seconds=1))
    )
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.update_holding(replacement)
    with store.transaction() as transaction:
        assert transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == child


def test_portfolio_update_preserves_creation_identity(tmp_path: Path) -> None:
    store, parent, _ = seeded_store(tmp_path / "immutable-parent.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.update_portfolio(replace(parent, created_at=NOW - timedelta(seconds=1)))


@pytest.mark.parametrize("limit", [0, 22, True, 1.5])
def test_portfolio_list_query_limit_is_strict_and_bounded(tmp_path: Path, limit: int) -> None:
    store, _, _ = seeded_store(tmp_path / "portfolio-limit.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.list_portfolios(OWNER, limit=limit)


@pytest.mark.parametrize("limit", [0, 102, True, 1.5])
def test_holding_list_query_limit_is_strict_and_bounded(tmp_path: Path, limit: int) -> None:
    store, parent, _ = seeded_store(tmp_path / "holding-limit.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.list_holdings(OWNER, parent.portfolio_id, limit=limit)


@pytest.mark.parametrize("field", ["quantity", "average_cost"])
@pytest.mark.parametrize("value", [True, 1, "01.000000", "NaN"])
def test_adapter_validates_strict_decimal_text_before_binding(
    tmp_path: Path, field: str, value: object
) -> None:
    store, parent, child = seeded_store(tmp_path / "typed-unit-input.sqlite3")
    invalid = replace(child, **{field: value})
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.update_holding(invalid)
    with store.transaction() as transaction:
        assert transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id) == child


@pytest.mark.parametrize("kind", ["portfolio", "holding"])
@pytest.mark.parametrize(
    "stamp", ["invalid", "2026-10-11T12:00:00", "2026-10-11T12:00:00+01:00", "2026-10-10T12:00:00Z"]
)
def test_corrupt_persisted_time_is_opaque_store_failure(
    tmp_path: Path, kind: str, stamp: str
) -> None:
    path = tmp_path / "corrupt-manual-time.sqlite3"
    store, parent, child = seeded_store(path)
    table = "local_manual_portfolios" if kind == "portfolio" else "local_manual_holdings"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"UPDATE {table} SET updated_at=?", (stamp,))
        connection.commit()
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            if kind == "portfolio":
                transaction.get_portfolio(OWNER, parent.portfolio_id)
            else:
                transaction.get_holding(OWNER, parent.portfolio_id, child.holding_id)


def test_list_order_uses_actual_utc_instants_then_ids_not_raw_text(tmp_path: Path) -> None:
    path = tmp_path / "utc-order.sqlite3"
    store = owned_store(path)
    earlier_id = "00000000-0000-4000-8000-000000000001"
    later_id = "00000000-0000-4000-8000-000000000002"
    first = portfolio(resource_id=earlier_id)
    second = portfolio(resource_id=later_id)
    first_child = replace(holding(first, instrument="SYN:BND"), holding_id=earlier_id)
    second_child = replace(holding(first), holding_id=later_id)
    with store.transaction(write=True) as transaction:
        transaction.insert_portfolio(second)
        transaction.insert_portfolio(first)
        transaction.insert_holding(second_child)
        transaction.insert_holding(first_child)
    # Both forms express the same allowed UTC instant. Raw '+' versus 'Z' order
    # would choose the larger-ID record before the smaller-ID one.
    with closing(sqlite3.connect(path)) as connection:
        for table, key in (
            ("local_manual_portfolios", "portfolio_id"),
            ("local_manual_holdings", "holding_id"),
        ):
            connection.execute(
                f"UPDATE {table} SET created_at=?,updated_at=? WHERE {key}=?",
                (NOW.isoformat().replace("+00:00", "Z"), NOW.isoformat(), earlier_id),
            )
        connection.commit()
    with store.transaction() as transaction:
        assert transaction.list_portfolios(OWNER, limit=1) == [first]
        assert transaction.list_holdings(OWNER, first.portfolio_id, limit=1) == [first_child]


class FailedCommitStore(SQLiteLocalPortfolioStore):
    def _before_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic manual domain rollback")


@pytest.mark.parametrize("operation", ["insert", "update", "child_delete", "parent_delete"])
def test_failed_domain_commit_rolls_back_whole_manual_mutation(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "manual-domain-rollback.sqlite3"
    store, parent, child = seeded_store(path)
    with pytest.raises(LocalStoreUnavailable):
        with FailedCommitStore(path).transaction(write=True) as transaction:
            if operation == "insert":
                transaction.insert_holding(holding(parent, instrument="SYN:BND"))
            elif operation == "update":
                transaction.update_portfolio(replace(parent, name="Changed", updated_at=LATER))
                transaction.update_holding(replace(child, quantity="2.000000", updated_at=LATER))
            elif operation == "child_delete":
                transaction.delete_holding(OWNER, parent.portfolio_id, child.holding_id)
            else:
                transaction.delete_portfolio(OWNER, parent.portfolio_id)
    with store.transaction() as transaction:
        assert transaction.list_portfolios(OWNER, limit=21) == [parent]
        assert transaction.list_holdings(OWNER, parent.portfolio_id, limit=101) == [child]


def test_read_unit_is_query_only_and_keeps_one_wal_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "manual-read-snapshot.sqlite3"
    store, parent, _ = seeded_store(path)
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.update_portfolio(replace(parent, name="Blocked", updated_at=LATER))
    with store.transaction() as reader:
        assert reader.count_portfolios(OWNER) == 1
        with SQLiteLocalPortfolioStore(path).transaction(write=True) as writer:
            writer.insert_portfolio(portfolio())
        assert reader.count_portfolios(OWNER) == 1
    with store.transaction() as transaction:
        assert transaction.count_portfolios(OWNER) == 2


def test_sql_parameters_do_not_turn_owner_or_ids_into_queries(tmp_path: Path) -> None:
    store, parent, child = seeded_store(tmp_path / "manual-query-parameters.sqlite3")
    injected = "' OR 1=1 --"
    with store.transaction(write=True) as transaction:
        assert transaction.get_portfolio(injected, parent.portfolio_id) is None
        assert transaction.get_portfolio(OWNER, injected) is None
        assert transaction.get_holding(injected, parent.portfolio_id, child.holding_id) is None
        assert transaction.get_holding(OWNER, parent.portfolio_id, injected) is None
        assert not transaction.delete_portfolio(injected, parent.portfolio_id)
        assert not transaction.delete_holding(OWNER, injected, child.holding_id)
        assert transaction.count_portfolios(OWNER) == 1
