"""Unit and Profile Test Suite for Deterministic Risk Scoring Engine v1 (S2-AI-01).

Acceptance Criteria:
1. Tests for at least 12 genuinely distinct user profile inputs.
2. Same answers ALWAYS produce the exact same score and deterministic output.
3. Direct boundary cases and transition points (33.99, 34.00, 66.99, 67.00) are rigorously covered.
4. No LLM is used for numeric scoring.
5. Missing, invalid, and malformed inputs are safely rejected.
"""

from datetime import datetime, timezone
import pytest
from ai.risk.schemas import QuestionAnswer, RiskAssessmentRequest, RiskCategory
from ai.risk.scoring import RiskScoringEngine, calculate_risk_score

engine = RiskScoringEngine()


# Helper to build answers from a list of 10 score integers (1-5)
def build_answers(scores: list[int]) -> list[QuestionAnswer]:
    assert len(scores) == 10, "Must supply exactly 10 scores: 5 for W, 5 for C"
    answers = []
    # W1..W5
    for i, s in enumerate(scores[:5], start=1):
        letter = chr(ord("A") + s - 1)
        answers.append(QuestionAnswer(question_id=f"W{i}", answer_code=f"W{i}_{letter}"))
    # C1..C5
    for i, s in enumerate(scores[5:], start=1):
        letter = chr(ord("A") + s - 1)
        answers.append(QuestionAnswer(question_id=f"C{i}", answer_code=f"C{i}_{letter}"))
    return answers


# Distinct profile input definitions for the 12 profile suite
PROFILES_INPUTS = {
    "profile_01": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],  # Extreme Conservative (All 1s)
    "profile_02": [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],  # Extreme Aggressive (All 5s)
    "profile_03": [3, 3, 3, 3, 3, 3, 3, 3, 3, 3],  # Balanced Moderate (All 3s)
    "profile_04": [5, 5, 5, 5, 5, 1, 1, 1, 1, 1],  # High Willingness, Low Capacity
    "profile_05": [1, 1, 1, 1, 1, 5, 5, 5, 5, 5],  # Low Willingness, High Capacity
    "profile_06": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],  # Steady Low-Risk Conservative (All 2s)
    "profile_07": [3, 2, 2, 2, 2, 3, 3, 2, 2, 2],  # Conservative Upper Bound (Composite = 32.5)
    "profile_08": [3, 3, 2, 2, 2, 3, 3, 2, 2, 2],  # Moderate Lower Bound (Composite = 35.0)
    "profile_09": [4, 4, 3, 3, 3, 4, 4, 3, 3, 3],  # Mid Moderate Profile (Composite = 60.0)
    "profile_10": [4, 4, 4, 3, 3, 4, 4, 4, 3, 3],  # Moderate Upper Bound (Composite = 65.0)
    "profile_11": [4, 4, 4, 4, 3, 4, 4, 4, 3, 3],  # Aggressive Lower Bound (Composite = 67.5)
    "profile_12": [5, 5, 5, 4, 4, 5, 5, 5, 4, 4],  # High Growth Aggressive (Composite = 90.0)
}


# =========================================================================
# TEST 1: 12 DISTINCT USER PROFILES TEST (Acceptance Requirement)
# =========================================================================

def test_12_profiles_strictly_distinct():
    """Verify that all 12 profiles defined in the test suite have genuinely distinct input vectors."""
    vectors = list(PROFILES_INPUTS.values())
    unique_vectors = {tuple(v) for v in vectors}
    assert len(unique_vectors) == 12, f"Expected 12 distinct profile inputs, got {len(unique_vectors)}"


# Profile 1: Extreme Conservative (All 1s)
def test_profile_01_extreme_conservative():
    answers = build_answers(PROFILES_INPUTS["profile_01"])
    result = calculate_risk_score(answers)

    assert result.willingness_score == 0.0
    assert result.capacity_score == 0.0
    assert result.composite_score == 0.0
    assert result.risk_category == RiskCategory.CONSERVATIVE
    assert result.risk_category_code == "CONSERVATIVE"
    assert "Conservative" in result.explanation.summary


# Profile 2: Extreme Aggressive (All 5s)
def test_profile_02_extreme_aggressive():
    answers = build_answers(PROFILES_INPUTS["profile_02"])
    result = calculate_risk_score(answers)

    assert result.willingness_score == 100.0
    assert result.capacity_score == 100.0
    assert result.composite_score == 100.0
    assert result.risk_category == RiskCategory.AGGRESSIVE
    assert result.risk_category_code == "AGGRESSIVE"
    assert "Aggressive" in result.explanation.summary


# Profile 3: Balanced Moderate (All 3s)
def test_profile_03_balanced_moderate():
    answers = build_answers(PROFILES_INPUTS["profile_03"])
    result = calculate_risk_score(answers)

    # Raw sums: W=15, C=15 -> Normalized: (15-5)/20 * 100 = 50.0
    assert result.willingness_score == 50.0
    assert result.capacity_score == 50.0
    assert result.composite_score == 50.0
    assert result.risk_category == RiskCategory.MODERATE
    assert result.risk_category_code == "MODERATE"


# Profile 4: High Willingness, Low Capacity (Aggressive Mindset, Conservative Financials)
def test_profile_04_high_willingness_low_capacity():
    answers = build_answers(PROFILES_INPUTS["profile_04"])
    result = calculate_risk_score(answers)

    assert result.willingness_score == 100.0
    assert result.capacity_score == 0.0
    assert result.composite_score == 50.0
    assert result.risk_category == RiskCategory.MODERATE
    assert "capacity is conservative" in result.explanation.alignment_note.lower()


# Profile 5: Low Willingness, High Capacity (Conservative Mindset, Wealthy Financials)
def test_profile_05_low_willingness_high_capacity():
    answers = build_answers(PROFILES_INPUTS["profile_05"])
    result = calculate_risk_score(answers)

    assert result.willingness_score == 0.0
    assert result.capacity_score == 100.0
    assert result.composite_score == 50.0
    assert result.risk_category == RiskCategory.MODERATE
    assert "psychological preference is conservative" in result.explanation.alignment_note.lower()


# Profile 6: Steady Low-Risk Conservative (All 2s)
def test_profile_06_steady_conservative():
    answers = build_answers(PROFILES_INPUTS["profile_06"])
    res = calculate_risk_score(answers)
    # Raw: W=10, C=10 -> Normalized: (10-5)/20 * 100 = 25.0 -> Composite = 25.0
    assert res.willingness_score == 25.0
    assert res.capacity_score == 25.0
    assert res.composite_score == 25.0
    assert res.risk_category == RiskCategory.CONSERVATIVE
    assert res.risk_category_code == "CONSERVATIVE"


# Profile 7: Conservative Upper Boundary (Composite = 32.5)
def test_profile_07_conservative_upper_boundary():
    # W: 3, 2, 2, 2, 2 = 11 (norm = 30.0)
    # C: 3, 3, 2, 2, 2 = 12 (norm = 35.0)
    # Composite = (30 + 35) / 2 = 32.5 -> Conservative
    answers = build_answers(PROFILES_INPUTS["profile_07"])
    res = calculate_risk_score(answers)
    assert res.composite_score == 32.5
    assert res.risk_category == RiskCategory.CONSERVATIVE


# Profile 8: Moderate Lower Boundary (Composite >= 34.0)
def test_profile_08_moderate_lower_boundary():
    answers = build_answers(PROFILES_INPUTS["profile_08"])
    res = calculate_risk_score(answers)
    assert res.composite_score == 35.0
    assert res.risk_category == RiskCategory.MODERATE


# Profile 9: Mid Moderate Profile (W=60.0, C=60.0 -> Composite=60.0)
def test_profile_09_mid_moderate():
    answers = build_answers(PROFILES_INPUTS["profile_09"])
    res = calculate_risk_score(answers)
    assert res.willingness_score == 60.0
    assert res.capacity_score == 60.0
    assert res.composite_score == 60.0
    assert res.risk_category == RiskCategory.MODERATE


# Profile 10: Moderate Upper Boundary (Composite just below 67.0)
def test_profile_10_moderate_upper_boundary():
    answers = build_answers(PROFILES_INPUTS["profile_10"])
    res = calculate_risk_score(answers)
    assert res.composite_score == 65.0
    assert res.risk_category == RiskCategory.MODERATE


# Profile 11: Aggressive Lower Boundary (Composite >= 67.0)
def test_profile_11_aggressive_lower_boundary():
    answers = build_answers(PROFILES_INPUTS["profile_11"])
    res = calculate_risk_score(answers)
    assert res.willingness_score == 70.0
    assert res.capacity_score == 65.0
    assert res.composite_score == 67.5
    assert res.risk_category == RiskCategory.AGGRESSIVE


# Profile 12: High Growth Aggressive Profile (W=90.0, C=90.0 -> Composite=90.0)
def test_profile_12_high_growth_aggressive():
    answers = build_answers(PROFILES_INPUTS["profile_12"])
    res = calculate_risk_score(answers)
    assert res.willingness_score == 90.0
    assert res.capacity_score == 90.0
    assert res.composite_score == 90.0
    assert res.risk_category == RiskCategory.AGGRESSIVE


# =========================================================================
# TEST 2: DIRECT BOUNDARY TRANSITION COVERAGE
# =========================================================================

@pytest.mark.parametrize(
    "score,expected_category,expected_code",
    [
        (0.00, RiskCategory.CONSERVATIVE, "CONSERVATIVE"),
        (33.99, RiskCategory.CONSERVATIVE, "CONSERVATIVE"),
        (33.999, RiskCategory.CONSERVATIVE, "CONSERVATIVE"),
        (34.00, RiskCategory.MODERATE, "MODERATE"),
        (34.001, RiskCategory.MODERATE, "MODERATE"),
        (66.99, RiskCategory.MODERATE, "MODERATE"),
        (66.999, RiskCategory.MODERATE, "MODERATE"),
        (67.00, RiskCategory.AGGRESSIVE, "AGGRESSIVE"),
        (67.001, RiskCategory.AGGRESSIVE, "AGGRESSIVE"),
        (100.00, RiskCategory.AGGRESSIVE, "AGGRESSIVE"),
    ],
)
def test_direct_boundary_transition_points(score, expected_category, expected_code):
    """Direct tests around exact transition points:
    33.99 -> Conservative
    34.00 -> Moderate
    66.99 -> Moderate
    67.00 -> Aggressive
    """
    category, code = engine.map_to_category(score)
    assert category == expected_category
    assert code == expected_code


def test_boundary_explanation_generation():
    """Verify explanation generation across exact boundary points."""
    for score in [33.99, 34.00, 66.99, 67.00]:
        cat, _ = engine.map_to_category(score)
        exp = engine._generate_explanation(score, score, score, cat)
        assert cat.value in exp.summary
        assert exp.is_fallback is True


# =========================================================================
# TEST 3: DETERMINISM & REPRODUCIBILITY TESTS
# =========================================================================

def test_full_response_determinism_with_fixed_timestamp():
    """Verify that identical inputs with fixed calculated_at produce 100% deterministic full output."""
    answers = build_answers([2, 4, 3, 5, 1, 4, 3, 5, 2, 4])
    fixed_ts = "2026-08-24T12:00:00Z"

    first_result = calculate_risk_score(answers, calculated_at=fixed_ts)
    first_dict = first_result.model_dump()
    first_json = first_result.model_dump_json()

    for _ in range(100):
        subsequent = calculate_risk_score(answers, calculated_at=fixed_ts)
        assert subsequent.model_dump() == first_dict
        assert subsequent.model_dump_json() == first_json
        assert subsequent.calculated_at == fixed_ts


def test_determinism_consistency_1000_runs():
    """Verify that identical inputs produce the exact same score across 1,000 runs."""
    answers = build_answers([2, 4, 3, 5, 1, 4, 3, 5, 2, 4])
    first_run = calculate_risk_score(answers)

    for _ in range(1000):
        run = calculate_risk_score(answers)
        assert run.willingness_score == first_run.willingness_score
        assert run.capacity_score == first_run.capacity_score
        assert run.composite_score == first_run.composite_score
        assert run.risk_category == first_run.risk_category
        assert run.risk_category_code == first_run.risk_category_code
        assert run.explanation.summary == first_run.explanation.summary
        assert run.breakdown == first_run.breakdown


# =========================================================================
# TEST 4: VALIDATION, MALFORMED & ERROR CASES
# =========================================================================

def test_missing_question_raises_error():
    """Submitting only 9 of 10 required questions should raise ValueError."""
    answers = build_answers([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    incomplete_answers = answers[:-1]  # drop C5

    with pytest.raises(ValueError, match="Missing required questions:.*C5"):
        calculate_risk_score(incomplete_answers)


def test_duplicate_question_raises_error():
    """Submitting duplicate answers for the same question should raise ValueError."""
    answers = build_answers([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    duplicate_answers = answers + [QuestionAnswer(question_id="W1", answer_code="W1_B")]

    with pytest.raises(ValueError, match="Duplicate answer submitted for question: 'W1'"):
        calculate_risk_score(duplicate_answers)


def test_invalid_answer_code_raises_error():
    """Submitting an unrecognized answer code should raise ValueError."""
    answers = build_answers([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    answers[0] = QuestionAnswer(question_id="W1", answer_code="W1_Z")

    with pytest.raises(ValueError, match="Invalid answer_code: 'W1_Z'"):
        calculate_risk_score(answers)


def test_mismatched_answer_code_raises_error():
    """Submitting an answer code that belongs to C1 for question W1 should raise ValueError."""
    answers = build_answers([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    answers[0] = QuestionAnswer(question_id="W1", answer_code="C1_A")

    with pytest.raises(ValueError, match="Answer code 'C1_A' does not belong to question 'W1'"):
        calculate_risk_score(answers)


def test_invalid_questionnaire_id_raises_error():
    """Submitting an incorrect questionnaire_id should raise ValueError."""
    answers = build_answers([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    with pytest.raises(ValueError, match="Invalid questionnaire_id: 'unknown_questionnaire'"):
        calculate_risk_score(answers, questionnaire_id="unknown_questionnaire")


# =========================================================================
# TEST 5: NON-LLM EXPLANATION INTEGRITY
# =========================================================================

def test_non_llm_explanation_structure():
    """Verify that explanation contains all expected fields with valid text."""
    answers = build_answers([4, 4, 4, 4, 4, 2, 2, 2, 2, 2])
    result = calculate_risk_score(answers)

    assert result.explanation.is_fallback is True
    assert len(result.explanation.summary) > 20
    assert len(result.explanation.willingness_rationale) > 20
    assert len(result.explanation.capacity_rationale) > 20
    assert len(result.explanation.alignment_note) > 20
    assert result.model_version == "deterministic_v1.0.0"
    assert result.schema_version == "v1.0.0"
