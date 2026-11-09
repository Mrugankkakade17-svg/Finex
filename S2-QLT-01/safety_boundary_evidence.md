# S2-QLT-01 — Safety Boundary Evidence

## Purpose

This document proves that the Sprint 2 deterministic risk feature enforces educational-only language, prohibits personalized financial advice, discloses timestamps and version information, and operates within the approved safety boundary.

---

## 1. Educational Language Enforcement

### Required Language (Handbook v9.1 §20)

The system must:
- Use **educational assessment** language in all outputs
- Include **limitation disclaimers** on every result
- **Never** imply real financial advice, brokerage action, or guaranteed returns

### Evidence

#### Standard Disclaimers (from `ai/risk/explanation.py`)

```python
STANDARD_DISCLAIMERS = [
    "This risk profile is an educational assessment based strictly on self-reported questionnaire responses and does not constitute individualized financial, legal, or tax advice.",
    "Investments in financial markets carry inherent risks, including the potential loss of principal. Past performance does not guarantee future results, and no specific returns are guaranteed.",
    "Your financial situation and risk tolerance can evolve over time. You should revisit this assessment periodically or whenever significant life events occur.",
]
```

#### Contract Limitation (from `ai/risk/contract.py`)

```python
LIMITATION_CODE = "EDUCATIONAL_SELF_REPORTED_PROFILE"
LIMITATION_MESSAGE = (
    "This educational profile is based on self-reported answers and is not individualized "
    "financial, legal, tax, or investment advice."
)
```

**Verification**:
- [x] Every `evaluate_risk_contract()` result includes `limitation.code` and `limitation.message`
- [x] Every explanation output includes ≥3 standard disclaimers
- [x] Disclaimer text uses "educational assessment" and "does not constitute … advice"
- [x] No disclaimer promises returns or suggests specific investments

**Result**: ✅ Educational language enforced at all output points

---

## 2. Prohibited Phrase Filter

### Blocked Phrases (from `ai/risk/explanation.py`)

| # | Prohibited Phrase | Purpose |
|---|------------------|---------|
| 1 | "guaranteed return" | Prevents return promises |
| 2 | "guaranteed profit" | Prevents profit promises |
| 3 | "risk-free profit" | Prevents risk-free claims |
| 4 | "will definitely earn" | Prevents earnings promises |
| 5 | "promise you" | Prevents personal promises |
| 6 | "sure shot" | Prevents certainty claims |
| 7 | "buy this stock" | Prevents specific stock advice |
| 8 | "invest in crypto" | Prevents specific crypto advice |

### Test Evidence

| Test | Input | Expected | Observed | Status |
|------|-------|----------|----------|--------|
| `test_fallback_on_prohibited_guarantee_phrase` | LLM returns "guaranteed return of 15%" | Safety fallback triggers | `is_fallback=True`, prohibited phrase absent | ✅ PASS |
| `test_safety_no_financial_advice` | All 12 golden profiles | No prohibited phrase in any output | All clean | ✅ PASS |

**Result**: ✅ Prohibited phrases are actively filtered and trigger deterministic fallback

---

## 3. Timestamp and Version Disclosure

### Required Disclosures

Every result must include:
- `calculated_at` — ISO 8601 UTC timestamp
- `scoring_version` / `model_version` — engine identifier
- `schema_version` — output schema identifier
- `contract_version` — contract boundary identifier

### Evidence

| Field | Source | Value | Status |
|-------|--------|-------|--------|
| `calculated_at` | `RiskAssessmentResult.calculated_at` | ISO 8601 UTC | ✅ Present |
| `model_version` | `RiskAssessmentResult.model_version` | `deterministic_v1.0.0` | ✅ Present |
| `schema_version` | `RiskAssessmentResult.schema_version` | `v1.0.0` | ✅ Present |
| `contract_version` | `evaluate_risk_contract()` | `s2-risk-contract/v1.0` | ✅ Present |
| `scoring_version` | Contract output | `deterministic_v1.0.0` | ✅ Present |
| `prompt_version` | `RiskExplanationResponse.prompt_version` | `v1.0.0` | ✅ Present |

**Result**: ✅ All version and timestamp fields are disclosed in every output

---

## 4. No Personalized Financial Advice

### Boundary Checks

| Check | Criterion | Evidence | Status |
|-------|-----------|----------|--------|
| No individual investment recommendations | Output never suggests specific securities | All explanations use generic educational language | ✅ PASS |
| No portfolio allocation advice | Output never recommends asset splits | Explanations describe profile, not actions | ✅ PASS |
| No return projections | Output never predicts future returns | Disclaimers explicitly state "no specific returns are guaranteed" | ✅ PASS |
| No suitability determination | Output never declares user "suitable" for investments | Language uses "categorized as" not "suitable for" | ✅ PASS |
| No real brokerage action | System never executes trades or account changes | Boundary: synthetic local educational pilot only | ✅ PASS |

**Result**: ✅ No personalized financial advice in any system output

---

## 5. Prompt Injection Resistance

### Input Validation (from `ai/risk/schemas.py`)

```python
@field_validator("question_id")
@classmethod
def validate_question_id(cls, v: str) -> str:
    v = v.strip().upper()
    if not v:
        raise ValueError("question_id cannot be empty")
    if not re.match(r"^[A-Z0-9_]+$", v):
        raise ValueError(f"Invalid question_id format: '{v}'")
    return v
```

### Test Evidence

| Attack Vector | Input | Expected | Status |
|--------------|-------|----------|--------|
| SQL injection in question_id | `"W1; DROP TABLE users;"` | `ValidationError` | ✅ PASS |
| SQL injection in answer_code | `"W1_C' OR '1'='1"` | `ValidationError` | ✅ PASS |
| Empty question_id | `""` | `ValidationError` | ✅ PASS |
| Special characters | `"W1<script>alert(1)</script>"` | `ValidationError` | ✅ PASS |

**Result**: ✅ Pydantic validators reject all injection attempts

---

## 6. Data Boundary

| Boundary | Enforcement | Status |
|----------|------------|--------|
| No real PII in test data | All fixtures use synthetic identifiers | ✅ Verified |
| No external API calls during scoring | Scoring engine is fully local and deterministic | ✅ Verified |
| No persistent storage of scores | Tests operate in-memory only | ✅ Verified |
| No cloud services required | Runs from clean local checkout | ✅ Verified |
| No production credentials | `.env.example` contains no secrets | ✅ Verified |

**Result**: ✅ Data boundary maintained

---

## Summary

| Safety Area | Checks | Passed |
|-------------|--------|--------|
| Educational language | 4 | ✅ 4 |
| Prohibited phrase filter | 2 | ✅ 2 |
| Timestamp/version disclosure | 6 | ✅ 6 |
| No financial advice | 5 | ✅ 5 |
| Prompt injection resistance | 4 | ✅ 4 |
| Data boundary | 5 | ✅ 5 |
| **TOTAL** | **26** | **✅ 26** |

---

*Safety boundary verified by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*
