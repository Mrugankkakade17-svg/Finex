"""Focused typed-adapter acceptance over real isolated native SQLite.

These cases were written before the adapter source. Schema RED evidence is in
the companion physical SQL/migration tests, not a missing-module import error.
Documents here are intentionally opaque storage fixtures, not scored results.
"""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.local_application import (
    LocalSession,
    LocalStoreUnavailable,
    LocalUser,
    OnboardingRecord,
)
from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.ports.adapters.sqlite_local_application import (
    SQLiteLocalApplicationStore,
    SQLiteLocalTransaction,
)
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore, SQLiteLocalRiskTransaction

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
DIGEST = "a" * 64
PARTIAL = '[{"question_id":"C5","answer_code":"C5_C"},{"question_id":"W1","answer_code":"W1_A"}]'


def prepare(path: Path) -> SQLiteLocalRiskStore:
    user = LocalUser(OWNER, "learner-a")
    with SQLiteLocalApplicationStore(path).transaction(write=True) as transaction:
        transaction.create_user(user, "profile.v1", NOW)
        transaction.create_user(LocalUser(OTHER, "learner-b"), "profile.v1", NOW)
        transaction.insert_session(
            LocalSession(DIGEST, user, NOW + timedelta(minutes=30), None), NOW
        )
        transaction.save_onboarding(
            OnboardingRecord(OWNER, "profile.v1", "Synthetic learner", "beginner", NOW, NOW)
        )
        transaction.append_consent(OWNER, "consent.v1", True, NOW)
    return SQLiteLocalRiskStore(path)


def draft(*, owner: str = OWNER, answers: str = PARTIAL) -> LocalRiskDraftRecord:
    return LocalRiskDraftRecord(owner, "risk_questionnaire_v1", "v1", answers, NOW)


def assessment(*, owner: str = OWNER, key: str | None = None) -> LocalRiskAssessmentRecord:
    return LocalRiskAssessmentRecord(
        str(uuid4()),
        owner,
        key or str(uuid4()),
        "b" * 64,
        '{"synthetic_sql_fixture":"opaque immutable document"}',
        NOW,
    )


def test_risk_store_construction_performs_no_filesystem_operation(tmp_path: Path) -> None:
    path = tmp_path / "not-created" / "owned.sqlite3"
    SQLiteLocalRiskStore(path)
    assert not path.parent.exists()


def test_typed_risk_capability_has_auth_reads_but_no_s1_mutators(tmp_path: Path) -> None:
    store = prepare(tmp_path / "typed-capability.sqlite3")
    with store.transaction() as transaction:
        session = transaction.get_session(DIGEST)
        assert session is not None and session.user.id == OWNER
        assert transaction.get_onboarding(OWNER).completed_at == NOW
        consent = transaction.latest_consent(OWNER)
        assert consent is not None and consent.accepted
        assert transaction.get_risk_draft(OWNER) is None
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []
        for name in (
            "create_user",
            "insert_session",
            "revoke_session",
            "save_onboarding",
            "append_consent",
        ):
            assert not hasattr(transaction, name)
    assert not issubclass(SQLiteLocalRiskTransaction, SQLiteLocalTransaction)


def test_draft_full_replacement_empty_clear_and_native_restart_are_owner_isolated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "draft-restart.sqlite3"
    store = prepare(path)
    original = draft()
    with store.transaction(write=True) as transaction:
        transaction.save_risk_draft(original)
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) == original
        assert transaction.get_risk_draft(OTHER) is None
    empty = replace(original, answers_json="[]", updated_at=NOW + timedelta(seconds=1))
    with store.transaction(write=True) as transaction:
        transaction.save_risk_draft(empty)
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) == empty
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []


def test_assessment_insert_returns_native_sequence_and_preserves_opaque_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "assessment-restart.sqlite3"
    store = prepare(path)
    record = assessment()
    with store.transaction(write=True) as transaction:
        inserted = transaction.insert_risk_assessment(record)
    assert inserted.sequence > 0
    assert replace(inserted, sequence=0) == record
    assert record.sequence == 0
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert transaction.get_risk_assessment(OWNER, record.assessment_id) == inserted
        assert transaction.get_risk_assessment_by_key(OWNER, record.idempotency_key) == inserted
        assert transaction.get_risk_assessment(OTHER, record.assessment_id) is None
        assert transaction.get_risk_assessment_by_key(OTHER, record.idempotency_key) is None


def test_same_retry_key_is_unique_per_owner_and_duplicate_write_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "retry-owner.sqlite3"
    store = prepare(path)
    record = assessment()
    other = assessment(owner=OTHER, key=record.idempotency_key)
    with store.transaction(write=True) as transaction:
        first = transaction.insert_risk_assessment(record)
        second = transaction.insert_risk_assessment(other)
    assert second.sequence > first.sequence
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.save_risk_draft(draft())
            transaction.insert_risk_assessment(assessment(key=record.idempotency_key))
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) is None
        assert transaction.get_risk_assessment_by_key(OWNER, record.idempotency_key) == first
        assert transaction.get_risk_assessment_by_key(OTHER, record.idempotency_key) == second


def test_globally_unique_resource_id_cannot_be_replaced_by_another_owner(tmp_path: Path) -> None:
    store = prepare(tmp_path / "resource-owner.sqlite3")
    original = assessment()
    with store.transaction(write=True) as transaction:
        saved = transaction.insert_risk_assessment(original)
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.insert_risk_assessment(
                replace(assessment(owner=OTHER), assessment_id=original.assessment_id)
            )
    with store.transaction() as transaction:
        assert transaction.get_risk_assessment(OWNER, original.assessment_id) == saved
        assert transaction.get_risk_assessment(OTHER, original.assessment_id) is None


def test_history_is_descending_owner_filtered_and_bounded_before_native_sequence(
    tmp_path: Path,
) -> None:
    store = prepare(tmp_path / "sequence-pagination.sqlite3")
    with store.transaction(write=True) as transaction:
        first = transaction.insert_risk_assessment(assessment())
        transaction.insert_risk_assessment(assessment(owner=OTHER))
        middle = transaction.insert_risk_assessment(assessment())
        latest = transaction.insert_risk_assessment(assessment())
    with store.transaction() as transaction:
        assert transaction.list_risk_assessments(OWNER, before=None, limit=2) == [latest, middle]
        assert transaction.list_risk_assessments(OWNER, before=middle.sequence, limit=2) == [first]
        assert transaction.list_risk_assessments(OWNER, before=first.sequence, limit=2) == []


@pytest.mark.parametrize(
    "limit,before", [(0, None), (52, None), (True, None), (20, 0), (20, True), (20, 2**63)]
)
def test_adapter_rejects_unbounded_or_invalid_internal_history_arguments(
    tmp_path: Path, limit: int, before: int | None
) -> None:
    store = prepare(tmp_path / "bounded-history.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.list_risk_assessments(OWNER, before=before, limit=limit)


@pytest.mark.parametrize("target", ["draft", "assessment"])
def test_read_snapshot_cannot_write_risk_records(tmp_path: Path, target: str) -> None:
    store = prepare(tmp_path / "query-only-risk.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            if target == "draft":
                transaction.save_risk_draft(draft())
            else:
                transaction.insert_risk_assessment(assessment())
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) is None
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []


@pytest.mark.parametrize("target", ["draft", "assessment"])
def test_risk_foreign_key_rejects_unknown_owner(tmp_path: Path, target: str) -> None:
    store = prepare(tmp_path / "risk-fk.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            if target == "draft":
                transaction.save_risk_draft(draft(owner="unknown-owner"))
            else:
                transaction.insert_risk_assessment(assessment(owner="unknown-owner"))


def test_parameterized_owner_and_identifiers_cannot_expand_read_scope(tmp_path: Path) -> None:
    store = prepare(tmp_path / "parameterized-risk.sqlite3")
    record = assessment()
    with store.transaction(write=True) as transaction:
        transaction.save_risk_draft(draft())
        transaction.insert_risk_assessment(record)
    injection = "' OR 1=1 --"
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(injection) is None
        assert transaction.get_risk_assessment(injection, record.assessment_id) is None
        assert transaction.get_risk_assessment(OWNER, injection) is None
        assert transaction.get_risk_assessment_by_key(injection, record.idempotency_key) is None
        assert transaction.get_risk_assessment_by_key(OWNER, injection) is None
        assert transaction.list_risk_assessments(injection, before=None, limit=20) == []


def test_user_exception_rolls_back_both_draft_and_assessment(tmp_path: Path) -> None:
    store = prepare(tmp_path / "risk-rollback.sqlite3")
    with pytest.raises(RuntimeError, match="Synthetic abort"):
        with store.transaction(write=True) as transaction:
            transaction.save_risk_draft(draft())
            transaction.insert_risk_assessment(assessment())
            raise RuntimeError("Synthetic abort")
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) is None
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []


class FailedCommitStore(SQLiteLocalRiskStore):
    def _before_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic risk precommit failure")


def test_precommit_failure_rolls_back_risk_sql_but_not_prior_bootstrap(tmp_path: Path) -> None:
    path = tmp_path / "risk-precommit.sqlite3"
    store = prepare(path)
    original = draft()
    with store.transaction(write=True) as transaction:
        transaction.save_risk_draft(original)
    with pytest.raises(LocalStoreUnavailable):
        with FailedCommitStore(path).transaction(write=True) as transaction:
            transaction.save_risk_draft(replace(original, answers_json="[]"))
            transaction.insert_risk_assessment(assessment())
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) == original
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []


@pytest.mark.parametrize("target", ["draft", "assessment"])
@pytest.mark.parametrize(
    "bad_time", ["not-a-time", "2026-10-11T12:00:00", "2026-10-11T12:00:00+02:00"]
)
def test_corrupt_stored_risk_time_fails_closed(tmp_path: Path, target: str, bad_time: str) -> None:
    path = tmp_path / "invalid-risk-time.sqlite3"
    store = prepare(path)
    record = assessment()
    with store.transaction(write=True) as transaction:
        if target == "draft":
            transaction.save_risk_draft(draft())
    with closing(sqlite3.connect(path)) as connection:
        if target == "draft":
            connection.execute("UPDATE local_risk_drafts SET updated_at=?", (bad_time,))
        else:
            connection.execute(
                "INSERT INTO local_risk_assessments(assessment_id,user_id,idempotency_key,"
                "request_fingerprint,document_json,created_at) VALUES(?,?,?,?,?,?)",
                (
                    record.assessment_id,
                    record.user_id,
                    record.idempotency_key,
                    record.request_fingerprint,
                    record.document_json,
                    bad_time,
                ),
            )
        connection.commit()
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            if target == "draft":
                transaction.get_risk_draft(OWNER)
            else:
                transaction.get_risk_assessment(OWNER, record.assessment_id)


@pytest.mark.parametrize("target", ["draft", "assessment"])
def test_naive_record_time_cannot_be_written(tmp_path: Path, target: str) -> None:
    store = prepare(tmp_path / "naive-write.sqlite3")
    naive = NOW.replace(tzinfo=None)
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            if target == "draft":
                transaction.save_risk_draft(replace(draft(), updated_at=naive))
            else:
                transaction.insert_risk_assessment(replace(assessment(), created_at=naive))


def test_read_unit_keeps_auth_and_draft_on_one_wal_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "risk-snapshot.sqlite3"
    store = prepare(path)
    original = draft()
    replacement = replace(original, answers_json="[]", updated_at=NOW + timedelta(seconds=1))
    with store.transaction(write=True) as transaction:
        transaction.save_risk_draft(original)
    with store.transaction() as reader:
        assert reader.get_session(DIGEST) is not None
        assert reader.get_risk_draft(OWNER) == original
        with SQLiteLocalRiskStore(path).transaction(write=True) as writer:
            writer.save_risk_draft(replacement)
        assert reader.get_risk_draft(OWNER) == original
    with store.transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) == replacement


def test_insert_rejects_caller_supplied_sequence_before_writing(tmp_path: Path) -> None:
    store = prepare(tmp_path / "caller-sequence.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.insert_risk_assessment(replace(assessment(), sequence=7))
    with store.transaction() as transaction:
        assert transaction.list_risk_assessments(OWNER, before=None, limit=20) == []


def test_native_connection_keeps_foreign_keys_and_three_second_busy_timeout(tmp_path: Path) -> None:
    store = prepare(tmp_path / "connection-bounds.sqlite3")
    with closing(store._connect()) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 3000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
