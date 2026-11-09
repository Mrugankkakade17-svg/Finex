"""S2 owned risk HTTP contract; assertions precede the new implementation.

All personas and answers are synthetic. Session credentials stay in memory;
assertions and evidence never print them.
"""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from ai.risk.scoring import RiskScoringEngine
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider
from app.main import create_app
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from tests.contract.test_local_s1_api import (
    AUTH,
    COMPLETE,
    CONSENT,
    ONBOARDING,
    PROFILE,
    TestClock,
    assert_error,
    finish,
    login,
)

RISK = "/api/v1/local-risk"
QUESTION_IDS = [f"{dimension}{number}" for dimension in ("W", "C") for number in range(1, 6)]
FIXTURES = [item for item in S2Dat01FixtureProvider().list_fixtures() if item["kind"] == "valid"]
OPERATIONS = [
    ("GET", "/questionnaire"),
    ("GET", "/draft"),
    ("PUT", "/draft"),
    ("POST", "/assessments"),
    ("GET", "/assessments"),
    ("GET", "/assessments/82d09e04-77fc-4c40-8ec0-f7038ad59cf6"),
]


def risk_input(letter: str = "C", *, partial: bool = False) -> dict:
    return {
        "questionnaire_id": "risk_questionnaire_v1",
        "questionnaire_version": "v1",
        "answers": [
            {"question_id": qid, "answer_code": f"{qid}_{letter}"}
            for qid in (QUESTION_IDS[:2] if partial else QUESTION_IDS)
        ],
    }


def submit_input(letter: str = "C", key: str | None = None) -> dict:
    return {**risk_input(letter), "idempotency_key": key or str(uuid4())}


def application(path: Path, clock: TestClock | None = None, *, enabled: bool = True):
    return create_app(
        Settings(
            _env_file=None,
            local_app_enabled=enabled,
            local_db_path=path,
            llm_provider="none",
            market_data_provider="mock",
        ),
        local_clock=clock or TestClock(),
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(application(tmp_path / "risk.sqlite3"))


def completed(client: TestClient, alias: str = "learner-a") -> dict[str, str]:
    headers = login(client, alias)
    finish(client, headers)
    return headers


def saved(client: TestClient, headers: dict[str, str], payload: dict | None = None) -> dict:
    response = client.post(f"{RISK}/assessments", headers=headers, json=payload or submit_input())
    assert response.status_code == 200
    assert response.json()["meta"]["dataStatus"] == "CACHED"
    return response.json()["data"]


@pytest.mark.parametrize("method,suffix", OPERATIONS)
def test_each_operation_requires_bearer_before_storage(
    tmp_path: Path, method: str, suffix: str
) -> None:
    path = tmp_path / "missing-session.sqlite3"
    client = TestClient(application(path))
    body = submit_input() if method == "POST" else risk_input(partial=True)
    response = client.request(
        method, RISK + suffix, json=body if method in {"POST", "PUT"} else None
    )
    assert_error(response, 401, "SESSION_INVALID")
    assert not path.exists()


def test_disabled_boundary_precedes_malformed_body_and_creates_no_database(tmp_path: Path) -> None:
    path = tmp_path / "disabled.sqlite3"
    client = TestClient(application(path, enabled=False))
    response = client.post(
        f"{RISK}/assessments", content="{malformed", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 403, "LOCAL_APPLICATION_ONLY")
    assert not path.exists()


@pytest.mark.parametrize("method,suffix", OPERATIONS)
def test_each_operation_requires_current_completed_onboarding(
    client: TestClient, method: str, suffix: str
) -> None:
    headers = login(client)
    body = submit_input() if method == "POST" else risk_input(partial=True)
    response = client.request(
        method, RISK + suffix, headers=headers, json=body if method in {"POST", "PUT"} else None
    )
    assert_error(response, 409, "ONBOARDING_REQUIRED")


def test_questionnaire_preserves_order_versions_and_canonical_rule_hash(client: TestClient) -> None:
    headers = completed(client)
    response = client.get(f"{RISK}/questionnaire", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scope"] == "local_educational_application"
    assert data["contract_version"] == "local.v1"
    assert data["questionnaire_id"] == "risk_questionnaire_v1"
    assert data["questionnaire_version"] == "v1"
    assert data["scoring_version"] == "deterministic_v1.0.0"
    assert data["explanation_version"] == "educational_v1.0.0"
    assert [question["question_id"] for question in data["questions"]] == QUESTION_IDS
    for question in data["questions"]:
        assert [option["code"] for option in question["options"]] == [
            f"{question['question_id']}_{letter}" for letter in "ABCDE"
        ]
    canonical = json.dumps(
        RiskScoringEngine().config, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert data["rules_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert response.json()["meta"]["dataStatus"] == "CACHED"


def test_partial_draft_is_full_replacement_and_resumes_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "draft-restart.sqlite3"
    clock = TestClock()
    first = TestClient(application(path, clock))
    headers = completed(first)
    initial = first.get(f"{RISK}/draft", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["answers"] == []
    assert initial.json()["data"]["updated_at"] is None
    payload = risk_input(partial=True)
    payload["answers"].reverse()
    response = first.put(f"{RISK}/draft", headers=headers, json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["answers"] == payload["answers"]
    assert data["updated_at"] == clock.now.isoformat()
    restarted = TestClient(application(path, clock))
    assert restarted.get(f"{RISK}/draft", headers=headers).json()["data"] == data
    empty = {**risk_input(), "answers": []}
    cleared = restarted.put(f"{RISK}/draft", headers=headers, json=empty)
    assert cleared.status_code == 200
    assert cleared.json()["data"]["answers"] == []
    assert cleared.json()["data"]["updated_at"] is not None


@pytest.mark.parametrize("fixture", FIXTURES, ids=[item["case_id"] for item in FIXTURES])
def test_saved_assessments_reuse_all_valid_approved_golden_vectors(
    client: TestClient, fixture: dict
) -> None:
    headers = completed(client)
    result = saved(client, headers, {**fixture["request"], "idempotency_key": str(uuid4())})
    assert result["scope"] == "local_educational_application"
    assert result["contract_version"] == "local.v1"
    assert result["persisted"] is True
    assert result["input"] == fixture["request"]
    expected = fixture["expected"]
    for field in ("willingness_score", "capacity_score", "composite_score", "risk_category"):
        assert result["assessment"][field] == expected[field]
    assert result["assessment"]["calculated_at"] == result["created_at"]
    assert result["explanation"]["calculated_at"] == result["created_at"]
    assert result["explanation_version"] == "educational_v1.0.0"
    assert "not individualized" in result["explanation"]["limitation"]
    snapshot = json.dumps(
        result["rules_snapshot"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert len(snapshot) <= 65536
    assert result["rules_sha256"] == hashlib.sha256(snapshot).hexdigest()
    assert result["rules_snapshot"] == RiskScoringEngine().config
    detail = client.get(f"{RISK}/assessments/{result['assessment_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["data"] == result
    assert detail.json()["meta"]["dataAsOf"] == result["created_at"]


def test_replay_retains_original_order_time_and_result_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "replay.sqlite3"
    clock = TestClock()
    client = TestClient(application(path, clock))
    headers = completed(client)
    payload = submit_input()
    original = saved(client, headers, payload)
    clock.now += timedelta(minutes=1)
    reordered = deepcopy(payload)
    reordered["answers"].reverse()
    restarted = TestClient(application(path, clock))
    assert saved(restarted, headers, reordered) == original
    history = restarted.get(f"{RISK}/assessments", headers=headers)
    assert history.status_code == 200
    assert history.json()["data"]["items"] == [original]
    assert history.json()["data"]["next_cursor"] is None
    conflict = submit_input("D", payload["idempotency_key"])
    assert_error(
        restarted.post(f"{RISK}/assessments", headers=headers, json=conflict),
        409,
        "IDEMPOTENCY_CONFLICT",
    )
    assert restarted.get(f"{RISK}/assessments", headers=headers).json()["data"]["items"] == [
        original
    ]


def test_owner_isolation_same_key_and_indistinguishable_not_found(client: TestClient) -> None:
    owner = completed(client)
    other = completed(client, "learner-b")
    payload = submit_input()
    first = saved(client, owner, payload)
    empty = client.get(f"{RISK}/assessments", headers=other)
    assert empty.status_code == 200
    assert empty.json()["data"]["items"] == []
    missing = client.get(f"{RISK}/assessments/{uuid4()}", headers=other)
    hidden = client.get(f"{RISK}/assessments/{first['assessment_id']}", headers=other)
    for response in (missing, hidden):
        assert_error(response, 404, "RISK_ASSESSMENT_NOT_FOUND")
    assert missing.json()["message"] == hidden.json()["message"]
    second = saved(client, other, payload)
    assert second["assessment_id"] != first["assessment_id"]
    assert client.get(f"{RISK}/assessments", headers=owner).json()["data"]["items"] == [first]


def test_submission_and_empty_draft_never_change_immutable_history(client: TestClient) -> None:
    headers = completed(client)
    draft = risk_input(partial=True)
    response = client.put(f"{RISK}/draft", headers=headers, json=draft)
    assert response.status_code == 200
    first_draft = response.json()["data"]
    result = saved(client, headers)
    assert client.get(f"{RISK}/draft", headers=headers).json()["data"] == first_draft
    clear = client.put(f"{RISK}/draft", headers=headers, json={**risk_input(), "answers": []})
    assert clear.status_code == 200
    assert client.get(f"{RISK}/assessments", headers=headers).json()["data"]["items"] == [result]


@pytest.mark.parametrize(
    "change,code",
    [
        ("version", "UNSUPPORTED_QUESTIONNAIRE_VERSION"),
        ("duplicate", "DUPLICATE_QUESTION_ANSWER"),
        ("unknown", "UNKNOWN_QUESTION_ID"),
        ("missing", "MISSING_REQUIRED_QUESTION"),
        ("code", "INVALID_ANSWER_CODE"),
        ("wrong-question", "ANSWER_NOT_PERMITTED_FOR_QUESTION"),
    ],
)
def test_complete_semantic_errors_are_stable_and_write_nothing(
    client: TestClient, change: str, code: str
) -> None:
    headers = completed(client)
    payload = submit_input()
    if change == "version":
        payload["questionnaire_version"] = "v99"
        payload["answers"].append(payload["answers"][0])
    elif change == "duplicate":
        payload["answers"].append(payload["answers"][0])
    elif change == "unknown":
        payload["answers"][0]["question_id"] = "X1"
    elif change == "missing":
        payload["answers"].pop()
    elif change == "code":
        payload["answers"][0]["answer_code"] = "W1_X"
    else:
        payload["answers"][0]["answer_code"] = "W2_C"
    assert_error(client.post(f"{RISK}/assessments", headers=headers, json=payload), 400, code)
    assert client.get(f"{RISK}/assessments", headers=headers).json()["data"]["items"] == []


@pytest.mark.parametrize(
    "mutation", ["owner", "time", "score", "missing-key", "bad-key", "missing-answers"]
)
def test_transport_forbids_client_authority_and_invalid_keys(
    client: TestClient, mutation: str
) -> None:
    headers = completed(client)
    payload = submit_input()
    if mutation in {"owner", "time", "score"}:
        field = {"owner": "user_id", "time": "calculated_at", "score": "composite_score"}[mutation]
        payload[field] = "synthetic-private-value"
    elif mutation == "missing-key":
        payload.pop("idempotency_key")
    elif mutation == "missing-answers":
        payload.pop("answers")
    else:
        payload["idempotency_key"] = "not-a-key"
    response = client.post(f"{RISK}/assessments", headers=headers, json=payload)
    assert_error(response, 422, "VALIDATION_ERROR")
    assert "synthetic-private-value" not in response.text


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=51",
        "limit=01",
        "limit=1.0",
        "before=0",
        "before=-1",
        "before=01",
        "before=9223372036854775808",
    ],
)
def test_history_pagination_rejects_noncanonical_or_unbounded_values(
    client: TestClient, query: str
) -> None:
    headers = completed(client)
    assert_error(
        client.get(f"{RISK}/assessments?{query}", headers=headers), 422, "VALIDATION_ERROR"
    )


def test_equal_time_history_and_new_insert_do_not_duplicate_next_page(client: TestClient) -> None:
    headers = completed(client)
    first, second, third = [saved(client, headers) for _ in range(3)]
    page = client.get(f"{RISK}/assessments?limit=2", headers=headers)
    assert page.status_code == 200
    data = page.json()["data"]
    assert data["items"] == [third, second]
    assert data["next_cursor"] is not None
    saved(client, headers)
    following = client.get(
        f"{RISK}/assessments?limit=2&before={data['next_cursor']}", headers=headers
    )
    assert following.status_code == 200
    assert following.json()["data"]["items"] == [first]
    assert following.json()["data"]["next_cursor"] is None


def test_withdrawal_reacceptance_and_recompletion_preserve_and_gate_history(
    client: TestClient,
) -> None:
    headers = completed(client)
    result = saved(client, headers)
    assert (
        client.post(
            f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": False}
        ).status_code
        == 200
    )
    assert_error(client.get(f"{RISK}/assessments", headers=headers), 409, "ONBOARDING_REQUIRED")
    assert client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT).status_code == 200
    assert_error(client.get(f"{RISK}/assessments", headers=headers), 409, "ONBOARDING_REQUIRED")
    assert client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE).status_code == 200
    assert client.get(f"{RISK}/assessments", headers=headers).json()["data"]["items"] == [result]
    changed = {**PROFILE, "display_name": "Changed synthetic label"}
    assert client.put(f"{ONBOARDING}/draft", headers=headers, json=changed).status_code == 200
    assert_error(client.get(f"{RISK}/draft", headers=headers), 409, "ONBOARDING_REQUIRED")


def test_exact_expiry_and_revocation_block_saved_risk_access(tmp_path: Path) -> None:
    clock = TestClock()
    client = TestClient(application(tmp_path / "expiry.sqlite3", clock))
    headers = completed(client)
    saved(client, headers)
    clock.now += timedelta(minutes=30)
    assert_error(client.get(f"{RISK}/assessments", headers=headers), 401, "SESSION_INVALID")
    replacement = completed(client)
    assert client.post(f"{AUTH}/logout", headers=replacement, json={}).status_code == 200
    assert_error(client.get(f"{RISK}/draft", headers=replacement), 401, "SESSION_INVALID")


def test_injected_s1_only_store_never_falls_back_to_other_local_database(tmp_path: Path) -> None:
    fallback = tmp_path / "must-not-create.sqlite3"
    app = create_app(
        Settings(_env_file=None, local_app_enabled=True, local_db_path=fallback),
        local_store=SQLiteLocalApplicationStore(tmp_path / "injected-s1.sqlite3"),
        local_clock=TestClock(),
    )
    client = TestClient(app)
    headers = completed(client)
    assert_error(client.get(f"{RISK}/draft", headers=headers), 503, "LOCAL_STORE_UNAVAILABLE")
    assert not fallback.exists()


def test_openapi_defines_six_bearer_operations_and_nullability(client: TestClient) -> None:
    spec = client.app.openapi()
    actual = {
        (method.upper(), path[len(RISK) :])
        for path, methods in spec["paths"].items()
        if path.startswith(RISK + "/")
        for method in methods
    }
    expected = set(OPERATIONS[:-1]) | {("GET", "/assessments/{assessment_id}")}
    assert actual == expected
    for path, methods in spec["paths"].items():
        if not path.startswith(RISK + "/"):
            continue
        for operation in methods.values():
            assert operation["security"] == [{"LocalApplicationBearer": []}]
            assert {"401", "403", "409", "422", "503"} <= set(operation["responses"])
    schemas = spec["components"]["schemas"]
    for name, field in (("LocalRiskDraft", "updated_at"), ("LocalRiskHistory", "next_cursor")):
        assert field in schemas[name]["required"]
        assert {"type": "null"} in schemas[name]["properties"][field]["anyOf"]
    assert schemas["LocalRiskSubmitRequest"]["additionalProperties"] is False
    assert "idempotency_key" in schemas["LocalRiskSubmitRequest"]["required"]
