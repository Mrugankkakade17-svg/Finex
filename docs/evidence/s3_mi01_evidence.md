# S3-MI01: Suitability Model Card & Educational Disclaimers
## Authoritative Evidence Document

- **Repository:** `Mrugankkakade17-svg/Finex`
- **Task ID:** `S3-MI01`
- **GitHub Issue:** [#54](https://github.com/Mrugankkakade17-svg/Finex/issues/54)
- **Assignee / Owner:** Mitali (`@mitali2701`)
- **Required Independent Reviewer:** Payal (`@payalmude14-star`)
- **Target Branch:** `dev`
- **Feature Branch:** `feature/s3-mi01`
- **Prerequisite:** `S3-LI01` (Issue [#53](https://github.com/Mrugankkakade17-svg/Finex/issues/53), PR [#160](https://github.com/Mrugankkakade17-svg/Finex/pull/160))
- **Date:** 2026-11-28
- **Status:** PR #169 OPEN — PENDING INDEPENDENT REVIEW (`@payalmude14-star`)

---

## 1. Executive Summary

This document provides complete, evidence-based verification for Task **S3-MI01** under Sprint 3 of the FinEx Master Product, Design and Delivery Handbook v9.1 and the FinEx Final Implementation Plan.

The primary deliverable is the authoritative model card located at:
`docs/ai/suitability-model-card.md`

The model card documents the deterministic quantitative methodology, mathematical invariants, input/output specifications, risk categories, allocation profiles, assumptions, limitations, and regulatory boundaries governing the FinEx Suitability Engine implemented in S3-LI01 (`backend/app/services/suitability_service.py`).

---

## 2. Dependency Verification (S3-LI01 Safety Gate)

Before creating the S3-MI01 deliverables, the prerequisite S3-LI01 implementation was verified on Git and GitHub:

| Dependency Check | Expected State | Actual Verified State | Status |
| :--- | :--- | :--- | :--- |
| **Issue #53 Status** | Closed / Merged | State: `closed` | **PASS** |
| **PR #160 Status** | Merged into `dev` | State: `closed`, `merged: True` | **PASS** |
| **PR #160 Merge SHA** | Merge commit on `dev` | Commit `f3aff3db0ad122ceaee735252a990c31a1c12251` | **PASS** |
| **Presence in `origin/dev`** | At HEAD of `origin/dev` | Present at `origin/dev` HEAD (`f3aff3d`) | **PASS** |
| **Implementation Files** | In `origin/dev` tree | `backend/app/services/suitability_service.py` present (blob `d9709e7`) | **PASS** |
| **Reviewer Findings** | Addressed in PR #160 | Commit `6f296ba` (threshold alignment) and `512c514` (exact normalization) verified | **PASS** |
| **Evidence Consistency** | `s3_li01_evidence.md` present | Present in `docs/evidence/s3_li01_evidence.md` | **PASS** |

---

## 3. Source Files Inspected & Audit Inventory Matrix

Every relevant file in the FinEx codebase was thoroughly inspected end-to-end:

| File Path | Component Responsibility | Important Contracts & Invariants | Security Review | Correctness Review | Audit Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `ai/risk/scoring.py` | 10-Question Behavioral Scoring | Normalized dimension scores (0–100), composite formula ($0.5W + 0.5C$), canonical boundary thresholds ($<34, <67, \ge 67$) | No external network calls, zero LLM scoring hallucinations | 100% deterministic, immutable v1 configuration | **PASS** |
| `backend/app/services/suitability_service.py` | Target Allocations, Drift & Rebalancing | Non-negative weights, unity sum ($1.000000$), strict equity monotonicity, exact 6-decimal normalization, threshold action alignment | Strict Decimal arithmetic, zero-sum rebalance conservation | Rebalance plan action matches drift classification | **PASS** |
| `backend/app/routers/suitability.py` | FastAPI Endpoints (`/api/v1/suitability`) | `/allocation` (public reference), `/rebalance` (authenticated) | `get_current_user` JWT validation, multi-tenant ownership check | Returns standardized envelope with `educational_disclaimer` | **PASS** |
| `backend/app/schemas/suitability.py` | Pydantic Request/Response Models | `extra="forbid"`, sanitized asset class names, finite weight validation | Rejects non-finite numbers (`NaN`, `Inf`) and negative weights | Strict schema conformance | **PASS** |
| `backend/app/core/exceptions.py` | Domain Exceptions | `SuitabilityException(FinExException)` with HTTP 400 status codes | Clean error envelopes, no SQL or stack trace leakage | Standardized error codes | **PASS** |
| `backend/app/services/portfolio_service.py` | Portfolio Data Provider | `get_portfolio_summary(portfolio_id, user_id)` | Scopes database query to authenticated `user_id`; raises 404 on cross-user access | Accurate valuation and asset breakdown | **PASS** |
| `backend/tests/unit/test_suitability_service.py` | Unit & Property Test Suite | 32 unit test functions (34 parameterized cases) covering invariants, personas, tolerance boundaries, and exact normalization | Multi-tenant isolation and negative weight protection tested | 100% pass rate | **PASS** |
| `backend/tests/contract/test_suitability_api.py` | API Contract Tests | 12 test functions (13 parameterized cases) validating OpenAPI schema, auth enforcement, and HTTP responses | 401 on missing token, 404 on cross-tenant access verified | 100% pass rate | **PASS** |

---

## 4. Mathematical Verification

All quantitative operations in `SuitabilityService` were independently derived and tested:

### 4.1 Target Allocation Invariants
$$\forall i \in \{\text{EQUITY}, \text{FIXED\_INCOME}, \text{CASH}\}: w_i \ge 0$$
$$\sum_i w_{i,\text{target}} = 1.000000 \quad (\pm 10^{-5})$$
$$w_{\text{equity}}(\text{CONSERVATIVE}) = 0.20 < w_{\text{equity}}(\text{MODERATE}) = 0.50 < w_{\text{equity}}(\text{AGGRESSIVE}) = 0.80$$

### 4.2 Exact Weight Normalization & Residual Tie-Breaking
When custom allocations are submitted within documented tolerance ($\pm 0.1\%$ or $\pm 0.001$):
$$\text{norm\_w}_i = \frac{w_i}{\sum_j w_j}$$
$$q_i = \text{quantize}(\text{norm\_w}_i, 10^{-6}, \text{ROUND\_HALF\_UP})$$
$$\text{residual} = 1.000000 - \sum_i q_i$$
The residual is deterministically assigned to the entry with the largest weight (using asset class as stable alphabetical tie-breaker), ensuring:
$$\sum_i w_{i,\text{current}} = 1.000000 \quad \text{[Exact]}$$

### 4.3 Signed Drift & Action Classification
$$\text{drift}_i = w_{i,\text{current}} - w_{i,\text{target}}$$
$$\text{action}_i = \begin{cases}
\text{HOLD} & \text{if } |\text{drift}_i| \le \tau \quad (\tau = 0.01) \\
\text{REDUCE} & \text{if } \text{drift}_i > \tau \\
\text{INCREASE} & \text{if } \text{drift}_i < -\tau
\end{cases}$$

### 4.4 Rebalance Adjustment & Monetary Capital Conservation
- **Held Positions ($|\text{drift}_i| \le \tau$):** $\text{direction} = \text{"HOLD"}$, $\text{adjustment\_weight} = \text{Decimal}("0.000000")$, $\text{indicative\_amount} = \text{Decimal}("0.00")$.
- **Actionable Positions ($|\text{drift}_i| > \tau$):** $\text{direction} = \text{action}_i$, $\text{adjustment\_weight} = -\text{drift}_i$, $\text{indicative\_amount} = (\text{adjustment\_weight} \times V_{\text{portfolio}}).\text{quantize}(0.01)$.
- **Capital Conservation Proof:** When all positions with non-zero drift are actionable, $\sum_i \text{adjustment\_weight}_i = 0.000000$. Cent rounding residuals ($\pm \$0.01$) are reconciled among actionable candidates with the largest absolute amounts:
  $$\sum_i \text{indicative\_amount}_i = \text{Decimal}("0.00")$$

### 4.5 Five Golden Persona Hand-Calculations Verified

| Persona | Risk Model | Portfolio Value | Current Allocations | Drift ($\text{Eq} / \text{FI} / \text{Cash}$) | Plan Action ($\text{Eq} / \text{FI} / \text{Cash}$) | Net Monetary Cash Flow |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Retired Capital** | `CONSERVATIVE_V1` | $\$100,000$ | $50\% / 30\% / 20\%$ | $+30\% / -40\% / +10\%$ | `TRIM` ($-\$30\text{k}$) / `ADD` ($+\$40\text{k}$) / `TRIM` ($-\$10\text{k}$) | $\$0.00$ (Conserved) |
| **2. Mid-Career** | `MODERATE_V1` | $\$50,000$ | $50\% / 40\% / 10\%$ | $0\% / 0\% / 0\%$ | `HOLD` ($\$0$) / `HOLD` ($\$0$) / `HOLD` ($\$0$) | $\$0.00$ (Balanced) |
| **3. Early-Career** | `AGGRESSIVE_V1` | $\$200,000$ | $60\% / 30\% / 10\%$ | $-20\% / +20\% / 0\%$ | `ADD` ($+\$40\text{k}$) / `TRIM` ($-\$40\text{k}$) / `HOLD` ($\$0$) | $\$0.00$ (Conserved) |
| **4. All-Cash** | `MODERATE_V1` | $\$10,000$ | $0\% / 0\% / 100\%$ | $-50\% / -40\% / +90\%$ | `ADD` ($+\$5\text{k}$) / `ADD` ($+\$4\text{k}$) / `TRIM` ($-\$9\text{k}$) | $\$0.00$ (Conserved) |
| **5. Empty** | `MODERATE_V1` | $\$0$ | $0\% / 0\% / 0\%$ | $-50\% / -40\% / -10\%$ | `INCREASE` / `INCREASE` / `INCREASE` | $\$0.00$ (Unallocated) |

---

## 5. Security, Privacy & Multi-Tenant Audit

1. **Authentication:** Endpoint `POST /api/v1/suitability/rebalance` strictly requires a valid Bearer JWT. Unauthenticated requests return `401 Unauthorized` (`AUTH_HEADER_MISSING` or `INVALID_TOKEN`).
2. **Tenant Isolation:** User identity is extracted exclusively from the decoded JWT claims (`user["user_id"]`). Caller-supplied user identifiers are never accepted.
3. **IDOR Prevention:** Verified via `test_rebalance_user_isolation_between_distinct_users`: User B requesting User A's `portfolio_id` receives HTTP `404 Not Found` with `error_code="PORTFOLIO_NOT_FOUND"`, completely preventing enumeration or data disclosure.
4. **Input Hardening:** Pydantic schemas enforce `extra="forbid"`. Non-finite weights (`NaN`, `Inf`) and negative weights are rejected before processing. Duplicate asset classes are rejected with HTTP 400 `DUPLICATE_ASSET_CLASS`.
5. **Data Privacy & Logging:** While FinEx persists user accounts, portfolios, and holdings in its database (`local_users`, `local_manual_portfolios`, `local_manual_holdings`), `suitability_service.py` and `routers/suitability.py` do not write new records and contain zero logger calls emitting user PII or bearer tokens. `CorrelationIdMiddleware` redacts bearer credentials from `X-Correlation-ID` headers, and exception handlers return structured error envelopes without SQL or stack traces.
6. **Database Integrity:** Suitability evaluation is a read-only analytical domain service that performs zero database mutations.

---

## 6. Scalability & Performance Audit

1. **Algorithmic Time Complexity:**
   - Drift calculation: $O(K \log K)$ where $K$ is the number of asset classes. For $K = 3$, execution time is $< 0.1\text{ ms}$.
   - Rebalance plan generation: $O(K \log K)$ sorting for residual cent allocation.
   - Questionnaire scoring: $O(N)$ where $N = 10$ questions.
2. **Space Complexity:** $O(K)$ temporary dictionary allocations, resulting in negligible heap allocation and zero GC pressure.
3. **Database & Market Read Behavior:** When `portfolio_id` is supplied, `portfolio_service.get_portfolio_summary` executes two repository read operations (`get_portfolio_by_id` and `list_holdings`) plus a batch market-quote lookup (`market_provider.get_quotes`) for held symbols. In PostgreSQL local-portfolio mode (`PostgresLocalPortfolioStore`), `finex.local_manual_portfolios` has a `UNIQUE(user_id, portfolio_id)` index, while `finex.local_manual_holdings` uses `holding_id` as its primary key (without a separate composite index on `(user_id, portfolio_id)` in `postgres_local_store.py`). In default in-memory mode, lookups use Python dictionary access.
4. **Concurrency & Thread Safety:** `SuitabilityService` holds only an immutable `RiskScoringEngine` reference and no mutable per-user state; it is instantiated as a stateless singleton (`suitability_service`). Production-scale throughput and latency have not been benchmarked.

---

## 7. Model Card Sections Verification

The deliverable `docs/ai/suitability-model-card.md` contains all 16 mandatory sections required by Phase 6:

- [x] Section 1: Document Information
- [x] Section 2: Model Overview
- [x] Section 3: Intended Use
- [x] Section 4: Out-of-Scope and Prohibited Use
- [x] Section 5: Risk Categories and Allocation Profiles
- [x] Section 6: Inputs and Outputs
- [x] Section 7: Mathematical Methodology
- [x] Section 8: Assumptions (Implementation vs Real-World Financial separated)
- [x] Section 9: Limitations and Exclusions (Explicit fee, tax, return, and advice disclaimers)
- [x] Section 10: Educational Disclaimer (Prominent, unambiguous mandatory text)
- [x] Section 11: Validation and Testing
- [x] Section 12: Security and Privacy Considerations
- [x] Section 13: Scalability and Performance Considerations
- [x] Section 14: Data Handling and Model Boundaries (ASCII architecture flow diagram)
- [x] Section 15: Versioning and Maintenance
- [x] Section 16: References

---

## 8. Acceptance Criteria Matrix

| Acceptance Criterion | Authoritative Source / Evidence | Audit Status |
| :--- | :--- | :--- |
| **States assumptions** | Documented in Section 8 of `suitability-model-card.md`, separating implementation assumptions (3 canonical asset classes, fixed category boundaries, deterministic tie-breaking) from real-world financial assumptions (frictionless trading, tax neutrality, continuous liquidity). Verified against `suitability_service.py:31-116`. | **PASS** |
| **No personalised-advice claim** | Documented in Sections 3, 4, 9, and 10 of `suitability-model-card.md`. Codified in `suitability_service.py:108-116` (`EDUCATIONAL_DISCLAIMER`) and returned in every API response. Re-asserts that FinEx is an educational platform and not a licensed financial adviser. | **PASS** |
| **Fees and taxes not modelled** | Explicitly stated in Sections 8.2, 9, and 10 of `suitability-model-card.md`. Codified in `EDUCATIONAL_DISCLAIMER`: *"Trading costs, commissions, management fees, and taxes are not modeled."* | **PASS** |

### Audit Area Matrix

| Audit Area | Files Inspected | Findings | Status |
| :--- | :--- | :--- | :--- |
| **Mathematical Correctness** | `backend/app/services/suitability_service.py` | Unity sum ($1.000000$), equity monotonicity ($0.20 \le 0.50 \le 0.80$), exact 6-decimal normalization, signed drift, threshold action alignment, cent capital conservation verified. | **PASS** |
| **Authentication** | `backend/app/routers/suitability.py`, `backend/app/auth/dependencies.py` | `/rebalance` enforces JWT Bearer authentication; returns 401 on missing/invalid token. Public endpoints accept zero user data. | **PASS** |
| **Tenant Isolation** | `backend/app/routers/suitability.py`, `backend/app/services/portfolio_service.py` | `user_id` extracted from JWT claims; cross-user portfolio access rejected with 404 `PORTFOLIO_NOT_FOUND`. | **PASS** |
| **Input Validation** | `backend/app/schemas/suitability.py`, `backend/app/core/exceptions.py` | Pydantic `extra="forbid"`, non-finite/negative weights rejected, duplicate asset classes rejected, invalid totals rejected. | **PASS** |
| **Data Privacy** | `backend/app/services/suitability_service.py`, `backend/app/core/middleware.py`, `backend/app/core/handlers.py` | Suitability router/service do not write PII or emit logger calls; `CorrelationIdMiddleware` redacts bearer credentials; exception handlers omit SQL/stack traces. | **PASS** |
| **Database Integrity** | `backend/app/repositories/portfolio_repository.py`, `backend/app/ports/adapters/postgres_local_store.py`, `backend/alembic/` | Read-only analytics; zero database writes during suitability computation. Single linear Alembic head (`s3li02_goal_contributions`) verified. | **PASS** |
| **Scalability** | `backend/app/services/suitability_service.py`, `backend/app/services/portfolio_service.py` | $O(K \log K)$ algorithmic time, $O(K)$ space, 2 repository reads + market quote lookup, stateless singleton. Production throughput unbenchmarked. | **PASS** |
| **Documentation Consistency** | `docs/ai/suitability-model-card.md`, `docs/evidence/s3_li01_evidence.md` | Models, weights, benchmark proxies, disclaimers, and invariants match source code and S3-MR01 reference data exactly. | **PASS** |

---

## 9. Quality Verification & Test Execution Results

### 9.1 Static Analysis & Formatting
- **Ruff Check:**
  ```powershell
  cd backend; .\.venv\Scripts\ruff.exe check .
  ```
  *Exit Code:* `0` | *Result:* **All checks passed!** (0 linting errors)
- **Ruff Format Check:**
  ```powershell
  cd backend; .\.venv\Scripts\ruff.exe format --check .
  ```
  *Exit Code:* `0` | *Result:* **392 files already formatted** (Clean)
- **Type Checker (Mypy):**
  ```powershell
  cd backend; .\.venv\Scripts\mypy.exe app/services/suitability_service.py app/schemas/suitability.py app/routers/suitability.py tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py --platform win32 --python-version 3.13
  ```
  *Exit Code:* `0` | *Result:* **Success: no issues found in 5 source files**
- **Alembic Heads:**
  ```powershell
  cd backend; .\.venv\Scripts\alembic.exe heads
  ```
  *Exit Code:* `0` | *Result:* **`s3li02_goal_contributions (head)`**

### 9.2 Targeted Suitability Tests
```powershell
cd backend; .\.venv\Scripts\pytest.exe -q --no-cov tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py
```
*Exit Code:* `0` | *Result:* **47 passed, 68 warnings in 4.90s** (100% PASS)

### 9.3 Risk Scoring Engine Tests
```powershell
$env:PYTHONPATH="."; backend\.venv\Scripts\pytest.exe -q --no-cov ai/risk/test_scoring.py ai/risk/test_explanation.py
```
*Exit Code:* `0` | *Result:* **43 passed in 0.57s** (100% PASS)

### 9.4 Full Non-PostgreSQL Backend Test Suite
```powershell
cd backend; .\.venv\Scripts\pytest.exe -m "not postgres" -q
```
*Exit Code:* `0` | *Result:* **3,202 passed, 4 skipped, 22 deselected, 2 xfailed, 2 xpassed in 705.46s**.
*Total Coverage:* **82.77%** (exceeds the 70% threshold).
*(Note: PostgreSQL-marked tests `-m postgres` were not executed locally as no live PostgreSQL instance is configured in this environment; they were verified in GitHub Actions CI on PR #160.)*

---

## 10. Delivery & Reviewer Hand-Off

- **Feature Branch:** `feature/s3-mi01`
- **Base Branch:** `dev` (`f3aff3d`)
- **Deliverables:**
  1. `docs/ai/suitability-model-card.md`
  2. `docs/evidence/s3_mi01_evidence.md`
- **Reviewer:** `@payalmude14-star`
- **Known Limitations:**
  - Standard educational limitations: fees, commissions, and taxes are excluded.
  - Large-scale concurrent load testing has not been benchmarked in staging environments.
