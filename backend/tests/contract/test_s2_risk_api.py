"""TDD HTTP golden cases, OpenAPI, privacy and local-pilot guards for #161."""

from copy import deepcopy
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider
from app.main import create_app

FIXTURES = S2Dat01FixtureProvider().list_fixtures()
PATH = "/api/v1/risk-contract/assessments"


@pytest.fixture
def pilot_client() -> TestClient:
    return TestClient(create_app(Settings(app_env="local", _env_file=None)))


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["case_id"] for f in FIXTURES])
def test_http_golden_cases(pilot_client: TestClient, fixture: dict) -> None:
    response = pilot_client.post(
        PATH, json=fixture["request"], headers={"X-Correlation-ID": "s2-proof"}
    )
    body = response.json()
    assert response.headers["X-Correlation-ID"] == "s2-proof"
    if fixture["kind"] == "invalid":
        assert response.status_code in (400, 422)
        assert body["error"]["code"] == fixture["expected"]["error_code"]
        assert body["error"]["correlationId"] == "s2-proof"
        assert '"answer_code"' not in response.text
        return
    assert response.status_code == 200
    assessment = body["data"]["assessment"]
    for field in ("willingness_score", "capacity_score", "composite_score", "risk_category"):
        assert assessment[field] == fixture["expected"][field]
    assert body["meta"]["correlationId"] == "s2-proof"
    assert body["meta"]["dataAsOf"] == assessment["calculated_at"]
    assert datetime.fromisoformat(assessment["calculated_at"]).utcoffset() is not None
    assert body["data"]["scope"] == "local_educational_pilot"
    assert body["data"]["persisted"] is False
    assert body["data"]["explanation"]["calculated_at"] == assessment["calculated_at"]
    assert "not individualized" in body["data"]["explanation"]["limitation"]


def test_questionnaire_and_openapi_are_versioned_and_typed(pilot_client: TestClient) -> None:
    response = pilot_client.get("/api/v1/risk-contract/questionnaire")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["questionnaire_id"] == "risk_questionnaire_v1"
    assert data["questionnaire_version"] == "v1"
    assert len(data["questions"]) == 10
    assert len(data["questions"][0]["options"]) == 5
    assert "proposed_score" not in response.text
    schema = pilot_client.get("/openapi.json").json()
    operation = schema["paths"][PATH]["post"]
    assert {"200", "400", "403", "422", "500"} <= set(operation["responses"])
    assert "$ref" in operation["requestBody"]["content"]["application/json"]["schema"]
    assert "$ref" in operation["responses"]["200"]["content"]["application/json"]["schema"]


def test_malformed_payload_and_extra_identity_never_echo_input(pilot_client: TestClient) -> None:
    payload = deepcopy(FIXTURES[3]["request"])
    payload["user_id"] = "private-input"
    response = pilot_client.post(PATH, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MALFORMED_ANSWER"
    assert "private-input" not in response.text
    response = pilot_client.post(
        PATH, content="{invalid-private-input", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MALFORMED_ANSWER"
    assert "private-input" not in response.text


def test_same_answers_produce_same_numeric_decision(pilot_client: TestClient) -> None:
    first = pilot_client.post(PATH, json=FIXTURES[3]["request"]).json()["data"]["assessment"]
    second = pilot_client.post(PATH, json=FIXTURES[3]["request"]).json()["data"]["assessment"]
    for field in ("calculated_at",):
        first.pop(field)
        second.pop(field)
    assert first == second


@pytest.mark.parametrize("environment", ["dev", "uat", "prod"])
def test_anonymous_pilot_is_not_a_deployment_endpoint(environment: str) -> None:
    settings = Settings(
        app_env=environment,
        debug=False,
        api_base_url="https://api.example.invalid",
        allowed_origins=["https://app.example.invalid"],
        secret_key="s" * 32,
        llm_provider="none",
        fixture_mode="disabled",
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    response = client.post(PATH, json=FIXTURES[3]["request"])
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_PILOT_ONLY"


def test_unexpected_adapter_error_is_sanitized(pilot_client: TestClient) -> None:
    from app.services.risk_contract_service import get_assessment_scorer

    class BrokenScorer:
        def score(self, payload: object) -> dict:
            raise RuntimeError("private-input provider diagnostics")

    pilot_client.app.dependency_overrides[get_assessment_scorer] = lambda: BrokenScorer()
    response = pilot_client.post(PATH, json=FIXTURES[3]["request"])
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "RISK_ASSESSMENT_UNAVAILABLE"
    assert "private-input" not in response.text


@pytest.mark.parametrize("endpoint", ["evaluate", "explain", "evaluate-and-explain"])
def test_legacy_anonymous_risk_routes_also_have_the_deployment_guard(endpoint: str) -> None:
    settings = Settings(
        app_env="uat",
        debug=False,
        api_base_url="https://api.example.invalid",
        allowed_origins=["https://app.example.invalid"],
        secret_key="s" * 32,
        llm_provider="none",
        fixture_mode="disabled",
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    response = client.post(
        f"/api/v1/risk/{endpoint}", json={"answers": FIXTURES[3]["request"]["answers"]}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_PILOT_ONLY"
