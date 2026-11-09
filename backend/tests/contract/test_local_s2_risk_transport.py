"""Additional strict wire and injection regressions for the frozen saved-risk API."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore
from app.routers import local_application
from tests.contract.test_local_s1_api import TestClock, assert_error
from tests.contract.test_local_s2_risk_api import RISK, application, completed, risk_input, saved


@pytest.mark.parametrize(
    "key",
    [
        "D2DB1A91-4D92-4BE8-BB2F-5344E8D3696A",
        "d2db1a91-4d92-1be8-bb2f-5344e8d3696a",
        "d2db1a91-4d92-4be8-7b2f-5344e8d3696a",
        "{d2db1a91-4d92-4be8-bb2f-5344e8d3696a}",
        "d2db1a91-4d92-4be8-bb2f-5344e8d3696a\n",
        42,
    ],
)
def test_retry_key_is_canonical_lowercase_uuid4_without_coercion(
    tmp_path: Path, key: object
) -> None:
    client = TestClient(application(tmp_path / "key.sqlite3"))
    headers = completed(client)
    response = client.post(
        f"{RISK}/assessments",
        headers=headers,
        json={**risk_input(), "idempotency_key": key},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
    assert client.get(f"{RISK}/assessments", headers=headers).json()["data"]["items"] == []


@pytest.mark.parametrize("field", ["questionnaire_id", "questionnaire_version"])
def test_numeric_questionnaire_identity_is_not_coerced(tmp_path: Path, field: str) -> None:
    client = TestClient(application(tmp_path / "identity.sqlite3"))
    headers = completed(client)
    payload = {**risk_input(), "idempotency_key": str(uuid4()), field: 1}
    assert_error(
        client.post(f"{RISK}/assessments", headers=headers, json=payload),
        422,
        "VALIDATION_ERROR",
    )


@pytest.mark.parametrize(
    "query",
    ["limit=+1", "limit=%201", "limit=1%20", "limit=١", "before=1.0", "before="],
)
def test_query_values_are_ascii_canonical_decimals(tmp_path: Path, query: str) -> None:
    client = TestClient(application(tmp_path / "query.sqlite3"))
    headers = completed(client)
    assert_error(
        client.get(f"{RISK}/assessments?{query}", headers=headers), 422, "VALIDATION_ERROR"
    )


def test_questionnaire_draft_and_history_asof_match_the_frozen_contract(tmp_path: Path) -> None:
    clock = TestClock()
    client = TestClient(application(tmp_path / "metadata.sqlite3", clock))
    headers = completed(client)
    for suffix in ("questionnaire", "draft", "assessments"):
        response = client.get(f"{RISK}/{suffix}", headers=headers)
        assert response.status_code == 200
        assert response.json()["meta"]["dataAsOf"] is None
    draft = client.put(f"{RISK}/draft", headers=headers, json=risk_input(partial=True))
    assert draft.status_code == 200
    assert draft.json()["meta"]["dataAsOf"] == clock.now.isoformat()
    fetched = client.get(f"{RISK}/draft", headers=headers)
    assert fetched.json()["meta"]["dataAsOf"] == draft.json()["data"]["updated_at"]
    result = saved(client, headers)
    assert set(result) == {
        "scope",
        "contract_version",
        "persisted",
        "assessment_id",
        "created_at",
        "input",
        "assessment",
        "explanation",
        "explanation_version",
        "rules_sha256",
        "rules_snapshot",
    }
    assert set(result["input"]) == {"questionnaire_id", "questionnaire_version", "answers"}
    assert "informational_tension" in result["assessment"]
    history = client.get(f"{RISK}/assessments", headers=headers)
    assert history.json()["meta"]["dataAsOf"] is None


class FalseyS1Store(SQLiteLocalApplicationStore):
    def __bool__(self) -> bool:
        return False


class FalseyRiskStore(SQLiteLocalRiskStore):
    def __bool__(self) -> bool:
        return False


def test_explicit_falsey_domain_injections_use_their_owned_database(tmp_path: Path) -> None:
    owned = tmp_path / "injected.sqlite3"
    fallback = tmp_path / "must-not-create.sqlite3"
    app = create_app(
        Settings(_env_file=None, local_app_enabled=True, local_db_path=fallback),
        local_store=FalseyS1Store(owned),
        local_risk_store=FalseyRiskStore(owned),
        local_clock=TestClock(),
    )
    assert not owned.exists() and not fallback.exists()
    client = TestClient(app)
    headers = completed(client)
    result = saved(client, headers)
    assert result["persisted"] is True
    assert owned.exists() and not fallback.exists()


def test_malformed_bearer_precedes_unavailable_risk_injection(tmp_path: Path) -> None:
    path = tmp_path / "must-not-create.sqlite3"
    app = create_app(
        Settings(_env_file=None, local_app_enabled=True, local_db_path=path),
        local_store=SQLiteLocalApplicationStore(tmp_path / "s1-only.sqlite3"),
    )
    client = TestClient(app)
    assert_error(
        client.get(f"{RISK}/draft", headers={"Authorization": "Bearer malformed"}),
        401,
        "SESSION_INVALID",
    )
    assert not path.exists() and not (tmp_path / "s1-only.sqlite3").exists()


@pytest.mark.parametrize("store_type", [SQLiteLocalRiskStore, FalseyRiskStore])
def test_risk_only_injection_never_constructs_an_unrelated_s1_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store_type: type[SQLiteLocalRiskStore]
) -> None:
    fallback = tmp_path / "must-not-create-s1.sqlite3"
    owned = tmp_path / "isolated-risk.sqlite3"
    constructions: list[bool] = []

    def forbidden_fallback(path: Path) -> SQLiteLocalApplicationStore:
        constructions.append(True)
        raise RuntimeError("Synthetic unrelated store construction")

    monkeypatch.setattr(local_application, "SQLiteLocalApplicationStore", forbidden_fallback)
    app = create_app(
        Settings(_env_file=None, local_app_enabled=True, local_db_path=fallback),
        local_risk_store=store_type(owned),
        local_clock=TestClock(),
    )
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert response.status_code == 503
    assert_error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert constructions == []
    assert not fallback.exists() and not owned.exists()


def test_malformed_s1_bearer_precedes_unavailable_s1_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fallback = tmp_path / "must-not-create-invalid-session.sqlite3"
    owned = tmp_path / "isolated-risk-invalid-session.sqlite3"
    constructions: list[bool] = []

    def forbidden_fallback(path: Path) -> SQLiteLocalApplicationStore:
        constructions.append(True)
        raise RuntimeError("Synthetic unrelated store construction")

    monkeypatch.setattr(local_application, "SQLiteLocalApplicationStore", forbidden_fallback)
    client = TestClient(
        create_app(
            Settings(_env_file=None, local_app_enabled=True, local_db_path=fallback),
            local_risk_store=SQLiteLocalRiskStore(owned),
        ),
        raise_server_exceptions=False,
    )
    response = client.get("/api/v1/local-auth/me", headers={"Authorization": "Bearer malformed"})
    assert_error(response, 401, "SESSION_INVALID")
    assert constructions == []
    assert not fallback.exists() and not owned.exists()
