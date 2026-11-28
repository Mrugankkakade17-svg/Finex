# FinEx Suitability Engine — Model Card & Educational Disclaimers

---

## 1. Document Information

- **Model Name:** FinEx Educational Suitability, Asset Allocation & Portfolio Drift Engine
- **Task ID:** `S3-MI01`
- **GitHub Issue:** [#54](https://github.com/Mrugankkakade17-svg/Finex/issues/54)
- **Model Version:** `v1.0.0` (Deterministic Rule-Based)
- **Implementation Modules:**
  - `backend/app/services/suitability_service.py`
  - `backend/app/routers/suitability.py`
  - `backend/app/schemas/suitability.py`
  - `ai/risk/scoring.py`
- **Author / Owner:** Mitali (`@mitali2701`)
- **Secondary Reviewer:** Payal (`@payalmude14-star`)
- **Date:** 2026-11-28
- **Classification:** Educational AI / Deterministic Quantitative Engine
- **Status:** APPROVED & AUDITED

---

## 2. Model Overview

The FinEx Suitability Engine is a deterministic quantitative framework that provides educational asset allocation guidance, portfolio drift analysis, and illustrative rebalancing recommendations.

It serves as a core educational bridge between behavioral risk self-assessment and practical portfolio construction:
1. **Risk-to-Allocation Mapping:** Translates canonical risk categories (`CONSERVATIVE`, `MODERATE`, `AGGRESSIVE`) derived from the 10-question behavioral questionnaire (`ai.risk.scoring`) or direct selection into standardized educational asset-class target weights (`EQUITY`, `FIXED_INCOME`, `CASH`).
2. **Allocation Drift Analysis:** Evaluates existing portfolio allocations against target benchmarks, quantifying signed drift ($\text{drift} = w_{\text{current}} - w_{\text{target}}$) and classifying asset positions as `BALANCED`, `OVERWEIGHT`, or `UNDERWEIGHT` based on a configurable threshold ($\tau = 0.01$).
3. **Illustrative Rebalance Planning:** Computes target-restoring adjustments (`HOLD`, `REDUCE`, `INCREASE`) and indicative monetary amounts ($\text{adjustment\_weight} = -\text{drift}$, $\text{indicative\_amount} = V_{\text{portfolio}} \times \text{adjustment\_weight}$) mapped to approved synthetic benchmark ETF proxies (`SPY`, `AGG`, `CSHX`).
4. **Deterministic Guarantee:** The engine executes 100% outside Large Language Models (LLMs) using arbitrary-precision Python `Decimal` arithmetic, guaranteeing zero numerical hallucination, mathematical invariant conservation, and full auditability.

---

## 3. Intended Use

The FinEx Suitability Engine is strictly intended for:
- **Educational Demonstration:** Demonstrating how modern portfolio theory concepts (risk profiling, asset allocation, drift monitoring, and periodic rebalancing) operate quantitatively.
- **Self-Directed Financial Literacy:** Allowing users to explore hypothetical asset distribution models and understand the impact of market movements on asset class diversification.
- **Simulated Paper Trading Context:** Guiding users within the FinEx simulated environment on how portfolio drift can be reconciled toward a benchmark profile.
- **Consistent Multi-Platform Presentation:** Providing identical deterministic calculations across React web and Flutter mobile applications.

---

## 4. Out-of-Scope and Prohibited Use

The engine is explicitly prohibited from:
- **Regulated Personal Investment Advice:** Generating tailored financial advice, fiduciary investment recommendations, or wealth management mandates.
- **Automated Order Execution:** Submitting orders, routing trades, or executing real-money transactions with any broker, exchange, or custodian.
- **Tax Optimization:** Providing tax-loss harvesting, capital gains tax optimization, or tax-advantaged account placement strategies.
- **Predictive Market Timing:** Forecasting future asset prices, macroeconomic trends, or interest rate movements.
- **Individual Instrument Selection:** Recommending individual single stocks, corporate bonds, derivatives, or speculative assets beyond the illustrative ETF proxy benchmarks.
- **Autonomous Operation:** Executing changes to user portfolios without explicit, informed, and manual user initiation within a simulated paper environment.

---

## 5. Risk Categories and Allocation Profiles

The engine establishes three canonical allocation profiles codified in `ALLOCATION_TARGETS` based on S3-MR01 reference models (`scripts/seed_reference_data.py` and Alembic migration `fx_006`):

| Model Code | Risk Category | Equity Weight ($w_{\text{eq}}$) | Fixed Income Weight ($w_{\text{fi}}$) | Cash Weight ($w_{\text{cash}}$) | Total Weight | Benchmark ETF Proxies |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `CONSERVATIVE_V1` | **CONSERVATIVE** | **20.0%** (`0.200000`) | **70.0%** (`0.700000`) | **10.0%** (`0.100000`) | **100.0%** (`1.000000`) | `SPY` (20%), `AGG` (70%), `CSHX` (10%) |
| `MODERATE_V1` | **MODERATE** | **50.0%** (`0.500000`) | **40.0%** (`0.400000`) | **10.0%** (`0.100000`) | **100.0%** (`1.000000`) | `SPY` (50%), `AGG` (40%), `CSHX` (10%) |
| `AGGRESSIVE_V1` | **AGGRESSIVE** | **80.0%** (`0.800000`) | **10.0%** (`0.100000`) | **10.0%** (`0.100000`) | **100.0%** (`1.000000`) | `SPY` (80%), `AGG` (10%), `CSHX` (10%) |

### Mathematical Invariants
Every allocation profile strictly satisfies four structural invariants:
1. **Non-Negativity:** $\forall i \in \{\text{EQUITY}, \text{FIXED\_INCOME}, \text{CASH}\}: w_i \ge 0$.
2. **Completeness (Unity Sum):** $\sum_{i} w_i = 1.000000 \quad (\pm 10^{-5})$.
3. **Strict Equity Monotonicity:** Equity exposure increases monotonically with risk tolerance:
   $$w_{\text{equity}}(\text{CONSERVATIVE}) < w_{\text{equity}}(\text{MODERATE}) < w_{\text{equity}}(\text{AGGRESSIVE}) \implies 0.20 < 0.50 < 0.80$$
4. **Liquidity Buffer Baseline:** All models maintain an identical $10.0\%$ cash liquidity baseline (`CSHX`).

---

## 6. Inputs and Outputs

### 6.1 Target Allocation Resolution (`POST /api/v1/suitability/allocation`)
- **Inputs:**
  - `risk_category` *(Optional string)*: Explicit category identifier (`"CONSERVATIVE"`, `"MODERATE"`, `"AGGRESSIVE"`).
  - `questionnaire_answers` *(Optional list)*: 10 structured questionnaire responses (`QuestionAnswer(question_id, answer_code)`).
- **Outputs (`TargetAllocationResponse`):**
  - Canonical `risk_category`, `model_code`, `model_name`, `version`, `description`.
  - Itemized `allocations`: `asset_class`, `target_weight`, `target_pct`, `benchmark_symbol`, `benchmark_name`.
  - `invariants_satisfied`: Boolean verification flag.
  - `educational_disclaimer`: Mandatory boundary disclosure text.

### 6.2 Portfolio Rebalance Evaluation (`POST /api/v1/suitability/rebalance`)
- **Inputs (`SuitabilityRebalanceRequest`):**
  - `risk_category` or `questionnaire_answers` *(One required)*.
  - `portfolio_id` *(Optional UUID)*: User-owned portfolio ID for live evaluation with multi-tenant isolation.
  - `current_allocation` *(Optional list)*: Direct list of current holdings (`CurrentAllocationItem(asset_class, weight, value)`).
  - `portfolio_value` *(Optional Decimal)*: Explicit portfolio monetary valuation for indicative cash calculations.
  - `drift_threshold` *(Optional Decimal, default `0.01`)*: Drift threshold fraction $\tau \in [0.0, 0.5]$.
- **Outputs (`SuitabilityRebalanceResponse`):**
  - `drift_summary`: Per-asset-class metrics including `current_weight`, `target_weight`, `drift`, `drift_pct`, `status` (`BALANCED` / `OVERWEIGHT` / `UNDERWEIGHT`), and `action` (`HOLD` / `REDUCE` / `INCREASE`).
  - `rebalance_plan`: Per-asset-class actionable recommendations including `adjustment_weight`, `direction`, `indicative_amount`, `benchmark_symbol`, and human-readable educational `explanation`.
  - `max_drift`: Maximum absolute drift fraction across all asset classes ($\max_i |\text{drift}_i|$).
  - `rebalance_required`: Boolean flag (`True` if any asset class drift exceeds $\tau$).
  - `is_empty_portfolio`: Boolean flag (`True` if portfolio holds no assets or $\$0.00$ value).
  - `educational_disclaimer`: Mandatory disclosure.

---

## 7. Mathematical Methodology

All calculations are performed using Python `Decimal` objects with `ROUND_HALF_UP` quantization. Floating-point arithmetic (`float`) is strictly prohibited in the quantitative engine.

### 7.1 Risk Scoring Evaluation
When questionnaire answers are supplied, `RiskScoringEngine` processes 10 questions across two dimensions:
- **Willingness to Take Risk ($W$, Questions W1–W5):** Measures self-reported psychological risk tolerance.
- **Financial Risk Capacity ($C$, Questions C1–C5):** Measures self-reported financial ability to absorb losses.

Each answer maps to an integer score $s \in [1, 5]$. Raw dimension score:
$$\text{raw\_score} = \sum_{j=1}^{5} s_j \quad (\min = 5, \max = 25)$$
Normalized dimension score:
$$\text{normalized\_score} = \left(\frac{\text{raw\_score} - 5}{25 - 5}\right) \times 100.0$$
Composite score (equally weighted combination):
$$\text{composite\_score} = (0.5 \times \text{normalized\_willingness}) + (0.5 \times \text{normalized\_capacity})$$
Category mapping:
$$\text{Category} = \begin{cases}
\text{CONSERVATIVE} & \text{if } \text{composite\_score} < 34.0 \\
\text{MODERATE} & \text{if } 34.0 \le \text{composite\_score} < 67.0 \\
\text{AGGRESSIVE} & \text{if } \text{composite\_score} \ge 67.0
\end{cases}$$

### 7.2 Custom Allocation Validation & Exact Normalization
When clients provide custom current allocations, the engine applies strict pre-flight validation:
1. **Asset Class Uniqueness:** Duplicate asset classes are rejected (HTTP 400 `DUPLICATE_ASSET_CLASS`).
2. **Numeric Sanity:** Non-finite (`NaN`, `Inf`) and negative weights are rejected (HTTP 400).
3. **Scale Detection & Tolerance Validation:**
   - Percentage scale: Validated against $100.0\% \pm 0.1\%$.
   - Fractional scale: Validated against $1.000000 \pm 0.001$.
   - Out-of-tolerance inputs are rejected (HTTP 400 `INVALID_ALLOCATION_TOTAL`).
4. **Exact Normalization to 6 Decimal Places:**
   $$\text{norm\_w}_i = \frac{w_i}{\sum_j w_j}$$
   $$q_i = \text{quantize}(\text{norm\_w}_i, 10^{-6}, \text{ROUND\_HALF\_UP})$$
   $$\text{residual} = 1.000000 - \sum_i q_i$$
   The residual is deterministically allocated to the largest weight using asset class name as a stable alphabetical tie-breaker, guaranteeing:
   $$\sum_i w_{i,\text{current}} = 1.000000 \quad \text{[Exact]}$$

### 7.3 Signed Drift Calculation
For each asset class $i \in \text{Current} \cup \text{Target}$:
$$\text{drift}_i = w_{i,\text{current}} - w_{i,\text{target}}$$
$$\text{drift\_pct}_i = \text{drift}_i \times 100.0$$
For any normalized portfolio:
$$\sum_i \text{drift}_i = \sum_i w_{i,\text{current}} - \sum_i w_{i,\text{target}} = 1.000000 - 1.000000 = 0.000000$$

### 7.4 Action Classification & Threshold Policy
Given drift threshold $\tau$ (default $\tau = 0.01$):
$$\text{status}_i = \begin{cases}
\text{BALANCED} & \text{if } |\text{drift}_i| \le \tau \\
\text{OVERWEIGHT} & \text{if } \text{drift}_i > \tau \\
\text{UNDERWEIGHT} & \text{if } \text{drift}_i < -\tau
\end{cases}, \quad
\text{action}_i = \begin{cases}
\text{HOLD} & \text{if } |\text{drift}_i| \le \tau \\
\text{REDUCE} & \text{if } \text{drift}_i > \tau \\
\text{INCREASE} & \text{if } \text{drift}_i < -\tau
\end{cases}$$

### 7.5 Rebalance Adjustment & Monetary Capital Conservation
- **Held Positions ($|\text{drift}_i| \le \tau$):**
  $$\text{direction} = \text{"HOLD"}$$
  $$\text{adjustment\_weight}_i = \text{Decimal}("0.000000")$$
  $$\text{indicative\_amount}_i = \text{Decimal}("0.00") \quad (\text{if } V_{\text{portfolio}} > 0)$$
- **Actionable Positions ($|\text{drift}_i| > \tau$):**
  $$\text{direction} = \text{action}_i \in \{\text{"REDUCE"}, \text{"INCREASE"}\}$$
  $$\text{adjustment\_weight}_i = w_{i,\text{target}} - w_{i,\text{current}} = -\text{drift}_i$$
  $$\text{raw\_amount}_i = \text{quantize}(\text{adjustment\_weight}_i \times V_{\text{portfolio}}, 0.01, \text{ROUND\_HALF\_UP})$$
- **Capital Conservation Rules:**
  1. *Unconstrained Zero-Sum Case:* When all positions with non-zero drift are actionable (e.g. $\tau = 0.0$ or all drifts exceed $\tau$), continuous adjustment weights sum to zero:
     $$\sum_i \text{adjustment\_weight}_i = \sum_i (-\text{drift}_i) = 0.000000$$
     Cent rounding residuals ($\pm \$0.01$) are deterministically reconciled among actionable candidates with the largest absolute amounts, ensuring exact dollar conservation:
     $$\sum_i \text{indicative\_amount}_i = \text{Decimal}("0.00")$$
  2. *Threshold-Suppressed Case:* When one or more non-zero drift positions are held within threshold ($|\text{drift}_i| \le \tau$), their drift is intentionally excluded from trading. In this case, zero-sum conservation is not claimed across actionable trades, held positions strictly receive $\$0.00$, and actionable trades receive honest target-restoring adjustments without residual distortion.

---

## 8. Assumptions

The engine is built upon documented assumptions separated into implementation constraints and financial modeling assumptions:

### 8.1 Implementation & Technical Assumptions
1. **Three-Asset Canonical Universe:** Current reference models are composed exclusively of Equity, Fixed Income, and Cash. Non-standard holdings are tracked but not assigned target weights unless provided via custom allocation.
2. **Fixed Category Boundaries:** Risk scores map to categories via fixed immutable thresholds ($[0, 34)$, $[34, 67)$, $[67, 100]$) codified in approved v1 policy.
3. **Deterministic Tie-Breaking:** Rounding residuals in weight normalization and monetary adjustments are resolved deterministically by magnitude with stable alphabetical tie-breaking.
4. **Synchronous Execution:** Drift and rebalance calculations assume a single point-in-time snapshot of portfolio holdings and valuations.
5. **Single Primary Currency:** Monetary calculations assume currency consistency across holdings and portfolio totals (default USD).

### 8.2 Real-World Financial & Economic Assumptions
1. **Frictionless Rebalancing:** Calculations assume zero trading fees, zero commissions, zero bid-ask spread impact, zero exchange transaction costs, and zero market impact.
2. **Tax Neutrality:** The model assumes transactions generate zero taxable events (no capital gains tax, dividend withholding tax, or transaction taxes).
3. **Continuous Fractional Liquidity:** Transactions are assumed to be executable in arbitrary fractional units without lot size constraints.
4. **Static Target Weights:** Target allocations remain constant over time and do not dynamically adjust based on investor age, life events, or market volatility.
5. **Perfect Proxy Tracking:** Approved benchmark proxies (`SPY`, `AGG`, `CSHX`) are assumed to represent broad asset classes without tracking error.

---

## 9. Limitations and Exclusions

The following limitations must be prominently disclosed across all consuming applications:

1. **Fees Are Not Modelled:** Brokerage commissions, asset management fees, ETF expense ratios, custody fees, and transfer costs are completely excluded from indicative amounts.
2. **Taxes Are Not Modelled:** Local, state, national, and international tax liabilities arising from rebalancing trades are not calculated or considered.
3. **Returns Are Not Guaranteed:** Historical performance of benchmark asset classes or illustrative models provides no guarantee of future financial returns.
4. **Capital Protection Is Not Guaranteed:** Investment in equity, bond, or cash proxies carries investment risk, including the possible loss of principal.
5. **Future Market Performance Is Not Predicted:** The engine does not project, simulate, or anticipate future macroeconomic conditions, inflation rates, or asset price fluctuations.
6. **No Broker Order Execution:** Recommendations are illustrative only; no actual buy or sell orders are generated, transmitted, or executed with any market venue.
7. **Not a Substitute for Qualified Advice:** The model does not account for an individual's complete financial situation, liabilities, emergency reserves, tax residency, or investment objectives, and is not a substitute for professional financial advice.

---

## 10. Educational Disclaimer

The following disclaimer is mandatory, permanently codified in `EDUCATIONAL_DISCLAIMER`, and emitted in every API response envelope:

> **FinEx suitability outputs are educational and illustrative only. They are not personalised investment advice and do not constitute a recommendation to buy, sell or hold any financial instrument. Users remain responsible for their own financial decisions. Actual investment outcomes may differ from illustrative calculations. Fees and taxes are not modelled.**
> 
> *FinEx is an educational software platform, not a registered investment adviser, broker-dealer, financial planner, or wealth management institution. Past performance is no guarantee of future returns. Reference allocation models illustrate hypothetical distributions based on generalized risk profiles. Consult a licensed financial professional before making real-world financial commitments.*

---

## 11. Validation and Testing

The Suitability Engine is subjected to comprehensive automated verification across unit, integration, contract, and property-based test suites:

### 11.1 Test Coverage Summary
- `backend/tests/unit/test_suitability_service.py` (36 unit & property tests):
  - Invariant validation: weight non-negativity, exact unity sum, and equity monotonicity across all categories.
  - Scale tolerance verification: acceptance of $\pm 0.1\%$ percentage and $\pm 0.001$ fractional inputs; strict rejection of $80\%$ and $120\%$ totals.
  - Exact 6-decimal normalization: residual tie-breaking to Cash and mathematical conservation.
  - Cent rounding conservation: zero-sum dollar rebalancing across fractional-cent portfolio valuations ($150,000.55, $100,000.01, $99.99, $0.01).
  - Drift threshold behavior: verification of 0.5% drift held at 0.00 adjustments under 1.0% threshold, inclusive boundary behavior, and custom thresholds ($0.002$).
  - Five golden persona hand-calculated scenarios (Retired Capital Preservation, Mid-Career Balanced, Early-Career Growth, All-Cash, Empty Portfolio).
- `backend/tests/contract/test_suitability_api.py` (11 API contract tests):
  - OpenAPI schema presence and response structure validation.
  - Public access to `/allocation` and `/allocation/{category}`.
  - Authentication enforcement on `/rebalance` (401 on missing token).
  - Multi-tenant isolation (404 on attempting to rebalance another user's `portfolio_id`).
  - Validation error handling (400 on duplicate asset classes, non-finite weights, invalid totals).

### 11.2 Verification Results
- **Unit & Contract Suite:** 47 / 47 PASSED in 5.34s.
- **Risk Scoring Suite:** 43 / 43 PASSED in 0.68s.
- **Static Analysis:** `ruff check .` (0 errors), `ruff format --check .` (clean), `mypy` (0 type issues).
- **GitHub Actions CI:** 18 / 18 automated check runs succeeded on PR #160 (`f3aff3d`).

---

## 12. Security and Privacy Considerations

1. **Authentication & Authorization:** All personalized endpoints (`POST /api/v1/suitability/rebalance`) enforce strict bearer JWT authentication via `Depends(get_current_user)`. Unauthenticated requests are rejected with HTTP 401.
2. **Multi-Tenant User Isolation:** When `portfolio_id` is supplied, the engine resolves holdings via `portfolio_service.get_portfolio_summary(portfolio_id, user_id)`. The user identity is extracted strictly from the cryptographic JWT claims, never from caller-controlled request bodies. Cross-tenant access attempts return HTTP 404 `PORTFOLIO_NOT_FOUND`, preventing resource enumeration and data leakage.
3. **Injection & Input Hardening:** Pydantic models enforce `extra="forbid"`. Asset class identifiers are sanitized and normalized (`strip().upper()`). Non-finite numeric payloads (`NaN`, `sNaN`, `+Inf`, `-Inf`) are rejected immediately before arithmetic processing.
4. **Zero PII Exposure:** Suitability calculations consume and emit purely quantitative asset weights, categories, and amounts. No personally identifiable information (PII) is stored or logged. Error responses return structured FinEx error envelopes without database queries or stack traces.

---

## 13. Scalability and Performance Considerations

1. **Algorithmic Complexity:**
   - Drift and rebalance evaluation operates in $O(K \log K)$ time, where $K$ is the number of distinct asset classes. Because $K \le 10$ in practice (typically $K = 3$), calculation execution completes in under 1 millisecond.
   - Space complexity is $O(K)$, creating minimal garbage collection overhead.
2. **Database Access Efficiency:**
   - Live portfolio evaluations perform exactly two read queries (`get_portfolio_by_id` and `list_holdings`), avoiding N+1 query patterns.
   - Suitability evaluations perform zero database write operations, eliminating transaction lock contention.
3. **Asynchronous & Stateless Architecture:**
   - The engine is instantiated as a stateless singleton (`suitability_service`). It is thread-safe and capable of handling high-concurrency requests across ASGI worker processes.
4. **Production Benchmarking Note:**
   - While algorithmic complexity is asymptotically minimal and verified locally, large-scale concurrent load testing (> 10,000 requests/sec) has not been benchmarked in staging environments.

---

## 14. Data Handling and Model Boundaries

```
[User Request]
      │
      ▼
[FastAPI Router /api/v1/suitability] ── (Validates JWT & extra="forbid" Schemas)
      │
      ├───────────────────────────────┐
      │ (Public Reference)            │ (Authenticated Portfolio Rebalance)
      ▼                               ▼
[resolve_risk_category]         [portfolio_service.get_portfolio_summary]
      │                               │ (Enforces user_id ownership; 404 if invalid)
      │                               ▼
      ├───────────────────────> [SuitabilityService]
      │                               │
      │                               ├─ 1. Exact Weight Normalization (10^-6)
      │                               ├─ 2. Signed Drift Computation (w_curr - w_target)
      │                               ├─ 3. Threshold Action Classification (BALANCED/HOLD)
      │                               └─ 4. Rebalance Adjustment & Cent Conservation
      ▼                               │
[TargetAllocationResponse]            ▼
                                [SuitabilityRebalanceResponse]
                                      │
                                      ▼
                        (Emits EDUCATIONAL_DISCLAIMER)
```

- **Boundary Enforcement:** The Suitability Engine is purely an analytical layer. It has no access to order execution gateways, payment rails, or external broker APIs.
- **Model Isolation:** Scoring logic resides in `ai.risk` and reference allocations reside in `suitability_service`. There is no coupling to non-deterministic LLM prompt pipelines.

---

## 15. Versioning and Maintenance

- **Current Version:** `v1.0.0`
- **Deprecation Policy:** Any change to target allocation weights, canonical risk categories, boundary thresholds, or model codes requires a major version increment (e.g. `v2.0.0`) and migration documentation.
- **Audit Schedule:** Model weights and proxy benchmarks must be reviewed annually against FinEx Investment Committee educational guidelines.

---

## 16. References

1. FinEx Master Product, Design and Delivery Handbook v9.1 (Sprint 3 Delivery Architecture).
2. FinEx Final Implementation Plan & Updated Assignments (`S3-LI01`, `S3-MI01`).
3. GitHub Issue [#53](https://github.com/Mrugankkakade17-svg/Finex/issues/53) — Suitability Engine Implementation.
4. GitHub Pull Request [#160](https://github.com/Mrugankkakade17-svg/Finex/pull/160) — Suitability Engine Implementation & Corrections.
5. GitHub Issue [#54](https://github.com/Mrugankkakade17-svg/Finex/issues/54) — Suitability Model Card & Disclaimers.
6. S3-MR01 Database Migration `fx_006` — Reference Allocation Models & Benchmark Map.
7. S3-PA01 Portfolio Analytics Engine (`app/services/portfolio_analytics_service.py`).
8. S2-DAT-02 Risk Questionnaire v1 Specification (`backend/data/questionnaire/risk_questionnaire_v1.json`).
