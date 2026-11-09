"""Independent GREEN-only S1 acceptance probes against real native SQLite.

These tests preserve already-working invariants; they do not claim a RED phase.
Credentials stay in memory and out of pytest assertion diagnostics.
"""

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event

import pytest

from app.core.exceptions import FinExException
from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.schemas.local_application import LocalConsentRequest, LocalDraftRequest
from app.services.local_application_service import LocalApplicationService

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


class AcceptanceClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class PrecommitFailureStore(SQLiteLocalApplicationStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.fail_next = False

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        if self.fail_next:
            self.fail_next = False
            raise sqlite3.OperationalError("Synthetic precommit failure")


class PausedCommitStore(SQLiteLocalApplicationStore):
    """Pause a real mutation after SQL changes but before its commit."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.pause_next = False
        self.mutation_waiting = Event()
        self.continue_commit = Event()

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        if self.pause_next:
            self.pause_next = False
            self.mutation_waiting.set()
            if not self.continue_commit.wait(3):
                raise RuntimeError("The independent race harness did not release the commit")


class BeginObservedStore(SQLiteLocalApplicationStore):
    """Observe the competing BEGIN IMMEDIATE without printing any SQL."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.begin_attempted = Event()

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def observe(statement: str) -> None:
            if statement == "BEGIN IMMEDIATE":
                self.begin_attempted.set()

        connection.set_trace_callback(observe)
        return connection


def profile(label: str = "Synthetic learner") -> LocalDraftRequest:
    return LocalDraftRequest(
        profile_schema_version="profile.v1",
        display_name=label,
        experience_level="beginner",
    )


def consent(accepted: bool) -> LocalConsentRequest:
    return LocalConsentRequest(consent_version="consent.v1", consent_given=accepted)


def prepare_completed(service: LocalApplicationService, credential: str) -> None:
    service.draft(credential, profile())
    service.consent(credential, consent(True))
    completed = service.complete(credential, "consent.v1", "profile.v1")
    assert completed.onboarding_completed


def test_precommit_logout_failure_does_not_revoke_the_session(tmp_path: Path) -> None:
    store = PrecommitFailureStore(tmp_path / "logout-rollback.sqlite3")
    service = LocalApplicationService(store, AcceptanceClock())
    login = service.login("learner-a")
    owner_id = login.user.id
    store.fail_next = True
    with pytest.raises(LocalStoreUnavailable):
        service.logout(login.access_token)

    identity = service.me(login.access_token)
    assert identity.id == owner_id


def test_precommit_draft_failure_preserves_profile_and_completion(tmp_path: Path) -> None:
    store = PrecommitFailureStore(tmp_path / "draft-rollback.sqlite3")
    service = LocalApplicationService(store, AcceptanceClock())
    credential = service.login("learner-a").access_token
    prepare_completed(service, credential)
    before = service.state(credential)

    store.fail_next = True
    with pytest.raises(LocalStoreUnavailable):
        service.draft(credential, profile("Uncommitted replacement"))

    after = service.state(credential)
    assert after == before
    assert after.onboarding_completed


def test_precommit_completion_failure_does_not_restore_withdrawn_completion(tmp_path: Path) -> None:
    store = PrecommitFailureStore(tmp_path / "completion-rollback.sqlite3")
    service = LocalApplicationService(store, AcceptanceClock())
    credential = service.login("learner-a").access_token
    prepare_completed(service, credential)
    service.consent(credential, consent(False))
    service.consent(credential, consent(True))
    before = service.state(credential)
    assert not before.onboarding_completed

    store.fail_next = True
    with pytest.raises(LocalStoreUnavailable):
        service.complete(credential, "consent.v1", "profile.v1")

    after = service.state(credential)
    assert after == before
    assert after.completed_at is None


@pytest.mark.parametrize("ttl_minutes", [1, 30, 60])
def test_session_is_valid_just_before_expiry_but_not_at_exact_expiry(
    tmp_path: Path, ttl_minutes: int
) -> None:
    clock = AcceptanceClock()
    path = tmp_path / "exact-expiry.sqlite3"
    service = LocalApplicationService(SQLiteLocalApplicationStore(path), clock, ttl_minutes)
    login = service.login("learner-a")
    owner_id = login.user.id
    expires_at = NOW + timedelta(minutes=ttl_minutes)
    clock.now = expires_at - timedelta(microseconds=1)
    identity = service.me(login.access_token)
    assert identity.id == owner_id

    # A new adapter instance must apply the same exact server-side lifetime.
    clock.now = expires_at
    restarted = LocalApplicationService(SQLiteLocalApplicationStore(path), clock, ttl_minutes)
    with pytest.raises(FinExException) as rejected:
        restarted.me(login.access_token)
    assert rejected.value.error_code == "SESSION_INVALID"


def test_repeat_login_preserves_owner_and_logout_revokes_only_that_session(tmp_path: Path) -> None:
    path = tmp_path / "session-isolation.sqlite3"
    clock = AcceptanceClock()
    service = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    first = service.login("learner-a")
    second = service.login("learner-a")
    other = service.login("learner-b")
    first_owner, second_owner, other_owner = first.user.id, second.user.id, other.user.id
    reused_credential = first.access_token == second.access_token
    assert not reused_credential
    assert first_owner == second_owner
    assert first_owner != other_owner
    prepare_completed(service, first.access_token)
    completed = service.state(second.access_token)
    service.logout(first.access_token)

    restarted = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    with pytest.raises(FinExException) as rejected:
        restarted.me(first.access_token)
    assert rejected.value.error_code == "SESSION_INVALID"
    surviving_identity = restarted.me(second.access_token)
    assert surviving_identity.id == second_owner
    persisted = restarted.state(second.access_token)
    assert persisted == completed
    other_state = restarted.state(other.access_token)
    assert other_state.draft.display_name is None
    assert other_state.consent is None
    assert not other_state.onboarding_completed
    replacement = restarted.login("learner-a")
    replacement_owner = replacement.user.id
    assert replacement_owner == first_owner


def test_native_files_contain_only_session_digest_and_order_same_time_events(
    tmp_path: Path,
) -> None:
    path = tmp_path / "digest-and-order.sqlite3"
    service = LocalApplicationService(SQLiteLocalApplicationStore(path), AcceptanceClock())
    login = service.login("learner-a")
    for accepted in (True, False, True):
        service.consent(login.access_token, consent(accepted))

    with closing(sqlite3.connect(path)) as connection:
        stored = connection.execute("SELECT digest FROM local_sessions").fetchone()[0]
        expected = hashlib.sha256(login.access_token.encode("utf-8")).hexdigest()
        digest_matches = stored == expected
        assert digest_matches
        events = connection.execute(
            "SELECT event_id, accepted, recorded_at FROM local_consent_events ORDER BY event_id"
        ).fetchall()
        assert [row[1] for row in events] == [1, 0, 1]
        assert events[0][0] < events[1][0] < events[2][0]
        assert len({row[2] for row in events}) == 1

    files = (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm"))
    plaintext_found = any(
        login.access_token.encode("utf-8") in file.read_bytes() for file in files if file.exists()
    )
    assert not plaintext_found
    final = service.state(login.access_token)
    assert final.consent is not None and final.consent.accepted
    assert not final.onboarding_completed


def test_logout_commits_before_competing_domain_write_rechecks_session(tmp_path: Path) -> None:
    path = tmp_path / "logout-write-race.sqlite3"
    clock = AcceptanceClock()
    first_store = PausedCommitStore(path)
    first = LocalApplicationService(first_store, clock)
    credential = first.login("learner-a").access_token
    prepare_completed(first, credential)
    second_store = BeginObservedStore(path)
    second = LocalApplicationService(second_store, clock)
    first_store.pause_next = True

    def later_write() -> str:
        try:
            with second.authorized_transaction(
                credential, write=True, onboarding_required=True
            ) as (session, transaction):
                saved = transaction.get_onboarding(session.user.id)
                transaction.save_onboarding(replace(saved, display_name="Unauthorized mutation"))
            return "incorrectly-authorized"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        revocation = pool.submit(first.logout, credential)
        try:
            assert first_store.mutation_waiting.wait(2)
            writer = pool.submit(later_write)
            assert second_store.begin_attempted.wait(2)
        finally:
            first_store.continue_commit.set()
        revocation.result(timeout=4)
        result = writer.result(timeout=4)
    assert result == "SESSION_INVALID"
    replacement = second.login("learner-a")
    unchanged = second.state(replacement.access_token)
    assert unchanged.draft.display_name == "Synthetic learner"
    assert unchanged.onboarding_completed


def test_withdrawal_commits_before_competing_completion_rechecks_latest_consent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "withdraw-completion-race.sqlite3"
    clock = AcceptanceClock()
    first_store = PausedCommitStore(path)
    first = LocalApplicationService(first_store, clock)
    credential = first.login("learner-a").access_token
    prepare_completed(first, credential)
    second_store = BeginObservedStore(path)
    second = LocalApplicationService(second_store, clock)
    first_store.pause_next = True

    def later_completion() -> str:
        try:
            second.complete(credential, "consent.v1", "profile.v1")
            return "incorrectly-completed"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        withdrawal = pool.submit(first.consent, credential, consent(False))
        try:
            assert first_store.mutation_waiting.wait(2)
            completion = pool.submit(later_completion)
            assert second_store.begin_attempted.wait(2)
        finally:
            first_store.continue_commit.set()
        withdrawal.result(timeout=4)
        result = completion.result(timeout=4)
    assert result == "CONSENT_REQUIRED"
    final = second.state(credential)
    assert final.consent is not None and not final.consent.accepted
    assert not final.onboarding_completed
    assert final.completed_at is None
