# S2-QLT-01 — Release Metadata

## Purpose

Exact versions, branch lineage, and execution environment for the Sprint 2 deterministic risk evaluation evidence.

---

## Version Matrix

| Component | Version | Source |
|-----------|---------|--------|
| Scoring Engine | `deterministic_v1.0.0` | `ai/risk/scoring.py` |
| Explanation Engine | `deterministic_rule_v1.0.0` | `ai/risk/explanation.py` |
| Schema Version | `v1.0.0` | `ai/risk/schemas.py` |
| Contract Version | `s2-risk-contract/v1.0` | `ai/risk/contract.py` |
| Prompt Version | `v1.0.0` | `ai/risk/explanation.py` |
| Questionnaire | `risk_questionnaire_v1` / `v1` | `backend/data/questionnaire/risk_questionnaire_v1.json` |
| Golden Examples | 10 profiles | `ai/risk/golden_examples_v1.json` |
| Evidence Package | `S2-QLT-01` | This directory |

---

## Branch Lineage

```
main
 └── release/2026-W40  (recovery tree; W36 quarantined)
      └── feature/144-s2-risk-evidence  (this PR)
```

| Property | Value |
|----------|-------|
| Recovery Base | `release/2026-W40` |
| Feature Branch | `feature/144-s2-risk-evidence` |
| PR Target | `release/2026-W40` |
| Quarantined | `release/2026-W36` (must not be reused) |

---

## Evidence PR

| Property | Value |
|----------|-------|
| PR | [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) |
| Commit | `27ade62` |
| CI Status | ✅ Green (exact-head) |
| Merge Status | ✅ Merged |

---

## Execution Environment

| Property | Value |
|----------|-------|
| OS | Windows 11 |
| Python | 3.14.x |
| Shell | PowerShell 7.x |
| Key Dependencies | `pydantic ≥ 2.0`, `pytest ≥ 8.0` |
| PYTHONPATH | `.` (repository root) |
| Cloud Services | None (fully local) |
| Docker | Not required |

---

## Test Execution Output

### Command

```powershell
$env:PYTHONPATH = "."
python -m pytest S2-QLT-01/tests/ ai/risk/test_scoring.py ai/risk/test_explanation.py -v -o addopts=""
```

### Result

```
42 passed, 0 failed, 0 errors, 0 warnings
```

| Suite | Tests | Passed | Failed |
|-------|-------|--------|--------|
| `ai/risk/test_scoring.py` | 23 | 23 | 0 |
| `ai/risk/test_explanation.py` | 11 | 11 | 0 |
| `S2-QLT-01/tests/test_s2_evaluation_harness.py` | 8 | 8 | 0 |
| **Total** | **42** | **42** | **0** |

---

## Dependencies

| Dependency | Issue | Status |
|-----------|-------|--------|
| S1-UAT-01 | #145 | ✅ Accepted |
| S1-RSK-00 (Risk Contract) | #146 | ✅ Approved |
| S2-RSK-01 (Risk Implementation) | #143 | ✅ Completed |
| PR #180 (S2 Evaluation Gate) | — | ✅ Merged |

---

## Handbook Reference

| Section | Topic |
|---------|-------|
| §7 | Sprint Planning and Issue Structure |
| §10 | Quality Gates |
| §12 | Evidence Requirements |
| §13 | UAT Acceptance |
| §14 | Recovery Procedures |
| §16 | Regression Testing |
| §20 | Educational Pilot Boundaries |
| §24 | Version Control and Branching |

Master Handbook: [v9.1](https://github.com/IgnAite-Showcase/Finex/blob/docs/v9.1-master-handbook/docs/governance/FinEx_Master_Product_Design_Delivery_Handbook_v9.1.pdf)

---

*Release metadata compiled by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*
