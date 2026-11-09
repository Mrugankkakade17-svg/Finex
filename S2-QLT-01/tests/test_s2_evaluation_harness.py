"""S2-QLT-01 — Evaluation Harness Tests.

Covers the contract boundary, golden case determinism, safety checks,
and version disclosure for the Sprint 2 deterministic risk feature.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai.risk.contract import (
    CONTRACT_VERSION,
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    RiskContractError,
    evaluate_risk_contract,
    educational_explanation,
    validate_risk_input,
)
from ai.risk.scoring import RiskScoringEngine

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_golden_cases() -> list[dict]:
    path = FIXTURES_DIR / "golden_case_matrix.json"
    return json.loads(path.read_text())["cases"]


def _build_valid_payload(engine: RiskScoringEngine, answer_level: int = 3) -> dict:
    """Build a valid payload where every answer uses the given level (1-5)."""
    answers = []
    for qid, q in engine.questions_by_id.items():
        code = f"{qid}_{chr(64 + answer_level)}"  # W1_A, W1_B, W1_C ...
        answers.append({"question_id": qid, "answer_code": code})
    return {
        "questionnaire_id": engine.questionnaire_id,
        "questionnaire_version": engine.version_label,
        "answers": answers,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestContractBoundary:
    """Verify contract.py boundary accepts valid payloads and rejects invalid ones."""

    def test_contract_boundary_valid_payload(self):
        engine = RiskScoringEngine()
        payload = _build_valid_payload(engine, answer_level=3)
        result = evaluate_risk_contract(payload, engine=engine)

        assert result["contract_version"] == CONTRACT_VERSION
        assert result["questionnaire_id"] == engine.questionnaire_id
        assert result["scoring_version"] == "deterministic_v1.0.0"
        assert 0.0 <= result["willingness_score"] <= 100.0
        assert 0.0 <= result["capacity_score"] <= 100.0
        assert 0.0 <= result["composite_score"] <= 100.0
        assert result["risk_category"]["code"] in {"CONSERVATIVE", "MODERATE", "AGGRESSIVE"}
        assert result["limitation"]["code"] == LIMITATION_CODE

    def test_contract_boundary_all_error_codes(self):
        engine = RiskScoringEngine()
        valid = _build_valid_payload(engine)

        # MALFORMED_ANSWER — wrong keys
        with pytest.raises(RiskContractError, match="Malformed"):
            evaluate_risk_contract({"bad": "keys"}, engine=engine)

        # UNSUPPORTED_QUESTIONNAIRE_VERSION
        bad_version = {**valid, "questionnaire_version": "v999"}
        with pytest.raises(RiskContractError, match="Unsupported"):
            evaluate_risk_contract(bad_version, engine=engine)

        # DUPLICATE_QUESTION_ANSWER
        dup = {**valid, "answers": valid["answers"] + [valid["answers"][0]]}
        with pytest.raises(RiskContractError, match="More than one answer"):
            evaluate_risk_contract(dup, engine=engine)

        # UNKNOWN_QUESTION_ID
        unknown = {**valid, "answers": [{"question_id": "ZZ9", "answer_code": "ZZ9_A"}]}
        with pytest.raises(RiskContractError, match="unknown"):
            evaluate_risk_contract(unknown, engine=engine)

        # MISSING_REQUIRED_QUESTION
        partial = {**valid, "answers": valid["answers"][:5]}
        with pytest.raises(RiskContractError, match="required"):
            evaluate_risk_contract(partial, engine=engine)

        # INVALID_ANSWER_CODE
        bad_code = {**valid, "answers": [
            {**a, "answer_code": "INVALID_Z"} if i == 0 else a
            for i, a in enumerate(valid["answers"])
        ]}
        with pytest.raises(RiskContractError, match="undefined"):
            evaluate_risk_contract(bad_code, engine=engine)

    def test_contract_educational_explanation(self):
        engine = RiskScoringEngine()
        payload = _build_valid_payload(engine, answer_level=3)
        result = evaluate_risk_contract(payload, engine=engine)
        explanation = educational_explanation(result)

        assert "educational" in explanation["summary"].lower() or "self-reported" in explanation["summary"].lower()
        assert explanation["limitation"] == LIMITATION_MESSAGE
        assert "deterministic" in explanation["method"].lower() or "rules" in explanation["method"].lower()

    def test_contract_tension_detection(self):
        """When W and C are in different category bands, informational_tension appears."""
        engine = RiskScoringEngine()
        # High willingness (all 5s), low capacity (all 1s)
        answers = []
        for qid in engine.questions_by_id:
            if qid.startswith("W"):
                answers.append({"question_id": qid, "answer_code": f"{qid}_E"})
            else:
                answers.append({"question_id": qid, "answer_code": f"{qid}_A"})
        payload = {
            "questionnaire_id": engine.questionnaire_id,
            "questionnaire_version": engine.version_label,
            "answers": answers,
        }
        result = evaluate_risk_contract(payload, engine=engine)
        # W=100 (Aggressive), C=0 (Conservative) → tension should exist
        assert "informational_tension" in result
        assert result["informational_tension"]["code"] in {
            "CAPACITY_BELOW_WILLINGNESS",
            "WILLINGNESS_BELOW_CAPACITY",
        }


class TestGoldenCaseDeterminism:
    """Verify all golden cases produce exact expected scores."""

    def test_golden_case_matrix_determinism(self):
        cases = _load_golden_cases()
        engine = RiskScoringEngine()
        for case in cases:
            payload = {
                "questionnaire_id": engine.questionnaire_id,
                "questionnaire_version": engine.version_label,
                "answers": case["answers"],
            }
            result = evaluate_risk_contract(payload, engine=engine)
            assert result["willingness_score"] == case["expected_willingness"], (
                f"Profile {case['profile']}: W mismatch"
            )
            assert result["capacity_score"] == case["expected_capacity"], (
                f"Profile {case['profile']}: C mismatch"
            )
            assert result["composite_score"] == case["expected_composite"], (
                f"Profile {case['profile']}: Composite mismatch"
            )
            assert result["risk_category"]["code"] == case["expected_category_code"], (
                f"Profile {case['profile']}: Category mismatch"
            )


class TestSafety:
    """Verify safety boundaries."""

    PROHIBITED_PHRASES = [
        "guaranteed return",
        "guaranteed profit",
        "risk-free profit",
        "will definitely earn",
        "promise you",
        "sure shot",
        "buy this stock",
        "invest in crypto",
    ]

    def test_safety_no_financial_advice(self):
        engine = RiskScoringEngine()
        for level in [1, 2, 3, 4, 5]:
            payload = _build_valid_payload(engine, answer_level=level)
            result = evaluate_risk_contract(payload, engine=engine)
            explanation = educational_explanation(result)
            combined = json.dumps(explanation).lower()
            for phrase in self.PROHIBITED_PHRASES:
                assert phrase not in combined, f"Prohibited phrase '{phrase}' found in output"

    def test_version_disclosure(self):
        engine = RiskScoringEngine()
        payload = _build_valid_payload(engine, answer_level=3)
        result = evaluate_risk_contract(payload, engine=engine)

        assert result["contract_version"] == "s2-risk-contract/v1.0"
        assert result["scoring_version"] == "deterministic_v1.0.0"
        assert "calculated_at" in result

    def test_educational_language_check(self):
        engine = RiskScoringEngine()
        payload = _build_valid_payload(engine, answer_level=3)
        result = evaluate_risk_contract(payload, engine=engine)

        assert result["limitation"]["code"] == "EDUCATIONAL_SELF_REPORTED_PROFILE"
        assert "educational" in result["limitation"]["message"].lower()
        assert "not individualized" in result["limitation"]["message"].lower() or \
               "not … advice" in result["limitation"]["message"].lower() or \
               "not" in result["limitation"]["message"].lower()
