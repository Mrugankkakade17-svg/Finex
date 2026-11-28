# S2-NI04 Verification Evidence

- **Task ID:** `S2-NI04`
- **Sprint:** Sprint 2: Real market data, watchlist, paper trading
- **Assignee:** Nilisha (`@NilishaBhole`)
- **Reviewer:** Mrugnak (`@Mrugankkakade17-svg`)
- **Pre-requisites:** `S2-NI01` (#45), `S2-NI03` (#47)
- **Branch:** `feature/s2-ni04` (branched from `feature/s2-ni03` at `faeae4e`, which builds on `origin/dev` at `16568b6`)

## 1. Summary of Changes

1. **Playwright Setup**
   - **[frontend-react/package.json](../../frontend-react/package.json)** & **[frontend-react/package-lock.json](../../frontend-react/package-lock.json)**
     - Added `@playwright/test` (`^1.65.1`) as a devDependency and `"test:e2e": "playwright test"` script.
   - **[frontend-react/playwright.config.ts](../../frontend-react/playwright.config.ts)**
     - Configured Chromium Playwright E2E runner targeting `./e2e` with serial execution (`workers: 1`), CI retries (`1`), trace/screenshot/video failure capture, and dual `webServer` orchestration (`node e2e/fixture-server.mjs` on `127.0.0.1:8010` + `npm start` on `127.0.0.1:3000` with `REACT_APP_FINEX_API_BASE_URL=http://127.0.0.1:8010`, `REACT_APP_MARKET_MODE=fixture`, `REACT_APP_ENABLE_REAL_AUTH=false`).
   - **[frontend-react/.gitignore](../../frontend-react/.gitignore)**
     - Ignored generated Playwright output directories (`test-results/`, `playwright-report/`, `blob-report/`, `playwright/.cache/`).

2. **Fixture Provider API Server & E2E 1 Journey (`frontend-react/e2e/`)**
   - **[frontend-react/e2e/fixture-server.mjs](../../frontend-react/e2e/fixture-server.mjs)**
     - Deterministic loopback HTTP fixture server implementing the FinEx API contracts for:
       - `POST /api/e2e/reset` & `GET /api/v1/health`
       - Local authentication & onboarding (`POST /api/v1/local-auth/mock-login`, `GET /api/v1/local-auth/me`, `POST /api/v1/local-auth/logout`, `GET /api/v1/local-onboarding/state`, `POST /api/v1/local-onboarding/consent`, `PUT /api/v1/local-onboarding/draft`, `POST /api/v1/local-onboarding/complete`)
       - Fixture market instruments & quotes (`GET /api/v1/market/instruments`, `GET /api/v1/market/quotes/{symbol}`)
       - Authenticated user-scoped watchlists (`GET/POST /api/v1/watchlists`, `GET/PUT/DELETE /api/v1/watchlists/{id}/items...`)
       - Authenticated user-scoped paper trading (`GET /api/v1/paper/account`, `GET /api/v1/paper/positions`, `GET/POST /api/v1/paper/orders` with deterministic `$50,000.00` virtual USD cash, `10` bps fee, idempotency replay/conflict checks, and `CACHED`/`DELAYED` fixture quotes).
   - **[frontend-react/e2e/e2e-1-core-journey.spec.ts](../../frontend-react/e2e/e2e-1-core-journey.spec.ts)**
     - Test 1 (`completes full primary journey: login -> search -> watchlist -> paper order`):
       - Signs in as synthetic persona `learner-a`, completes consent + profile onboarding, and navigates to `/dashboard`.
       - Searches `MSFT` on `/market` in `Fixture mode`, verifies `421.10 USD`, `data-status="CACHED"`, `yfinance-fixture` source, verifies outage symbol `DOWN` shows `UNAVAILABLE` without a fake `0.00 USD` price, and adds `MSFT` to the watchlist.
       - Navigates to `/watchlist` and confirms `AAPL` and `MSFT` render with `CACHED` freshness badges and `421.10 USD`.
       - Navigates to `/paper-trading`, verifies `SIMULATED` banner/badge and `$50,000.00 USD` virtual cash, submits a `BUY` order for `5` shares of `AAPL` on `NASDAQ` at fixture price `$227.16`, verifies fill confirmation, `$1.14` fee, `$48,863.06 USD` cash balance, `$1,135.80` portfolio value, `AAPL` position row, `FILLED` ledger row, and server persistence after navigating to `/dashboard`, returning to `/paper-trading`, and clicking `Reload account`.
     - Test 2 (`rejects unauthenticated paper trading access honestly without fabricating a balance`):
       - Verifies that without a bearer token in `sessionStorage`, `PaperTradingPage` displays the `SIMULATED` banner and `paper-load-error` alert without fabricating a cash balance.

3. **CI Workflow**
   - **[.github/workflows/frontend-react-e2e.yml](../../.github/workflows/frontend-react-e2e.yml)**
     - Runs on `push` and `pull_request` touching `frontend-react/**`, `.nvmrc`, or `.github/workflows/frontend-react-e2e.yml`.
     - Sets up Node from `.nvmrc`, runs `npm ci`, installs Playwright Chromium (`npx playwright install --with-deps chromium`), runs `npx playwright test` with `CI=true`, and uploads `frontend-react/playwright-report/` on failure.

## 2. Quality & Test Commands Executed

Executed from `frontend-react/`:

```powershell
$env:CI='true'
npx.cmd tsc --noEmit
npm.cmd run build
npm.cmd test -- --watchAll=false --runInBand
npx.cmd playwright test --reporter=list
```

### Observed Output

- **TypeScript (`npx.cmd tsc --noEmit`):** Exited with code `0`.
- **Production build (`npm.cmd run build` with `CI=true`):**
  - `Compiled successfully.`
  - `build\static\js\main.b675cfa7.js` (`111.43 kB` gzip)
  - `build\static\css\main.7783a283.css` (`6.61 kB` gzip)
- **Full Jest test suite (`npm.cmd test -- --watchAll=false --runInBand`):**
  - `Test Suites: 31 passed, 31 total`
  - `Tests:       813 passed, 813 total`
  - `Snapshots:   0 total`
  - `Time:        64.668 s`
- **Playwright E2E suite (`npx.cmd playwright test --reporter=list`):**
  - `Running 2 tests using 1 worker`
  - `ok 1 [chromium] › e2e\e2e-1-core-journey.spec.ts:11:3 › ... › completes full primary journey: login -> search -> watchlist -> paper order (17.1s)`
  - `ok 2 [chromium] › e2e\e2e-1-core-journey.spec.ts:127:3 › ... › rejects unauthenticated paper trading access honestly without fabricating a balance (9.8s)`
  - `2 passed (38.5s)`
