"""Owned saved-risk rules against a typed, atomic in-memory unit of work.

These assertions were authored before the service implementation. The HTTP
baseline supplies real behavior RED; absent new modules are not counted as RED.
Personas, answers and credentials below are synthetic and memory-only.
"""

import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Iterator
from uuid import uuid4

import pytest
from ai.risk.contract import RiskContractError, educational_explanation, evaluate_risk_contract
from ai.risk.scoring import RiskScoringEngine
from pydantic import ValidationError

from app.core.exceptions import FinExException
from app.domain.local_application import (
    ConsentRecord,
    LocalSession,
    LocalStoreUnavailable,
    LocalUser,
    OnboardingRecord,
)
from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider
from app.ports.local_risk_store import LocalRiskTransaction
from app.schemas.local_risk import LocalRiskInput, LocalRiskSubmitRequest
from app.services.local_risk_service import LocalRiskService
from tests.unit.test_local_risk_validation import SNAPSHOT_CORRUPTIONS, corrupt_snapshot

QUESTION_IDS = [f"{dimension}{index}" for dimension in ("W", "C") for index in range(1, 6)]
TOKEN_A = "a" * 43
TOKEN_B = "b" * 43
TIME = datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc)
GOLDENS = S2Dat01FixtureProvider().list_fixtures()


class MutableClock:
    def __init__(self) -> None:
        self.now = TIME

    def __call__(self) -> datetime:
        return self.now


class MemoryRiskTransaction:
    def __init__(self, store: "MemoryRiskStore", write: bool) -> None:
        self.store = store
        self.write = write

    def _read(self, name: str) -> None:
        assert self.store.active
        self.store.events.append(name)

    def _write(self, name: str) -> None:
        self._read(name)
        assert self.write

    def get_session(self, digest: str) -> LocalSession | None:
        self._read("session")
        return self.store.sessions.get(digest)

    def get_onboarding(self, user_id: str) -> OnboardingRecord:
        self._read("onboarding")
        return self.store.profiles[user_id]

    def latest_consent(self, user_id: str) -> ConsentRecord | None:
        self._read("consent")
        return self.store.consents.get(user_id)

    def get_risk_draft(self, user_id: str) -> LocalRiskDraftRecord | None:
        self._read("draft")
        return self.store.drafts.get(user_id)

    def save_risk_draft(self, record: LocalRiskDraftRecord) -> None:
        self._write("save")
        self.store.drafts[record.user_id] = record

    def get_risk_assessment(
        self, user_id: str, assessment_id: str
    ) -> LocalRiskAssessmentRecord | None:
        self._read("assessment")
        record = self.store.assessments.get(assessment_id)
        return record if record and record.user_id == user_id else None

    def get_risk_assessment_by_key(
        self, user_id: str, idempotency_key: str
    ) -> LocalRiskAssessmentRecord | None:
        self._read("key")
        return next(
            (
                record
                for record in self.store.assessments.values()
                if record.user_id == user_id and record.idempotency_key == idempotency_key
            ),
            None,
        )

    def insert_risk_assessment(
        self, record: LocalRiskAssessmentRecord
    ) -> LocalRiskAssessmentRecord:
        self._write("insert")
        assert not any(
            row.user_id == record.user_id and row.idempotency_key == record.idempotency_key
            for row in self.store.assessments.values()
        )
        self.store.sequence += 1
        inserted = replace(record, sequence=self.store.sequence)
        self.store.assessments[record.assessment_id] = inserted
        return inserted

    def list_risk_assessments(
        self, user_id: str, *, before: int | None, limit: int
    ) -> list[LocalRiskAssessmentRecord]:
        self._read("list")
        self.store.last_limit = limit
        records = [
            row
            for row in self.store.assessments.values()
            if row.user_id == user_id and (before is None or row.sequence < before)
        ]
        return sorted(records, key=lambda row: row.sequence, reverse=True)[:limit]


class MemoryRiskStore:
    def __init__(self, clock: MutableClock) -> None:
        self.sessions: dict[str, LocalSession] = {}
        self.profiles: dict[str, OnboardingRecord] = {}
        self.consents: dict[str, ConsentRecord] = {}
        self.drafts: dict[str, LocalRiskDraftRecord] = {}
        self.assessments: dict[str, LocalRiskAssessmentRecord] = {}
        self.sequence = 0
        self.active = False
        self.events: list[str] = []
        self.last_limit = 0
        self.fail_commit = False
        self.lock = RLock()
        for alias, token in (("learner-a", TOKEN_A), ("learner-b", TOKEN_B)):
            user = LocalUser(str(uuid4()), alias)
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            self.sessions[digest] = LocalSession(
                digest, user, clock.now + timedelta(minutes=30), None
            )
            self.profiles[user.id] = OnboardingRecord(
                user.id, "profile.v1", "Synthetic learner", "beginner", clock.now, clock.now
            )
            self.consents[user.id] = ConsentRecord(1, user.id, "consent.v1", True, clock.now)

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[LocalRiskTransaction]:
        with self.lock:
            assert not self.active
            self.active = True
            self.events.append("begin-write" if write else "begin-read")
            old_drafts = deepcopy(self.drafts)
            old_assessments = deepcopy(self.assessments)
            old_sequence = self.sequence
            try:
                yield MemoryRiskTransaction(self, write)
                if write and self.fail_commit:
                    raise LocalStoreUnavailable()
                self.events.append("commit")
            except Exception:
                self.drafts = old_drafts
                self.assessments = old_assessments
                self.sequence = old_sequence
                self.events.append("rollback")
                raise
            finally:
                self.active = False


@pytest.fixture
def owned() -> tuple[MemoryRiskStore, LocalRiskService, MutableClock]:
    clock = MutableClock()
    store = MemoryRiskStore(clock)
    return store, LocalRiskService(store, clock), clock


def input_payload(letter: str = "C", count: int = 10) -> LocalRiskInput:
    return LocalRiskInput.model_validate(
        {
            "questionnaire_id": "risk_questionnaire_v1",
            "questionnaire_version": "v1",
            "answers": [
                {"question_id": qid, "answer_code": f"{qid}_{letter}"}
                for qid in QUESTION_IDS[:count]
            ],
        }
    )


def submission(letter: str = "C", key: str | None = None) -> LocalRiskSubmitRequest:
    return LocalRiskSubmitRequest.model_validate(
        {**input_payload(letter).model_dump(), "idempotency_key": key or str(uuid4())}
    )


def owner_id(store: MemoryRiskStore, token: str = TOKEN_A) -> str:
    return store.sessions[hashlib.sha256(token.encode("utf-8")).hexdigest()].user.id


def assert_code(caught: pytest.ExceptionInfo[FinExException], status: int, code: str) -> None:
    assert caught.value.status_code == status
    assert caught.value.error_code == code


def test_records_are_immutable_and_uninserted_sequence_has_an_explicit_sentinel() -> None:
    draft = LocalRiskDraftRecord("owner", "risk_questionnaire_v1", "v1", "[]", TIME)
    record = LocalRiskAssessmentRecord(str(uuid4()), "owner", str(uuid4()), "f" * 64, "{}", TIME)
    assert record.sequence == 0
    with pytest.raises(FrozenInstanceError):
        setattr(draft, "user_id", "other")


def test_questionnaire_and_initial_draft_are_scoped_ordered_and_authorized(owned) -> None:
    store, service, _ = owned
    questionnaire = service.questionnaire(TOKEN_A)
    assert questionnaire.scope == "local_educational_application"
    assert questionnaire.contract_version == "local.v1"
    assert questionnaire.explanation_version == "educational_v1.0.0"
    assert [question.question_id for question in questionnaire.questions] == QUESTION_IDS
    assert store.events == ["begin-read", "session", "onboarding", "consent", "commit"]
    for question in questionnaire.questions:
        assert [option.code for option in question.options] == [
            f"{question.question_id}_{letter}" for letter in "ABCDE"
        ]
    draft = service.draft(TOKEN_A)
    assert draft.answers == []
    assert draft.updated_at is None
    assert service.history(TOKEN_A).items == []
    assert service.history(TOKEN_A).next_cursor is None


def test_draft_is_replacement_preserves_order_and_records_each_explicit_save(owned) -> None:
    store, service, clock = owned
    payload = input_payload(count=2)
    payload.answers.reverse()
    first = service.save_draft(TOKEN_A, payload)
    assert [answer.question_id for answer in first.answers] == ["W2", "W1"]
    assert first.updated_at == clock.now.isoformat()
    assert store.events == ["begin-write", "session", "onboarding", "consent", "save", "commit"]
    clock.now += timedelta(seconds=1)
    identical = service.save_draft(TOKEN_A, payload)
    assert identical.updated_at == clock.now.isoformat()
    assert identical.answers == first.answers
    cleared = service.save_draft(TOKEN_A, input_payload(count=0))
    assert cleared.answers == []
    assert cleared.updated_at is not None
    assert service.draft(TOKEN_B).answers == []
    assert not store.assessments


@pytest.mark.parametrize(
    "answers,code",
    [
        ([{"question_id": "W1", "answer_code": "W1_Z"}], "INVALID_ANSWER_CODE"),
        ([{"question_id": "W1", "answer_code": "C1_C"}], "ANSWER_NOT_PERMITTED_FOR_QUESTION"),
        ([{"question_id": "X1", "answer_code": "W1_C"}], "UNKNOWN_QUESTION_ID"),
        ([{"question_id": "W1", "answer_code": "   "}], "MALFORMED_ANSWER"),
        (
            [
                {"question_id": "W1", "answer_code": "W1_C"},
                {"question_id": "W1", "answer_code": "W1_D"},
            ],
            "DUPLICATE_QUESTION_ANSWER",
        ),
    ],
)
def test_partial_validation_omits_only_missing_and_failed_save_preserves_draft(
    owned, answers, code
) -> None:
    store, service, _ = owned
    first = service.save_draft(TOKEN_A, input_payload(count=1))
    payload = LocalRiskInput.model_validate({**input_payload().model_dump(), "answers": answers})
    with pytest.raises(FinExException) as caught:
        service.save_draft(TOKEN_A, payload)
    assert_code(caught, 400, code)
    assert service.draft(TOKEN_A) == first
    assert not store.assessments


def test_bad_version_precedes_duplicate_and_key_comparison(owned) -> None:
    store, service, _ = owned
    payload = submission()
    service.submit(TOKEN_A, payload)
    invalid = payload.model_dump()
    invalid["questionnaire_version"] = "v99"
    invalid["answers"].append(invalid["answers"][0])
    with pytest.raises(FinExException) as caught:
        service.submit(TOKEN_A, LocalRiskSubmitRequest.model_validate(invalid))
    assert_code(caught, 400, "UNSUPPORTED_QUESTIONNAIRE_VERSION")
    assert len(store.assessments) == 1


@pytest.mark.parametrize("fixture", GOLDENS, ids=[case["case_id"] for case in GOLDENS])
def test_saved_service_preserves_all_existing_golden_results_and_errors(owned, fixture) -> None:
    store, service, clock = owned
    if fixture["coverage"] == "malformed":
        with pytest.raises(RiskContractError) as logical:
            evaluate_risk_contract(fixture["request"], calculated_at=clock.now)
        assert logical.value.code == fixture["expected"]["error_code"]
        with pytest.raises(ValidationError):
            LocalRiskSubmitRequest.model_validate(
                {**fixture["request"], "idempotency_key": str(uuid4())}
            )
        assert not store.assessments
        return
    payload = LocalRiskSubmitRequest.model_validate(
        {**fixture["request"], "idempotency_key": str(uuid4())}
    )
    if fixture["kind"] == "invalid":
        with pytest.raises(FinExException) as caught:
            service.submit(TOKEN_A, payload)
        assert_code(caught, 400, fixture["expected"]["error_code"])
        assert not store.assessments
        return
    result = service.submit(TOKEN_A, payload)
    expected = evaluate_risk_contract(fixture["request"], calculated_at=clock.now)
    expected.setdefault("informational_tension", None)
    assert result.assessment.model_dump() == expected
    assert result.explanation.model_dump() == educational_explanation(expected)
    assert result.created_at == result.assessment.calculated_at == clock.now.isoformat()
    assert result.persisted is True
    assert result.input.model_dump() == fixture["request"]
    assert "informational_tension" in result.assessment.model_dump()
    assert service.assessment(TOKEN_A, result.assessment_id) == result


def test_retry_returns_exact_original_order_time_and_document_and_does_not_touch_draft(
    owned,
) -> None:
    store, service, clock = owned
    draft = service.save_draft(TOKEN_A, input_payload(count=2))
    payload = submission()
    first = service.submit(TOKEN_A, payload)
    row_before = next(iter(store.assessments.values()))
    clock.now += timedelta(seconds=20)
    reordered = payload.model_dump()
    reordered["answers"].reverse()
    retry = service.submit(TOKEN_A, LocalRiskSubmitRequest.model_validate(reordered))
    assert retry.model_dump() == first.model_dump()
    assert next(iter(store.assessments.values())) == row_before
    assert service.draft(TOKEN_A) == draft
    assert len(store.assessments) == 1
    assert "idempotency_key" not in retry.model_dump()
    assert "user_id" not in retry.model_dump()


def test_key_conflict_is_owner_scoped_and_semantic_failure_precedes_it(owned) -> None:
    store, service, _ = owned
    key = str(uuid4())
    first = service.submit(TOKEN_A, submission("C", key))
    second_owner = service.submit(TOKEN_B, submission("E", key))
    assert first.assessment_id != second_owner.assessment_id
    with pytest.raises(FinExException) as caught:
        service.submit(TOKEN_A, submission("E", key))
    assert_code(caught, 409, "IDEMPOTENCY_CONFLICT")
    invalid = submission("E", key).model_dump()
    invalid["answers"].pop()
    with pytest.raises(FinExException) as caught:
        service.submit(TOKEN_A, LocalRiskSubmitRequest.model_validate(invalid))
    assert_code(caught, 400, "MISSING_REQUIRED_QUESTION")
    assert len(store.assessments) == 2


def test_history_is_bounded_owned_and_sequence_ordered_across_equal_times_and_inserts(
    owned,
) -> None:
    store, service, _ = owned
    first = service.submit(TOKEN_A, submission("A"))
    service.submit(TOKEN_B, submission("E"))
    second = service.submit(TOKEN_A, submission("B"))
    third = service.submit(TOKEN_A, submission("C"))
    page = service.history(TOKEN_A, limit=2)
    assert [item.assessment_id for item in page.items] == [
        third.assessment_id,
        second.assessment_id,
    ]
    assert page.next_cursor is not None
    assert store.last_limit == 3
    service.submit(TOKEN_A, submission("D"))
    following = service.history(TOKEN_A, before=int(page.next_cursor), limit=2)
    assert [item.assessment_id for item in following.items] == [first.assessment_id]
    assert following.next_cursor is None
    with pytest.raises(FinExException) as other_owner:
        service.assessment(TOKEN_B, first.assessment_id)
    with pytest.raises(FinExException) as absent:
        service.assessment(TOKEN_B, str(uuid4()))
    assert_code(other_owner, 404, "RISK_ASSESSMENT_NOT_FOUND")
    assert (absent.value.status_code, absent.value.error_code, absent.value.message) == (
        other_owner.value.status_code,
        other_owner.value.error_code,
        other_owner.value.message,
    )


@pytest.mark.parametrize(
    "operation", ["questionnaire", "draft", "save", "submit", "history", "detail"]
)
@pytest.mark.parametrize("gate", ["expired", "revoked", "withdrawn", "profile", "reaccepted"])
def test_every_service_operation_uses_current_same_transaction_prerequisites(
    owned, operation: str, gate: str
) -> None:
    store, service, clock = owned
    digest = hashlib.sha256(TOKEN_A.encode("utf-8")).hexdigest()
    user_id = owner_id(store)
    if gate in {"expired", "revoked"}:
        store.sessions[digest] = replace(
            store.sessions[digest],
            expires_at=clock.now if gate == "expired" else clock.now + timedelta(minutes=1),
            revoked_at=clock.now if gate == "revoked" else None,
        )
    elif gate == "withdrawn":
        store.consents[user_id] = replace(store.consents[user_id], accepted=False)
    else:
        store.profiles[user_id] = replace(store.profiles[user_id], completed_at=None)
    actions = {
        "questionnaire": lambda: service.questionnaire(TOKEN_A),
        "draft": lambda: service.draft(TOKEN_A),
        "save": lambda: service.save_draft(TOKEN_A, input_payload(count=1)),
        "submit": lambda: service.submit(TOKEN_A, submission()),
        "history": lambda: service.history(TOKEN_A),
        "detail": lambda: service.assessment(TOKEN_A, str(uuid4())),
    }
    with pytest.raises(FinExException) as caught:
        actions[operation]()
    assert_code(
        caught,
        401 if gate in {"expired", "revoked"} else 409,
        "SESSION_INVALID" if gate in {"expired", "revoked"} else "ONBOARDING_REQUIRED",
    )
    assert "insert" not in store.events
    assert "save" not in store.events
    assert not store.assessments and not store.drafts
    assert store.events.count("session") == 1


def test_commit_failure_returns_no_confirmation_and_rolls_back_prior_state(owned) -> None:
    store, service, _ = owned
    draft = service.save_draft(TOKEN_A, input_payload(count=1))
    saved = service.submit(TOKEN_A, submission())
    store.fail_commit = True
    with pytest.raises(LocalStoreUnavailable):
        service.save_draft(TOKEN_A, input_payload("E", count=2))
    with pytest.raises(LocalStoreUnavailable):
        service.submit(TOKEN_A, submission("E"))
    store.fail_commit = False
    assert service.draft(TOKEN_A) == draft
    assert service.history(TOKEN_A).items == [saved]
    assert not store.active


def test_history_reproduces_stored_rules_without_reading_the_current_source_config(
    owned, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, service, clock = owned
    saved = service.submit(TOKEN_A, submission())

    def unavailable(*args, **kwargs):
        raise OSError("synthetic unavailable source")

    monkeypatch.setattr(RiskScoringEngine, "__init__", unavailable)
    fresh = LocalRiskService(store, clock)
    assert fresh.assessment(TOKEN_A, saved.assessment_id) == saved
    assert fresh.history(TOKEN_A).items == [saved]
    with pytest.raises(FinExException) as caught:
        fresh.questionnaire(TOKEN_A)
    assert_code(caught, 503, "RISK_ASSESSMENT_UNAVAILABLE")
    assert "synthetic unavailable source" not in caught.value.message


def test_unavailable_oversized_rules_never_become_a_cached_valid_engine(
    owned, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, service, _ = owned
    snapshot = deepcopy(RiskScoringEngine().config)
    snapshot["questionnaire"]["title"] = "X" * (70 * 1024)
    oversized = RiskScoringEngine.from_config(snapshot)

    def source(instance: RiskScoringEngine) -> None:
        instance.__dict__.update(oversized.__dict__)

    monkeypatch.setattr(RiskScoringEngine, "__init__", source)
    with pytest.raises(FinExException) as first:
        service.questionnaire(TOKEN_A)
    assert_code(first, 503, "RISK_ASSESSMENT_UNAVAILABLE")
    with pytest.raises(FinExException) as retry:
        service.save_draft(TOKEN_A, input_payload(count=1))
    assert_code(retry, 503, "RISK_ASSESSMENT_UNAVAILABLE")
    assert not store.drafts and not store.assessments


@pytest.mark.parametrize("operation", ["draft", "submit"])
def test_unexpected_validator_failure_is_an_opaque_safe_unavailable_error(
    owned, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    store, service, _ = owned

    def broken(*args, **kwargs):
        raise ValueError("synthetic private validator failure")

    monkeypatch.setattr("app.services.local_risk_service.validate_risk_input", broken)
    with pytest.raises(FinExException) as caught:
        if operation == "draft":
            service.save_draft(TOKEN_A, input_payload(count=1))
        else:
            service.submit(TOKEN_A, submission())
    assert_code(caught, 503, "RISK_ASSESSMENT_UNAVAILABLE")
    assert "synthetic private" not in caught.value.message
    assert not store.drafts and not store.assessments


def test_history_preserves_original_valid_utc_spelling_without_new_normalization(owned) -> None:
    store, service, _ = owned
    saved = service.submit(TOKEN_A, submission())
    row = store.assessments[saved.assessment_id]
    document = json.loads(row.document_json)
    original_time = document["created_at"].replace("+00:00", "Z")
    document["created_at"] = original_time
    document["assessment"]["calculated_at"] = original_time
    document["explanation"]["calculated_at"] = original_time
    store.assessments[row.assessment_id] = replace(row, document_json=json.dumps(document))
    restored = service.assessment(TOKEN_A, saved.assessment_id)
    assert restored.created_at == restored.assessment.calculated_at == original_time
    assert restored.explanation.calculated_at == original_time


@pytest.mark.parametrize(
    "corruption",
    [
        case
        for case in SNAPSHOT_CORRUPTIONS
        if not case.endswith("nonfinite") and not case.endswith("tuple")
    ],
)
def test_corrupt_rules_with_a_recomputed_hash_still_fail_public_history(
    owned, corruption: str
) -> None:
    store, service, _ = owned
    saved = service.submit(TOKEN_A, submission())
    row = store.assessments[saved.assessment_id]
    document = json.loads(row.document_json)
    corrupt_snapshot(document["rules_snapshot"], corruption)
    canonical = json.dumps(
        document["rules_snapshot"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    document["rules_sha256"] = hashlib.sha256(canonical).hexdigest()
    store.assessments[row.assessment_id] = replace(row, document_json=json.dumps(document))
    with pytest.raises(LocalStoreUnavailable):
        service.assessment(TOKEN_A, saved.assessment_id)
    with pytest.raises(LocalStoreUnavailable):
        service.history(TOKEN_A)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "local_educational_pilot"),
        ("persisted", False),
        ("assessment_id", "00000000-0000-4000-8000-000000000001"),
        ("created_at", "2026-10-11T16:00:01+00:00"),
        ("rules_sha256", "0" * 64),
        ("explanation_version", "educational_v99"),
    ],
)
def test_corrupt_stored_top_level_binding_never_returns_a_recalculated_fallback(
    owned, field: str, value: object
) -> None:
    store, service, _ = owned
    saved = service.submit(TOKEN_A, submission())
    row = store.assessments[saved.assessment_id]
    document = json.loads(row.document_json)
    document[field] = value
    store.assessments[row.assessment_id] = replace(row, document_json=json.dumps(document))
    with pytest.raises(LocalStoreUnavailable):
        service.assessment(TOKEN_A, saved.assessment_id)
    with pytest.raises(LocalStoreUnavailable):
        service.history(TOKEN_A)


@pytest.mark.parametrize(
    "corruption", ["score", "category", "explanation", "time", "input", "tension"]
)
def test_corrupt_stored_logical_result_or_input_is_rejected(owned, corruption: str) -> None:
    store, service, _ = owned
    saved = service.submit(TOKEN_A, submission())
    row = store.assessments[saved.assessment_id]
    document = json.loads(row.document_json)
    if corruption == "score":
        document["assessment"]["composite_score"] = 51.0
    elif corruption == "category":
        document["assessment"]["risk_category"]["label"] = "Aggressive"
    elif corruption == "explanation":
        document["explanation"]["summary"] = "synthetic inaccurate description"
    elif corruption == "time":
        document["explanation"]["calculated_at"] = "2026-10-11T16:00:01+00:00"
    elif corruption == "input":
        document["input"]["answers"][0]["answer_code"] = "W1_E"
    else:
        document["assessment"].pop("informational_tension")
    store.assessments[row.assessment_id] = replace(row, document_json=json.dumps(document))
    with pytest.raises(LocalStoreUnavailable):
        service.assessment(TOKEN_A, saved.assessment_id)


@pytest.mark.parametrize(
    "corruption", ["owner", "key", "fingerprint", "naive_time", "sequence", "json"]
)
def test_corrupt_stored_record_identity_and_types_are_opaque(
    owned, corruption: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, service, _ = owned
    saved = service.submit(TOKEN_A, submission())
    row = store.assessments[saved.assessment_id]
    if corruption == "owner":
        row = replace(row, user_id=owner_id(store, TOKEN_B))
        store.assessments[saved.assessment_id] = row
        # A malicious adapter returning a cross-owner row must not be trusted.
        monkeypatch.setattr(MemoryRiskTransaction, "get_risk_assessment", lambda *_: row)
        with pytest.raises(LocalStoreUnavailable):
            service.assessment(TOKEN_A, saved.assessment_id)
        return
    if corruption == "key":
        row = replace(row, idempotency_key="not-a-canonical-key")
    elif corruption == "fingerprint":
        row = replace(row, request_fingerprint="0" * 64)
    elif corruption == "naive_time":
        row = replace(row, created_at=TIME.replace(tzinfo=None))
    elif corruption == "sequence":
        row = replace(row, sequence=0)
    else:
        row = replace(row, document_json="{invalid")
    store.assessments[saved.assessment_id] = row
    with pytest.raises(LocalStoreUnavailable):
        service.assessment(TOKEN_A, saved.assessment_id)


@pytest.mark.parametrize("corruption", ["json", "version", "time", "answer"])
def test_corrupt_stored_drafts_are_not_normalized_into_valid_state(owned, corruption: str) -> None:
    store, service, _ = owned
    service.save_draft(TOKEN_A, input_payload(count=1))
    user_id = owner_id(store)
    row = store.drafts[user_id]
    if corruption == "json":
        row = replace(row, answers_json="{invalid")
    elif corruption == "version":
        row = replace(row, questionnaire_version="v99")
    elif corruption == "time":
        row = replace(row, updated_at=TIME.replace(tzinfo=None))
    else:
        row = replace(row, answers_json='[{"question_id":"W1","answer_code":"w1_c"}]')
    store.drafts[user_id] = row
    with pytest.raises(LocalStoreUnavailable):
        service.draft(TOKEN_A)


@pytest.mark.parametrize("limit,before", [(0, None), (51, None), (True, None), (20, 0), (20, True)])
def test_direct_pagination_is_bounded_and_never_coerces_bool(owned, limit, before) -> None:
    _, service, _ = owned
    with pytest.raises(FinExException) as caught:
        service.history(TOKEN_A, limit=limit, before=before)
    assert_code(caught, 422, "VALIDATION_ERROR")
