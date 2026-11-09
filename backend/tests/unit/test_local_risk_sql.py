"""Physical risk schema guarantees, tested before adapter implementation."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.local_application import LocalUser
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


def prepare_owners(path: Path) -> None:
    with SQLiteLocalApplicationStore(path).transaction(write=True) as transaction:
        transaction.create_user(LocalUser(OWNER, "learner-a"), "profile.v1", NOW)
        transaction.create_user(LocalUser(OTHER, "learner-b"), "profile.v1", NOW)


def insert_assessment(
    connection: sqlite3.Connection, owner: str, key: str, *, assessment_id: str | None = None
) -> int:
    cursor = connection.execute(
        "INSERT INTO local_risk_assessments(assessment_id,user_id,idempotency_key,"
        "request_fingerprint,document_json,created_at) VALUES(?,?,?,?,?,?)",
        (
            assessment_id or str(uuid4()),
            owner,
            key,
            "b" * 64,
            '{"synthetic_sql_fixture":"opaque immutable document"}',
            NOW.isoformat(),
        ),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_risk_draft_has_one_owned_row_fk_and_exact_ordered_json(tmp_path: Path) -> None:
    path = tmp_path / "owned-risk-draft.sqlite3"
    prepare_owners(path)
    answers = json.dumps(
        [
            {"question_id": "C5", "answer_code": "C5_C"},
            {"question_id": "W1", "answer_code": "W1_A"},
        ],
        separators=(",", ":"),
    )
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO local_risk_drafts VALUES(?,?,?,?,?)",
            (OWNER, "risk_questionnaire_v1", "v1", answers, NOW.isoformat()),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO local_risk_drafts VALUES(?,?,?,?,?)",
                (OWNER, "risk_questionnaire_v1", "v1", "[]", NOW.isoformat()),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO local_risk_drafts VALUES(?,?,?,?,?)",
                ("unknown-owner", "risk_questionnaire_v1", "v1", "[]", NOW.isoformat()),
            )
        connection.commit()
    with closing(sqlite3.connect(path)) as restarted:
        row = restarted.execute(
            "SELECT answers_json,updated_at FROM local_risk_drafts WHERE user_id=?", (OWNER,)
        ).fetchone()
        assert row == (answers, NOW.isoformat())
        assert (
            restarted.execute(
                "SELECT COUNT(*) FROM local_risk_drafts WHERE user_id=?", (OTHER,)
            ).fetchone()[0]
            == 0
        )


def test_risk_history_assigns_sequence_and_unique_owner_key_not_global_key(tmp_path: Path) -> None:
    path = tmp_path / "owned-retry-keys.sqlite3"
    prepare_owners(path)
    key = str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        first = insert_assessment(connection, OWNER, key)
        other = insert_assessment(connection, OTHER, key)
        latest = insert_assessment(connection, OWNER, str(uuid4()))
        assert 0 < first < other < latest
        with pytest.raises(sqlite3.IntegrityError):
            insert_assessment(connection, OWNER, key)
        with pytest.raises(sqlite3.IntegrityError):
            insert_assessment(connection, "unknown-owner", str(uuid4()))
        connection.commit()
        owned = connection.execute(
            "SELECT sequence FROM local_risk_assessments WHERE user_id=? ORDER BY sequence DESC",
            (OWNER,),
        ).fetchall()
        assert [row[0] for row in owned] == [latest, first]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(local_risk_assessments)")
        }
        assert {"sequence", "assessment_id", "user_id", "idempotency_key"}.issubset(columns)


def test_risk_history_update_delete_triggers_preserve_document_and_sequence(tmp_path: Path) -> None:
    path = tmp_path / "immutable-risk-history.sqlite3"
    prepare_owners(path)
    with closing(sqlite3.connect(path)) as connection:
        sequence = insert_assessment(connection, OWNER, str(uuid4()))
        connection.commit()
        for statement in (
            "UPDATE local_risk_assessments SET document_json='{}'",
            "UPDATE local_risk_assessments SET user_id='other-owner'",
            "DELETE FROM local_risk_assessments",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
        row = connection.execute(
            "SELECT sequence,document_json FROM local_risk_assessments"
        ).fetchone()
        assert row == (sequence, '{"synthetic_sql_fixture":"opaque immutable document"}')


def test_risk_assessment_uuid_is_unique_and_owner_sequence_index_is_present(tmp_path: Path) -> None:
    path = tmp_path / "risk-resource-index.sqlite3"
    prepare_owners(path)
    assessment_id = str(uuid4())
    with closing(sqlite3.connect(path)) as connection:
        insert_assessment(connection, OWNER, str(uuid4()), assessment_id=assessment_id)
        with pytest.raises(sqlite3.IntegrityError):
            insert_assessment(connection, OTHER, str(uuid4()), assessment_id=assessment_id)
        indexes = list(connection.execute("PRAGMA index_list(local_risk_assessments)"))
        indexed_columns = {
            tuple(row[2] for row in connection.execute(f"PRAGMA index_info('{index[1]}')"))
            for index in indexes
        }
        assert ("user_id", "sequence") in indexed_columns
