# S2-QLT-01 — Contract Verification

## Purpose

This document verifies that the deterministic risk scoring engine, explanation engine, and contract boundary (`ai/risk/contract.py`) align precisely with the approved Sprint 2 risk contract (#146) and the golden case matrix.

---

## Contract Under Test

| Property | Value |
|----------|-------|
| Contract Source | `ai/risk/contract.py` |
| Contract Version | `s2-risk-contract/v1.0` |
| Scoring Engine | `ai/risk/scoring.py` — `deterministic_v1.0.0` |
| Explanation Engine | `ai/risk/explanation.py` — `deterministic_rule_v1.0.0` |
| Schema Source | `ai/risk/schemas.py` — `v1.0.0` |
| Questionnaire Config | `backend/data/questionnaire/risk_questionnaire_v1.json` |
| Golden Cases | `ai/risk/golden_examples_v1.json` (10 profiles) |
| Approved Contract Issue | [#146 — S1-RSK-00](https://github.com/IgnAite-Showcase/Finex/issues/146) |

---

## 1. Contract Input Shape

### Expected Input (from #146 contract)

```json
{
  "questionnaire_id": "risk_questionnaire_v1",
  "questionnaire_version": "v1",
  "answers": [
    {"question_id": "W1", "answer_code": "W1_C"},
    {"question_id": "W2", "answer_code": "W2_C"},
    {"question_id": "W3", "answer_code": "W3_C"},
    {"question_id": "W4", "answer_code": "W4_C"},
    {"question_id": "W5", "answer_code": "W5_C"},
    {"question_id": "C1", "answer_code": "C1_C"},
    {"question_id": "C2", "answer_code": "C2_C"},
    {"question_id": "C3", "answer_code": "C3_C"},
    {"question_id": "C4", "answer_code": "C4_C"},
    {"question_id": "C5", "answer_code": "C5_C"}
  ]
}
```

### Verification

- [x] `contract.py` expects exactly `{questionnaire_id, questionnaire_version, answers}` keys
- [x] `questionnaire_id` must match engine's `questionnaire_id` (validated at line 62–65)
- [x] `questionnaire_version` must match engine's `version_label` (validated at line 62–65)
- [x] Each answer must have exactly `{question_id, answer_code}` keys (validated at line 57)
- [x] All values must be non-empty strings (validated at line 59)
- [x] Questions W1–W5 and C1–C5 are all required (10 total)

**Result**: ✅ Input shape matches approved #146 contract

---

## 2. Contract Output Shape

### Expected Output (from #146 contract)

```json
{
  "contract_version": "s2-risk-contract/v1.0",
  "questionnaire_id": "risk_questionnaire_v1",
  "questionnaire_version": "v1",
  "scoring_version": "deterministic_v1.0.0",
  "willingness_score": 50.0,
  "capacity_score": 50.0,
  "composite_score": 50.0,
  "risk_category": {"code": "MODERATE", "label": "Moderate"},
  "calculated_at": "2026-10-12T00:00:00Z",
  "limitation": {
    "code": "EDUCATIONAL_SELF_REPORTED_PROFILE",
    "message": "This educational profile is based on self-reported answers and is not individualized financial, legal, tax, or investment advice."
  }
}
```

### Verification

- [x] `contract_version` is `s2-risk-contract/v1.0` (hardcoded constant, line 15)
- [x] `questionnaire_id` echoed from engine configuration
- [x] `questionnaire_version` echoed from engine configuration
- [x] `scoring_version` is `deterministic_v1.0.0` from `RiskAssessmentResult.model_version`
- [x] `willingness_score` — float, 0.0–100.0, normalized from raw 5–25 range
- [x] `capacity_score` — float, 0.0–100.0, normalized from raw 5–25 range
- [x] `composite_score` — float, 0.0–100.0, weighted average (50/50)
- [x] `risk_category` — `{code: str, label: str}` matching canonical enum
- [x] `calculated_at` — ISO 8601 UTC timestamp
- [x] `limitation` — fixed educational disclaimer (code + message)

**Result**: ✅ Output shape matches approved #146 contract

---

## 3. Error Code Vocabulary

| Error Code | Contract Description | Implementation | Status |
|-----------|---------------------|----------------|--------|
| `MALFORMED_ANSWER` | Malformed request or answer | `contract.py:48,52,55,58,60` | ✅ Match |
| `UNSUPPORTED_QUESTIONNAIRE_VERSION` | Wrong questionnaire ID/version | `contract.py:65` | ✅ Match |
| `DUPLICATE_QUESTION_ANSWER` | Same question answered twice | `contract.py:68` | ✅ Match |
| `UNKNOWN_QUESTION_ID` | Unknown question in request | `contract.py:70` | ✅ Match |
| `MISSING_REQUIRED_QUESTION` | Required question has no answer | `contract.py:72` | ✅ Match |
| `INVALID_ANSWER_CODE` | Undefined answer code | `contract.py:74` | ✅ Match |
| `ANSWER_NOT_PERMITTED_FOR_QUESTION` | Answer belongs to different question | `contract.py:79` | ✅ Match |

**Result**: ✅ All 7 error codes match the approved contract vocabulary

---

## 4. Scoring Determinism Verification

| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| Normalization formula | `(raw - 5) / 20 * 100` | `scoring.py:normalize_dimension()` line 98–104 | ✅ Match |
| Conservative boundary | `< 34.0` | `scoring.py:map_to_category()` line 114 | ✅ Match |
| Moderate boundary | `≥ 34.0 and < 67.0` | `scoring.py:map_to_category()` line 116 | ✅ Match |
| Aggressive boundary | `≥ 67.0` | `scoring.py:map_to_category()` line 118 | ✅ Match |
| Willingness weight | `0.5` | From questionnaire config `scoring.combination` | ✅ Match |
| Capacity weight | `0.5` | From questionnaire config `scoring.combination` | ✅ Match |
| Raw score range | `5–25` | From questionnaire config `scoring.dimension_raw_range` | ✅ Match |

**Result**: ✅ Scoring engine produces identical results to golden case matrix

---

## 5. Explanation Engine Contract Parity

| Check | Expected | Observed | Status |
|-------|----------|----------|--------|
| Prompt version | `v1.0.0` | `PROMPT_VERSION_V1` constant | ✅ Match |
| Schema version | `v1.0.0` | `SCHEMA_VERSION_V1` constant | ✅ Match |
| Fallback model version | `deterministic_rule_v1.0.0` | Default in `RiskExplanationResponse` | ✅ Match |
| Prohibited phrases | 8 phrases blocked | `PROHIBITED_PHRASES` list in `explanation.py` | ✅ Match |
| Standard disclaimers | 3 mandatory disclaimers | `STANDARD_DISCLAIMERS` list | ✅ Match |
| Zero drift guarantee | Explanation never recalculates scores | Verified in `test_explanation.py` | ✅ Match |

**Result**: ✅ Explanation engine matches approved contract

---

## 6. Educational Limitation Parity

| Check | Contract Text | Implementation | Status |
|-------|--------------|----------------|--------|
| Limitation code | `EDUCATIONAL_SELF_REPORTED_PROFILE` | `contract.py:16` | ✅ Match |
| Limitation message | "This educational profile is based on self-reported answers…" | `contract.py:17–20` | ✅ Match |
| No financial advice | Must not promise returns or suggest investments | `PROHIBITED_PHRASES` + `STANDARD_DISCLAIMERS` | ✅ Match |

**Result**: ✅ Educational limitation enforced at contract boundary

---

## Summary

| Contract Area | Checks | Passed | Status |
|--------------|--------|--------|--------|
| Input shape | 6 | 6 | ✅ |
| Output shape | 10 | 10 | ✅ |
| Error vocabulary | 7 | 7 | ✅ |
| Scoring determinism | 7 | 7 | ✅ |
| Explanation parity | 6 | 6 | ✅ |
| Educational limitation | 3 | 3 | ✅ |
| **TOTAL** | **39** | **39** | **✅** |

---

*Verified by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*  
*Contract version: s2-risk-contract/v1.0*
