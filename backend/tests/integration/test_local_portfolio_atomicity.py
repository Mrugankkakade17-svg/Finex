"""Real manual/S1 lock ordering, quotas, deletion and commit atomicity.

These service-integrated invariants are written before the service is complete;
passing controls are GREEN-only, never invented application RED evidence.
Each database belongs to its isolated pytest directory. The 100-holding checks
use an explicit 101-instrument synthetic catalogue, not the default four.
Only boolean lock events are observed; expanded SQL and credentials are never
collected, logged or included in assertion expressions.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from app.core.exceptions import FinExException
from app.domain.local_application import LocalStoreUnavailable
from app.domain.local_portfolio import (
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
)
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_portfolio_store import SQLiteLocalPortfolioStore
from app.schemas.local_application import LocalConsentRequest, LocalDraftRequest
from app.schemas.local_portfolio import (
    LocalHoldingCreateRequest,
    LocalHoldingUpdateRequest,
    LocalPortfolioRequest,
)
from app.services.local_application_service import LocalApplicationService
from app.services.local_portfolio_service import LocalPortfolioService

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


class Clock:
    now = NOW

    def __call__(self) -> datetime:
        return self.now


class ExpandedCatalogue:
    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        return LocalPortfolioCatalogSnapshot(
            "synthetic_catalog.v1",
            "USD",
            tuple(
                LocalPortfolioInstrument(
                    f"SYN:T{index}", f"Synthetic {index}", "EQUITY", "GENERAL", "USD"
                )
                for index in range(101)
            ),
        )


def portfolio_payload(name: str = "Synthetic portfolio") -> LocalPortfolioRequest:
    return LocalPortfolioRequest(
        portfolio_version="portfolio.v1", name=name, description=None, currency="USD"
    )


def holding_payload(index: int = 0) -> LocalHoldingCreateRequest:
    return LocalHoldingCreateRequest(
        holding_version="holding.v1",
        instrument_id=f"SYN:T{index}",
        quantity="1.000000",
        average_cost="0.0000",
        currency="USD",
    )


def profile(label: str = "Synthetic learner") -> LocalDraftRequest:
    return LocalDraftRequest(
        profile_schema_version="profile.v1", display_name=label, experience_level="beginner"
    )


def consent(accepted: bool) -> LocalConsentRequest:
    return LocalConsentRequest(consent_version="consent.v1", consent_given=accepted)


def complete_persona(service: LocalApplicationService, alias: str = "learner-a") -> str:
    token = service.login(alias).access_token
    service.draft(token, profile())
    service.consent(token, consent(True))
    completed = service.complete(token, "consent.v1", "profile.v1").onboarding_completed
    assert completed
    return token


def portfolio_service(store: SQLiteLocalPortfolioStore, clock: Clock) -> LocalPortfolioService:
    return LocalPortfolioService(store, clock, catalogue=ExpandedCatalogue())


class PausedPortfolioStore(SQLiteLocalPortfolioStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pause_next = False
        self.waiting = Event()
        self.release = Event()
        self.commit_calls = 0

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        self.commit_calls += 1
        if self.pause_next:
            self.pause_next = False
            self.waiting.set()
            if not self.release.wait(3):
                raise RuntimeError("Synthetic manual race was not released")


class ObservedPortfolioStore(SQLiteLocalPortfolioStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.begin_attempted = Event()
        self.commit_calls = 0

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def observe(statement: str) -> None:
            if statement == "BEGIN IMMEDIATE":
                self.begin_attempted.set()

        connection.set_trace_callback(observe)
        return connection

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        self.commit_calls += 1


class PausedS1Store(SQLiteLocalApplicationStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pause_next = False
        self.waiting = Event()
        self.release = Event()

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        if self.pause_next:
            self.pause_next = False
            self.waiting.set()
            if not self.release.wait(3):
                raise RuntimeError("Synthetic S1 race was not released")


class ObservedS1Store(SQLiteLocalApplicationStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.begin_attempted = Event()
        self.commit_calls = 0

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def observe(statement: str) -> None:
            if statement == "BEGIN IMMEDIATE":
                self.begin_attempted.set()

        connection.set_trace_callback(observe)
        return connection

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        self.commit_calls += 1


@pytest.mark.parametrize("resource", ["portfolio", "holding"])
@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("logout", "SESSION_INVALID"),
        ("withdraw", "ONBOARDING_REQUIRED"),
        ("profile", "ONBOARDING_REQUIRED"),
        ("expiry", "SESSION_INVALID"),
    ],
)
def test_waiting_manual_write_rechecks_current_s1_after_actual_lock(
    tmp_path: Path, resource: str, mutation: str, expected: str
) -> None:
    path = tmp_path / "s1-first-manual-lock.sqlite3"
    clock = Clock()
    first_store = PausedS1Store(path)
    onboarding = LocalApplicationService(first_store, clock)
    token = complete_persona(onboarding)
    owner = onboarding.me(token).id
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    second_store = ObservedPortfolioStore(path)
    later = portfolio_service(second_store, clock)
    first_store.pause_next = True

    def mutate() -> None:
        if mutation == "logout":
            onboarding.logout(token)
        elif mutation == "withdraw":
            onboarding.consent(token, consent(False))
        elif mutation == "profile":
            onboarding.draft(token, profile("Changed incomplete profile"))
        else:
            onboarding.draft(token, profile())

    def later_write() -> str:
        try:
            if resource == "portfolio":
                later.create_portfolio(token, portfolio_payload("Later"))
            else:
                later.create_holding(token, parent.portfolio_id, holding_payload())
            return "incorrectly-saved"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(mutate)
        try:
            assert first_store.waiting.wait(2)
            waiting = pool.submit(later_write)
            assert second_store.begin_attempted.wait(2)
            assert not waiting.done()
            if mutation == "expiry":
                clock.now = NOW + timedelta(minutes=30)
        finally:
            first_store.release.set()
        first.result(timeout=4)
        result = waiting.result(timeout=4)
    assert result == expected
    assert second_store.commit_calls == 0
    with SQLiteLocalPortfolioStore(path).transaction() as transaction:
        assert transaction.count_portfolios(owner) == 1
        assert transaction.count_holdings(owner, parent.portfolio_id) == 0


@pytest.mark.parametrize("resource", ["portfolio", "holding"])
@pytest.mark.parametrize("mutation", ["logout", "withdraw"])
def test_manual_commit_once_precedes_waiting_s1_revocation_and_preserves_owned_rows(
    tmp_path: Path, resource: str, mutation: str
) -> None:
    path = tmp_path / "manual-first-s1-lock.sqlite3"
    clock = Clock()
    onboarding = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    token = complete_persona(onboarding)
    owner = onboarding.me(token).id
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    first_store = PausedPortfolioStore(path)
    first = portfolio_service(first_store, clock)
    second_store = ObservedS1Store(path)
    later = LocalApplicationService(second_store, clock)
    first_store.pause_next = True

    def create_resource() -> str:
        if resource == "portfolio":
            return first.create_portfolio(
                token, portfolio_payload("Saved before revocation")
            ).portfolio_id
        return first.create_holding(token, parent.portfolio_id, holding_payload()).holding_id

    def revoke() -> None:
        if mutation == "logout":
            later.logout(token)
        else:
            later.consent(token, consent(False))

    with ThreadPoolExecutor(max_workers=2) as pool:
        committed = pool.submit(create_resource)
        try:
            assert first_store.waiting.wait(2)
            revocation = pool.submit(revoke)
            assert second_store.begin_attempted.wait(2)
            assert not revocation.done()
        finally:
            first_store.release.set()
        saved_id = committed.result(timeout=4)
        revocation.result(timeout=4)
    assert first_store.commit_calls == 1
    assert second_store.commit_calls == 1
    expected = "SESSION_INVALID" if mutation == "logout" else "ONBOARDING_REQUIRED"
    with pytest.raises(FinExException) as blocked_read:
        first.portfolios(token)
    assert blocked_read.value.error_code == expected
    with pytest.raises(FinExException) as blocked_write:
        first.update_portfolio(token, parent.portfolio_id, portfolio_payload("Must not change"))
    assert blocked_write.value.error_code == expected
    assert first_store.commit_calls == 1
    with SQLiteLocalPortfolioStore(path).transaction() as transaction:
        if resource == "portfolio":
            assert transaction.get_portfolio(owner, saved_id) is not None
            assert transaction.count_portfolios(owner) == 2
        else:
            assert transaction.get_holding(owner, parent.portfolio_id, saved_id) is not None
            assert transaction.count_holdings(owner, parent.portfolio_id) == 1
    if mutation == "logout":
        token = onboarding.login("learner-a").access_token
    else:
        onboarding.consent(token, consent(True))
        onboarding.complete(token, "consent.v1", "profile.v1")
    restarted = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    restored_id = (
        restarted.portfolio(token, saved_id).portfolio_id
        if resource == "portfolio"
        else restarted.holding(token, parent.portfolio_id, saved_id).holding_id
    )
    assert restored_id == saved_id


@pytest.mark.parametrize("resource", ["portfolio", "holding"])
def test_actual_two_writer_capacity_race_cannot_exceed_owner_or_parent_limit(
    tmp_path: Path, resource: str
) -> None:
    path = tmp_path / "manual-capacity-lock.sqlite3"
    clock = Clock()
    token = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    if resource == "portfolio":
        for index in range(18):
            healthy.create_portfolio(token, portfolio_payload(f"Synthetic {index}"))
    else:
        for index in range(99):
            healthy.create_holding(token, parent.portfolio_id, holding_payload(index))
    first_store = PausedPortfolioStore(path)
    second_store = ObservedPortfolioStore(path)
    first, second = portfolio_service(first_store, clock), portfolio_service(second_store, clock)
    first_store.pause_next = True

    def create(service: LocalPortfolioService, index: int) -> None:
        if resource == "portfolio":
            service.create_portfolio(token, portfolio_payload(f"Final {index}"))
        else:
            service.create_holding(token, parent.portfolio_id, holding_payload(index))

    def later_create() -> str:
        try:
            create(second, 100)
            return "incorrectly-saved"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = pool.submit(create, first, 99)
        try:
            assert first_store.waiting.wait(2)
            waiting = pool.submit(later_create)
            assert second_store.begin_attempted.wait(2)
            assert not waiting.done()
        finally:
            first_store.release.set()
        saved.result(timeout=4)
        outcome = waiting.result(timeout=4)
    assert outcome == (
        "PORTFOLIO_LIMIT_REACHED" if resource == "portfolio" else "HOLDING_LIMIT_REACHED"
    )
    assert first_store.commit_calls == 1
    assert second_store.commit_calls == 0
    count = (
        healthy.portfolios(token).count
        if resource == "portfolio"
        else healthy.holdings(token, parent.portfolio_id).count
    )
    assert count == (20 if resource == "portfolio" else 100)


@pytest.mark.parametrize("at_capacity", [False, True])
def test_actual_duplicate_race_is_single_owned_insert_even_at_capacity(
    tmp_path: Path, at_capacity: bool
) -> None:
    path = tmp_path / "manual-duplicate-lock.sqlite3"
    clock = Clock()
    token = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    if at_capacity:
        for index in range(99):
            healthy.create_holding(token, parent.portfolio_id, holding_payload(index))
    first_store, second_store = PausedPortfolioStore(path), ObservedPortfolioStore(path)
    first, second = portfolio_service(first_store, clock), portfolio_service(second_store, clock)
    first_store.pause_next = True
    request = holding_payload(99)

    def duplicate() -> str:
        try:
            second.create_holding(token, parent.portfolio_id, request)
            return "incorrectly-saved"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = pool.submit(first.create_holding, token, parent.portfolio_id, request)
        try:
            assert first_store.waiting.wait(2)
            waiting = pool.submit(duplicate)
            assert second_store.begin_attempted.wait(2)
            assert not waiting.done()
        finally:
            first_store.release.set()
        saved.result(timeout=4)
        outcome = waiting.result(timeout=4)
    assert outcome == "HOLDING_ALREADY_EXISTS"
    assert first_store.commit_calls == 1
    assert second_store.commit_calls == 0
    count = healthy.holdings(token, parent.portfolio_id).count
    assert count == (100 if at_capacity else 1)


@pytest.mark.parametrize("delete_first", [False, True])
def test_parent_delete_and_child_insert_serialize_without_orphans_or_replay(
    tmp_path: Path, delete_first: bool
) -> None:
    path = tmp_path / "manual-delete-insert-lock.sqlite3"
    clock = Clock()
    token = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    first_store, second_store = PausedPortfolioStore(path), ObservedPortfolioStore(path)
    first, second = portfolio_service(first_store, clock), portfolio_service(second_store, clock)
    first_store.pause_next = True

    def first_operation() -> None:
        if delete_first:
            first.delete_portfolio(token, parent.portfolio_id)
        else:
            first.create_holding(token, parent.portfolio_id, holding_payload())

    def second_operation() -> str:
        try:
            if delete_first:
                second.create_holding(token, parent.portfolio_id, holding_payload())
            else:
                second.delete_portfolio(token, parent.portfolio_id)
            return "saved"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = pool.submit(first_operation)
        try:
            assert first_store.waiting.wait(2)
            waiting = pool.submit(second_operation)
            assert second_store.begin_attempted.wait(2)
            assert not waiting.done()
        finally:
            first_store.release.set()
        saved.result(timeout=4)
        outcome = waiting.result(timeout=4)
    assert outcome == ("LOCAL_PORTFOLIO_NOT_FOUND" if delete_first else "saved")
    assert first_store.commit_calls == 1
    assert second_store.commit_calls == (0 if delete_first else 1)
    owner = LocalApplicationService(SQLiteLocalApplicationStore(path), clock).me(token).id
    with SQLiteLocalPortfolioStore(path).transaction() as transaction:
        assert transaction.count_portfolios(owner) == 0
        assert transaction.count_holdings(owner, parent.portfolio_id) == 0


def test_two_full_puts_are_last_committed_wins_not_optimistic_locking(tmp_path: Path) -> None:
    path = tmp_path / "manual-full-put-lock.sqlite3"
    clock = Clock()
    token = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    first_clock, second_clock = Clock(), Clock()
    first_clock.now, second_clock.now = NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)
    first_store, second_store = PausedPortfolioStore(path), ObservedPortfolioStore(path)
    first = portfolio_service(first_store, first_clock)
    second = portfolio_service(second_store, second_clock)
    first_store.pause_next = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = pool.submit(
            first.update_portfolio, token, parent.portfolio_id, portfolio_payload("First")
        )
        try:
            assert first_store.waiting.wait(2)
            waiting = pool.submit(
                second.update_portfolio, token, parent.portfolio_id, portfolio_payload("Last")
            )
            assert second_store.begin_attempted.wait(2)
            assert not waiting.done()
        finally:
            first_store.release.set()
        first_result = saved.result(timeout=4)
        second_result = waiting.result(timeout=4)
    assert first_result.name == "First" and second_result.name == "Last"
    final = healthy.portfolio(token, parent.portfolio_id)
    assert final == second_result
    assert final.created_at == parent.created_at
    assert first_store.commit_calls == second_store.commit_calls == 1


class FailedPortfolioCommitStore(SQLiteLocalPortfolioStore):
    def _before_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic manual commit failure")


@pytest.mark.parametrize(
    "operation", ["portfolio_create", "holding_create", "holding_update", "delete"]
)
def test_service_does_not_confirm_failed_commit_or_lose_prior_owned_rows(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "manual-service-rollback.sqlite3"
    clock = Clock()
    token = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parent = healthy.create_portfolio(token, portfolio_payload())
    child = healthy.create_holding(token, parent.portfolio_id, holding_payload())
    failed = portfolio_service(FailedPortfolioCommitStore(path), clock)
    with pytest.raises(LocalStoreUnavailable):
        if operation == "portfolio_create":
            failed.create_portfolio(token, portfolio_payload("Not committed"))
        elif operation == "holding_create":
            failed.create_holding(token, parent.portfolio_id, holding_payload(1))
        elif operation == "holding_update":
            failed.update_holding(
                token,
                parent.portfolio_id,
                child.holding_id,
                LocalHoldingUpdateRequest(
                    holding_version="holding.v1",
                    quantity="2.000000",
                    average_cost="1.0000",
                    currency="USD",
                ),
            )
        else:
            failed.delete_portfolio(token, parent.portfolio_id)
    restarted = portfolio_service(SQLiteLocalPortfolioStore(path), clock)
    parents, children = restarted.portfolios(token), restarted.holdings(token, parent.portfolio_id)
    assert parents.items == [parent]
    assert children.items == [child]
