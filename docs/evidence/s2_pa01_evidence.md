# S2-PA01 — DataFreshness schema and provider chain evidence

- **Task ID:** `S2-PA01`
- **Sprint:** Sprint 2: Deterministic Risk Contract & Portfolio Allocation (Milestone #3)
- **Branch:** `feature/s2-pa01`
- **Target Branch:** `dev`
- **Assignee:** Payal (`payalmude14-star`)
- **Secondary Reviewer:** Mrugnak (`@Mrugankkakade17-svg`)
- **Status:** Verified. All schemas, adapters, provider chain, circuit breaker, rate limiter, and test contracts pass.

---

## 1. Architectural Implementation

### Files Created & Modified
1. `backend/app/schemas/market.py` (New):
   - `DataFreshness` enum (`LIVE`, `DELAYED`, `END_OF_DAY`, `CACHED`, `UNAVAILABLE`).
   - `CircuitState` enum (`CLOSED`, `OPEN`, `HALF_OPEN`).
   - `MarketQuoteResponse` schema with Pydantic `@field_validator("freshness")` strictly enforcing the invariant: **no path can emit LIVE for yfinance**.
   - `BatchQuotesResponse`, `ProviderHealth`, and `SecuritySearchResult` models.
2. `backend/app/adapters/yfinance_adapter.py` (Extended):
   - Integrated `CircuitBreaker` (three-state fault tolerance) and `RateLimiter` (sliding-window throttling).
   - Added `FixtureMarketDataProvider` implementing the canonical `MarketDataProvider` port for reliable fallback.
   - Hardened `YFinanceMarketDataProvider` ensuring quotes are always tagged stale/delayed and never LIVE.
3. `backend/app/services/market_service.py` (New):
   - `MarketService(MarketDataProvider)` coordinating the multi-provider fallback chain (`yfinance` primary $\rightarrow$ `fixture` fallback).
   - Automatic provider failover on `ProviderTimeoutException`, `ProviderUnavailableException`, `RateLimitExceededException`, or `CircuitBreakerOpenException`.
   - Truthful degraded `UNAVAILABLE` state response when the entire chain fails.
   - Diagnostic health and circuit breaker status inspection via `get_health()`.
4. `backend/tests/unit/test_s2_pa01_market_freshness.py` (New):
   - 12 comprehensive unit and contract tests verifying circuit breaker transitions, rate limits, provider failovers, timeout fallbacks, UNAVAILABLE responses, and strict non-LIVE invariants.

---

## 2. Acceptance Criteria Verification

### Criterion 1: Timeout, Next Provider, and UNAVAILABLE with Recorded Responses

#### Scenario A: Timeout Fallback to Next Provider
When the primary provider (`yfinance`) times out, the chain catches `ProviderTimeoutException`, increments the provider's circuit breaker failure count, and automatically falls back to `FixtureMarketDataProvider`.

**Recorded Response:**
```json
{
  "symbol": "AAPL",
  "price": 227.16,
  "currency": "USD",
  "change": 1.5,
  "change_pct": 0.75,
  "source": "fixture",
  "as_of": "2026-11-23T01:23:45.000000+00:00",
  "fetched_at": "2026-11-23T01:23:45.000000+00:00",
  "freshness": "CACHED",
  "is_stale": false,
  "error": null
}
```
*Result:* **PASS** — Failover verified; source is `fixture`, freshness is `CACHED`.

#### Scenario B: Provider Unavailable Fallback
When primary provider raises `ProviderUnavailableException`, the chain advances to the next provider.

**Recorded Response:**
```json
{
  "symbol": "MSFT",
  "price": 505.12,
  "currency": "USD",
  "change": 2.3,
  "change_pct": 0.46,
  "source": "fixture",
  "freshness": "CACHED",
  "is_stale": false,
  "error": null
}
```
*Result:* **PASS** — Clean failover verified.

#### Scenario C: All Providers Fail $\rightarrow$ Truthful UNAVAILABLE Response
When both primary (`yfinance`) and secondary (`fixture`) providers fail (e.g. timeout + unavailable):

**Recorded Response (without fallback):**
```json
{
  "symbol": "AAPL",
  "price": null,
  "currency": "USD",
  "change": 0.0,
  "change_pct": 0.0,
  "source": "none",
  "as_of": null,
  "fetched_at": "2026-11-23T01:23:45.000000+00:00",
  "freshness": "UNAVAILABLE",
  "is_stale": true,
  "error": "All market providers in chain failed or unavailable: yfinance: Market-data provider 'yfinance' timed out after 1.5 seconds.; fixture: Market-data provider 'fixture' is unavailable: fixture provider is unavailable"
}
```

**Recorded Response (with cost-basis fallback price):**
```json
{
  "symbol": "AAPL",
  "price": 150.0,
  "currency": "USD",
  "change": 0.0,
  "change_pct": 0.0,
  "source": "none",
  "as_of": null,
  "fetched_at": "2026-11-23T01:23:45.000000+00:00",
  "freshness": "UNAVAILABLE",
  "is_stale": true,
  "error": "All market providers in chain failed or unavailable..."
}
```
*Result:* **PASS** — Truthful degradation to `UNAVAILABLE` verified without inventing live prices.

---

### Criterion 2: No Path Can Emit LIVE for yfinance

Strict invariant enforcement:
1. `YFinanceMarketDataProvider.get_quote()` always returns `is_stale=True`.
2. `MarketService.get_quote_with_freshness()` maps all yfinance responses to `DataFreshness.DELAYED`, never `LIVE`.
3. `MarketQuoteResponse` contains a Pydantic `@field_validator("freshness")` that rejects any schema instantiation where `source` contains `yfinance` and `freshness == DataFreshness.LIVE`:
   ```python
   # Raises ValidationError:
   # "Contract violation: yfinance provider is never permitted to emit LIVE data."
   ```
*Result:* **PASS** — Proved by tests `test_yfinance_adapter_never_emits_live_freshness`, `test_market_service_yfinance_quotes_emit_delayed_never_live`, and `test_schema_validator_rejects_live_freshness_for_yfinance`.

---

## 3. Quality & Test Execution

### Static Analysis
```powershell
cd backend
python -m ruff check .
```
**Result:** **PASS** — All checks passed!

### Targeted Unit & Contract Tests
```powershell
cd backend
python -m pytest tests/test_yfinance_adapter.py tests/unit/test_s2_pa01_market_freshness.py --no-cov -v
```
**Result:** **PASS** — 15 passed in 1.80s:
- `test_known_quote_is_deterministic_and_stale` PASSED
- `test_unknown_quote_uses_explicit_fallback_or_fails` PASSED
- `test_configured_failure_modes_have_typed_errors` PASSED
- `test_circuit_breaker_closed_to_open_transition` PASSED
- `test_circuit_breaker_open_to_half_open_and_recovery` PASSED
- `test_circuit_breaker_half_open_failure_re_trips_to_open` PASSED
- `test_rate_limiter_permits_within_limit_and_blocks_when_exceeded` PASSED
- `test_yfinance_adapter_never_emits_live_freshness` PASSED
- `test_market_service_yfinance_quotes_emit_delayed_never_live` PASSED
- `test_schema_validator_rejects_live_freshness_for_yfinance` PASSED
- `test_acceptance_timeout_falls_back_to_next_provider` PASSED
- `test_acceptance_provider_unavailable_falls_back_to_next_provider` PASSED
- `test_acceptance_all_providers_fail_returns_unavailable_recorded_response` PASSED
- `test_market_service_port_contract_raises_on_unavailable_without_fallback` PASSED
- `test_market_service_batch_quotes_and_health` PASSED

### Full Test Suite
- `pytest -q -m "not postgres"`: 2,792 passed (45 failures isolated to Windows host PowerShell script execution policy on `.ps1` files, matching baseline).

---

## 4. Definition of Done Verification

| Requirement | Status | Notes |
|---|---|---|
| Committed to `feature/s2-pa01` | **PASS** | Branch created from `origin/dev` |
| Zero breaking changes to frozen routes | **PASS** | Existing API routes and signatures unchanged |
| User isolation verified | **PASS** | Market services are stateless/symbol-scoped; no cross-user data leakage |
| Empty / error states handled | **PASS** | `UNAVAILABLE` state gracefully handled with recorded error messages |
| No secrets committed | **PASS** | Zero credentials or keys in source |
| Peer review assigned | **PASS** | Secondary Reviewer: Mrugnak (`@Mrugankkakade17-svg`) |
