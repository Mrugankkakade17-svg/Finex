# S2-QLT-01 — Known Limitations

## Purpose

This document records the known limitations, scope exclusions, and deferred items for the Sprint 2 deterministic risk evaluation evidence package.

---

## 1. Scope Exclusions

These items are **explicitly excluded** from this evaluation per the issue description (#144):

| # | Exclusion | Reason |
|---|-----------|--------|
| 1 | Model training | Out of scope for deterministic scoring |
| 2 | AI advice generation | Deterministic engine only; no LLM-generated advice in scoring |
| 3 | Unapproved external datasets | Only the approved `risk_questionnaire_v1.json` is used |
| 4 | Production monitoring services | Educational local pilot only |
| 5 | Automatic deployment promotion | Manual promotion gate via Anand |
| 6 | Cloud deployment | All tests run locally |
| 7 | Issue closure or reassignment | No issue state changes |
| 8 | Protection rule changes | No branch protection modifications |
| 9 | Dev/UAT/prod/main promotion | Evidence targets `release/2026-W40` only |

---

## 2. Known Constraints

| # | Constraint | Impact | Mitigation |
|---|-----------|--------|------------|
| 1 | LLM explanation path not tested in production | Only deterministic fallback is verified end-to-end | Fallback guarantees safe output regardless of LLM availability |
| 2 | No real user data in test fixtures | All profiles are synthetic | Sufficient for educational pilot scope |
| 3 | No end-to-end API integration test | Scoring engine tested in isolation | Contract boundary (`contract.py`) validates API shapes |
| 4 | W36 release quarantined | Cannot promote to original W36 target | W40 recovery tree is the authorized target |
| 5 | No Docker-based reproducibility | Tests verified on Windows local only | Documented commands and PYTHONPATH setup provided |
| 6 | Questionnaire v1 only | v2+ questionnaires are not supported | Out of scope per approved contract #146 |

---

## 3. Deferred Items

| # | Item | Deferred To | Notes |
|---|------|-------------|-------|
| 1 | Flutter risk journey UI tests | S2-FLT parity story | Backend scoring is Flutter-agnostic |
| 2 | React risk journey UI tests | S2-WEB parity story | Backend scoring is UI-agnostic |
| 3 | End-to-end API harness (FastAPI + database) | S2-UAT-01 (#164) | Requires full API stack |
| 4 | Performance benchmarks | Future sprint | Current tests verify correctness, not latency |
| 5 | Multi-language support | Future sprint | All outputs in English only |

---

## 4. W36 Quarantine Note

The original release target (`release/2026-W36`) is **quarantined** and must not be reused or promoted. All evidence in this package is based on the W40 recovery tree (`release/2026-W40`). The historical W36 branch instructions are superseded for this authorized recovery.

---

## 5. Recovery Authority

Per the issue description:
- **Anand** delegated development, validation, and technical review to Codex through Sprint 2
- No independent human approval is claimed beyond Anand's delegation
- GitHub assignees and original stable-pair ownership remain unchanged
- This is a synthetic local educational pilot — not a production deployment

---

*Known limitations documented by: P6 — Mrugank Kakade + Payal Mude*  
*Date: 2026-10-12*
