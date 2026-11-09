"""Static checks for the Sprint 2 risk contract and synthetic golden pack.

These checks deliberately validate only specification artifacts. They do not
recalculate a score or call the scoring engine; downstream stories own that
behavior and must consume the golden pack as executable regression cases.
"""

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RISK_DOCS = REPOSITORY_ROOT / "docs" / "features" / "risk-profiling"
CONTRACT_PATH = RISK_DOCS / "risk-contract.v1.json"
GOLDEN_CASES_PATH = RISK_DOCS / "golden-cases.v1.json"
QUESTIONNAIRE_PATH = (
    REPOSITORY_ROOT / "backend" / "data" / "questionnaire" / "risk_questionnaire_v1.json"
)


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _canonical_answer_codes(questionnaire: dict) -> dict[str, set[str]]:
    return {
        question["question_id"]: {answer["code"] for answer in question["answers"]}
        for question in questionnaire["questions"]
    }


def test_contract_references_the_approved_canonical_questionnaire() -> None:
    contract = _load_json(CONTRACT_PATH)
    questionnaire = _load_json(QUESTIONNAIRE_PATH)
    metadata = questionnaire["questionnaire"]
    questions = questionnaire["questions"]

    assert contract["contract_version"] == "s2-risk-contract/v1.0"
    assert contract["source_of_truth"]["questionnaire_path"] == (
        "backend/data/questionnaire/risk_questionnaire_v1.json"
    )
    assert contract["source_of_truth"]["questionnaire_id"] == metadata["questionnaire_id"]
    assert contract["source_of_truth"]["questionnaire_version"] == metadata["version_label"]
    assert contract["source_of_truth"]["source_status"] == metadata["status"]
    assert contract["source_of_truth"]["source_status"] == "APPROVED"
    assert contract["approval_boundary"]["approved_canonical_decisions"]
    assert contract["approval_boundary"]["s2_implementation_proposal"]

    contract_input = contract["input"]
    canonical_question_ids = [question["question_id"] for question in questions]
    assert contract_input["required_question_ids"] == canonical_question_ids
    assert contract_input["required_answer_count"] == len(canonical_question_ids) == 10
    assert all(question["required"] is True for question in questions)
    assert all(question["response_type"] == "single_choice" for question in questions)

    canonical_dimensions = {
        dimension: [
            question["question_id"] for question in questions if question["dimension"] == dimension
        ]
        for dimension in ("willingness", "capacity")
    }
    assert contract_input["dimension_membership"] == canonical_dimensions
    assert all(
        len(question["answers"]) == 5
        and {answer["proposed_score"] for answer in question["answers"]} == {1, 2, 3, 4, 5}
        for question in questions
    )


def test_scoring_policy_matches_the_canonical_v1_baseline() -> None:
    contract = _load_json(CONTRACT_PATH)
    questionnaire = _load_json(QUESTIONNAIRE_PATH)
    policy = contract["scoring_policy"]
    canonical_scoring = questionnaire["scoring"]

    assert policy["calculation_mode"] == "deterministic_only"
    assert policy["external_model_may_calculate_or_override_score"] is False
    assert policy["dimension_raw_range"] == canonical_scoring["dimension_raw_range"]
    assert policy["normalization"] == canonical_scoring["normalization"]
    assert policy["combination"] == canonical_scoring["combination"]
    assert [(category["code"], category["label"]) for category in policy["categories"]] == [
        ("CONSERVATIVE", "Conservative"),
        ("MODERATE", "Moderate"),
        ("AGGRESSIVE", "Aggressive"),
    ]
    assert policy["reachable_composite_increment"] == 2.5


def test_golden_valid_answer_sets_are_legal_for_the_canonical_questionnaire() -> None:
    contract = _load_json(CONTRACT_PATH)
    golden_cases = _load_json(GOLDEN_CASES_PATH)
    questionnaire = _load_json(QUESTIONNAIRE_PATH)
    permitted_answer_codes = _canonical_answer_codes(questionnaire)
    required_questions = set(contract["input"]["required_question_ids"])

    assert golden_cases["fixture_version"] == "s2-risk-golden-cases/v1.0"
    assert golden_cases["contract_ref"] == "risk-contract.v1.json"
    assert golden_cases["fixture_data_classification"] == "synthetic_non_production"
    assert golden_cases["base_request"] == {
        "questionnaire_id": "risk_questionnaire_v1",
        "questionnaire_version": "v1",
    }

    for answer_set_name, answers in golden_cases["answer_sets"].items():
        assert set(answers) == required_questions, answer_set_name
        for question_id, answer_code in answers.items():
            assert answer_code in permitted_answer_codes[question_id], (
                answer_set_name,
                question_id,
                answer_code,
            )

    valid_cases = [case for case in golden_cases["cases"] if case["kind"] == "valid"]
    assert len(valid_cases) == 9
    for case in valid_cases:
        assert case["answer_set"] in golden_cases["answer_sets"]
        expected = case["expected"]
        assert 0 <= expected["willingness_score"] <= 100
        assert 0 <= expected["capacity_score"] <= 100
        assert 0 <= expected["composite_score"] <= 100
        assert expected["risk_category"]["code"] in {
            "CONSERVATIVE",
            "MODERATE",
            "AGGRESSIVE",
        }
        assert expected["limitation_code"] == "EDUCATIONAL_SELF_REPORTED_PROFILE"
        tension_code = expected.get("informational_tension_code")
        if tension_code is not None:
            assert tension_code in contract["result"]["informational_tension"]["allowed_codes"]


def test_golden_invalid_cases_cover_the_contract_error_vocabulary() -> None:
    contract = _load_json(CONTRACT_PATH)
    golden_cases = _load_json(GOLDEN_CASES_PATH)
    declared_error_codes = {item["code"] for item in contract["errors"]}
    invalid_cases = [case for case in golden_cases["cases"] if case["kind"] == "invalid"]
    required_coverages = {
        "missing_required",
        "duplicate",
        "unknown_question",
        "invalid_answer_code",
        "contradictory",
        "malformed",
        "unsupported_version",
    }
    supported_operations = {
        "remove_by_question_id",
        "append_answer",
        "replace_answer",
        "set_questionnaire_version",
    }

    assert {case["coverage"] for case in invalid_cases} == required_coverages
    assert len(invalid_cases) == len(required_coverages)
    for case in invalid_cases:
        assert case["answer_set"] == "all_mid"
        assert case["expected"]["error_code"] in declared_error_codes
        assert case["expected"]["score_returned"] is False
        assert all(mutation["operation"] in supported_operations for mutation in case["mutations"])


def test_contract_requires_safe_explanation_and_local_operation() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert "LLM" in " ".join(contract["explanation_boundary"]["prohibited"])
    assert contract["privacy_and_operations"]["deployment_dependency"].startswith("None.")
    assert contract["result"]["limitation"]["code"] == ("EDUCATIONAL_SELF_REPORTED_PROFILE")
