# S2-NI03 Verification Evidence

- **Task ID:** `S2-NI03`
- **Sprint:** Sprint 2: Real market data, watchlist, paper trading
- **Assignee:** Nilisha (`@NilishaBhole`)
- **Reviewer:** Payal (`@payalmude14-star`)
- **Pre-requisites:** `S2-PA04` (#40) — `/api/v1/paper/account`, `/api/v1/paper/positions`, `/api/v1/paper/orders`
- **Branch:** `feature/s2-ni03` (branched from `origin/dev` at `16568b6`)

## 1. Summary of Changes

1. **[frontend-react/src/pages/PaperTradingPage.tsx](../../frontend-react/src/pages/PaperTradingPage.tsx)**
   - Wired `PaperTradingPage` to the authenticated `S2-PA04` backend endpoints via `finexApiClient` (`createPaperTradingApi`):
     - `GET /api/v1/paper/account` for virtual cash balance, portfolio value, total equity, open positions, and account ID.
     - `GET /api/v1/paper/orders?limit=20` for the append-only paper order & cash ledger.
     - `POST /api/v1/paper/orders` with strict schema payload `{ instrument_id, exchange, side, quantity, idempotency_key }` and `Authorization: Bearer <token>` resolution (`getActiveAuthSession()?.access_token` / `sessionStorage.getItem('finex_access_token')`).
   - Added an always-visible `SIMULATED` banner (`data-testid="paper-simulated-banner"`) and header badge (`data-testid="paper-simulated-badge"`) clearly separating simulated balances from manual portfolios and real funds.
   - Implemented **Virtual Cash Account** summary (`cash_balance`, `portfolio_value`, `total_equity`, `Reload account`), **Order Ticket** (`BUY`/`SELL`, symbol, `NASDAQ`/`NYSE` exchange selector, positive integer quantity validation `1..100,000`), **Simulated Positions** table (`instrument_id`, `exchange`, `quantity`, `average_cost`, `last_price`, `market_value`, `unrealized_pnl`), and **Simulated Order & Cash Ledger** table (`created_at`, `order_id`, `side`, `instrument_id`, `exchange`, `quantity`, `executed_price`, `notional`, `fee`, `cash_delta`, `quote_freshness`, `status`).
   - Enforced double-click safety and idempotency:
     - Synchronous in-flight mutex (`submittingRef`) + disabled submit state prevents duplicate concurrent submissions on rapid double-click.
     - Stable `idempotency_key` per order signature is reused across retryable failures (`REQUEST_TIMEOUT`, `API_UNAVAILABLE`, `QUOTE_UNAVAILABLE`, `PAPER_STORE_UNAVAILABLE`) and rotated only after confirmed fill/replay or terminal non-retryable rejection (`409`/`422`).
   - Handled loading (`paper-loading`), load error with retry (`paper-load-error`), non-destructive post-order refresh warning (`paper-refresh-warning`), empty positions (`paper-positions-empty`), and empty ledger (`paper-ledger-empty`) states without fabricating balances.

2. **[frontend-react/src/pages/PaperTradingPage.test.tsx](../../frontend-react/src/pages/PaperTradingPage.test.tsx)**
   - Added 8 unit & component tests covering:
     - `SIMULATED` banner visibility across loading, error, and loaded states (and no fabricated `$10,000.00` balance on load failure).
     - Empty positions and empty ledger states.
     - `BUY` order execution and state persistence across unmount/remount reload.
     - Rapid double-click dispatching only one `placeOrder` call while in flight.
     - Stable `idempotency_key` reuse on transient timeout retry and key rotation after fill.
     - Client-side validation for invalid symbol and out-of-range/non-integer quantity.
     - `SELL` order execution and `INSUFFICIENT_POSITION` error handling.
     - Full HTTP envelope contract verification through `createPaperTradingApi` + `createApiClient` (`Bearer` header, `201` fill, `200` idempotent replay, `409 MARKET_CLOSED`).

## 2. Acceptance Criteria Verification

- [x] **State persists after reload:** Account, positions, and order ledger are fetched from `/api/v1/paper/account` and `/api/v1/paper/orders` on mount and after every fill; verified across unmount/remount in `PaperTradingPage.test.tsx`.
- [x] **Double-click gives one order:** Protected by synchronous `submittingRef` lock, disabled button state, and stable `idempotency_key` generation/reuse; verified by both rapid double-click and retry/replay tests.
- [x] **SIMULATED banner, account, ticket, positions, ledger wired:** All five sections implemented and verified.

## 3. Verification Commands & Observed Output

Executed from `frontend-react/`:

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
npm.cmd test -- --watchAll=false --runInBand
```

### Results

- **TypeScript check (`npx.cmd tsc --noEmit`):**
  - Exited with code `0` (no errors).
- **Production build (`npm.cmd run build`):**
  - `Compiled successfully.`
  - `build\static\js\main.b675cfa7.js` (`111.43 kB` gzip)
  - `build\static\css\main.7783a283.css` (`6.61 kB` gzip)
- **Full Jest test suite (`npm.cmd test -- --watchAll=false --runInBand`):**
  - `Test Suites: 31 passed, 31 total`
  - `Tests:       813 passed, 813 total`
  - `Snapshots:   0 total`
  - `Time:        72.974 s`
