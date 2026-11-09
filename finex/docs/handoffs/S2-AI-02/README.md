# Task Handoff Package: S2-AI-02 (Deterministic Risk Result Explanation Prompt & Schemas)

- **Task ID**: `S2-AI-02`
- **Owner**: Pranjal
- **Reviewers**: Nayan + Likhita
- **Branch**: `feature/S2-AI-02-deterministic-risk-explanation`
- **Target Branch**: `dev` / `main`
- **Status**: Completed & Ready for Review

---

## 1. Summary of Changes & Architecture

Implemented the **Deterministic Risk Result Explanation Engine & Structured Prompt Framework (v1)** to provide beginner-friendly, auditable, and regulatory-compliant narrative explanations of questionnaire risk scores without introducing numerical drift or advice liability.

### Core Principles Enforced
1. **Zero LLM Numerical Drift (Strict Integrity)**:
   - All score calculations (`willingness_score`, `capacity_score`, `composite_score`, and canonical `risk_category`) remain 100% deterministic and computed outside the LLM by `S2-AI-01`.
   - The explanation framework is strictly prohibited from altering, re-rounding, or modifying any numerical score or category mapping.
2. **Beginner-Friendly Language & Jargon Elimination**:
   - Translates technical financial metrics into clear, relatable concepts (e.g. explains drawdown as short-term market dips and liquidity as access to emergency cash).
3. **Citation of Influencing Questionnaire Answers**:
   - Extracts and cites the top driver questions and chosen answers (e.g., behavioral reaction to 20% drops `W1`, time horizon `C1`, emergency cash cushion `C3`).
4. **Mandatory Regulatory Disclaimers & Non-Promise Policy**:
   - Automatically attaches compliance guardrails: points out self-reported questionnaire limitations, states educational purpose, and **strictly never promises returns** or specific security recommendations.
5. **Prompt & Schema Version Governance**:
   - Versioned prompt templates (`prompt_version: v1.0.0`) and JSON output schemas (`schema_version: v1.0.0`) enforced via Pydantic and FastAPI.
6. **Safe Non-LLM Fallback Engine**:
   - Deterministic rule-based fallback guarantees identical structural output in offline mode, network timeouts, malformed LLM responses, or prompt injection attacks.
7. **FastAPI Endpoints**:
   - Exposed `POST /api/v1/risk/evaluate`, `POST /api/v1/risk/explain`, and `POST /api/v1/risk/evaluate-and-explain` in standard FinEx API envelopes.

---

## 2. Deliverables Matrix

| File | Purpose |
| :--- | :--- |
| [`ai/risk/prompts/explanation_prompt_v1.py`](../../../ai/risk/prompts/explanation_prompt_v1.py) | Versioned system prompt (`v1.0.0`), user prompt formatter, and strict compliance instructions. |
| [`ai/risk/prompts/__init__.py`](../../../ai/risk/prompts/__init__.py) | Prompt package initialization exposing version constants and formatters. |
| [`ai/risk/schemas.py`](../../../ai/risk/schemas.py) | Pydantic response models (`RiskExplanationResponse`, `KeyInfluencingFactor`, `RiskAssessmentAndExplanationResult`, `RiskExplanationRequest`). |
| [`ai/risk/explanation.py`](../../../ai/risk/explanation.py) | `RiskExplanationEngine` orchestrating prompt building, key factor extraction, JSON schema validation, prohibited phrase checks, and safe fallback. |
| [`ai/risk/__init__.py`](../../../ai/risk/__init__.py) | Package exports for explanation engine, helpers, and schemas. |
| [`ai/risk/golden_examples_v1.json`](../../../ai/risk/golden_examples_v1.json) | 10 verified golden explanation examples across distinct risk profiles and boundary transition points. |
| [`backend/app/schemas/risk.py`](../../../backend/app/schemas/risk.py) | Backend API schema definitions. |
| [`backend/app/routers/risk.py`](../../../backend/app/routers/risk.py) | FastAPI router providing `/evaluate`, `/explain`, and `/evaluate-and-explain` endpoints. |
| [`backend/app/main.py`](../../../backend/app/main.py) | Registered `risk_router` in backend application. |
| [`ai/risk/test_explanation.py`](../../../ai/risk/test_explanation.py) | Comprehensive test suite validating zero numerical drift, fallback resilience, prompt injection resistance, boundary profiles, and schema validation. |
| [`backend/tests/test_risk_explanation_api.py`](../../../backend/tests/test_risk_explanation_api.py) | FastAPI endpoint integration tests for risk evaluation and structured explanation. |

---

## 3. Verification & Test Evidence

### Full Test Suite Summary (241/241 Passed, 79.10% Coverage)
```text
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.4.1, pluggy-1.6.0
rootdir: C:\Users\pranj\Documents\FINEXA\backend
configfile: pyproject.toml
plugins: anyio-4.12.1, langsmith-0.8.14, asyncio-1.4.0, cov-7.1.0

ai/risk/test_scoring.py ................................                 [ 13%]
ai/risk/test_explanation.py ...........                                  [ 17%]
backend/tests/test_api_contract.py ...                                   [ 19%]
backend/tests/test_auth.py .......                                       [ 21%]
backend/tests/test_auth_flow.py ..                                       [ 22%]
backend/tests/test_auth_service.py ........                              [ 26%]
backend/tests/test_c1_api_success.py ..                                  [ 26%]
backend/tests/test_c1_repository.py ....                                 [ 28%]
backend/tests/test_c1_service_create.py .                                [ 29%]
backend/tests/test_dat02_repository.py ..........                        [ 33%]
backend/tests/test_dat02_seed_idempotent.py ......                       [ 35%]
backend/tests/test_demo.py .                                             [ 36%]
backend/tests/test_exceptions.py ...........                             [ 40%]
backend/tests/test_health.py ...                                         [ 41%]
backend/tests/test_repository.py ...........                             [ 46%]
backend/tests/test_risk_explanation_api.py .......                       [ 49%]
backend/tests/test_security.py .........                                 [ 53%]
backend/tests/test_user_service.py .........                             [ 56%]
backend/tests/test_users_router.py ..                                    [ 57%]
backend/tests/unit/...                                                   [100%]

===================== 241 passed, 200 warnings in 22.72s ======================
Required test coverage of 70% reached. Total coverage: 79.10%
```

---

## 4. 10 Golden Explanation Examples Summary

| Example ID | Profile Title | Composite Score | Category | Key Influencing Factor Highlight |
| :--- | :--- | :---: | :---: | :--- |
| **01** | Extreme Conservative (All 1s) | **0.0** | Conservative | `W1_A` (Sell all immediately) & `C3_A` (No emergency savings) |
| **02** | Steady Low-Risk Conservative (All 2s) | **25.0** | Conservative | `W1_B` (Sell some to reduce risk) & `C1_B` (1-3 yr horizon) |
| **03** | Conservative Upper Boundary | **32.5** | Conservative | `W1_C` (Wait out dips) & `C1_C` (3-5 yr horizon) |
| **04** | Moderate Lower Boundary | **35.0** | Moderate | `W2_C` (Neutral comfort) & `C3_C` (1-3 months savings) |
| **05** | Balanced Core Moderate (All 3s) | **50.0** | Moderate | `W3_C` (Balance growth & stability) & `C2_C` (Low living expense dependency) |
| **06** | High Willingness / Low Capacity Tension | **50.0** | Moderate (Tension) | `W1_E` (Buy more on dip) vs `C3_A` (No emergency buffer constraint) |
| **07** | Low Willingness / High Capacity Tension | **50.0** | Moderate (Tension) | `W1_A` (Low emotional comfort) vs `C3_E` (>6 months emergency cushion) |
| **08** | Moderate Upper Boundary | **65.0** | Moderate | `W1_D` (Hold as normal) & `C4_D` (Stable income) |
| **09** | Aggressive Lower Boundary | **67.5** | Aggressive | `W1_D` (Normal fluctuation) & `C1_D` (5-10 yr horizon) |
| **10** | Extreme Aggressive Growth (All 5s) | **100.0** | Aggressive | `W1_E` (Buy more on dips) & `C1_E` (>10 yr horizon) |

*Full JSON payloads available in [`ai/risk/golden_examples_v1.json`](../../../ai/risk/golden_examples_v1.json).*

---

## 5. Reproducible Run Instructions

### 1. Run Explanation & Scoring Unit Tests
```bash
python -m pytest ai/risk/test_explanation.py ai/risk/test_scoring.py -v
```

### 2. Run API Integration Tests
```bash
python -m pytest backend/tests/test_risk_explanation_api.py -v
```

### 3. Run Full Test Suite with Coverage
```bash
python -m pytest ai/risk/ backend/tests/
```

### 4. Python Programmatic Usage
```python
from ai.risk import QuestionAnswer, evaluate_and_explain

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

# One-shot evaluate and explain
result = evaluate_and_explain({"answers": [a.model_dump() for a in answers]})
print(result.assessment.composite_score)      # 50.0
print(result.explanation.summary)            # Plain-language explanation
print(result.explanation.key_influencing_factors)
```

---

## 6. Definition of Done Checklist

- [x] Versioned prompt template (`prompt_version: v1.0.0`) in `ai/risk/prompts/explanation_prompt_v1.py`.
- [x] Versioned response schemas (`schema_version: v1.0.0`) in `ai/risk/schemas.py`.
- [x] Zero LLM numerical drift: calculations stay 100% in `S2-AI-01` deterministic scoring engine.
- [x] Cites influencing questionnaire answers and factors.
- [x] Beginner-friendly language without financial jargon.
- [x] Includes regulatory limitations and strict non-promise policy.
- [x] Safe non-LLM fallback engine handles malformed output, timeouts, and injection attempts.
- [x] FastAPI endpoints implemented in `backend/app/routers/risk.py` with validation and error handling.
- [x] 10 verified golden explanation examples in `ai/risk/golden_examples_v1.json`.
- [x] All 241 unit & integration tests passing with 79.10% coverage.
