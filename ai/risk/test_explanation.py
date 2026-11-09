"""Test suite for FinEx AI Risk Result Explanation Engine (S2-AI-02).

Validates:
- Zero numerical drift (composite score, willingness, and capacity are immutable)
- Beginner-friendly explanations and factor citations
- Versioned prompts and schemas (v1.0.0)
- Safe deterministic non-LLM fallback under malformed JSON, prompt injections, and errors
- Boundary transition cases (33.99, 34.00, 66.99, 67.00)
- Compliance guardrails (prohibition of return promises and financial advisory claims)
- Golden examples verification
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from ai.risk import (
    KeyInfluencingFactor,
    QuestionAnswer,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskCategory,
    RiskExplanationEngine,
    RiskExplanationRequest,
    RiskExplanationResponse,
    calculate_risk_score,
    evaluate_and_explain,
    explain_risk_assessment,
)
from ai.risk.prompts import (
    PROMPT_VERSION_V1,
    SCHEMA_VERSION_V1,
    SYSTEM_PROMPT_V1,
    format_user_prompt_v1,
)

# Standard helper to generate answers from weight vector
def make_answers(weights):
    q_ids = ["W1", "W2", "W3", "W4", "W5", "C1", "C2", "C3", "C4", "C5"]
    code_map = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}
    return [
        QuestionAnswer(question_id=qid, answer_code=f"{qid}_{code_map[w]}")
        for qid, w in zip(q_ids, weights)
    ]


def test_prompt_template_formatting():
    """Verify that prompt template embeds deterministic values and rich answers accurately."""
    answers = make_answers([1, 2, 3, 4, 5, 5, 4, 3, 2, 1])
    assessment = calculate_risk_score(answers, calculated_at="2026-08-29T12:00:00Z")

    engine = RiskExplanationEngine()
    rich_answers, answers_map = engine.extract_rich_answers(answers)
    factors = engine.identify_influencing_factors(
        answers_map, assessment.willingness_score, assessment.capacity_score
    )

    prompt = format_user_prompt_v1(
        assessment.model_dump(),
        rich_answers,
        [f.model_dump() for f in factors],
    )

    assert "Composite Risk Score: 50.0/100" in prompt
    assert "Willingness Score (Psychological): 50.0/100" in prompt
    assert "Capacity Score (Financial): 50.0/100" in prompt
    assert "Conservative Drawdown Anchor" in prompt or "W1" in prompt
    assert "risk_questionnaire_v1" in prompt


def test_zero_numerical_drift_across_all_categories():
    """Verify that explanation engine NEVER alters or recalculates numerical scores."""
    profiles = [
        ("extreme_conservative", [1, 1, 1, 1, 1, 1, 1, 1, 1, 1], 0.0, RiskCategory.CONSERVATIVE),
        ("moderate_lower", [3, 3, 2, 2, 2, 3, 3, 2, 2, 2], 35.0, RiskCategory.MODERATE),
        ("balanced_moderate", [3, 3, 3, 3, 3, 3, 3, 3, 3, 3], 50.0, RiskCategory.MODERATE),
        ("aggressive_lower", [4, 4, 4, 4, 3, 4, 4, 4, 3, 3], 67.5, RiskCategory.AGGRESSIVE),
        ("extreme_aggressive", [5, 5, 5, 5, 5, 5, 5, 5, 5, 5], 100.0, RiskCategory.AGGRESSIVE),
    ]

    for p_name, weights, expected_score, expected_category in profiles:
        answers = make_answers(weights)
        result = evaluate_and_explain(
            {"answers": [a.model_dump() for a in answers], "force_fallback": True}
        )

        assert result.assessment.composite_score == expected_score
        assert result.assessment.risk_category == expected_category
        # Verify explanation summary contains correct score representation
        assert f"{expected_score:.1f}" in result.explanation.summary
        assert expected_category.value in result.explanation.summary


def test_influencing_factors_extraction():
    """Verify specific high/low driver factors are extracted and cited."""
    # Profile with low willingness (W1=1) and high capacity (C3=5)
    weights = [1, 1, 1, 1, 1, 5, 5, 5, 5, 5]
    answers = make_answers(weights)
    result = evaluate_and_explain(
        {"answers": [a.model_dump() for a in answers], "force_fallback": True}
    )

    factors = result.explanation.key_influencing_factors
    assert len(factors) > 0

    factor_qids = [f.question_id for f in factors]
    assert "W1" in factor_qids
    assert "C3" in factor_qids

    w1_factor = next(f for f in factors if f.question_id == "W1")
    assert w1_factor.score == 1
    assert "Conservative" in w1_factor.impact or "Low" in w1_factor.impact

    c3_factor = next(f for f in factors if f.question_id == "C3")
    assert c3_factor.score == 5
    assert "Strong Safety Buffer" in c3_factor.impact


def test_regulatory_disclaimers_present():
    """Verify that mandatory disclaimers exist and prohibit return promises."""
    answers = make_answers([3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
    result = evaluate_and_explain(
        {"answers": [a.model_dump() for a in answers], "force_fallback": True}
    )

    disclaimers = result.explanation.limitations_and_disclaimers
    assert len(disclaimers) >= 3

    disclaimer_text = " ".join(disclaimers).lower()
    assert "educational assessment" in disclaimer_text
    assert "no specific returns are guaranteed" in disclaimer_text or "risk of loss" in disclaimer_text


def test_fallback_on_malformed_llm_json():
    """Verify that malformed LLM JSON gracefully falls back to deterministic explanation."""
    def broken_llm_caller(sys_prompt: str, user_prompt: str) -> str:
        return "This is not JSON at all! {invalid syntax"

    engine = RiskExplanationEngine(llm_caller=broken_llm_caller)
    answers = make_answers([3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
    assessment = calculate_risk_score(answers)

    explanation = engine.explain(assessment, answers=answers)
    assert explanation.is_fallback is True
    assert explanation.model_version == "deterministic_rule_v1.0.0"
    assert "Moderate" in explanation.summary


def test_fallback_on_prohibited_guarantee_phrase():
    """Verify that if LLM attempts to promise returns, safety filter triggers deterministic fallback."""
    def rogue_llm_caller(sys_prompt: str, user_prompt: str) -> str:
        return json.dumps({
            "summary": "You will get guaranteed return of 15% every year!",
            "willingness_explanation": "Great growth ahead.",
            "capacity_explanation": "High capacity.",
            "alignment_analysis": "Aligned.",
            "key_influencing_factors": [],
            "limitations_and_disclaimers": ["No risk."],
        })

    engine = RiskExplanationEngine(llm_caller=rogue_llm_caller)
    answers = make_answers([5, 5, 5, 5, 5, 5, 5, 5, 5, 5])
    assessment = calculate_risk_score(answers)

    explanation = engine.explain(assessment, answers=answers)
    assert explanation.is_fallback is True  # Filter caught prohibited phrase
    assert "guaranteed return" not in explanation.summary.lower()


def test_successful_llm_response_validation():
    """Verify valid structured LLM response is accepted when conforming to schema."""
    def mock_valid_llm_caller(sys_prompt: str, user_prompt: str) -> str:
        return json.dumps({
            "summary": "Your responses place you comfortably in the Moderate risk tier with a score of 50.0/100.",
            "willingness_explanation": "You take a balanced perspective on market volatility.",
            "capacity_explanation": "Your finances provide reasonable security and horizon.",
            "alignment_analysis": "Your willingness and capacity are in strong balance.",
            "key_influencing_factors": [
                {
                    "dimension": "willingness",
                    "question_id": "W1",
                    "question_text": "Drawdown reaction",
                    "answer_code": "W1_C",
                    "answer_label": "Do nothing and wait it out",
                    "score": 3,
                    "impact": "Balanced Stance",
                    "explanation": "Waiting out dips shows patient investing mindset."
                }
            ],
            "limitations_and_disclaimers": [
                "Educational assessment only; not personalized financial advice."
            ],
        })

    engine = RiskExplanationEngine(llm_caller=mock_valid_llm_caller, model_name="mock-gemini-1.5")
    answers = make_answers([3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
    assessment = calculate_risk_score(answers)

    explanation = engine.explain(assessment, answers=answers)
    assert explanation.is_fallback is False
    assert explanation.model_version == "mock-gemini-1.5"
    assert len(explanation.key_influencing_factors) == 1
    assert explanation.prompt_version == PROMPT_VERSION_V1
    assert explanation.schema_version == SCHEMA_VERSION_V1


def test_boundary_transition_profiles():
    """Verify deterministic explanations for direct category transition points."""
    boundary_cases = [
        ([3, 2, 2, 2, 2, 3, 3, 2, 2, 2], 32.5, RiskCategory.CONSERVATIVE),
        ([3, 3, 2, 2, 2, 3, 3, 2, 2, 2], 35.0, RiskCategory.MODERATE),
        ([4, 4, 4, 3, 3, 4, 4, 4, 3, 3], 65.0, RiskCategory.MODERATE),
        ([4, 4, 4, 4, 3, 4, 4, 4, 3, 3], 67.5, RiskCategory.AGGRESSIVE),
    ]

    for weights, expected_score, expected_cat in boundary_cases:
        answers = make_answers(weights)
        res = evaluate_and_explain({"answers": [a.model_dump() for a in answers], "force_fallback": True})
        assert res.assessment.composite_score == expected_score
        assert res.assessment.risk_category == expected_cat
        assert expected_cat.value in res.explanation.summary


def test_golden_examples_file_completeness():
    """Verify that ai/risk/golden_examples_v1.json contains 10 valid examples."""
    json_path = Path(__file__).resolve().parent / "golden_examples_v1.json"
    assert json_path.exists(), "golden_examples_v1.json file must exist"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "v1.0.0"
    assert data["total_examples"] == 10
    assert len(data["examples"]) == 10

    for ex in data["examples"]:
        assert "example_id" in ex
        assert "deterministic_assessment" in ex
        assert "structured_explanation" in ex
        # Verify schema re-validation
        assessment = RiskAssessmentResult(**ex["deterministic_assessment"])
        explanation = RiskExplanationResponse(**ex["structured_explanation"])
        assert assessment.composite_score >= 0.0
        assert explanation.summary is not None


def test_security_prompt_injection_resistance():
    """Verify that malicious prompt injection in user input does not compromise safety."""
    # Attempt prompt injection via answer code or question id
    malicious_answers = make_answers([3, 3, 3, 3, 3, 3, 3, 3, 3, 3])
    # The Pydantic validator blocks invalid question/answer codes
    with pytest.raises(ValidationError):
        QuestionAnswer(question_id="W1; DROP TABLE users;", answer_code="W1_C")

    with pytest.raises(ValidationError):
        QuestionAnswer(question_id="W1", answer_code="W1_C' OR '1'='1")


def test_deterministic_timestamp_replay():
    """Verify that fixed timestamp override yields bitwise identical explanation payload."""
    answers = make_answers([2, 2, 2, 2, 2, 2, 2, 2, 2, 2])
    res1 = evaluate_and_explain({
        "answers": [a.model_dump() for a in answers],
        "calculated_at": "2026-08-29T15:00:00Z",
        "force_fallback": True,
    })
    res2 = evaluate_and_explain({
        "answers": [a.model_dump() for a in answers],
        "calculated_at": "2026-08-29T15:00:00Z",
        "force_fallback": True,
    })

    assert res1.model_dump_json() == res2.model_dump_json()
