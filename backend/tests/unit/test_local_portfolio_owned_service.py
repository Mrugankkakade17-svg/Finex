"""Typed in-memory behavior tests, independent of the SQLite author or HTTP router."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import FinExException
from app.domain.local_application import (
    ConsentRecord,
    LocalSession,
    LocalStoreUnavailable,
    LocalUser,
    OnboardingRecord,
)
from app.domain.local_portfolio import (
    LocalHoldingRecord,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteSnapshot,
    LocalPortfolioRecord,
)
from app.ports.local_portfolio_store import LocalPortfolioTransaction
from app.schemas.local_portfolio import (
    LocalHoldingCreateRequest,
    LocalHoldingUpdateRequest,
    LocalPortfolioRequest,
)
from app.services.local_authorization import digest_token
from app.services.local_portfolio_service import LocalPortfolioService

NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)
TOKEN_A = "a" * 43  # Synthetic, memory-only test credentials; never captured.
TOKEN_B = "b" * 43
OWNER_A = "synthetic-a"
OWNER_B = "synthetic-b"


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class MemoryPortfolioStore:
    def __init__(self) -> None:
        self.sessions = {
            digest_token(token): LocalSession(
                digest_token(token), LocalUser(owner, owner), NOW + timedelta(hours=1), None
            )
            for token, owner in ((TOKEN_A, OWNER_A), (TOKEN_B, OWNER_B))
        }
        self.profiles = {
            owner: OnboardingRecord(owner, "profile.v1", "Training", "beginner", NOW, NOW)
            for owner in (OWNER_A, OWNER_B)
        }
        self.consents = {
            owner: ConsentRecord(index, owner, "consent.v1", True, NOW)
            for index, owner in enumerate((OWNER_A, OWNER_B), start=1)
        }
        self.portfolio_rows: dict[str, LocalPortfolioRecord] = {}
        self.holding_rows: dict[str, LocalHoldingRecord] = {}
        self.events: list[str] = []
        self.active = False
        self.write = False
        self.fail_commit = False
        self.corrupt_count = False
        self.duplicate_list = False
        self.delete_lies = False
        self.confirmation_lies = False

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[LocalPortfolioTransaction]:
        assert not self.active
        old_portfolios, old_holdings = self.portfolio_rows.copy(), self.holding_rows.copy()
        self.active, self.write = True, write
        self.events.append("begin_write" if write else "begin_read")
        try:
            yield self
            if self.fail_commit:
                raise LocalStoreUnavailable()
            self.events.append("commit")
        except Exception:
            self.portfolio_rows, self.holding_rows = old_portfolios, old_holdings
            self.events.append("rollback")
            raise
        finally:
            self.active = False

    def touch(self, operation: str, *, mutation: bool = False) -> None:
        assert self.active and (not mutation or self.write)
        self.events.append(operation)

    def get_session(self, digest: str) -> LocalSession | None:
        self.touch("session")
        return self.sessions.get(digest)

    def get_onboarding(self, user_id: str) -> OnboardingRecord:
        self.touch("profile")
        return self.profiles[user_id]

    def latest_consent(self, user_id: str) -> ConsentRecord | None:
        self.touch("consent")
        return self.consents.get(user_id)

    def get_portfolio(self, user_id: str, portfolio_id: str) -> LocalPortfolioRecord | None:
        self.touch("parent")
        row = self.portfolio_rows.get(portfolio_id)
        return row if row is not None and row.user_id == user_id else None

    def list_portfolios(self, user_id: str, *, limit: int) -> list[LocalPortfolioRecord]:
        self.touch(f"portfolios_limit_{limit}")
        rows = sorted(
            (row for row in self.portfolio_rows.values() if row.user_id == user_id),
            key=lambda row: (row.created_at, row.portfolio_id),
        )[:limit]
        return rows + rows if self.duplicate_list else rows

    def count_portfolios(self, user_id: str) -> int:
        self.touch("portfolio_count")
        return (
            -1
            if self.corrupt_count
            else sum(row.user_id == user_id for row in self.portfolio_rows.values())
        )

    def insert_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        self.touch("insert_portfolio", mutation=True)
        self.portfolio_rows[record.portfolio_id] = record
        return replace(record, name="Not the submitted name") if self.confirmation_lies else record

    def update_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord:
        self.touch("update_portfolio", mutation=True)
        self.portfolio_rows[record.portfolio_id] = record
        return record

    def delete_portfolio(self, user_id: str, portfolio_id: str) -> bool:
        self.touch("delete_portfolio", mutation=True)
        row = self.get_portfolio(user_id, portfolio_id)
        if row is None or self.delete_lies:
            return False
        del self.portfolio_rows[portfolio_id]
        self.holding_rows = {
            key: value
            for key, value in self.holding_rows.items()
            if (value.user_id, value.portfolio_id) != (user_id, portfolio_id)
        }
        return True

    def get_holding(
        self, user_id: str, portfolio_id: str, holding_id: str
    ) -> LocalHoldingRecord | None:
        self.touch("child")
        row = self.holding_rows.get(holding_id)
        return (
            row
            if row is not None and (row.user_id, row.portfolio_id) == (user_id, portfolio_id)
            else None
        )

    def list_holdings(
        self, user_id: str, portfolio_id: str, *, limit: int
    ) -> list[LocalHoldingRecord]:
        self.touch(f"holdings_limit_{limit}")
        rows = sorted(
            (
                row
                for row in self.holding_rows.values()
                if (row.user_id, row.portfolio_id) == (user_id, portfolio_id)
            ),
            key=lambda row: (row.created_at, row.holding_id),
        )[:limit]
        return rows + rows if self.duplicate_list else rows

    def count_holdings(self, user_id: str, portfolio_id: str) -> int:
        self.touch("holding_count")
        return (
            -1
            if self.corrupt_count
            else sum(
                (row.user_id, row.portfolio_id) == (user_id, portfolio_id)
                for row in self.holding_rows.values()
            )
        )

    def get_holding_by_instrument(
        self, user_id: str, portfolio_id: str, instrument_id: str
    ) -> LocalHoldingRecord | None:
        self.touch("duplicate")
        return next(
            (
                row
                for row in self.holding_rows.values()
                if (row.user_id, row.portfolio_id, row.instrument_id)
                == (user_id, portfolio_id, instrument_id)
            ),
            None,
        )

    def insert_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord:
        self.touch("insert_holding", mutation=True)
        self.holding_rows[record.holding_id] = record
        return record

    def update_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord:
        self.touch("update_holding", mutation=True)
        self.holding_rows[record.holding_id] = record
        return record

    def delete_holding(self, user_id: str, portfolio_id: str, holding_id: str) -> bool:
        self.touch("delete_holding", mutation=True)
        row = self.get_holding(user_id, portfolio_id, holding_id)
        if row is None or self.delete_lies:
            return False
        del self.holding_rows[holding_id]
        return True


def portfolio_request(name: str = "Training") -> LocalPortfolioRequest:
    return LocalPortfolioRequest(
        portfolio_version="portfolio.v1", name=name, description=None, currency="USD"
    )


def holding_request(instrument: str = "SYN:AAPL") -> LocalHoldingCreateRequest:
    return LocalHoldingCreateRequest(
        holding_version="holding.v1",
        instrument_id=instrument,
        quantity="10.000000",
        average_cost="150.0000",
        currency="USD",
    )


def holding_update(quantity: str = "10.000000") -> LocalHoldingUpdateRequest:
    return LocalHoldingUpdateRequest(
        holding_version="holding.v1", quantity=quantity, average_cost="150.0000", currency="USD"
    )


def seed_portfolio(store: MemoryPortfolioStore, owner: str = OWNER_A) -> LocalPortfolioRecord:
    row = LocalPortfolioRecord(owner, str(uuid4()), "Training", None, "USD", NOW, NOW)
    store.portfolio_rows[row.portfolio_id] = row
    return row


def seed_holding(
    store: MemoryPortfolioStore, parent: LocalPortfolioRecord, instrument: str = "SYN:AAPL"
) -> LocalHoldingRecord:
    row = LocalHoldingRecord(
        parent.user_id,
        parent.portfolio_id,
        str(uuid4()),
        instrument,
        "10.000000",
        "150.0000",
        "USD",
        NOW,
        NOW,
    )
    store.holding_rows[row.holding_id] = row
    return row


class FailingQuotes:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        self.calls.append(instrument_ids)
        raise RuntimeError("private-source-detail")


class ExpandedCatalogue:
    def __bool__(self) -> bool:
        return False

    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        return LocalPortfolioCatalogSnapshot(
            "synthetic_catalog.v1",
            "USD",
            tuple(
                LocalPortfolioInstrument(f"SYN:T{i}", f"Synthetic {i}", "EQUITY", "GENERAL", "USD")
                for i in range(101)
            ),
        )


def test_create_read_update_noop_and_delete_are_scoped_and_owned() -> None:
    store, clock = MemoryPortfolioStore(), MutableClock()
    service = LocalPortfolioService(store, clock)
    created = service.create_portfolio(TOKEN_A, portfolio_request("  Training  "))
    assert created.name == "Training" and created.scope == "local_educational_application"
    assert "user_id" not in created.model_dump() and "owner_id" not in created.model_dump()
    assert created == service.portfolio(TOKEN_A, created.portfolio_id)
    assert service.portfolios(TOKEN_A).items == [created]
    assert service.portfolios(TOKEN_B).items == []
    clock.now += timedelta(seconds=5)
    unchanged = service.update_portfolio(TOKEN_A, created.portfolio_id, portfolio_request())
    assert unchanged == created and "update_portfolio" not in store.events
    changed = service.update_portfolio(TOKEN_A, created.portfolio_id, portfolio_request("Other"))
    assert changed.updated_at == clock.now.isoformat() and changed.created_at == created.created_at
    deletion = service.delete_portfolio(TOKEN_A, created.portfolio_id)
    assert deletion.deleted is True and deletion.entity_type == "portfolio"
    with pytest.raises(FinExException) as error:
        service.delete_portfolio(TOKEN_A, created.portfolio_id)
    assert error.value.error_code == "LOCAL_PORTFOLIO_NOT_FOUND"


def test_holding_crud_never_queries_quotes_or_changes_parent_stamp() -> None:
    store, clock, quotes = MemoryPortfolioStore(), MutableClock(), FailingQuotes()
    parent = seed_portfolio(store)
    service = LocalPortfolioService(store, clock, quotes=quotes)
    clock.now += timedelta(seconds=10)
    row = service.create_holding(TOKEN_A, parent.portfolio_id, holding_request())
    assert row.display_name == "Synthetic Apple example" and row.quantity == "10.000000"
    assert service.holding(TOKEN_A, parent.portfolio_id, row.holding_id) == row
    assert service.holdings(TOKEN_A, parent.portfolio_id).items == [row]
    clock.now += timedelta(seconds=10)
    assert (
        service.update_holding(TOKEN_A, parent.portfolio_id, row.holding_id, holding_update())
        == row
    )
    assert "update_holding" not in store.events
    updated = service.update_holding(
        TOKEN_A, parent.portfolio_id, row.holding_id, holding_update("11.000000")
    )
    assert updated.updated_at == clock.now.isoformat() and updated.created_at == row.created_at
    assert service.delete_holding(TOKEN_A, parent.portfolio_id, row.holding_id).deleted
    assert quotes.calls == [] and store.portfolio_rows[parent.portfolio_id] == parent


@pytest.mark.parametrize(
    "operation",
    [
        "get",
        "update",
        "delete",
        "create_child",
        "children",
        "child",
        "update_child",
        "delete_child",
        "metrics",
    ],
)
def test_cross_owner_parent_is_a_stable_404_before_semantic_work(operation: str) -> None:
    store = MemoryPortfolioStore()
    parent = seed_portfolio(store)
    child = seed_holding(store, parent)
    service = LocalPortfolioService(store, MutableClock())
    actions = {
        "get": lambda: service.portfolio(TOKEN_B, parent.portfolio_id),
        "update": lambda: service.update_portfolio(
            TOKEN_B, parent.portfolio_id, portfolio_request()
        ),
        "delete": lambda: service.delete_portfolio(TOKEN_B, parent.portfolio_id),
        "create_child": lambda: service.create_holding(
            TOKEN_B, parent.portfolio_id, holding_request("SYN:OTHER")
        ),
        "children": lambda: service.holdings(TOKEN_B, parent.portfolio_id),
        "child": lambda: service.holding(TOKEN_B, parent.portfolio_id, child.holding_id),
        "update_child": lambda: service.update_holding(
            TOKEN_B, parent.portfolio_id, child.holding_id, holding_update()
        ),
        "delete_child": lambda: service.delete_holding(
            TOKEN_B, parent.portfolio_id, child.holding_id
        ),
        "metrics": lambda: service.metrics(TOKEN_B, parent.portfolio_id),
    }
    with pytest.raises(FinExException) as error:
        actions[operation]()
    assert (error.value.error_code, error.value.status_code) == ("LOCAL_PORTFOLIO_NOT_FOUND", 404)
    assert not any(item.startswith("insert") or item.startswith("delete") for item in store.events)


@pytest.mark.parametrize("operation", ["get", "update", "delete"])
def test_child_from_another_owned_portfolio_is_not_found(operation: str) -> None:
    store = MemoryPortfolioStore()
    first, second = seed_portfolio(store), seed_portfolio(store)
    child = seed_holding(store, first)
    service = LocalPortfolioService(store, MutableClock())
    with pytest.raises(FinExException) as error:
        if operation == "get":
            service.holding(TOKEN_A, second.portfolio_id, child.holding_id)
        elif operation == "update":
            service.update_holding(TOKEN_A, second.portfolio_id, child.holding_id, holding_update())
        else:
            service.delete_holding(TOKEN_A, second.portfolio_id, child.holding_id)
    assert error.value.error_code == "LOCAL_HOLDING_NOT_FOUND"


@pytest.mark.parametrize("mode", ["malformed", "expired", "revoked", "withdrawn", "profile"])
def test_authorization_and_current_onboarding_happen_inside_the_mutating_unit(mode: str) -> None:
    store = MemoryPortfolioStore()
    session = store.sessions[digest_token(TOKEN_A)]
    token = TOKEN_A
    if mode == "malformed":
        token = "not-a-session"
    elif mode == "expired":
        store.sessions[session.digest] = replace(session, expires_at=NOW)
    elif mode == "revoked":
        store.sessions[session.digest] = replace(session, revoked_at=NOW)
    elif mode == "withdrawn":
        store.consents[OWNER_A] = replace(store.consents[OWNER_A], accepted=False)
    else:
        store.profiles[OWNER_A] = replace(store.profiles[OWNER_A], completed_at=None)
    with pytest.raises(FinExException) as error:
        LocalPortfolioService(store, MutableClock()).create_portfolio(token, portfolio_request())
    assert error.value.error_code == (
        "ONBOARDING_REQUIRED" if mode in {"withdrawn", "profile"} else "SESSION_INVALID"
    )
    assert store.portfolio_rows == {}
    if mode == "malformed":
        assert store.events == []
    else:
        assert store.events[0] == "begin_write" and store.events[1] == "session"
        assert "insert_portfolio" not in store.events and store.events[-1] == "rollback"


def test_every_read_is_one_authorized_unit_and_bounded_lists() -> None:
    store = MemoryPortfolioStore()
    parent = seed_portfolio(store)
    service = LocalPortfolioService(store, MutableClock())
    for action in (
        lambda: service.catalogue(TOKEN_A),
        lambda: service.portfolios(TOKEN_A),
        lambda: service.portfolio(TOKEN_A, parent.portfolio_id),
        lambda: service.holdings(TOKEN_A, parent.portfolio_id),
        lambda: service.metrics(TOKEN_A, parent.portfolio_id),
    ):
        store.events.clear()
        action()
        assert store.events.count("begin_read") == 1 and store.events.count("commit") == 1
        assert store.events[1:4] == ["session", "profile", "consent"]
    store.events.clear()
    service.portfolios(TOKEN_A)
    assert "portfolios_limit_21" in store.events
    store.events.clear()
    service.holdings(TOKEN_A, parent.portfolio_id)
    assert "holdings_limit_101" in store.events


def test_portfolio_limit_is_atomic_and_other_owner_does_not_count() -> None:
    store = MemoryPortfolioStore()
    for _ in range(20):
        seed_portfolio(store)
    seed_portfolio(store, OWNER_B)
    with pytest.raises(FinExException) as error:
        LocalPortfolioService(store, MutableClock()).create_portfolio(TOKEN_A, portfolio_request())
    assert error.value.error_code == "PORTFOLIO_LIMIT_REACHED" and error.value.status_code == 409
    assert len(store.portfolio_rows) == 21


def test_falsey_catalogue_injection_and_duplicate_before_capacity() -> None:
    store = MemoryPortfolioStore()
    parent = seed_portfolio(store)
    for i in range(100):
        seed_holding(store, parent, f"SYN:T{i}")
    service = LocalPortfolioService(store, MutableClock(), catalogue=ExpandedCatalogue())
    assert service.catalogue(TOKEN_A).count == 101
    for instrument, code in (
        ("SYN:T0", "HOLDING_ALREADY_EXISTS"),
        ("SYN:T100", "HOLDING_LIMIT_REACHED"),
        ("SYN:OTHER", "UNSUPPORTED_INSTRUMENT"),
    ):
        with pytest.raises(FinExException) as error:
            service.create_holding(TOKEN_A, parent.portfolio_id, holding_request(instrument))
        assert error.value.error_code == code
    assert len(store.holding_rows) == 100


def test_empty_metrics_never_fetches_quotes_but_quote_faults_are_safe() -> None:
    store, quotes = MemoryPortfolioStore(), FailingQuotes()
    parent = seed_portfolio(store)
    service = LocalPortfolioService(store, MutableClock(), quotes=quotes)
    empty = service.metrics(TOKEN_A, parent.portfolio_id)
    assert empty.valuation_status == "EMPTY" and empty.totals.market_value == "0.00"
    assert quotes.calls == []
    seed_holding(store, parent)
    with pytest.raises(FinExException) as error:
        service.metrics(TOKEN_A, parent.portfolio_id)
    assert error.value.error_code == "LOCAL_QUOTE_UNAVAILABLE" and error.value.status_code == 503
    assert "private-source-detail" not in str(error.value)
    assert quotes.calls == [("SYN:AAPL",)]


def test_deletion_cascades_only_the_target_owners_manual_holdings() -> None:
    store = MemoryPortfolioStore()
    first, second = seed_portfolio(store), seed_portfolio(store, OWNER_B)
    first_child, second_child = seed_holding(store, first), seed_holding(store, second)
    LocalPortfolioService(store, MutableClock()).delete_portfolio(TOKEN_A, first.portfolio_id)
    assert first_child.holding_id not in store.holding_rows
    assert store.holding_rows == {second_child.holding_id: second_child}
    assert store.portfolio_rows == {second.portfolio_id: second}


@pytest.mark.parametrize("mode", ["record", "count", "duplicate", "oversized", "delete"])
def test_store_corruption_fails_opaque_instead_of_returning_success(mode: str) -> None:
    store = MemoryPortfolioStore()
    parent = seed_portfolio(store)
    service = LocalPortfolioService(store, MutableClock())
    with pytest.raises(LocalStoreUnavailable):
        if mode == "record":
            store.portfolio_rows[parent.portfolio_id] = replace(parent, currency="EUR")
            service.portfolio(TOKEN_A, parent.portfolio_id)
        elif mode == "count":
            store.corrupt_count = True
            service.create_portfolio(TOKEN_A, portfolio_request())
        elif mode == "duplicate":
            store.duplicate_list = True
            service.portfolios(TOKEN_A)
        elif mode == "oversized":
            for _ in range(20):
                seed_portfolio(store)
            service.portfolios(TOKEN_A)
        else:
            store.delete_lies = True
            service.delete_portfolio(TOKEN_A, parent.portfolio_id)
    assert store.events[-1] == "rollback"


def test_failed_commit_rolls_back_without_returning_a_successful_record() -> None:
    store = MemoryPortfolioStore()
    store.fail_commit = True
    with pytest.raises(LocalStoreUnavailable):
        LocalPortfolioService(store, MutableClock()).create_portfolio(TOKEN_A, portfolio_request())
    assert store.portfolio_rows == {} and store.events[-1] == "rollback"


def test_store_must_confirm_the_exact_inserted_record_or_rollback() -> None:
    store = MemoryPortfolioStore()
    store.confirmation_lies = True
    with pytest.raises(LocalStoreUnavailable):
        LocalPortfolioService(store, MutableClock()).create_portfolio(TOKEN_A, portfolio_request())
    assert store.portfolio_rows == {} and store.events[-1] == "rollback"


def test_falsey_quote_port_is_used_once_and_current_catalogue_metadata_is_readonly() -> None:
    from app.ports.adapters.synthetic_local_portfolio import SyntheticLocalPortfolioQuotes

    class FalseyQuotes(SyntheticLocalPortfolioQuotes):
        def __init__(self) -> None:
            self.calls = 0

        def __bool__(self) -> bool:
            return False

        def snapshot(self, ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
            self.calls += 1
            return super().snapshot(ids)

    class RevisedCatalogue:
        def snapshot(self) -> LocalPortfolioCatalogSnapshot:
            return LocalPortfolioCatalogSnapshot(
                "synthetic_catalog.v1",
                "USD",
                (
                    LocalPortfolioInstrument(
                        "SYN:AAPL", "Revised synthetic label", "EQUITY", "GENERAL", "USD"
                    ),
                ),
            )

    store, quotes = MemoryPortfolioStore(), FalseyQuotes()
    parent = seed_portfolio(store)
    row = seed_holding(store, parent)
    service = LocalPortfolioService(
        store, MutableClock(), catalogue=RevisedCatalogue(), quotes=quotes
    )
    assert service.holding(TOKEN_A, parent.portfolio_id, row.holding_id).display_name == (
        "Revised synthetic label"
    )
    result = service.metrics(TOKEN_A, parent.portfolio_id)
    assert result.holdings[0].display_name == "Revised synthetic label" and quotes.calls == 1
    assert (
        store.holding_rows[row.holding_id] == row
        and store.portfolio_rows[parent.portfolio_id] == parent
    )


def test_removed_stored_instrument_is_a_catalogue_fault_not_a_missing_quote() -> None:
    store, quotes = MemoryPortfolioStore(), FailingQuotes()
    parent = seed_portfolio(store)
    seed_holding(store, parent, "SYN:OTHER")
    service = LocalPortfolioService(store, MutableClock(), quotes=quotes)
    with pytest.raises(FinExException) as error:
        service.metrics(TOKEN_A, parent.portfolio_id)
    assert error.value.error_code == "LOCAL_CATALOG_UNAVAILABLE" and quotes.calls == []
