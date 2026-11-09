# S2-QLT-01 — UAT Walkthrough

## Purpose

Step-by-step guide to reproduce the Sprint 2 deterministic risk evaluation harness from a clean local checkout. No cloud services, Docker, or external dependencies are required.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | ≥ 3.11 (tested on 3.14) |
| Git | Any recent version |
| Repository | `https://github.com/IgnAite-Showcase/Finex.git` |
| Branch | `feature/144-s2-risk-evidence` (or `release/2026-W40` integrated tree) |
| Dependencies | `pydantic` (installed via pip) |

---

## Step 1: Clone and Checkout

```powershell
# Clone the repository
git clone https://github.com/IgnAite-Showcase/Finex.git
cd Finex

# Checkout the W40 recovery tree
git checkout release/2026-W40
```

---

## Step 2: Install Dependencies

```powershell
# Create virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install required packages
pip install pydantic pytest
```

---

## Step 3: Verify Questionnaire Configuration

```powershell
# Confirm the canonical questionnaire file exists
Test-Path backend/data/questionnaire/risk_questionnaire_v1.json
# Expected: True
```

---

## Step 4: Run the Scoring Engine Test Suite

```powershell
$env:PYTHONPATH = "."
python -m pytest ai/risk/test_scoring.py -v -o addopts=""
```

### Expected Output

```
ai/risk/test_scoring.py::test_12_profiles_strictly_distinct PASSED
ai/risk/test_scoring.py::test_profile_01_extreme_conservative PASSED
ai/risk/test_scoring.py::test_profile_02_extreme_aggressive PASSED
ai/risk/test_scoring.py::test_profile_03_balanced_moderate PASSED
ai/risk/test_scoring.py::test_profile_04_high_willingness_low_capacity PASSED
ai/risk/test_scoring.py::test_profile_05_low_willingness_high_capacity PASSED
ai/risk/test_scoring.py::test_profile_06_steady_conservative PASSED
ai/risk/test_scoring.py::test_profile_07_conservative_upper_boundary PASSED
ai/risk/test_scoring.py::test_profile_08_moderate_lower_boundary PASSED
ai/risk/test_scoring.py::test_profile_09_mid_moderate PASSED
ai/risk/test_scoring.py::test_profile_10_moderate_upper_boundary PASSED
ai/risk/test_scoring.py::test_profile_11_aggressive_lower_boundary PASSED
ai/risk/test_scoring.py::test_profile_12_high_growth_aggressive PASSED
ai/risk/test_scoring.py::test_direct_boundary_transition_points[...] PASSED (10 params)
ai/risk/test_scoring.py::test_boundary_explanation_generation PASSED
ai/risk/test_scoring.py::test_full_response_determinism_with_fixed_timestamp PASSED
ai/risk/test_scoring.py::test_determinism_consistency_1000_runs PASSED
ai/risk/test_scoring.py::test_missing_question_raises_error PASSED
ai/risk/test_scoring.py::test_duplicate_question_raises_error PASSED
ai/risk/test_scoring.py::test_invalid_answer_code_raises_error PASSED
ai/risk/test_scoring.py::test_mismatched_answer_code_raises_error PASSED
ai/risk/test_scoring.py::test_invalid_questionnaire_id_raises_error PASSED
ai/risk/test_scoring.py::test_non_llm_explanation_structure PASSED

23 passed
```

---

## Step 5: Run the Explanation Engine Test Suite

```powershell
$env:PYTHONPATH = "."
python -m pytest ai/risk/test_explanation.py -v -o addopts=""
```

### Expected Output

```
ai/risk/test_explanation.py::test_prompt_template_formatting PASSED
ai/risk/test_explanation.py::test_zero_numerical_drift_across_all_categories PASSED
ai/risk/test_explanation.py::test_influencing_factors_extraction PASSED
ai/risk/test_explanation.py::test_regulatory_disclaimers_present PASSED
ai/risk/test_explanation.py::test_fallback_on_malformed_llm_json PASSED
ai/risk/test_explanation.py::test_fallback_on_prohibited_guarantee_phrase PASSED
ai/risk/test_explanation.py::test_successful_llm_response_validation PASSED
ai/risk/test_explanation.py::test_boundary_transition_profiles PASSED
ai/risk/test_explanation.py::test_golden_examples_file_completeness PASSED
ai/risk/test_explanation.py::test_security_prompt_injection_resistance PASSED
ai/risk/test_explanation.py::test_deterministic_timestamp_replay PASSED

11 passed
```

---

## Step 6: Run the S2-QLT-01 Evaluation Harness

```powershell
$env:PYTHONPATH = "."
python -m pytest S2-QLT-01/tests/ -v -o addopts=""
```

### Expected Output

```
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_contract_boundary_valid_payload PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_contract_boundary_all_error_codes PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_contract_educational_explanation PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_contract_tension_detection PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_golden_case_matrix_determinism PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_safety_no_financial_advice PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_version_disclosure PASSED
S2-QLT-01/tests/test_s2_evaluation_harness.py::test_educational_language_check PASSED

8 passed
```

---

## Step 7: Run All Suites Together

```powershell
$env:PYTHONPATH = "."
python -m pytest S2-QLT-01/tests/ ai/risk/test_scoring.py ai/risk/test_explanation.py -v -o addopts=""
```

### Expected: 42 passed, 0 failed

---

## Step 8: Verify Golden Examples

```powershell
# Quick sanity check
python -c "
import json
from pathlib import Path
data = json.loads(Path('ai/risk/golden_examples_v1.json').read_text())
print(f'Schema: {data[\"schema_version\"]}')
print(f'Total examples: {data[\"total_examples\"]}')
print(f'Loaded: {len(data[\"examples\"])} examples')
for ex in data['examples']:
    print(f'  {ex[\"example_id\"]}: {ex[\"deterministic_assessment\"][\"risk_category\"]}')
"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError: ai.risk` | `PYTHONPATH` not set | `$env:PYTHONPATH = "."` |
| `FileNotFoundError: questionnaire config` | Wrong working directory | `cd` to repo root |
| `ImportError: pydantic` | Missing dependency | `pip install pydantic` |
| Tests fail with import errors | Virtual environment not activated | `.\.venv\Scripts\Activate.ps1` |

---

*Walkthrough authored by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*
