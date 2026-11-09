"""Real file persistence, rollback and serialized authorization; no cloud/Docker."""

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.main import create_app
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.services.local_application_service import LocalApplicationService
from tests.contract.test_local_s1_api import (
    AUTH,
    CONSENT,
    ONBOARDING,
    PROFILE,
    TestClock,
    finish,
    login,
    state,
)


def application_client(
    path: Path, clock: TestClock, store: SQLiteLocalApplicationStore | None = None
) -> TestClient:
    return TestClient(
        create_app(
            Settings(local_app_enabled=True, local_db_path=path),
            local_store=store,
            local_clock=clock,
        )
    )


def raw_token(headers: dict[str, str]) -> str:
    return headers["Authorization"].split()[1]


def test_restart_preserves_identity_profile_consent_and_revocation(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    clock = TestClock()
    first = application_client(path, clock)
    headers = login(first)
    completed = finish(first, headers)
    identity = first.get(f"{AUTH}/me", headers=headers).json()["data"]["user"]
    second = application_client(path, clock)
    assert state(second, headers) == completed
    assert second.get(f"{AUTH}/me", headers=headers).json()["data"]["user"] == identity
    assert second.post(f"{AUTH}/logout", headers=headers, json={}).status_code == 200
    third = application_client(path, clock)
    assert third.get(f"{AUTH}/me", headers=headers).status_code == 401
    replacement = login(third)
    assert state(third, replacement) == completed
    assert third.get(f"{AUTH}/me", headers=replacement).json()["data"]["user"] == identity
    other = login(third, "learner-b")
    assert state(third, other)["draft"]["display_name"] is None


def test_only_session_digest_is_persisted_and_consent_order_is_monotonic(tmp_path: Path) -> None:
    path = tmp_path / "digest.sqlite3"
    client = application_client(path, TestClock())
    headers = login(client)
    token = raw_token(headers)
    assert len(token) == 43
    for accepted in (True, False, True):
        client.post(
            f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": accepted}
        )
    with closing(sqlite3.connect(path)) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(local_sessions)")]
        assert "access_token" not in columns and "token" not in columns
        digest = connection.execute("SELECT digest FROM local_sessions").fetchone()[0]
        assert digest == hashlib.sha256(token.encode()).hexdigest()
        rows = connection.execute(
            "SELECT event_id,accepted,recorded_at FROM local_consent_events ORDER BY event_id"
        ).fetchall()
        assert [row[1] for row in rows] == [1, 0, 1]
        assert len({row[2] for row in rows}) == 1
        assert [row[0] for row in rows] == sorted(row[0] for row in rows)
    assert token.encode() not in path.read_bytes()
    assert state(client, headers)["consent"]["accepted"] is True
    assert state(client, headers)["onboarding_completed"] is False


class FailingCommitStore(SQLiteLocalApplicationStore):
    fail_next = False

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        if self.fail_next:
            self.fail_next = False
            raise sqlite3.OperationalError("Internal storage details must not be exposed")


def test_precommit_failure_rolls_back_consent_and_completion(tmp_path: Path) -> None:
    path = tmp_path / "rollback.sqlite3"
    store = FailingCommitStore(path)
    client = application_client(path, TestClock(), store)
    headers = login(client)
    before = finish(client, headers)
    store.fail_next = True
    response = client.post(
        f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": False}
    )
    assert response.status_code == 503
    assert response.json()["error_code"] == "LOCAL_STORE_UNAVAILABLE"
    assert "Internal storage details" not in response.text
    assert str(path) not in response.text
    assert state(client, headers) == before
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_consent_events").fetchone()[0] == 1


def test_login_failure_leaves_no_partial_user_or_plaintext_session(tmp_path: Path) -> None:
    path = tmp_path / "login-rollback.sqlite3"
    store = FailingCommitStore(path)
    store.fail_next = True
    client = application_client(path, TestClock(), store)
    response = client.post(f"{AUTH}/mock-login", json={"alias": "learner-a"})
    assert response.status_code == 503
    assert "access_token" not in response.text
    with closing(sqlite3.connect(path)) as connection:
        for table in ("local_users", "local_sessions", "local_onboarding"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_later_domain_gate_is_in_same_transaction_and_preserves_saved_data(tmp_path: Path) -> None:
    path = tmp_path / "gate.sqlite3"
    client = application_client(path, TestClock())
    headers = login(client)
    token = raw_token(headers)
    service: LocalApplicationService = client.app.state.local_application_service
    with pytest.raises(FinExException) as error:
        with service.authorized_transaction(token, write=True, onboarding_required=True):
            pytest.fail("An incomplete persona entered a domain transaction")
    assert error.value.error_code == "ONBOARDING_REQUIRED"
    finish(client, headers)
    with service.authorized_transaction(token, onboarding_required=True) as (session, transaction):
        assert transaction.get_onboarding(session.user.id).display_name == "Test learner"
    client.post(f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": False})
    client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT)
    with pytest.raises(FinExException) as error:
        with service.authorized_transaction(token, write=True, onboarding_required=True):
            pytest.fail("Reacceptance alone restored completion")
    assert error.value.error_code == "ONBOARDING_REQUIRED"
    assert state(client, headers)["draft"]["display_name"] == "Test learner"


def test_withdrawal_wins_concurrent_domain_write_before_authorization(tmp_path: Path) -> None:
    path = tmp_path / "race.sqlite3"
    client = application_client(path, TestClock())
    headers = login(client)
    finish(client, headers)
    token = raw_token(headers)
    service: LocalApplicationService = client.app.state.local_application_service
    withdrawal_locked = Event()
    writer_started = Event()
    release_withdrawal = Event()

    def withdraw() -> None:
        with service.authorized_transaction(token, write=True) as (session, transaction):
            transaction.append_consent(session.user.id, "consent.v1", False, service.clock())
            transaction.save_onboarding(
                replace(transaction.get_onboarding(session.user.id), completed_at=None)
            )
            withdrawal_locked.set()
            assert release_withdrawal.wait(2)

    def later_write() -> str:
        writer_started.set()
        try:
            with service.authorized_transaction(token, write=True, onboarding_required=True):
                return "incorrectly-authorized"
        except FinExException as error:
            return error.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        withdrawal = pool.submit(withdraw)
        assert withdrawal_locked.wait(2)
        writer = pool.submit(later_write)
        assert writer_started.wait(2)
        release_withdrawal.set()
        withdrawal.result(timeout=4)
        assert writer.result(timeout=4) == "ONBOARDING_REQUIRED"
    assert state(client, headers)["onboarding_completed"] is False


def test_restart_does_not_resurrect_expired_session(tmp_path: Path) -> None:
    path = tmp_path / "expired.sqlite3"
    clock = TestClock()
    headers = login(application_client(path, clock))
    clock.now += timedelta(minutes=30)
    restarted = application_client(path, clock)
    assert restarted.get(f"{AUTH}/me", headers=headers).status_code == 401


def test_onboarding_changes_invalidates_later_domain_gate(tmp_path: Path) -> None:
    path = tmp_path / "changed.sqlite3"
    client = application_client(path, TestClock())
    headers = login(client)
    finish(client, headers)
    client.put(
        f"{ONBOARDING}/draft", headers=headers, json={**PROFILE, "experience_level": "advanced"}
    )
    service: LocalApplicationService = client.app.state.local_application_service
    with pytest.raises(FinExException) as error:
        with service.authorized_transaction(raw_token(headers), onboarding_required=True):
            pytest.fail("A changed profile bypassed completion")
    assert error.value.error_code == "ONBOARDING_REQUIRED"


@pytest.mark.parametrize(
    "stored",
    [
        "2099-01-01T00:00:00",
        "2099-01-01T00:00:00+01:00",
        "malformed-time",
        b"2099-01-01T00:00:00+00:00",
    ],
)
@pytest.mark.parametrize(
    ("table", "column", "endpoint"),
    [
        ("local_sessions", "expires_at", f"{AUTH}/me"),
        ("local_sessions", "revoked_at", f"{AUTH}/me"),
        ("local_onboarding", "updated_at", f"{ONBOARDING}/state"),
        ("local_onboarding", "completed_at", f"{ONBOARDING}/state"),
        ("local_consent_events", "recorded_at", f"{ONBOARDING}/state"),
    ],
)
def test_corrupt_persisted_times_are_safe_storage_failures(
    tmp_path: Path, stored: str | bytes, table: str, column: str, endpoint: str
) -> None:
    path = tmp_path / "corrupt-time.sqlite3"
    application = create_app(
        Settings(local_app_enabled=True, local_db_path=path), local_clock=TestClock()
    )
    client = TestClient(application, raise_server_exceptions=False)
    headers = login(client)
    finish(client, headers)
    with closing(sqlite3.connect(path)) as connection:
        if table == "local_consent_events":
            # Add a corrupt last event without disabling immutable-history triggers.
            owner = connection.execute("SELECT user_id FROM local_users").fetchone()[0]
            connection.execute(
                "INSERT INTO local_consent_events(user_id,version,accepted,recorded_at) "
                "VALUES(?,'consent.v1',1,?)",
                (owner, stored),
            )
        else:
            # Identifiers come only from this fixed test matrix, never API input.
            connection.execute(f"UPDATE {table} SET {column}=?", (stored,))
        connection.commit()
    response = client.get(endpoint, headers=headers)
    assert response.status_code == 503
    assert response.json()["error_code"] == "LOCAL_STORE_UNAVAILABLE"
    leaked_token = raw_token(headers) in response.text
    leaked_path = str(path) in response.text
    assert leaked_token is False
    assert leaked_path is False
