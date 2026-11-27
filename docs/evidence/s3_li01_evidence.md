# S3-LI01: Suitability Engine — Risk Category → Target Allocation → Drift → Rebalance Plan
## GitHub Issue #53 Evidence Document

- **Repository**: `Mrugankkakade17-svg/Finex`
- **Task ID**: `S3-LI01`
- **Issue**: `#53`
- **Feature Branch**: `feature/s3-li01`
- **Base Commit**: `0b4640d5838eaa8cca85ca237761ebda634e0ffe` (`origin/dev`)
- **Author / Owner**: Mitali (`@mitali2701`)
- **Required Independent Reviewer**: Payal (`@payalmude14-star`)

---

## 1. Executive Summary & Deliverables

Implemented the deterministic quantitative Suitability Engine according to FinEx Master Product, Design and Delivery Handbook v9.1, Final Implementation Plan, Updated Assignments, and GitHub Issue #53.

The suitability engine provides:
1. **Target Allocation Mapping**: Maps canonical risk categories (`CONSERVATIVE`, `MODERATE`, `AGGRESSIVE`) to educational asset-class target weights (`EQUITY`, `FIXED_INCOME`, `CASH`) and approved benchmark ETF proxies (`SPY`, `AGG`, `CSHX`) established by S3-MR01 (Alembic migration `fx_006`).
2. **AI Risk Profiling Integration**: Integrates deterministically with the existing `ai.risk` engine (`RiskScoringEngine`, `RiskAssessmentRequest`, `QuestionAnswer`), accepting 10-question behavioral questionnaire answers and resolving composite scores to canonical risk categories.
3. **Allocation Drift Analysis**: Calculates signed drift per asset class ($\text{drift} = \text{current\_weight} - \text{target\_weight}$) and classifies drift into `BALANCED` (within configurable threshold), `OVERWEIGHT`, or `UNDERWEIGHT`.
4. **Educational Rebalance Plan**: Computes deterministic rebalance actions (`TRIM`, `ADD`, `HOLD`) and indicative adjustment amounts ($\text{adjustment\_weight} = -\text{drift}$, $\text{indicative\_amount} = \text{portfolio\_value} \times \text{adjustment\_weight}$), guaranteeing that total rebalance adjustments sum to zero.
5. **Strict Multi-Tenant User Isolation**: Securely fetches holdings via `portfolio_service.get_portfolio_summary`, enforcing ownership checks and returning `404 PORTFOLIO_NOT_FOUND` if a user attempts to evaluate another user's portfolio.
6. **Regulatory Educational Boundary**: Enforces educational boundaries with prominent disclaimers; no automated trading, order routing, or regulated investment advice.

---

## 2. Mathematical Formalization & Invariant Guarantees

All quantitative operations are implemented with Python `Decimal` arithmetic for exact financial precision without floating-point inaccuracies.

### Invariant 1: Non-Negative Target Weights
$$\forall i \in \{\text{EQUITY}, \text{FIXED\_INCOME}, \text{CASH}\}: \quad w_{i,\text{target}} \ge 0$$

### Invariant 2: Target Weight Unity
$$\sum_{i} w_{i,\text{target}} = 1.000000 \quad (\pm 10^{-5})$$
- Conservative (`CONSERVATIVE_V1`): $0.20 + 0.70 + 0.10 = 1.000000$
- Moderate (`MODERATE_V1`): $0.50 + 0.40 + 0.10 = 1.000000$
- Aggressive (`AGGRESSIVE_V1`): $0.80 + 0.10 + 0.10 = 1.000000$

### Invariant 3: Equity Monotonicity Across Risk Categories
$$w_{\text{equity}}(\text{CONSERVATIVE}) \le w_{\text{equity}}(\text{MODERATE}) \le w_{\text{equity}}(\text{AGGRESSIVE})$$
$$0.20 \le 0.50 \le 0.80 \quad \text{(Strictly monotone ascending)}$$

### Invariant 4: Allocation Drift Formula & Zero-Sum Invariant
$$\text{drift}_i = w_{i,\text{current}} - w_{i,\text{target}}$$
For any normalized portfolio where $\sum w_{i,\text{current}} = 1.0$:
$$\sum_i \text{drift}_i = \sum_i w_{i,\text{current}} - \sum_i w_{i,\text{target}} = 1.0 - 1.0 = 0.000000$$

### Invariant 5: Rebalance Adjustment & Conservation of Portfolio Capital
$$\text{adjustment\_weight}_i = w_{i,\text{target}} - w_{i,\text{current}} = -\text{drift}_i$$
$$\text{indicative\_amount}_i = V_{\text{portfolio}} \times \text{adjustment\_weight}_i$$
$$\sum_i \text{indicative\_amount}_i = V_{\text{portfolio}} \sum_i (-\text{drift}_i) = 0.00$$

### Invariant 6: Classification Threshold
Given drift threshold $\tau = 0.01$ (default 1%):
$$\text{Status}_i = \begin{cases}
\text{BALANCED} & \text{if } |\text{drift}_i| \le \tau \\
\text{OVERWEIGHT} & \text{if } \text{drift}_i > \tau \\
\text{UNDERWEIGHT} & \text{if } \text{drift}_i < -\tau
\end{cases}, \quad
\text{Action}_i = \begin{cases}
\text{HOLD} & \text{if } \text{Status}_i = \text{BALANCED} \\
\text{TRIM} & \text{if } \text{Status}_i = \text{OVERWEIGHT} \\
\text{ADD} & \text{if } \text{Status}_i = \text{UNDERWEIGHT}
\end{cases}$$

---

## 3. Five Golden Persona Hand-Calculated Scenarios

### Persona 1: Retired Capital Preservation (Conservative)
- **Target**: `CONSERVATIVE_V1` (20% Equity, 70% Fixed Income, 10% Cash)
- **Current Portfolio**: $100,000 Total Value
  - Equity: $50,000 (50.0%)
  - Fixed Income: $30,000 (30.0%)
  - Cash: $20,000 (20.0%)
- **Calculated Drift**:
  - Equity: $0.50 - 0.20 = +0.30$ (+30.0% -> `OVERWEIGHT`)
  - Fixed Income: $0.30 - 0.70 = -0.40$ (-40.0% -> `UNDERWEIGHT`)
  - Cash: $0.20 - 0.10 = +0.10$ (+10.0% -> `OVERWEIGHT`)
  - Maximum Drift: $0.40$ (40.0%)
- **Rebalance Plan**:
  - Equity: Action `TRIM`, Adjustment Weight $-0.30$, Amount $-\$30,000.00$
  - Fixed Income: Action `ADD`, Adjustment Weight $+0.40$, Amount $+\$40,000.00$
  - Cash: Action `TRIM`, Adjustment Weight $-0.10$, Amount $-\$10,000.00$
  - Net Monetary Flow: $-\$30,000 + \$40,000 - \$10,000 = \$0.00$

### Persona 2: Mid-Career Balanced (Moderate)
- **Target**: `MODERATE_V1` (50% Equity, 40% Fixed Income, 10% Cash)
- **Current Portfolio**: $50,000 Total Value
  - Equity: $25,000 (50.0%)
  - Fixed Income: $20,000 (40.0%)
  - Cash: $5,000 (10.0%)
- **Calculated Drift**:
  - Equity: $0.50 - 0.50 = 0.00$ (`BALANCED`)
  - Fixed Income: $0.40 - 0.40 = 0.00$ (`BALANCED`)
  - Cash: $0.10 - 0.10 = 0.00$ (`BALANCED`)
  - Maximum Drift: $0.00$
- **Rebalance Plan**:
  - Rebalance Required: `False`
  - Equity: `HOLD` ($0.00)
  - Fixed Income: `HOLD` ($0.00)
  - Cash: `HOLD` ($0.00)

### Persona 3: Early-Career Growth (Aggressive)
- **Target**: `AGGRESSIVE_V1` (80% Equity, 10% Fixed Income, 10% Cash)
- **Current Portfolio**: $200,000 Total Value
  - Equity: $120,000 (60.0%)
  - Fixed Income: $60,000 (30.0%)
  - Cash: $20,000 (10.0%)
- **Calculated Drift**:
  - Equity: $0.60 - 0.80 = -0.20$ (-20.0% -> `UNDERWEIGHT`)
  - Fixed Income: $0.30 - 0.10 = +0.20$ (+20.0% -> `OVERWEIGHT`)
  - Cash: $0.10 - 0.10 = 0.00$ (0.0% -> `BALANCED`)
  - Maximum Drift: $0.20$ (20.0%)
- **Rebalance Plan**:
  - Equity: Action `ADD`, Adjustment Weight $+0.20$, Amount $+\$40,000.00$
  - Fixed Income: Action `TRIM`, Adjustment Weight $-0.20$, Amount $-\$40,000.00$
  - Cash: Action `HOLD`, Adjustment Weight $0.00$, Amount $\$0.00$
  - Net Monetary Flow: $+\$40,000 - \$40,000 + \$0 = \$0.00$

### Persona 4: All-Cash New Investor (Moderate)
- **Target**: `MODERATE_V1` (50% Equity, 40% Fixed Income, 10% Cash)
- **Current Portfolio**: $10,000 Total Value (100% Cash)
- **Calculated Drift**:
  - Equity: $0.00 - 0.50 = -0.50$ (-50.0% -> `UNDERWEIGHT`)
  - Fixed Income: $0.00 - 0.40 = -0.40$ (-40.0% -> `UNDERWEIGHT`)
  - Cash: $1.00 - 0.10 = +0.90$ (+90.0% -> `OVERWEIGHT`)
- **Rebalance Plan**:
  - Equity: Action `ADD`, Adjustment Weight $+0.50$, Amount $+\$5,000.00$
  - Fixed Income: Action `ADD`, Adjustment Weight $+0.40$, Amount $+\$4,000.00$
  - Cash: Action `TRIM`, Adjustment Weight $-0.90$, Amount $-\$9,000.00$
  - Net Monetary Flow: $+\$5,000 + \$4,000 - \$9,000 = \$0.00$

### Persona 5: Empty Portfolio
- **Target**: `MODERATE_V1`
- **Current Portfolio**: 0 holdings, $0 total value
- **Outcome**: `is_empty_portfolio = True`, `rebalance_required = False`, drift calculated against 0.0 current weights, no monetary amounts executed.

---

## 4. API Endpoints Contract

Mounted at prefix `/api/v1/suitability` in `backend/app/main.py`:

| Method | Path | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/v1/suitability/allocation` | No (Public) | Returns target allocation by `risk_category` string OR `questionnaire_answers` |
| `GET` | `/api/v1/suitability/allocation/{risk_category}` | No (Public) | Direct path lookup of target allocation model |
| `POST` | `/api/v1/suitability/rebalance` | Yes (`Bearer` JWT) | Computes drift and educational rebalance plan; supports custom allocation or user-owned `portfolio_id` |

### OpenAPI Schema Validation
All endpoints are exposed under tag `suitability` and present in `/openapi.json`.

---

## 5. Security & Multi-Tenant User Isolation

- Rebalance evaluations that pass `portfolio_id` invoke `portfolio_service.get_portfolio_summary(portfolio_id, user_id)`.
- If an authenticated user attempts to access a portfolio belonging to another user, or a non-existent portfolio, the system raises `FinExException(PORTFOLIO_NOT_FOUND, status_code=404)`.
- Verified in `test_rebalance_user_isolation_between_distinct_users`: User A's portfolio returns 200 OK for User A, but returns 404 with error code `PORTFOLIO_NOT_FOUND` when requested by User B.

---

## 6. Verification and Test Execution Log

### Linters, Type Checking & Migrations
- `python -m alembic heads`
  - **Result**: PASSED (`s3pa03_daily_snapshots (head)` — exactly one linear head after synchronizing with `origin/dev`)
- `python -m ruff check .`
  - **Result**: PASSED (All checks passed!)
- `python -m ruff format --check .`
  - **Result**: PASSED (Formatted and clean)
- `python -m mypy app`
  - **Result**: PASSED (`Success: no issues found in source files`)

### Unit & Contract Tests
- `python -m pytest tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py`
  - **Result**: **39 PASSED** (including boundary tolerance normalization, 6-decimal residual allocation, and exact monetary capital conservation tests)

### Full Backend Test Suite
- `python -m pytest -m "not postgres" -q`
  - **Result**: **3,135+ PASSED**, zero regressions across all endpoints and domain services.
  - **Coverage**: Total backend coverage exceeds the minimum required 70%.

---

## 7. Modified & Created Files

1. `backend/app/core/exceptions.py` — Added `SuitabilityException(FinExException)`.
2. `backend/app/schemas/suitability.py` — Pydantic schemas for request/response models, invariants, and enums.
3. `backend/app/services/suitability_service.py` — Core suitability, drift, exact weight normalization (`_normalize_allocation_weights`), and rebalance plan generation with monetary capital conservation.
4. `backend/app/routers/suitability.py` — FastAPI REST endpoints mounted at `/api/v1/suitability`.
5. `backend/app/main.py` — Router registration.
6. `backend/tests/unit/test_suitability_service.py` — 28 unit, property, invariant, tolerance, boundary normalization, and persona tests.
7. `backend/tests/contract/test_suitability_api.py` — 11 contract, OpenAPI, authentication, user-isolation, and boundary allocation validation tests.
8. `docs/evidence/s3_li01_evidence.md` — Authoritative evidence document.

---

## 8. Status and Next Steps

- **Status**: **`READY FOR REVIEWER RE-VERIFICATION`**
- **Action**: Await independent code owner re-verification and acceptance from `@Mrugankkakade17-svg` and `@payalmude14-star`. Do not merge or close PR #160.

---

## 9. Reviewer Finding Remediation: Allocation Validation & Zero-Sum Invariant (PR #160)


### 9.1 Reviewer Finding Summary
- **Reviewer**: `@Mrugankkakade17-svg` (Comment ID: `4721224117` on `backend/app/services/suitability_service.py:494`)
- **Finding**:
  > `total_input` is accumulated but never checked against 1.0 (and duplicate asset classes overwrite `current_map` while still contributing multiple times here). For example, a custom allocation totaling 80% is treated as if the missing 20% did not exist, so `sum(adjustment_weight)` is 20% and indicative adjustments no longer conserve portfolio value, despite the documented zero-sum invariant. Please validate/normalize the input total and reject duplicate asset classes (or otherwise define how the unallocated remainder is represented) before calculating drift.

### 9.2 Root Cause Analysis
1. **Duplicate Asset Classes**:
   Previous logic assigned `current_map[item.asset_class] = w` inside a loop without checking if `item.asset_class` had already been encountered. Duplicate keys silently overwrote prior dictionary values while both weights contributed to `total_input`.
2. **Missing Total Unity Validation**:
   `total_input` was accumulated but only checked with `if total_input <= _ZERO: is_empty = True`. Incomplete custom allocations (e.g. 80%) or excess allocations (e.g. 120%) proceeded to drift calculation against target allocations summing to 1.0. This caused:
   $$\sum \text{drift} = \sum (w_{\text{curr}} - w_{\text{target}}) = 0.80 - 1.00 = -0.20 \neq 0$$
   $$\sum \text{adjustment\_weight} = \sum (-\text{drift}) = +0.20 \neq 0$$
   $$\sum \text{indicative\_amount} = +0.20 \times V_{\text{portfolio}} \neq 0$$
   This directly broke portfolio value conservation and the documented zero-sum rebalancing invariant.

### 9.3 Corrective Architecture & Implementation
In `backend/app/services/suitability_service.py`, custom allocations now pass through strict mathematical validation before drift calculation:
1. **Duplicate Asset Class Rejection**:
   - Asset class identifiers are normalized (`cat = str(item.asset_class).strip().upper()`).
   - Any duplicate asset class immediately raises `SuitabilityException` with error code `DUPLICATE_ASSET_CLASS` (HTTP 400).
2. **Weight Precision & Validity**:
   - Each weight is parsed as `Decimal`.
   - Non-finite values (`NaN`, `sNaN`, `+Inf`, `-Inf`) raise `NON_FINITE_WEIGHT` (HTTP 400).
   - Negative values (`w < 0.0`) raise `NEGATIVE_WEIGHT` (HTTP 400).
3. **Scale Detection & Documented Tolerance Policy**:
   - Input scale is automatically identified: percentage scale if any item `> 1.0` or raw sum `> 1.5`, otherwise fractional scale.
   - **Fractional Scale**: Expected total is $1.000000$ with tolerance $\pm 0.001$ ($0.1\%$).
   - **Percentage Scale**: Expected total is $100.00\%$ with tolerance $\pm 0.1\%$.
   - Any deviation exceeding tolerance immediately raises `SuitabilityException` with error code `INVALID_ALLOCATION_TOTAL` (HTTP 400), explicitly reporting the received total and discrepancy.
4. **Conservation of Invariants**:
   - Because all custom allocations entering drift computation are guaranteed to sum to $1.0 \pm 0.001$, the zero-sum invariant is mathematically guaranteed:
     $$\sum_i \text{drift}_i = \sum_i w_{i,\text{curr}} - \sum_i w_{i,\text{target}} = 1.0 - 1.0 = 0.0$$
     $$\sum_i \text{adjustment\_weight}_i = \sum_i (-\text{drift}_i) = 0.0$$
     $$\sum_i \text{indicative\_amount}_i = V_{\text{portfolio}} \sum_i \text{adjustment\_weight}_i = \$0.00$$
5. **Preservation of Empty Portfolio Semantics**:
   - Empty allocation list `[]` or explicit $0.00 portfolio value continues to produce clean empty portfolio guidance (`is_empty_portfolio = True`) without fake drift.

### 9.4 Regression Test Suite (34/34 Passing)
8 dedicated tests were added across unit and contract layers:
- `test_custom_allocation_duplicate_asset_class_rejected`: Validates rejection of duplicate keys including case-insensitive variants (`equity` and `EQUITY`).
- `test_custom_allocation_incomplete_total_rejected_80_percent`: Validates that 80% allocations (both fractional 0.80 and percentage 80.0%) are rejected with `INVALID_ALLOCATION_TOTAL`.
- `test_custom_allocation_excess_total_rejected_120_percent`: Validates that 120% allocations are rejected with `INVALID_ALLOCATION_TOTAL`.
- `test_custom_allocation_tolerance_boundaries`: Validates that 0.9995 is accepted within $\pm 0.001$ tolerance while 0.998 is rejected.
- `test_custom_allocation_zero_sum_rebalancing_and_value_conservation`: Mathematically asserts $\sum \text{drift} == 0$, $\sum \text{adjustment\_weight} == 0$, and $\sum \text{indicative\_amount} == \$0.00$.
- `test_rebalance_endpoint_duplicate_asset_class_returns_400`: FastAPI contract test verifying HTTP 400 and `DUPLICATE_ASSET_CLASS` error code.
- `test_rebalance_endpoint_incomplete_allocation_total_returns_400`: FastAPI contract test verifying HTTP 400 and `INVALID_ALLOCATION_TOTAL` error code for 80% custom allocation.
- `test_rebalance_endpoint_excess_allocation_total_returns_400`: FastAPI contract test verifying HTTP 400 and `INVALID_ALLOCATION_TOTAL` error code for 120% custom allocation.

---

## 10. Second Reviewer Correction: Exact Normalization & Capital Conservation (PR #160)

### 10.1 Reviewer Finding
- **Reviewer**: `@Mrugankkakade17-svg` (Comment ID: `4721845084` on line 538)
- **Finding**:
  > *"The tolerance allows totals different from 100%, but these weights are only divided by 100 and stored; they are not normalized. E.g. 20%, 30%, 49.95% is accepted and remains a 0.9995 total, so `sum(adjustment_weight)` is 0.0005 and indicative amounts do not conserve the portfolio value. The fractional branch has the same issue, compounded by 6-decimal quantization. Please normalize accepted weights to an exact total (and ensure rounding leaves the total exactly 1), or tighten validation so only totals that produce the claimed invariant are accepted; add a conservation test at both tolerance boundaries."*

### 10.2 Technical Root Cause & Analysis
While the previous remediation correctly validated that input totals lay within the documented tolerance window ($\pm 0.1\%$ or $\pm 0.001$), dividing accepted weights by 100 merely converted percentage scales into fractions without normalizing them by the actual input sum. Consequently:
- Input with total $99.95\%$ yielded stored weights summing to $0.999500 \neq 1.000000$.
- Target allocations sum to $1.000000$, resulting in:
  $$\sum \text{drift} = 0.999500 - 1.000000 = -0.000500 \neq 0$$
  $$\sum \text{adjustment\_weight} = -(-0.000500) = +0.000500 \neq 0$$
- Indicative monetary adjustments failed exact zero-sum capital conservation ($+\$0.0005 \times V_{\text{portfolio}}$).
- Independent six-decimal quantization (`10^-6`) can further introduce a $\pm 0.000001$ rounding residual across entries.
- Independent monetary cent rounding (`0.01`) can create a $\pm \$0.01$ discrepancy on fractional-cent portfolio values.

### 10.3 Exact Mathematical Normalization & Conservation Algorithm
1. **Validation Pre-Condition**:
   - Fractional inputs must satisfy $| \text{raw\_total} - 1.0 | \le 0.001$.
   - Percentage inputs must satisfy $| \text{raw\_total} - 100.0 | \le 0.1$.
   - Inputs outside tolerance continue to be rejected with HTTP 400 `INVALID_ALLOCATION_TOTAL`.
2. **Exact Normalization & 6-Decimal Quantization**:
   - Each accepted raw weight is divided by the actual input sum:
     $$\text{norm\_w}_i = \frac{w_i}{\sum_j w_j}$$
   - Quantized to 6 decimal places: $q_i = \text{quantize}(\text{norm\_w}_i, \text{Decimal}("0.000001"), \text{ROUND\_HALF\_UP})$.
3. **Deterministic Quantization Residual Allocation**:
   - Compute residual: $\text{residual} = \text{Decimal}("1.000000") - \sum_i q_i$.
   - If $\text{residual} \neq 0$, deterministically allocate the residual to the entry with the largest quantized weight, using asset class name as a stable alphabetical tie-breaker.
   - Assert all normalized weights remain non-negative and $\sum_i w_i == \text{Decimal}("1.000000")$ exactly.
4. **Deterministic Monetary Capital Conservation Policy**:
   - In `generate_rebalance_plan`, indicative amounts are quantized to cents ($0.01$).
   - Compute monetary residual: $\text{monetary\_residual} = \text{Decimal}("0.00") - \sum_i \text{indicative\_amount}_i$.
   - If $\text{monetary\_residual} \neq 0$, deterministically assign the rounding cent to the non-zero adjustment with the largest absolute monetary amount, using asset class as stable tie-breaker.
   - This proves $\sum \text{indicative\_amount} == \text{Decimal}("0.00")$ across all portfolio values, including irregular fractional-cent amounts ($150,000.55, $100,000.01, $99.99).

### 10.4 Invariant Mathematical Proofs
For every accepted custom allocation:
$$\sum_i w_{i,\text{current}} = \text{Decimal}("1.000000") \quad \text{[Exact]}$$
$$\sum_i w_{i,\text{target}} = \text{Decimal}("1.000000") \quad \text{[Exact]}$$
$$\sum_i \text{drift}_i = \sum_i (w_{i,\text{current}} - w_{i,\text{target}}) = 1.000000 - 1.000000 = \text{Decimal}("0.000000") \quad \text{[Exact]}$$
$$\sum_i \text{adjustment\_weight}_i = \sum_i (-\text{drift}_i) = \text{Decimal}("0.000000") \quad \text{[Exact]}$$
$$\sum_i \text{indicative\_amount}_i = \text{Decimal}("0.00") \quad \text{[Exact to the cent]}$$

### 10.5 Extended Regression Test Suite (39/39 Passing)
5 additional tests added (suite expanded from 34 to 39 tests, 100% passing):
- `test_custom_allocation_percentage_scale_boundary_normalization`: Asserts exact 1.000000 weight sum, 0.000000 drift sum, 0.000000 adjustment sum, and $0.00 monetary sum at 99.9%, 99.95% (reviewer case), and 100.1%.
- `test_custom_allocation_fractional_scale_boundary_normalization`: Asserts exact conservation at 0.999 and 1.001.
- `test_custom_allocation_quantization_residual_deterministic_allocation`: Tests 3 equal weights of 33.3% producing 6-decimal residual $+0.000001$; asserts deterministic tie-breaking to CASH, sum == 1.000000, and idempotency across repeated runs.
- `test_custom_allocation_monetary_conservation_fractional_cents`: Asserts $\sum \text{indicative\_amount} == \$0.00$ across $150,000.55, $100,000.01, $99.99, $12,345.67, and $0.01.
- `test_rebalance_endpoint_boundary_allocations_normalized_and_conserved`: FastAPI API contract test asserting that HTTP 200 responses return exactly normalized allocations and conserved adjustments.


