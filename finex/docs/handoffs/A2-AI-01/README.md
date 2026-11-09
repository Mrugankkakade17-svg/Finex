# Task Handoff Package: S2-AI-01 (Deterministic Risk Scoring v1)

- **Task ID**: `S2-AI-01`
- **Owner**: Khyati / Shivraj
- **Reviewers**: Nayan + Syona
- **Branch**: `feature/S2-AI-01-khyati` / `feature/A2-AI-01-risk-scoring`
- **Target Branch**: `dev`
- **Status**: Completed & Ready for Review

---

## 1. Summary of Changes & Architecture

Implemented the **Deterministic Risk Scoring Engine v1** adhering to the approved canonical questionnaire specification ([`backend/data/questionnaire/risk_questionnaire_v1.json`](../../../backend/data/questionnaire/risk_questionnaire_v1.json) from S2-DAT-02).

### Core Principles Enforced
1. **Strictly Deterministic (Zero LLM for Numeric Scoring)**:
   - All score calculations are mathematical, reproducible, and auditable.
   - Same answers *always* produce the exact same numerical scores, category mapping, and full serialized responses.
   - Supports optional `calculated_at` override timestamp for deterministic audit replay and testing.
2. **Dimension Separation**:
   - Evaluates **Willingness** (W1–W5: psychological loss tolerance, 5..25 raw) and **Capacity** (C1–C5: financial horizon, stability, emergency cushion, 5..25 raw).
   - Normalizes raw scores to standard `0.0 – 100.0` range using `((raw - 5) / 20) * 100`.
   - Combines with equal 50/50 weighting into composite score: `(willingness * 0.5) + (capacity * 0.5)`.
3. **Canonical Profile Classification & Boundary Precision**:
   - `0.0 <= score < 34.0` ➔ `Conservative` (`CONSERVATIVE`) — e.g. `33.99` ➔ Conservative
   - `34.0 <= score < 67.0` ➔ `Moderate` (`MODERATE`) — e.g. `34.00` & `66.99` ➔ Moderate
   - `67.0 <= score <= 100.0` ➔ `Aggressive` (`AGGRESSIVE`) — e.g. `67.00` ➔ Aggressive
4. **Safe Non-LLM Explanation Fallback**:
   - Generates structured, rule-based rationale analyzing willingness vs capacity dynamics without any external LLM/API dependencies.

---

## 2. Deliverables

| File | Purpose |
| :--- | :--- |
| [`ai/risk/__init__.py`](../../../ai/risk/__init__.py) | Package initialization exposing `RiskScoringEngine`, `calculate_risk_score`, and schemas. |
| [`backend/data/questionnaire/risk_questionnaire_v1.json`](../../../backend/data/questionnaire/risk_questionnaire_v1.json) | Approved canonical S2-DAT-02 questionnaire configuration with 10 questions, answer weights (1–5), raw ranges, and category boundaries. |
| [`ai/risk/schemas.py`](../../../ai/risk/schemas.py) | Pydantic request/response models (`RiskAssessmentRequest`, `RiskAssessmentResult`, `DimensionScore`, `NonLLMExplanation`). |
| [`ai/risk/scoring.py`](../../../ai/risk/scoring.py) | Deterministic scoring engine with dimension normalization, composite calculation, category mapping, audit timestamp support, and safe non-LLM explanation fallback. |
| [`ai/risk/test_scoring.py`](../../../ai/risk/test_scoring.py) | Comprehensive test suite covering 12 genuinely distinct profiles, 1,000-run determinism, byte-for-byte serialized determinism, direct boundary transition points (33.99, 34.00, 66.99, 67.00), and input validation error handling. |

---

## 3. Verification & Test Evidence

### Test Execution Summary (32/32 Passed)
```text
ai/risk/test_scoring.py::test_12_profiles_strictly_distinct PASSED       [  3%]
ai/risk/test_scoring.py::test_profile_01_extreme_conservative PASSED     [  6%]
ai/risk/test_scoring.py::test_profile_02_extreme_aggressive PASSED       [  9%]
ai/risk/test_scoring.py::test_profile_03_balanced_moderate PASSED        [ 12%]
ai/risk/test_scoring.py::test_profile_04_high_willingness_low_capacity PASSED [ 15%]
ai/risk/test_scoring.py::test_profile_05_low_willingness_high_capacity PASSED [ 18%]
ai/risk/test_scoring.py::test_profile_06_steady_conservative PASSED      [ 21%]
ai/risk/test_scoring.py::test_profile_07_conservative_upper_boundary PASSED [ 25%]
ai/risk/test_scoring.py::test_profile_08_moderate_lower_boundary PASSED  [ 28%]
ai/risk/test_scoring.py::test_profile_09_mid_moderate PASSED             [ 31%]
ai/risk/test_scoring.py::test_profile_10_moderate_upper_boundary PASSED  [ 34%]
ai/risk/test_scoring.py::test_profile_11_aggressive_lower_boundary PASSED [ 37%]
ai/risk/test_scoring.py::test_profile_12_high_growth_aggressive PASSED   [ 40%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[0.0-Conservative-CONSERVATIVE] PASSED [ 43%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[33.99-Conservative-CONSERVATIVE] PASSED [ 46%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[33.999-Conservative-CONSERVATIVE] PASSED [ 50%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[34.0-Moderate-MODERATE] PASSED [ 53%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[34.001-Moderate-MODERATE] PASSED [ 56%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[66.99-Moderate-MODERATE] PASSED [ 59%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[66.999-Moderate-MODERATE] PASSED [ 62%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[67.0-Aggressive-AGGRESSIVE] PASSED [ 65%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[67.001-Aggressive-AGGRESSIVE] PASSED [ 68%]
ai/risk/test_scoring.py::test_direct_boundary_transition_points[100.0-Aggressive-AGGRESSIVE] PASSED [ 71%]
ai/risk/test_scoring.py::test_boundary_explanation_generation PASSED     [ 75%]
ai/risk/test_scoring.py::test_full_response_determinism_with_fixed_timestamp PASSED [ 78%]
ai/risk/test_scoring.py::test_determinism_consistency_1000_runs PASSED   [ 81%]
ai/risk/test_scoring.py::test_missing_question_raises_error PASSED       [ 84%]
ai/risk/test_scoring.py::test_duplicate_question_raises_error PASSED     [ 87%]
ai/risk/test_scoring.py::test_invalid_answer_code_raises_error PASSED    [ 90%]
ai/risk/test_scoring.py::test_mismatched_answer_code_raises_error PASSED [ 93%]
ai/risk/test_scoring.py::test_invalid_questionnaire_id_raises_error PASSED [ 96%]
ai/risk/test_scoring.py::test_non_llm_explanation_structure PASSED       [100%]

============================= 32 passed in 0.13s ==============================
```

### 12 Genuinely Distinct Profiles Matrix

| Profile | Description | Input Vector | W Raw | C Raw | W Score | C Score | Composite | Classification |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **01** | Extreme Conservative (All 1s) | `[1, 1, 1, 1, 1, 1, 1, 1, 1, 1]` | 5 | 5 | 0.0 | 0.0 | **0.0** | Conservative |
| **02** | Extreme Aggressive (All 5s) | `[5, 5, 5, 5, 5, 5, 5, 5, 5, 5]` | 25 | 25 | 100.0 | 100.0 | **100.0** | Aggressive |
| **03** | Balanced Moderate (All 3s) | `[3, 3, 3, 3, 3, 3, 3, 3, 3, 3]` | 15 | 15 | 50.0 | 50.0 | **50.0** | Moderate |
| **04** | High Willingness, Low Capacity | `[5, 5, 5, 5, 5, 1, 1, 1, 1, 1]` | 25 | 5 | 100.0 | 0.0 | **50.0** | Moderate (Capacity warning) |
| **05** | Low Willingness, High Capacity | `[1, 1, 1, 1, 1, 5, 5, 5, 5, 5]` | 5 | 25 | 0.0 | 100.0 | **50.0** | Moderate (Comfort warning) |
| **06** | Steady Low-Risk Conservative | `[2, 2, 2, 2, 2, 2, 2, 2, 2, 2]` | 10 | 10 | 25.0 | 25.0 | **25.0** | Conservative |
| **07** | Conservative Upper Bound | `[3, 2, 2, 2, 2, 3, 3, 2, 2, 2]` | 11 | 12 | 30.0 | 35.0 | **32.5** | Conservative |
| **08** | Moderate Lower Bound | `[3, 3, 2, 2, 2, 3, 3, 2, 2, 2]` | 12 | 12 | 35.0 | 35.0 | **35.0** | Moderate |
| **09** | Mid Moderate Profile | `[4, 4, 3, 3, 3, 4, 4, 3, 3, 3]` | 17 | 17 | 60.0 | 60.0 | **60.0** | Moderate |
| **10** | Moderate Upper Bound | `[4, 4, 4, 3, 3, 4, 4, 4, 3, 3]` | 18 | 18 | 65.0 | 65.0 | **65.0** | Moderate |
| **11** | Aggressive Lower Bound | `[4, 4, 4, 4, 3, 4, 4, 4, 3, 3]` | 19 | 18 | 70.0 | 65.0 | **67.5** | Aggressive |
| **12** | High Growth Aggressive | `[5, 5, 5, 4, 4, 5, 5, 5, 4, 4]` | 23 | 23 | 90.0 | 90.0 | **90.0** | Aggressive |

---

## 4. Reproducible Run Instructions

### Environment Setup & Dependency Installation
```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 2. Install required dependencies
pip install -r backend/requirements.txt
```

### Running the Test Suite (Project-Standard Commands)
Run the risk scoring unit and profile test suite from the repository root:
```bash
pytest ai/risk/test_scoring.py -v
```

Or via Python module invocation:
```bash
python -m pytest ai/risk/test_scoring.py -v
```

To run the full test suite across both the backend and AI scoring with coverage:
```bash
pytest ai/risk/test_scoring.py backend/tests
```

### Python Programmatic Usage Example
```python
from ai.risk import calculate_risk_score, QuestionAnswer

answers = [
    QuestionAnswer(question_id="W1", answer_code="W1_C"),
    QuestionAnswer(question_id="W2", answer_code="W2_C"),
    QuestionAnswer(question_id="W3", answer_code="W3_C"),
    QuestionAnswer(question_id="W4", answer_code="W4_C"),
    QuestionAnswer(question_id="W5", answer_code="W5_C"),
    QuestionAnswer(question_id="C1", answer_code="C1_C"),
    QuestionAnswer(question_id="C2", answer_code="C2_C"),
    QuestionAnswer(question_id="C3", answer_code="C3_C"),
    QuestionAnswer(question_id="C4", answer_code="C4_C"),
    QuestionAnswer(question_id="C5", answer_code="C5_C"),
]

# Live scoring call
result = calculate_risk_score(answers)
print(f"Risk Category: {result.risk_category.value}")      # Moderate
print(f"Composite Score: {result.composite_score}")        # 50.0

# Deterministic audit replay with fixed timestamp
audit_result = calculate_risk_score(answers, calculated_at="2026-08-24T12:00:00Z")
print(audit_result.model_dump_json())
```

---

## 5. Known Limitations

1. **Discrete Score Granularity**:
   - The questionnaire v1 contains 10 single-choice questions with integer weights (1–5).
   - With 5 questions per dimension, each dimension has 21 discrete integer sums (5..25), corresponding to steps of 5.0 on normalized scores and 2.5 on composite scores.
2. **Fixed 50/50 Dimension Weighting**:
   - Questionnaire v1 implements static equal weighting (`willingness_weight: 0.5`, `capacity_weight: 0.5`) as specified in S2-DAT-02. Dynamic investor-type weighting or life-stage adaptive weighting is planned for future iterations.
3. **Template-Based Non-LLM Explanations**:
   - In adherence to zero-LLM scoring requirements, all rationale and alignment notes are rule-based deterministic heuristics. Dynamic conversational GenAI explanations with LLM guardrails are scheduled in milestone S2-AI-02.
4. **Single Active Questionnaire Version in v1**:
   - The engine is designed for versioned configurations, currently bound to `risk_questionnaire_v1`. Future multi-version active/retired questionnaires will be loaded dynamically via Lakebase/Postgres DB repository integration.

---

## 6. Acceptance Checklist

- [x] Consumes approved canonical S2-DAT-02 questionnaire (`backend/data/questionnaire/risk_questionnaire_v1.json`).
- [x] 12 genuinely distinct profile inputs tested and verified (`test_12_profiles_strictly_distinct`).
- [x] Full response determinism supported via `calculated_at` override and 1,000-run consistency verified.
- [x] Direct boundary transition coverage for `33.99` ➔ Conservative, `34.00` ➔ Moderate, `66.99` ➔ Moderate, `67.00` ➔ Aggressive.
- [x] Zero LLM for numeric scoring.
- [x] Safe non-LLM explanation fallback implemented.
- [x] All 223 backend and risk scoring tests passing (79.14% coverage).
