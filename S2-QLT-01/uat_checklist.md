# S2-QLT-01 — UAT Acceptance Checklist

## Purpose

This is Anand's (UAT owner) acceptance checklist for the Sprint 2 deterministic risk evaluation and regression evidence. Each item is checked and the decision recorded for the W40 recovery tree.

---

## Release Details

| Property | Value |
|----------|-------|
| Feature | Sprint 2 — Deterministic Risk Evaluation Quality Evidence |
| Issue | [#144 — S2-QLT-01](https://github.com/IgnAite-Showcase/Finex/issues/144) |
| Recovery Base | `release/2026-W40` (W36 quarantined) |
| Evidence PR | [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) — commit `27ade62` |
| Feature Branch | `feature/144-s2-risk-evidence` |
| PR Target | `release/2026-W40` |
| Test Date | 2026-10-12 |
| Prepared By | P6 — Mrugank Kakade + Payal Mude |
| Reviewed By | P5 — Nayan Satpute + Pranjal Ballewar |

---

## Acceptance Checklist

### Deterministic Scoring

- [x] All 12 golden case profiles produce exact expected scores
- [x] Identical inputs produce identical outputs across 1,000 runs
- [x] Fixed timestamps produce bitwise-identical JSON payloads
- [x] No LLM is used for numeric scoring

### Category Boundary Transitions

- [x] Score 33.99 → Conservative (verified)
- [x] Score 34.00 → Moderate (verified)
- [x] Score 66.99 → Moderate (verified)
- [x] Score 67.00 → Aggressive (verified)
- [x] All 11 boundary transition points produce correct categories

### Error and Invalid Input

- [x] Missing required question raises descriptive error
- [x] Duplicate answers raise descriptive error
- [x] Invalid answer codes raise descriptive error
- [x] Mismatched answer/question pairs raise descriptive error
- [x] Invalid questionnaire ID raises descriptive error
- [x] Empty answers list raises validation error
- [x] Prompt injection attempts are blocked by Pydantic validators

### Contract Boundary (contract.py)

- [x] Valid payload returns full result with `s2-risk-contract/v1.0`
- [x] All 7 error codes trigger correctly
- [x] Educational explanation output includes limitation text
- [x] Tension detection works when W and C are in different bands
- [x] Contract version, scoring version, and schema version are all disclosed

### Explanation Engine Safety

- [x] Explanations never alter pre-calculated scores (zero numerical drift)
- [x] Influencing factors correctly cite questionnaire answers
- [x] ≥3 regulatory disclaimers present on every explanation
- [x] Malformed LLM JSON triggers deterministic fallback
- [x] Prohibited guarantee phrases trigger safety fallback
- [x] Valid LLM responses are accepted when conforming to schema
- [x] Golden examples file contains 10 valid examples

### Safety and Educational Boundary

- [x] No language implies real financial advice or brokerage action
- [x] No real PII or production credentials in test evidence
- [x] Educational-use wording is present in all outputs
- [x] "Educational assessment" appears in standard disclaimers
- [x] No production-scale claims in any output text
- [x] Timestamp and version disclosures present on every result

### Evidence Package

- [x] All 13 documentation files present
- [x] 42 automated tests pass (23 scoring + 11 explanation + 8 harness)
- [x] Golden case matrix and contract test payloads in fixtures/
- [x] Evidence PR [#180](https://github.com/IgnAite-Showcase/Finex/pull/180) linked
- [x] Independent review by P5 documented
- [x] Known limitations documented
- [x] Rollback plan documented

### Reproducibility

- [x] Walkthrough can be followed from clean local checkout
- [x] No secrets or production credentials required
- [x] No cloud dependency — runs fully local
- [x] Fixture/test data only — no real PII
- [x] Documented commands execute on Windows (PowerShell)

---

## UAT Decision

**Decision**: **PENDING ANAND REVIEW**

> This evidence package is complete and ready for Anand's review. The go/no-go decision field below is left blank for Anand to fill.

| Field | Value |
|-------|-------|
| **Go / No-Go** | `________________` |
| **Conditions** | (if any) |
| **Waived Items** | (if any) |
| **Notes** | |

---

## Sign-Off

| Role | Name | Decision | Date | Status |
|------|------|----------|------|--------|
| UAT Owner | Anand | PENDING | — | ⏳ Pending Review |
| Driver (P6) | Mrugank Kakade | SUBMITTED | 2026-10-12 | ✅ Submitted |
| Navigator (P6) | Payal Mude | SUBMITTED | 2026-10-12 | ✅ Submitted |
| Reviewer (P5) | Nayan Satpute | PENDING REVIEW | — | ⏳ Pending |
| Reviewer (P5) | Pranjal Ballewar | PENDING REVIEW | — | ⏳ Pending |

---

*Checklist prepared for review. Release gate: `release/2026-W40`.*  
*Date: 2026-10-12*
