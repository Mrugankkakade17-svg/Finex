# S1-RSK-00 — Sprint 2 Deterministic Risk Contract

| Item | Details |
|---|---|
| **Issue** | #146 |
| **Branch** | `feature/146-s1-risk-contract` |
| **Base** | `main` @ `2ccdebcb4bfe53ea5294fea5052c75a99d24c14b` |
| **PR target** | `release/2026-W36` |
| **Pair** | **P5 — Nayan Satpute (Driver) + Pranjal Ballewar (Navigator)** |
| **Independent reviewer** | **P6 — Mrugank + Payal** |
| **Status** | **DRAFT — pending P6 review and Anand approval** |
| **Contract version** | `risk_contract_v1.0.0-proposed` |
| **Handbook** | FinEx Master Product, Design, Delivery, and Production Handbook v9.1 |

> **Approval gate:** Nothing in this handoff becomes an authoritative Sprint 2 contract until Anand records acceptance.

---

## Purpose

This handoff defines the **Sprint 2 deterministic risk-scoring contract and golden-case specification** for downstream implementation.

It is a **specification and test-design artifact only**. It does not introduce or modify production scoring logic, API endpoints, UI wiring, LLM/RAG integration, market-data dependencies, or trading functionality.

### What this document establishes

- Versioned questionnaire and assessment contract
- Deterministic input/output structure
- Risk-category vocabulary and proposed scoring rules
- Validation and error behavior
- Educational-only explanation boundaries
- Versioned deterministic golden cases for downstream regression testing
- Explicit approval decisions and deferred defects

---

## Evidence and Decision Status

To keep observed repository behavior separate from proposed Sprint 2 decisions, this handoff uses four labels:

| Label | Meaning |
|---|---|
| **[EXISTING/OBSERVED]** | Behavior verified in the current repository. It is evidence, not automatically a Sprint 2 requirement. |
| **[PROPOSED]** | A proposed contract rule for Sprint 2. It is not binding until Anand approves it. |
| **[APPROVAL REQUIRED]** | A decision that must be explicitly accepted or returned by Anand before downstream implementation. |
| **[FOLLOW-UP DEFECT]** | A known implementation gap identified during the contract work. It remains deferred and is not fixed under #146. |

---

## Scope Boundary

### Included

- Contract and schema definition
- Proposed deterministic scoring rules
- Golden-case specification
- Validation/error contract
- Explanation boundaries
- Approval and governance record

### Excluded

- Production scoring implementation
- New API endpoints
- Frontend implementation
- LLM/RAG integration
- Market-data integration
- Broker or real-money trading functionality
- Personal investment recommendations
- Real personal/financial data
- Cloud deployment changes

### ✅ Handbook version — resolved
Issue #146 requires *"FinEx Master Product, Design, Delivery, and Production Handbook v9.1."* That file has been provided and confirmed: title page reads *"FinEx Master Product, Design, Delivery, and Production Handbook v9.1,"* dated 6 September 2026, stating explicitly *"this version replaces v9 as the single source of truth."* This document is built against v9.1.

v9.1 confirms the sprint/gate structure this contract operates under: its execution map explicitly lists *"#146 risk-contract/golden-case preparation"* as Sprint 1 work, and states *"deterministic risk scoring and its evaluation (#143 and #144) remain Sprint 2 work and start only after the Sprint 1 identity/onboarding gate, the approved questionnaire contract, and versioned fixtures are available."*

### Governance assignment note
The current delivery assignment is **P5 — Nayan Satpute (Driver) + Pranjal Ballewar (Navigator)** for **S1-RSK-00 / #146**, per Anand's latest delivery instruction and the #146 issue. The older v9.1 Project 21 map separately lists #146 as Sprint 1 risk-contract/golden-case preparation and lists the later S2-SPEC-01 specification-freeze story under P2. That is retained as a historical mapping discrepancy for auditability; it does not override the current #146 delivery assignment.

### Process note — release-train model (v9.1 addition)
v9.1 introduces a required `release/<YYYY-WW>` branch between `feature/*` and `dev` (`feature/* → release/<week> → dev → uat → prod → main/tag`), replacing v9's simpler flow. This matches issue #146's stated PR target (`release/2026-W36`). v9.1 also requires every card/PR to name its **handbook version and section references**, plus Driver/Navigator, feature branch, base SHA/tag, and release-train target.

### Backing from the v9.1 handbook (§13, §18 — FR-04/05/06, S2-SPEC-01)
- **[EXISTING/OBSERVED — handbook text] FR-04 (Versioned questionnaire):** *"question/option IDs and version are retained with answers, invalid values are rejected, and prior assessment semantics remain reproducible."*
- **[EXISTING/OBSERVED — handbook text] FR-05 (Deterministic risk score):** *"identical approved inputs/version produce identical results; the result identifies calculation version and assumptions; AI never selects the score."*
- **[EXISTING/OBSERVED — handbook text] FR-06 (Risk explanation):** *"explanation reflects computed metrics and approved wording, not investment advice or invented facts."*
- **[EXISTING/OBSERVED — handbook text] S2-SPEC-01 acceptance criteria:** *"Rules, edge cases, limits, non-goals, and approval points are explicit... Every calculation/provider/AI dependency has a version and safe fallback... Anand accepts the version before implementation."*

These are handbook requirements the contract must satisfy — they are not, by themselves, approval of any specific number in this document.

---

## 1. Questionnaire schema [EXISTING/OBSERVED]

| Field | Value |
|---|---|
| Questionnaire ID | `risk_questionnaire_v1` |
| Version | `v1` |
| Active from | `2026-08-23T21:21:00+05:30` |
| Question count | 10, all required, single-choice |
| Question IDs | `W1–W5` (willingness), `C1–C5` (capacity) |
| Answer options | 50 total (5 per question), scored 1–5 |

Source: `backend/data/questionnaire/risk_questionnaire_v1.json`. **[PROPOSED]** Adopt this as the canonical Sprint 2 questionnaire definition — pending Anand acceptance, per S2-SPEC-01's requirement that Anand accept the version before implementation.

**[FOLLOW-UP DEFECT — not fixed here]** No production seed migration exists; the questionnaire is loaded via `load_risk_questionnaire_v1.ipynb` (a notebook), not a repeatable seed. A stale checkpoint notebook (`load_risk_questionnaire_v1-checkpoint.ipynb`) still contains `DRAFT_PENDING_APPROVAL` state and should not be used as a reference.

---

## 2. Output DTO / category vocabulary

**[EXISTING/OBSERVED] Request:** `RiskAssessmentRequest` — `questionnaire_id`, `version`, optional `user_id`, optional `calculated_at`, list of `{question_id, answer_code}`.

**[EXISTING/OBSERVED] Result:** `RiskAssessmentResult` — willingness score, capacity score, composite score, `risk_category`, `risk_category_code`, per-dimension breakdown, deterministic explanation, `model_version`, `schema_version`, `calculated_at`. Source: `schemas.py:13-107, 109-214`.

**[EXISTING/OBSERVED] Category vocabulary:** `CONSERVATIVE`, `MODERATE`, `AGGRESSIVE`.

**[PROPOSED — APPROVAL REQUIRED] Contract version:** `risk_contract_v1.0.0-proposed`. This is a proposed #146 contract identifier and is not approved until Anand records acceptance.

**[PROPOSED — APPROVAL REQUIRED, see §5A]** Add an explicit `scoring_version` field, distinct from `questionnaire_id`/`version`/`model_version`/`schema_version`, so a future rule change is distinguishable from a questionnaire content change.

---

## 3. Scoring formula

**[EXISTING/OBSERVED]**
```
dimension_score  = ((raw_sum - 5) / (25 - 5)) * 100      # per dimension, range 0-100
composite_score  = willingness_score * 0.5 + capacity_score * 0.5
```

| Parameter | Current value | Source |
|---|---|---|
| Raw range per dimension | 5–25 | `risk_questionnaire_v1.json:167-190` |
| Willingness weight | 0.5 | same |
| Capacity weight | 0.5 | same |
| Conservative | `< 34.0` | same |
| Moderate | `>= 34.0 and < 67.0` | same |
| Aggressive | `>= 67.0` | same |

Dimension/composite scores are rounded to 4 decimals in the canonical engine — see §5A for the rounding decision.

**[PROPOSED — APPROVAL REQUIRED, see §5A]** Ratify these weights and thresholds as the Sprint 2 contract values. They are implemented and tested, but implementation existing is not the same as Anand approval; nothing here is binding until recorded.

---

## 4. Canonical engine decision

**[EXISTING/OBSERVED]** Two backend scoring paths currently exist:

| | Canonical (proposed authority) | Legacy/duplicate |
|---|---|---|
| Files | `scoring.py`, `explanation.py` | `risk_service.py`, `risk_repository.py` |
| Endpoints | `/evaluate`, `/explain`, `/evaluate-and-explain` | `/questions`, `/assessments` |
| Request field | `answer_code` | `answer_id` |
| Persistence | none (pure function) | in-memory dict, non-durable |
| Constants | reads JSON config (partially — see §5B) | hardcoded duplicate (0.5/0.5, 34/67) |
| Version rejection | does not reject unsupported version (see §5B) | explicitly rejects versions other than `v1` |
| Rounding | 4 decimals | 2 decimals |

**[PROPOSED]** Name `scoring.py`/`explanation.py` as the single canonical engine for the Sprint 2 contract. `risk_service.py`/`risk_repository.py` are flagged as a **[FOLLOW-UP DEFECT]** — a duplicate implementation to consolidate in a later story. **No code changes happen under S1-RSK-00.**

**[EXISTING/OBSERVED, out of #146 scope but flagged for visibility]** React (`onboardingService.ts`, always returns `MODERATE`, no backend call) and Flutter (`risk_service.dart`/`risk_question.dart`, 5 questions/4 options, thresholds ≤7/≤13) both implement local, non-canonical, divergent scoring. Neither is touched by S1-RSK-00, but downstream API/frontend-integration stories need to know the frontends are not currently wired to this contract at all.

---

## 5. Open items — separated by type

### 5A. Approval / contract decisions (Anand must choose a value; not bugs)

**A0 — Contract version.** No existing production contract version field is present. **[PROPOSED]** Use `risk_contract_v1.0.0-proposed` for the #146 specification artifact. **[APPROVAL REQUIRED]**

**A1 — `scoring_version` field.** No field currently distinguishes a scoring-rule version from the questionnaire version. **[PROPOSED]** Add `scoring_version` (e.g. `risk_scoring_v1`) to the result contract. **[APPROVAL REQUIRED]**

**A3 — Rounding precision.** Canonical engine rounds to 4 decimals; legacy rounds to 2. This affects every non-round golden-case expected value. **[PROPOSED]** Adopt 4-decimal rounding as the contract standard. **[APPROVAL REQUIRED]**

**A4 — Error-code vocabulary.** Legacy uses specific codes (`EMPTY_RISK_ANSWERS`, `INCOMPLETE_RISK_ANSWERS`, `DUPLICATE_RISK_ANSWER`, `INVALID_QUESTION_ID`, `INVALID_ANSWER_ID`, `INCOMPLETE_RISK_DIMENSIONS`, `INVALID_QUESTIONNAIRE_VERSION`); canonical collapses most rejections into generic `INVALID_RISK_ASSESSMENT_INPUT` / `RISK_SCORING_ERROR`. The golden matrix deliberately states only `"rejected"` + a reason for each validation case, not a code, since choosing the convention is this decision. **[APPROVAL REQUIRED]**

**A5 — Exact weights/thresholds ratification.** Willingness/capacity weights (0.5/0.5) and category thresholds (34/67) are implemented and tested but predate v9.1 governance. **[PROPOSED]** Ratify as-is. **[APPROVAL REQUIRED]**

**A6 — Explanation-factor policy.** Current implementation surfaces W1, W2, C1, C3 as material influencing factors; W3, W4, W5, C2, C4, C5 affect scoring but are not consistently surfaced. This is **[EXISTING IMPLEMENTATION BEHAVIOR]**, not an approved business rule — the repository contains no explicit sign-off that this is the intended factor set. **[PROPOSED contract wording]:** *"Expected explanation must remain deterministic and must reflect the computed dimensions/material influencing inputs according to the approved explanation-factor policy."* The specific W1/W2/C1/C3 selection is **[APPROVAL REQUIRED]**, not assumed correct.

### 5B. Implementation defects / follow-up items (not fixed under #146)

**B1 — Questionnaire version mismatch not rejected.** The canonical engine accepts a declared `version` field but never validates it against the loaded questionnaire's actual version — a caller can declare `version: "v2"` and silently receive a `v1`-computed result labeled `v2`. Encoded as golden case **GC-24**, explicitly marked not-currently-satisfied (see §7). **Downstream:** #143 acceptance and #144 regression.

**B2 — Config-driven category boundaries loaded but ignored.** `RiskScoringEngine._build_indexes()` loads boundaries from JSON into `self.boundaries`, but `scoring.py:105-114` hardcodes `34.0`/`67.0` directly instead of reading them. Currently harmless since the values match, but the config isn't actually authoritative at runtime. **Downstream:** #143 implementation and #144 boundary regression.

**B3 — Duplicate legacy scoring path.** `risk_service.py`/`risk_repository.py` re-implement scoring independently (different request field name, 2-decimal rounding, in-memory-only persistence) rather than delegating to the canonical engine. **Downstream:** #143 authoritative scoring-path cleanup.

**B4 — Malformed-input handling inconsistency.** The canonical path returns a structured Pydantic validation error for malformed types; the legacy path raises a raw `TypeError` for the equivalent case. **Downstream:** #143 validation/error contract and #144 regression.

None of B1–B4 are fixed by this issue. They are documented here so #143's implementation work has a known punch list and doesn't need to re-discover them.

---

## 6. Validation behavior [EXISTING/OBSERVED] — proposed for canonical adoption

Handled by the canonical engine (`scoring.py:184-277`):
- Unknown/unsupported questionnaire ID
- Duplicate answers for the same question
- Missing required questions (incomplete input)
- Unknown question ID or answer code
- Answer code belonging to the wrong question/dimension
- Malformed DTO values (Pydantic-level, `schemas.py:21-43`)

See §5B (B4) for the legacy-path inconsistency on malformed input.

---

## 7. Explanation boundaries

**[EXISTING/OBSERVED]** From `explanation.py` — deterministic, template-based, no LLM required for the authoritative path:
- Identifies material influencing factors (currently W1, W2, C1, C3 — see §5A5, this specific set is not yet approved)
- States questionnaire version (and, pending §5A1, scoring version)
- Mandatory disclaimer: educational decision support, not financial advice
- Optional LLM enrichment is schema-validated and rejects prohibited phrases (guarantees, specific security advice, personalized recommendations), falling back to the deterministic template on any failure

**[FOLLOW-UP DEFECT]** Not currently checked: whether an LLM-enriched explanation's stated factors/category actually match the deterministic assessment. Flagged for a future test; LLM path is excluded from the authoritative Sprint 2 scoring contract regardless.

**[PROPOSED contract requirement]:** explanation factors must be derived only from deterministic assessment inputs and an approved factor-selection rule, not from an unreviewed default in code.

---

## 8. Explicit exclusions (per issue #146)

No production scoring code, API endpoint, UI wiring, LLM/RAG, market-data dependency, broker/trading feature, personal recommendation, cloud deployment, or real personal data. All golden-case inputs are synthetic. Every weight, threshold, field, and rule marked **[PROPOSED]** in this document remains **PROPOSED — NOT YET APPROVED** until Anand records acceptance; existing implementation behavior is evidence, not authorization.

---

## 9. Suggested repository locations (for the PR)
- Contract: `docs/handoffs/S1-RSK-00/README.md`
- Golden-case matrix: `ai/risk/golden_examples_r1.json`

---

## 10. Downstream use
This document and the accompanying golden-case matrix (`ai/risk/golden_examples_r1.json`) are intended to support, in order: (1) the P5 pair walkthrough, (2) P6 independent review, (3) Anand approval, (4) #143's implementation, and (5) #144's regression-evidence design. Nothing here authorizes starting #143 — that remains gated on Anand acceptance of both #146 and #145.

## 11. Fixture validation
Run the structural R1 fixture validation with:

```powershell
python -m pytest ai/risk/test_golden_examples_r1.py -q
```
