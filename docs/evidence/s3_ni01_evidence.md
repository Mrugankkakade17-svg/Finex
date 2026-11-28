# S3-NI01 Verification Evidence

- **Task ID:** `S3-NI01`
- **Sprint:** Sprint 3: Portfolio intelligence, suitability, goals and spending (Milestone #4)
- **Assignee:** Nilisha (`@NilishaBhole`)
- **Secondary Reviewer:** Payal (`@payalmude14-star`)
- **Pre-requisites:** `S3-PA01` (#50) — `GET /api/v1/portfolios/{portfolio_id}/analytics`
- **Branch:** `feature/s3-ni01` (branched from `origin/dev` at `f3aff3d`)

## 1. Summary of Changes

1. **[frontend-react/src/services/portfolioApi.ts](../../frontend-react/src/services/portfolioApi.ts)**
   - Defined the unified `PortfolioApi` interface (`listPortfolios`, `getPortfolio`, `listHoldings`, `getAnalytics`) along with normalized TypeScript contracts (`PortfolioRecord`, `PortfolioHoldingRecord`, `PortfolioAnalytics`, `PortfolioAnalyticsQuery`, `PortfolioApiError`).
   - Implemented `fetchPortfolioCapabilities`, `choosePortfolioBackendMode`, and `resolvePortfolioApi` to query `GET /api/v1/capabilities` and select `'local'` vs `'postgres'` mode cleanly without breaking local-persona sessions.
   - Implemented `createPostgresPortfolioApi` calling `/api/v1/portfolios`, `/api/v1/portfolios/{id}`, `/api/v1/portfolios/{id}/holdings`, and `/api/v1/portfolios/{id}/analytics` with `Authorization: Bearer <token>`, query parameter normalization (`benchmark`, `top_n`, `confidence_level`), timeout/cancellation handling, and strict envelope decoding.
   - Implemented `createLocalPortfolioApi` and `mapLocalMetricsToAnalytics` adapting `LocalS2Capabilities` (`domain.metrics`) honestly: snapshot concentration (`current_value`, `hhi`, `top_holdings`) and limitations are preserved, while history-dependent metrics (`returns`, `annualized_volatility`, `sharpe_ratio`, `beta`, `value_at_risk`) remain `null` (`INSUFFICIENT_DATA`) rather than being fabricated.

2. **[frontend-react/src/components/PortfolioAnalyticsPanel.tsx](../../frontend-react/src/components/PortfolioAnalyticsPanel.tsx)**
   - Built the reusable `PortfolioAnalyticsPanel` consuming `PortfolioApi`.
   - Displays the `ANALYTICAL` capability label, backend mode badge (`PostgreSQL Analytics` vs `Local SQLite Snapshot`), and analytics status badge (`COMPLETE` / `INSUFFICIENT_DATA`).
   - Provides interactive controls (`Benchmark`, `VaR confidence` 95%/99%, `Top holdings` 3/5/10, and `Refresh analytics`) when `api.supportsHistoricalAnalytics` is enabled.
   - Renders KPI cards (Current Value, HHI with concentration tier, Cumulative/Annualized/Daily Mean Returns, Annualized Volatility, Sharpe Ratio with risk-free rate source & as-of date, Beta vs benchmark, 1-day Historical & Parametric VaR), a Recharts `BarChart` + accessible table for top holdings weights, and assumptions/limitations disclosures.
   - Handles empty (`portfolioId === null`), loading, error + retry, and `INSUFFICIENT_DATA` states without inventing unavailable figures.

3. **[frontend-react/src/pages/LocalPortfolioPage.tsx](../../frontend-react/src/pages/LocalPortfolioPage.tsx)**
   - Preserved the existing local manual portfolio CRUD, reconciliation, `MetricsView`, and `useLocalS2Tasks` flow unchanged when signed in with a local persona (`localUser !== null`), while embedding `PortfolioAnalyticsPanel` backed by `createLocalPortfolioApi`.
   - Added `/api/v1/capabilities`-driven PostgreSQL portfolio, holdings, and `PortfolioAnalyticsPanel` rendering when `localUser === null`.
   - Kept all local-mode parity tests completely untouched.

4. **Unit & Component Tests**
   - **[frontend-react/src/services/portfolioApi.test.ts](../../frontend-react/src/services/portfolioApi.test.ts):** 6 tests covering `/api/v1/capabilities` mode selection, `PostgresPortfolioApi` HTTP contracts and error mapping, and `LocalPortfolioApi` honest `PortfolioMetrics` mapping.
   - **[frontend-react/src/components/PortfolioAnalyticsPanel.test.tsx](../../frontend-react/src/components/PortfolioAnalyticsPanel.test.tsx):** 8 tests covering empty/loading/error/retry states, `COMPLETE` Postgres analytics rendering, interactive query updates, `INSUFFICIENT_DATA` partial concentration fallback, local snapshot mode rendering, and `LocalPortfolioPage` capabilities-driven Postgres vs local routing.

## 2. Acceptance Criteria Verification

- [x] `src/components/PortfolioAnalyticsPanel.tsx` implemented and wired via `PortfolioApi` interface (`src/services/portfolioApi.ts`) in `LocalPortfolioPage.tsx`.
- [x] Local vs Postgres backend selected from `/api/v1/capabilities` (`resolvePortfolioApi` / `choosePortfolioBackendMode`).
- [x] Local-mode parity tests untouched (`localS2PortfolioParity.test.ts`, `localS2NativeParity.test.ts`, `localS1ContractParity.test.ts`, `localS2RiskObservedParity.test.ts`, `App.s2.http.test.tsx`, `App.s2.journey.test.tsx`, `App.s2.test.tsx` all unmodified and passing).

## 3. Verification Commands & Observed Output

Executed from `frontend-react/`:

```powershell
npx.cmd tsc --noEmit
$env:CI="true"
npm.cmd test -- --watchAll=false
npm.cmd run build
```

### Results

- **TypeScript check (`npx.cmd tsc --noEmit`):**
  - Exited with code `0` (0 errors).
- **Full Jest test suite (`CI=true npm.cmd test -- --watchAll=false`):**
  - `Test Suites: 34 passed, 34 total`
  - `Tests:       833 passed, 833 total`
  - `Snapshots:   0 total`
  - `Time:        53.008 s`
  - Includes all existing local-mode parity tests (`localS1ContractParity.test.ts`, `localS2Models.test.ts`, `localS2Client.test.ts`, `localS2PortfolioParity.test.ts`, `localS2RiskObservedParity.test.ts`, `localS2NativeParity.test.ts`, `App.s2.http.test.tsx`, `App.s2.test.tsx`, `App.s2.journey.test.tsx`) plus `portfolioApi.test.ts` and `PortfolioAnalyticsPanel.test.tsx`.
- **Production build (`CI=true npm.cmd run build`):**
  - `Compiled successfully.`
  - `build\static\js\main.63156172.js` (`226.3 kB` gzip)
  - `build\static\css\main.7783a283.css` (`6.61 kB` gzip)

Executed from `backend/` (no backend files modified in this task):

```powershell
python -m ruff check .
python -m pytest tests/unit/test_portfolio_analytics_service.py -q --no-cov
```

- **Backend Ruff (`python -m ruff check .`):** `All checks passed!`
- **Backend Portfolio Analytics Unit Tests:** `11 passed in 0.54s`
