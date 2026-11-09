# S2-QLT-01 — Deterministic-Risk Evaluation and Regression Evidence

## What This Is

This folder contains the **quality evaluation evidence package** for the Sprint 2 deterministic risk scoring and explanation feature in the FinEx platform. It proves that the risk assessment engine — from questionnaire input through composite scoring, category mapping, boundary transitions, and safe educational explanations — produces **100% deterministic, reproducible results** on every run.

> **Recovery Context**: This evidence is produced under the W40 recovery (`release/2026-W40`). The historical `release/2026-W36` tree is quarantined and must not be reused or promoted. PR [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) (commit `27ade62`) is merged with corrected exact-head green CI.

## In Simple Terms

Before the risk scoring feature can be promoted in any release, we need to:
1. **Prove determinism** — identical inputs always produce the exact same scores, categories, and explanations
2. **Test every boundary** — Conservative/Moderate at 34.0, Moderate/Aggressive at 67.0
3. **Verify the contract** — API/client shapes match the approved S2 risk contract (#146)
4. **Check safety** — no personalized financial advice, educational-only language enforced
5. **Document everything** — command transcripts, pass/fail summaries, and UAT handoff checklist

## What's Inside

| File | Purpose |
|------|---------|
| `README.md` | This overview document |
| `acceptance_matrix.md` | 58-scenario test matrix covering golden cases, boundaries, errors, and safety |
| `contract_verification.md` | Proof of alignment with S2 risk contract (#146) and `contract.py` boundary |
| `regression_tests.md` | Repeatable regression suite with 100% passing results |
| `accessibility_audit.md` | Educational language, screen reader, and compliance checks |
| `safety_boundary_evidence.md` | Proof that educational-only language is enforced and no financial advice is given |
| `evidence_catalog.md` | Catalog of all attached evidence files, JSON dumps, and test logs |
| `uat_walkthrough.md` | Step-by-step guide to reproduce the evaluation harness locally |
| `uat_checklist.md` | Anand's UAT checklist and go/no-go decision field |
| `known_limitations.md` | Scope exclusions, known constraints, and deferred items |
| `rollback_plan.md` | Safe revert procedures for the risk evaluation feature |
| `independent_review.md` | P5 (Nayan + Pranjal) completed review record |
| `release_metadata.md` | Exact versions under test, branch lineage, and execution output |
| `tests/` | Automated evaluation harness test scripts |
| `fixtures/` | Controlled golden-case fixtures and test data |

## Key Details

- **Sprint**: Sprint 2 — Gated Deterministic Risk
- **Issue**: [#144 — S2-QLT-01](https://github.com/IgnAite-Showcase/Finex/issues/144)
- **Feature Branch**: `feature/144-s2-risk-evidence`
- **Base**: `release/2026-W40` (W40 recovery tree)
- **PR Target**: `release/2026-W40`
- **Evidence PR**: [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) — commit `27ade62`
- **Pair**: P6 — Mrugank Kakade (Driver) + Payal Mude (Navigator)
- **Reviewer**: P5 — Nayan Satpute + Pranjal Ballewar
- **UAT Owner**: Anand
- **Master Handbook**: [v9.1](https://github.com/IgnAite-Showcase/Finex/blob/docs/v9.1-master-handbook/docs/governance/FinEx_Master_Product_Design_Delivery_Handbook_v9.1.pdf), §§7, 10, 12–14, 16, 20, 24

## Scope Boundary

This evidence covers **only** the deterministic risk scoring, explanation, and contract boundary. It does **NOT** include:
- Model training or AI advice generation
- Unapproved external datasets
- Production monitoring services or automatic deployment promotion
- Real authentication or OAuth
- Cloud deployment or live environment testing
- Real user data or PII
- Paid tooling integrations
- Issue closure, reassignment, or protection changes

## Dependencies

| Dependency | Issue | Status | Notes |
|-----------|-------|--------|-------|
| S1-UAT-01 | #145 | ✅ Accepted | Sprint 1 consent and profile onboarding pilot |
| S1-RSK-00 | #146 | ✅ Approved | S2 risk contract and golden cases |
| S2-RSK-01 | #143 | ✅ Completed | Versioned deterministic risk scoring and explanation |
| PR #180 | — | ✅ Merged | Deterministic S2 evaluation and safe snapshot gate |

## How to Use

1. Read `uat_walkthrough.md` for the step-by-step reproduction guide
2. Review `acceptance_matrix.md` to understand all 58 tested scenarios
3. Run the automated suite locally to verify:
   ```
   cd <repo-root>
   $env:PYTHONPATH="."; python -m pytest S2-QLT-01/tests/ ai/risk/test_scoring.py ai/risk/test_explanation.py -v -o addopts=""
   ```
4. Inspect `independent_review.md` and `uat_checklist.md` for sign-off records
5. Check `safety_boundary_evidence.md` for educational language proof
