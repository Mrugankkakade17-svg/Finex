"""Executable #146 golden contract and safe deterministic scoring tests (#143)."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from ai.risk.contract import RiskContractError, educational_explanation, evaluate_risk_contract
from ai.risk.schemas import RiskAssessmentRequest
from ai.risk.scoring import RiskScoringEngine

from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider

FIXTURES = S2Dat01FixtureProvider().list_fixtures()
FIXED_TIME = "2026-10-10T12:00:00Z"


@pytest.mark.parametrize("fixture", FIXTURES, ids=[f["case_id"] for f in FIXTURES])
def test_every_versioned_golden_case(fixture: dict) -> None:
    expected = fixture["expected"]
    if fixture["kind"] == "invalid":
        with pytest.raises(RiskContractError) as caught:
            evaluate_risk_contract(fixture["request"], calculated_at=FIXED_TIME)
        assert caught.value.code == expected["error_code"]
        assert "answer_code" not in str(caught.value)
        return

    result = evaluate_risk_contract(fixture["request"], calculated_at=FIXED_TIME)
    for field in ("willingness_score", "capacity_score", "composite_score"):
        assert result[field] == expected[field]
    assert result["risk_category"] == expected["risk_category"]
    assert result["limitation"]["code"] == expected["limitation_code"]
    if "informational_tension_code" in expected:
        assert result["informational_tension"]["code"] == expected["informational_tension_code"]
    assert result["questionnaire_version"] == "v1"
    assert result["contract_version"] == "s2-risk-contract/v1.0"
    assert result["scoring_version"] == "deterministic_v1.0.0"
    assert result["calculated_at"] == FIXED_TIME


def test_score_explanation_and_fixed_timestamp_are_deterministic_and_order_independent() -> None:
    request = deepcopy(FIXTURES[3]["request"])
    first = evaluate_risk_contract(request, calculated_at=FIXED_TIME)
    request["answers"].reverse()
    for _ in range(10):
        assert evaluate_risk_contract(request, calculated_at=FIXED_TIME) == first
    assert "not individualized" in first["limitation"]["message"]
    explanation = educational_explanation(first)
    assert explanation == educational_explanation(first)
    assert explanation["questionnaire_version"] == "v1"
    assert explanation["calculated_at"] == FIXED_TIME
    assert "not individualized" in explanation["limitation"]


@pytest.mark.parametrize("payload", [None, [], {}, {"answers": "private-input"}])
def test_malformed_requests_fail_without_echoing_input(payload: object) -> None:
    with pytest.raises(RiskContractError, match="Malformed") as caught:
        evaluate_risk_contract(payload)
    assert caught.value.code == "MALFORMED_ANSWER"
    assert "private-input" not in str(caught.value)


def test_error_precedence_follows_the_versioned_contract() -> None:
    payload = deepcopy(FIXTURES[3]["request"])
    payload["questionnaire_version"] = "v99"
    payload["answers"].append(payload["answers"][0])
    with pytest.raises(RiskContractError) as caught:
        evaluate_risk_contract(payload)
    assert caught.value.code == "UNSUPPORTED_QUESTIONNAIRE_VERSION"
    payload["questionnaire_version"] = "v1"
    payload["answers"][1]["question_id"] = "X1"
    with pytest.raises(RiskContractError) as caught:
        evaluate_risk_contract(payload)
    assert caught.value.code == "DUPLICATE_QUESTION_ANSWER"
    payload["answers"].pop()
    with pytest.raises(RiskContractError) as caught:
        evaluate_risk_contract(payload)
    assert caught.value.code == "UNKNOWN_QUESTION_ID"


def test_explicit_missing_config_does_not_silently_fall_back(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RiskScoringEngine(tmp_path / "missing-questionnaire.json")


def test_legacy_engine_also_checks_requested_version() -> None:
    payload = FIXTURES[3]["request"]
    request = RiskAssessmentRequest(version="v99", answers=payload["answers"])
    with pytest.raises(ValueError, match="Unsupported questionnaire version"):
        RiskScoringEngine().evaluate(request)


def test_strict_boundary_does_not_accept_extra_identity_or_silent_normalization() -> None:
    request = deepcopy(FIXTURES[3]["request"])
    request["user_id"] = "private-input"
    with pytest.raises(RiskContractError) as caught:
        evaluate_risk_contract(request)
    assert caught.value.code == "MALFORMED_ANSWER"
    request.pop("user_id")
    request["answers"][0]["answer_code"] = "w1_c"
    with pytest.raises(RiskContractError) as caught:
        evaluate_risk_contract(request)
    assert caught.value.code == "INVALID_ANSWER_CODE"


@pytest.mark.parametrize("field,value", [("willingness_weight", 0.7), ("capacity_weight", 0.3)])
def test_changed_v1_weights_require_a_new_policy_version(
    tmp_path: Path, field: str, value: float
) -> None:
    engine = RiskScoringEngine()
    config = deepcopy(engine.config)
    config["scoring"]["combination"][field] = value
    path = tmp_path / "changed-v1.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="publish a new version"):
        RiskScoringEngine(path)


def test_legacy_deterministic_explanation_contains_no_portfolio_instructions() -> None:
    request = RiskAssessmentRequest(answers=FIXTURES[8]["request"]["answers"])
    text = RiskScoringEngine().evaluate(request).explanation.model_dump_json().lower()
    for prohibited in (
        "portfolio strategy",
        "should",
        "growth opportunities",
        "objective financial",
    ):
        assert prohibited not in text
    assert "self-reported" in text
    assert "not investment advice" in text
