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

### Linters & Type Checking
- `python -m ruff check app/core/exceptions.py app/schemas/suitability.py app/services/suitability_service.py app/routers/suitability.py tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py`
  - **Result**: PASSED (0 errors)
- `python -m ruff format --check app/core/exceptions.py app/schemas/suitability.py app/services/suitability_service.py app/routers/suitability.py tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py`
  - **Result**: PASSED (6 files inspected, 6 formatted)
- `python -m mypy app/core/exceptions.py app/schemas/suitability.py app/services/suitability_service.py app/routers/suitability.py tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py`
  - **Result**: PASSED (`Success: no issues found in 6 source files`)

### Unit & Contract Tests
- `python -m pytest tests/unit/test_suitability_service.py tests/contract/test_suitability_api.py`
  - **Result**: **26 PASSED** in 4.00s

### Full Backend Test Suite
- `python -m pytest -m "not postgres" -q`
  - **Result**: **3,135 PASSED**, 4 skipped, 19 deselected, 2 xfailed, 2 xpassed in 693.14s (11m 33s)
  - **Coverage**: **82.64%** total backend coverage (exceeding minimum requirement of 70%)
  - **Zero Regressions** across all existing endpoints and domain services.

---

## 7. Modified & Created Files

1. `backend/app/core/exceptions.py` — Added `SuitabilityException(FinExException)`.
2. `backend/app/schemas/suitability.py` — Pydantic schemas for request/response models, invariants, and enums.
3. `backend/app/services/suitability_service.py` — Core suitability, drift, and rebalance calculation engine.
4. `backend/app/routers/suitability.py` — FastAPI REST endpoints mounted at `/api/v1/suitability`.
5. `backend/app/main.py` — Router registration.
6. `backend/tests/unit/test_suitability_service.py` — 19 comprehensive unit, property, invariant, and persona tests.
7. `backend/tests/contract/test_suitability_api.py` — 7 contract, OpenAPI, authentication, and user-isolation tests.
8. `docs/evidence/s3_li01_evidence.md` — Authoritative evidence document.

---

## 8. Status and Next Steps

- **Status**: **`READY FOR PAYAL REVIEW`**
- **Action**: Await independent code owner review and acceptance from `@payalmude14-star`. Do not merge or close issue.
