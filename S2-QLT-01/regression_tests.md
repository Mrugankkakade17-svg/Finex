# S2-QLT-01 — Regression Tests

## Purpose

This document records the automated regression suite that gates promotion of the Sprint 2 deterministic risk feature. All tests must pass for `release/2026-W40` promotion; failures block until resolved or explicitly waived by Anand.

---

## Test Execution Summary

| Property | Value |
|----------|-------|
| Command | `$env:PYTHONPATH="."; python -m pytest S2-QLT-01/tests/ ai/risk/test_scoring.py ai/risk/test_explanation.py -v -o addopts=""` |
| Environment | Python 3.14, Windows local dev |
| Recovery Base | `release/2026-W40` |
| Evidence PR | [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) — commit `27ade62` |
| Test Date | 2026-10-12 |

---

## Test Suite Inventory

### 1. Scoring Engine Tests (`ai/risk/test_scoring.py`)

| Test | Description | Status |
|------|-------------|--------|
| `test_12_profiles_strictly_distinct` | All 12 profile inputs have distinct vectors | ✅ PASS |
| `test_profile_01_extreme_conservative` | All-1s → W=0.0, C=0.0, Composite=0.0, Conservative | ✅ PASS |
| `test_profile_02_extreme_aggressive` | All-5s → W=100, C=100, Composite=100, Aggressive | ✅ PASS |
| `test_profile_03_balanced_moderate` | All-3s → W=50, C=50, Composite=50, Moderate | ✅ PASS |
| `test_profile_04_high_willingness_low_capacity` | Max W / Min C → 50.0, alignment tension | ✅ PASS |
| `test_profile_05_low_willingness_high_capacity` | Min W / Max C → 50.0, alignment tension | ✅ PASS |
| `test_profile_06_steady_conservative` | All-2s → 25.0, Conservative | ✅ PASS |
| `test_profile_07_conservative_upper_boundary` | Composite=32.5, Conservative | ✅ PASS |
| `test_profile_08_moderate_lower_boundary` | Composite=35.0, Moderate | ✅ PASS |
| `test_profile_09_mid_moderate` | Composite=60.0, Moderate | ✅ PASS |
| `test_profile_10_moderate_upper_boundary` | Composite=65.0, Moderate | ✅ PASS |
| `test_profile_11_aggressive_lower_boundary` | Composite=67.5, Aggressive | ✅ PASS |
| `test_profile_12_high_growth_aggressive` | Composite=90.0, Aggressive | ✅ PASS |
| `test_direct_boundary_transition_points` | 10 parametrized boundary values (33.99→34.00→66.99→67.00) | ✅ PASS |
| `test_boundary_explanation_generation` | Explanation generated correctly at all boundary points | ✅ PASS |
| `test_full_response_determinism_with_fixed_timestamp` | 100 runs → identical JSON | ✅ PASS |
| `test_determinism_consistency_1000_runs` | 1,000 runs → identical scores/categories | ✅ PASS |
| `test_missing_question_raises_error` | 9 of 10 answers → ValueError | ✅ PASS |
| `test_duplicate_question_raises_error` | Duplicate W1 → ValueError | ✅ PASS |
| `test_invalid_answer_code_raises_error` | W1_Z → ValueError | ✅ PASS |
| `test_mismatched_answer_code_raises_error` | C1_A for W1 → ValueError | ✅ PASS |
| `test_invalid_questionnaire_id_raises_error` | Unknown questionnaire → ValueError | ✅ PASS |
| `test_non_llm_explanation_structure` | All explanation fields present and valid | ✅ PASS |

**Subtotal: 23 tests, 23 passed, 0 failed**

### 2. Explanation Engine Tests (`ai/risk/test_explanation.py`)

| Test | Description | Status |
|------|-------------|--------|
| `test_prompt_template_formatting` | Prompt embeds correct scores and answer references | ✅ PASS |
| `test_zero_numerical_drift_across_all_categories` | 5 profiles: explanation never alters scores | ✅ PASS |
| `test_influencing_factors_extraction` | W1 and C3 drivers correctly extracted | ✅ PASS |
| `test_regulatory_disclaimers_present` | ≥3 disclaimers with "educational assessment" | ✅ PASS |
| `test_fallback_on_malformed_llm_json` | Broken JSON → deterministic fallback | ✅ PASS |
| `test_fallback_on_prohibited_guarantee_phrase` | "guaranteed return" → safety fallback | ✅ PASS |
| `test_successful_llm_response_validation` | Valid JSON accepted with correct version | ✅ PASS |
| `test_boundary_transition_profiles` | 4 boundary profiles → correct categories | ✅ PASS |
| `test_golden_examples_file_completeness` | 10 golden examples validate | ✅ PASS |
| `test_security_prompt_injection_resistance` | SQL injection in codes → ValidationError | ✅ PASS |
| `test_deterministic_timestamp_replay` | Fixed timestamp → bitwise-identical payload | ✅ PASS |

**Subtotal: 11 tests, 11 passed, 0 failed**

### 3. S2-QLT-01 Evaluation Harness Tests (`S2-QLT-01/tests/`)

| Test | Description | Status |
|------|-------------|--------|
| `test_contract_boundary_valid_payload` | Full valid payload through `evaluate_risk_contract()` | ✅ PASS |
| `test_contract_boundary_all_error_codes` | All 7 error codes triggered and verified | ✅ PASS |
| `test_contract_educational_explanation` | Educational explanation contains limitation text | ✅ PASS |
| `test_contract_tension_detection` | Tension detected when W and C in different bands | ✅ PASS |
| `test_golden_case_matrix_determinism` | All 12 golden cases produce exact expected scores | ✅ PASS |
| `test_safety_no_financial_advice` | No prohibited phrases in any explanation output | ✅ PASS |
| `test_version_disclosure` | Engine version, schema version, contract version all present | ✅ PASS |
| `test_educational_language_check` | Educational disclaimer present in all outputs | ✅ PASS |

**Subtotal: 8 tests, 8 passed, 0 failed**

---

## Grand Total

| Suite | Tests | Passed | Failed |
|-------|-------|--------|--------|
| Scoring Engine | 23 | 23 | 0 |
| Explanation Engine | 11 | 11 | 0 |
| S2-QLT-01 Harness | 8 | 8 | 0 |
| **TOTAL** | **42** | **42** | **0** |

---

## Regression Gate

**All 42 tests pass.** Regressions in any of these tests block promotion from `release/2026-W40` until resolved or explicitly waived by Anand per Handbook v9.1 §16.

---

*Regression suite executed by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*  
*Recovery base: release/2026-W40*
