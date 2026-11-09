# S2-QLT-01 — Acceptance Matrix

## Overview

This matrix covers every testable scenario for the Sprint 2 deterministic risk scoring, explanation, and contract boundary evaluation. Each row represents a distinct scenario, its expected behavior, and the observed result.

> **Recovery Base**: `release/2026-W40` (W40 recovery tree; W36 is quarantined)  
> **Evidence PR**: [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) — commit `27ade62`  
> **Scoring Engine**: `ai/risk/scoring.py` — `deterministic_v1.0.0`  
> **Contract Boundary**: `ai/risk/contract.py` — `s2-risk-contract/v1.0`  
> **Golden Cases**: `ai/risk/golden_examples_v1.json` (10 approved profiles)  
> **Test Date**: 2026-10-12

---

## 1. Golden Case Deterministic Scoring (12 Profiles)

| ID | Profile | Input Weights | Expected W | Expected C | Expected Composite | Expected Category | Status |
|----|---------|---------------|------------|------------|-------------------|------------------|--------|
| GC-01 | Extreme Conservative | [1,1,1,1,1,1,1,1,1,1] | 0.0 | 0.0 | 0.0 | Conservative | ✅ PASS |
| GC-02 | Extreme Aggressive | [5,5,5,5,5,5,5,5,5,5] | 100.0 | 100.0 | 100.0 | Aggressive | ✅ PASS |
| GC-03 | Balanced Moderate | [3,3,3,3,3,3,3,3,3,3] | 50.0 | 50.0 | 50.0 | Moderate | ✅ PASS |
| GC-04 | High W / Low C | [5,5,5,5,5,1,1,1,1,1] | 100.0 | 0.0 | 50.0 | Moderate | ✅ PASS |
| GC-05 | Low W / High C | [1,1,1,1,1,5,5,5,5,5] | 0.0 | 100.0 | 50.0 | Moderate | ✅ PASS |
| GC-06 | Steady Low-Risk | [2,2,2,2,2,2,2,2,2,2] | 25.0 | 25.0 | 25.0 | Conservative | ✅ PASS |
| GC-07 | Conservative Upper Bound | [3,2,2,2,2,3,3,2,2,2] | 30.0 | 35.0 | 32.5 | Conservative | ✅ PASS |
| GC-08 | Moderate Lower Bound | [3,3,2,2,2,3,3,2,2,2] | 35.0 | 35.0 | 35.0 | Moderate | ✅ PASS |
| GC-09 | Mid Moderate | [4,4,3,3,3,4,4,3,3,3] | 60.0 | 60.0 | 60.0 | Moderate | ✅ PASS |
| GC-10 | Moderate Upper Bound | [4,4,4,3,3,4,4,4,3,3] | 65.0 | 65.0 | 65.0 | Moderate | ✅ PASS |
| GC-11 | Aggressive Lower Bound | [4,4,4,4,3,4,4,4,3,3] | 70.0 | 65.0 | 67.5 | Aggressive | ✅ PASS |
| GC-12 | High Growth Aggressive | [5,5,5,4,4,5,5,5,4,4] | 90.0 | 90.0 | 90.0 | Aggressive | ✅ PASS |

---

## 2. Category Boundary Transition Points

| ID | Composite Score | Expected Category | Expected Code | Status |
|----|----------------|------------------|---------------|--------|
| BT-01 | 0.00 | Conservative | CONSERVATIVE | ✅ PASS |
| BT-02 | 33.99 | Conservative | CONSERVATIVE | ✅ PASS |
| BT-03 | 33.999 | Conservative | CONSERVATIVE | ✅ PASS |
| BT-04 | 34.00 | Moderate | MODERATE | ✅ PASS |
| BT-05 | 34.001 | Moderate | MODERATE | ✅ PASS |
| BT-06 | 50.00 | Moderate | MODERATE | ✅ PASS |
| BT-07 | 66.99 | Moderate | MODERATE | ✅ PASS |
| BT-08 | 66.999 | Moderate | MODERATE | ✅ PASS |
| BT-09 | 67.00 | Aggressive | AGGRESSIVE | ✅ PASS |
| BT-10 | 67.001 | Aggressive | AGGRESSIVE | ✅ PASS |
| BT-11 | 100.00 | Aggressive | AGGRESSIVE | ✅ PASS |

---

## 3. Determinism and Reproducibility

| ID | Scenario | Expected Behavior | Runs | Status |
|----|----------|-------------------|------|--------|
| DR-01 | Full response determinism (fixed timestamp) | Identical inputs → identical JSON output across 100 runs | 100 | ✅ PASS |
| DR-02 | Score consistency (1,000 runs) | Same W/C/Composite/Category/Explanation across 1,000 runs | 1000 | ✅ PASS |
| DR-03 | Timestamp replay | Fixed `calculated_at` → bitwise-identical payload | 100 | ✅ PASS |
| DR-04 | Golden examples file parity | All 10 golden examples validate against scoring engine | 10 | ✅ PASS |

---

## 4. Error and Invalid Input Handling

| ID | Scenario | Expected Behavior | Status |
|----|----------|-------------------|--------|
| ERR-01 | Missing required question (9 of 10) | `ValueError: Missing required questions: ['C5']` | ✅ PASS |
| ERR-02 | Duplicate answer for same question | `ValueError: Duplicate answer submitted for question: 'W1'` | ✅ PASS |
| ERR-03 | Invalid answer code (W1_Z) | `ValueError: Invalid answer_code: 'W1_Z'` | ✅ PASS |
| ERR-04 | Mismatched answer code (C1_A for W1) | `ValueError: Answer code 'C1_A' does not belong to question 'W1'` | ✅ PASS |
| ERR-05 | Invalid questionnaire ID | `ValueError: Invalid questionnaire_id` | ✅ PASS |
| ERR-06 | Empty answers list | `ValidationError: answers list cannot be empty` | ✅ PASS |
| ERR-07 | SQL injection in question_id | `ValidationError: Invalid question_id format` | ✅ PASS |
| ERR-08 | SQL injection in answer_code | `ValidationError: Invalid answer_code format` | ✅ PASS |

---

## 5. Contract Boundary Validation (`contract.py`)

| ID | Scenario | Expected Behavior | Status |
|----|----------|-------------------|--------|
| CB-01 | Valid complete payload | Returns full result with `contract_version: s2-risk-contract/v1.0` | ✅ PASS |
| CB-02 | Malformed payload (missing keys) | `RiskContractError: MALFORMED_ANSWER` | ✅ PASS |
| CB-03 | Wrong questionnaire version | `RiskContractError: UNSUPPORTED_QUESTIONNAIRE_VERSION` | ✅ PASS |
| CB-04 | Duplicate question in contract | `RiskContractError: DUPLICATE_QUESTION_ANSWER` | ✅ PASS |
| CB-05 | Unknown question ID | `RiskContractError: UNKNOWN_QUESTION_ID` | ✅ PASS |
| CB-06 | Missing required question | `RiskContractError: MISSING_REQUIRED_QUESTION` | ✅ PASS |
| CB-07 | Invalid answer code | `RiskContractError: INVALID_ANSWER_CODE` | ✅ PASS |
| CB-08 | Answer for wrong question | `RiskContractError: ANSWER_NOT_PERMITTED_FOR_QUESTION` | ✅ PASS |
| CB-09 | Educational explanation output | Contains limitation message without advice | ✅ PASS |
| CB-10 | Tension detection (W≠C bands) | `informational_tension` present when W and C in different bands | ✅ PASS |

---

## 6. Explanation Engine Safety

| ID | Scenario | Expected Behavior | Status |
|----|----------|-------------------|--------|
| EX-01 | Zero numerical drift (5 profiles) | Explanation never alters pre-calculated scores | ✅ PASS |
| EX-02 | Influencing factors extraction | W1 and C3 drivers correctly cited | ✅ PASS |
| EX-03 | Regulatory disclaimers present | ≥3 disclaimers, includes "educational assessment" | ✅ PASS |
| EX-04 | Malformed LLM JSON fallback | Graceful fallback to deterministic explanation | ✅ PASS |
| EX-05 | Prohibited guarantee phrase filter | "guaranteed return" triggers fallback | ✅ PASS |
| EX-06 | Valid LLM response validation | Conforming JSON accepted with correct model version | ✅ PASS |
| EX-07 | Boundary transition explanations | Correct category name in summary at boundary points | ✅ PASS |
| EX-08 | Golden examples file completeness | 10 valid examples with assessment and explanation | ✅ PASS |
| EX-09 | Prompt injection resistance | Invalid characters in question/answer codes rejected | ✅ PASS |
| EX-10 | Timestamp replay determinism | Fixed timestamp → bitwise-identical explanation | ✅ PASS |

---

## 7. Non-LLM Explanation Structure

| ID | Scenario | Expected Behavior | Status |
|----|----------|-------------------|--------|
| NL-01 | Explanation field completeness | All fields (summary, willingness, capacity, alignment) present and >20 chars | ✅ PASS |
| NL-02 | Fallback flag | `is_fallback: true` for deterministic explanations | ✅ PASS |
| NL-03 | Model version stamp | `deterministic_v1.0.0` in result | ✅ PASS |
| NL-04 | Schema version stamp | `v1.0.0` in result | ✅ PASS |
| NL-05 | Alignment tension (W:Aggressive, C:Conservative) | "capacity is conservative" in alignment note | ✅ PASS |
| NL-06 | Alignment tension (W:Conservative, C:Aggressive) | "psychological preference is conservative" in alignment note | ✅ PASS |

---

## Summary

| Category | Total | Passed | Failed | Deferred |
|----------|-------|--------|--------|----------|
| Golden Case Scoring | 12 | 12 | 0 | 0 |
| Boundary Transitions | 11 | 11 | 0 | 0 |
| Determinism/Reproducibility | 4 | 4 | 0 | 0 |
| Error/Invalid Input | 8 | 8 | 0 | 0 |
| Contract Boundary | 10 | 10 | 0 | 0 |
| Explanation Safety | 10 | 10 | 0 | 0 |
| Non-LLM Explanation | 6 | 6 | 0 | 0 |
| **TOTAL** | **61** | **61** | **0** | **0** |

---

*Matrix completed by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*  
*Recovery base: release/2026-W40*
