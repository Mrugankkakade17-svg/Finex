"""Real native lock, restart, idempotency and authorization acceptance.

These are GREEN-only cross-service invariants after the SQL RED/implementation;
they do not manufacture RED evidence for behavior that already works. Session
credentials remain in memory and are never included in assertion values/logs.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from app.core.exceptions import FinExException
from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore
from app.schemas.local_application import LocalConsentRequest, LocalDraftRequest
from app.schemas.local_risk import LocalRiskInput, LocalRiskSubmitRequest
from app.services.local_application_service import LocalApplicationService
from app.services.local_risk_service import LocalRiskService

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
QUESTION_IDS = [f"{dimension}{index}" for dimension in ("W", "C") for index in range(1, 6)]


class Clock:
    now = NOW

    def __call__(self) -> datetime:
        return self.now


def input_payload(letter: str = "C", *, count: int = 10) -> LocalRiskInput:
    return LocalRiskInput.model_validate(
        {
            "questionnaire_id": "risk_questionnaire_v1",
            "questionnaire_version": "v1",
            "answers": [
                {"question_id": question_id, "answer_code": f"{question_id}_{letter}"}
                for question_id in QUESTION_IDS[:count]
            ],
        },
        strict=True,
    )


def submission(
    key: str | None = None, *, letter: str = "C", reverse: bool = False
) -> LocalRiskSubmitRequest:
    data = input_payload(letter).model_dump(mode="json")
    if reverse:
        data["answers"] = list(reversed(data["answers"]))
    return LocalRiskSubmitRequest.model_validate(
        {**data, "idempotency_key": key or str(uuid4())}, strict=True
    )


def profile(label: str = "Synthetic learner") -> LocalDraftRequest:
    return LocalDraftRequest(
        profile_schema_version="profile.v1", display_name=label, experience_level="beginner"
    )


def consent(accepted: bool) -> LocalConsentRequest:
    return LocalConsentRequest(consent_version="consent.v1", consent_given=accepted)


def complete_persona(service: LocalApplicationService, alias: str = "learner-a") -> str:
    credential = service.login(alias).access_token
    service.draft(credential, profile())
    service.consent(credential, consent(True))
    assert service.complete(credential, "consent.v1", "profile.v1").onboarding_completed
    return credential


class PausedS1CommitStore(SQLiteLocalApplicationStore):
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


class PausedRiskCommitStore(SQLiteLocalRiskStore):
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
                raise RuntimeError("Synthetic risk race was not released")


class ObservedRiskStore(SQLiteLocalRiskStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.begin_attempted = Event()

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def observe(statement: str) -> None:
            # No SQL/parameters/credentials are ever collected or printed.
            if statement == "BEGIN IMMEDIATE":
                self.begin_attempted.set()

        connection.set_trace_callback(observe)
        return connection


class ObservedS1Store(SQLiteLocalApplicationStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.begin_attempted = Event()
        self.commit_calls = 0

    def _connect(self) -> sqlite3.Connection:
        connection = super()._connect()

        def observe(statement: str) -> None:
            # Observe the actual lock attempt only; never retain expanded SQL.
            if statement == "BEGIN IMMEDIATE":
                self.begin_attempted.set()

        connection.set_trace_callback(observe)
        return connection

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        self.commit_calls += 1


@pytest.mark.parametrize("mutation", ["logout", "withdraw"])
def test_risk_write_commits_once_before_waiting_s1_revocation_takes_effect(
    tmp_path: Path, mutation: str
) -> None:
    path = tmp_path / "risk-first-revocation-lock.sqlite3"
    clock = Clock()
    onboarding = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    credential = complete_persona(onboarding)
    owner_id = onboarding.me(credential).id
    first_store = PausedRiskCommitStore(path)
    risk = LocalRiskService(first_store, clock)
    second_store = ObservedS1Store(path)
    later_onboarding = LocalApplicationService(second_store, clock)
    first_store.pause_next = True
    payload = submission()

    def later_revocation() -> None:
        if mutation == "logout":
            later_onboarding.logout(credential)
        else:
            later_onboarding.consent(credential, consent(False))

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved_future = pool.submit(risk.submit, credential, payload)
        try:
            assert first_store.waiting.wait(2)
            revocation_future = pool.submit(later_revocation)
            assert second_store.begin_attempted.wait(2)
            assert not revocation_future.done()
        finally:
            first_store.release.set()
        saved = saved_future.result(timeout=4)
        revocation_future.result(timeout=4)
    assert first_store.commit_calls == 1
    assert second_store.commit_calls == 1

    # The revocation ordered after this commit now gates all later risk requests,
    # including the same-key retry; it must not replay or erase the first result.
    expected_code = "SESSION_INVALID" if mutation == "logout" else "ONBOARDING_REQUIRED"
    with pytest.raises(FinExException) as denied_history:
        risk.history(credential)
    assert denied_history.value.error_code == expected_code
    with pytest.raises(FinExException) as denied_assessment:
        risk.assessment(credential, saved.assessment_id)
    assert denied_assessment.value.error_code == expected_code
    with pytest.raises(FinExException) as denied_retry:
        risk.submit(credential, payload)
    assert denied_retry.value.error_code == expected_code
    assert first_store.commit_calls == 1

    with SQLiteLocalRiskStore(path).transaction() as transaction:
        rows = transaction.list_risk_assessments(owner_id, before=None, limit=20)
        assert len(rows) == 1
        assert rows[0].assessment_id == saved.assessment_id
        assert transaction.get_risk_draft(owner_id) is None
    if mutation == "logout":
        replacement = onboarding.login("learner-a")
        credential = replacement.access_token
        state = onboarding.state(credential)
        assert state.onboarding_completed
    else:
        state = onboarding.state(credential)
        assert state.consent is not None and not state.consent.accepted
        assert not state.onboarding_completed
        onboarding.consent(credential, consent(True))
        onboarding.complete(credential, "consent.v1", "profile.v1")
    restarted = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    assert restarted.history(credential).items == [saved]


@pytest.mark.parametrize(
    "mutation,expected_code",
    [
        ("logout", "SESSION_INVALID"),
        ("withdraw", "ONBOARDING_REQUIRED"),
        ("profile", "ONBOARDING_REQUIRED"),
        ("expiry", "SESSION_INVALID"),
    ],
)
def test_competing_risk_write_rechecks_s1_after_actual_native_lock(
    tmp_path: Path, mutation: str, expected_code: str
) -> None:
    path = tmp_path / "authorization-lock.sqlite3"
    clock = Clock()
    first_store = PausedS1CommitStore(path)
    first = LocalApplicationService(first_store, clock)
    credential = complete_persona(first)
    second_store = ObservedRiskStore(path)
    risk = LocalRiskService(second_store, clock)
    first_store.pause_next = True

    def mutate_s1() -> None:
        if mutation == "logout":
            first.logout(credential)
        elif mutation == "withdraw":
            first.consent(credential, consent(False))
        elif mutation == "profile":
            first.draft(credential, profile("Uncompleted replacement"))
        else:
            first.draft(credential, profile())

    def later_risk_write() -> str:
        try:
            risk.submit(credential, submission())
            return "incorrectly-saved"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        mutation_future = pool.submit(mutate_s1)
        try:
            assert first_store.waiting.wait(2)
            risk_future = pool.submit(later_risk_write)
            assert second_store.begin_attempted.wait(2)
            if mutation == "expiry":
                clock.now = NOW + timedelta(minutes=30)
        finally:
            first_store.release.set()
        mutation_future.result(timeout=4)
        result = risk_future.result(timeout=4)
    assert result == expected_code
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_risk_assessments").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM local_risk_drafts").fetchone()[0] == 0


@pytest.mark.parametrize("changed", [False, True])
def test_simultaneous_same_owner_retry_key_serializes_to_one_saved_record(
    tmp_path: Path, changed: bool
) -> None:
    path = tmp_path / "same-key-lock.sqlite3"
    clock = Clock()
    credential = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    first_store = PausedRiskCommitStore(path)
    first = LocalRiskService(first_store, clock)
    second_store = ObservedRiskStore(path)
    second = LocalRiskService(second_store, clock)
    first_store.pause_next = True
    key = str(uuid4())
    original_payload = submission(key)
    later_payload = submission(key, letter="B" if changed else "C", reverse=True)

    def later_submit() -> tuple[str, str]:
        try:
            saved = second.submit(credential, later_payload)
            return "saved", saved.assessment_id
        except FinExException as error:
            return error.error_code, ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        original_future = pool.submit(first.submit, credential, original_payload)
        try:
            assert first_store.waiting.wait(2)
            later_future = pool.submit(later_submit)
            assert second_store.begin_attempted.wait(2)
        finally:
            first_store.release.set()
        saved = original_future.result(timeout=4)
        outcome = later_future.result(timeout=4)
    assert outcome == (("IDEMPOTENCY_CONFLICT", "") if changed else ("saved", saved.assessment_id))
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_risk_assessments").fetchone()[0] == 1
    restarted = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    assert restarted.history(credential).items == [saved]
    # Equivalent reordering restores the original input order, times and document.
    assert restarted.submit(credential, submission(key, reverse=True)) == saved
    assert saved.input.answers == original_payload.answers


class FailedRiskCommitStore(SQLiteLocalRiskStore):
    def _before_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic failed assessment commit")


@pytest.mark.parametrize("operation", ["submit", "draft"])
def test_service_confirmation_waits_for_actual_commit_and_preserves_prior_state(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "service-confirmation.sqlite3"
    clock = Clock()
    credential = complete_persona(LocalApplicationService(SQLiteLocalApplicationStore(path), clock))
    healthy = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    before = healthy.save_draft(credential, input_payload(count=2))
    failed = LocalRiskService(FailedRiskCommitStore(path), clock)
    with pytest.raises(LocalStoreUnavailable):
        if operation == "submit":
            failed.submit(credential, submission())
        else:
            failed.save_draft(credential, input_payload(count=0))
    restarted = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    assert restarted.draft(credential) == before
    assert restarted.history(credential).items == []


def test_real_saved_snapshot_restart_and_ownership_survive_later_rules_source_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "stored-snapshot.sqlite3"
    clock = Clock()
    onboarding = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    credential = complete_persona(onboarding)
    other_credential = complete_persona(onboarding, "learner-b")
    service = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    saved = service.submit(credential, submission())
    assert service.draft(credential).answers == []

    def unavailable_source(self: LocalRiskService) -> None:
        raise RuntimeError("Synthetic current rules source failure")

    monkeypatch.setattr(LocalRiskService, "_approved_engine", unavailable_source)
    restarted = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    assert restarted.assessment(credential, saved.assessment_id) == saved
    assert restarted.history(credential).items == [saved]
    assert restarted.history(other_credential).items == []
    with pytest.raises(FinExException) as denied:
        restarted.assessment(other_credential, saved.assessment_id)
    assert denied.value.error_code == "RISK_ASSESSMENT_NOT_FOUND"


def test_separate_owner_can_use_same_key_but_never_read_another_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "native-owner-keys.sqlite3"
    clock = Clock()
    onboarding = LocalApplicationService(SQLiteLocalApplicationStore(path), clock)
    credential = complete_persona(onboarding)
    other_credential = complete_persona(onboarding, "learner-b")
    service = LocalRiskService(SQLiteLocalRiskStore(path), clock)
    key = str(uuid4())
    first = service.submit(credential, submission(key))
    other = service.submit(other_credential, submission(key, letter="B"))
    assert first.assessment_id != other.assessment_id
    assert service.history(credential).items == [first]
    assert service.history(other_credential).items == [other]
    with pytest.raises(FinExException) as denied:
        service.assessment(credential, other.assessment_id)
    assert denied.value.error_code == "RISK_ASSESSMENT_NOT_FOUND"
