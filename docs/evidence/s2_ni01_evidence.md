# S2-NI01 Verification Evidence

- **Task ID:** `S2-NI01`
- **Sprint:** Sprint 2: Real market data, watchlist, paper trading
- **Branch:** `feature/s2-ni01` (branched from `dev` at `ff4dd15`)
- **Assignee:** Nilisha (`@NilishaBhole`)
- **Reviewer:** Payal (`@payalmude14-star`)
- **Pre-requisites:** `S2-PA03` (#39 / PR #145)

## 1. Summary of Changes

1. **[frontend-react/src/types/market.ts](../../frontend-react/src/types/market.ts)**
   - Extended `DataStatus` to include all FinEx freshness states (`LIVE`, `DELAYED`, `END_OF_DAY`, `CACHED`, `MARKET_CLOSED`, `STALE`, `UNAVAILABLE`).
   - Added `DataFreshness` (`{ status, source, as_of, fetched_at, reason? }`), `MarketMode` (`'fixture' | 'api'`), `MarketServiceConfig`, `normalizeDataStatus()`, and `getFreshnessBadgeMeta()` (`FRESHNESS_BADGE_META`) styled for the FinEx Good Money Energy palette.
   - Extended `MarketQuote` and `WatchlistItem` while keeping backward compatibility with all existing fields.

2. **[frontend-react/src/services/marketService.ts](../../frontend-react/src/services/marketService.ts)**
   - Preserved all existing `marketService` method names and signatures: `search`, `getQuote`, `getWatchlist`, `addToWatchlist`, `removeFromWatchlist`.
   - Routed API mode calls through the shared `S1-NI01` client (`apiClient.ts`: `finexApiClient` / `createApiClient` / `getApiBaseUrl`) with Bearer token forwarding and `AbortController` timeouts.
   - Wired API mode to:
     - `GET /api/v1/market/instruments?query=...` (`S2-PA03`)
     - `GET /api/v1/market/quotes/{symbol}` (`S2-PA01` `MarketQuoteResponse` & `DataFreshness`, enforcing that `yfinance` never emits `LIVE` and degrading provider/network errors to `UNAVAILABLE` without fabricating prices)
     - `GET /api/v1/watchlists`, `GET /api/v1/watchlists/{watchlist_id}/items`, `PUT /api/v1/watchlists/{watchlist_id}/items/{instrument_id}`, `DELETE /api/v1/watchlists/{watchlist_id}/items/{instrument_id}` (and flat `/api/v1/watchlists` fallback)
   - Kept deterministic `fixture` mode (`REACT_APP_MARKET_MODE`, defaulting to `fixture`) with US, NSE (`.NS`), BSE (`.BO`), and outage (`DOWN`) fixtures covering `CACHED`, `DELAYED`, `END_OF_DAY`, `MARKET_CLOSED`, `STALE`, and `UNAVAILABLE`.

3. **[frontend-react/src/pages/MarketPage.tsx](../../frontend-react/src/pages/MarketPage.tsx)**
   - Added true freshness status badge (`data-testid="quote-freshness-badge"`, `data-status`) in the quote header (`Live`, `Delayed`, `End of day`, `Cached`, `Market closed`, `Stale`, `Unavailable`).
   - Added `ANALYTICAL` capability & mode badge (`data-testid="market-mode-badge"`), exchange + currency labels in search results, `DataFreshness` source/timestamp/reason details, honest unavailable rendering (never showing a fake `0.00` price when `UNAVAILABLE`), and safe watchlist-add busy/error handling.

4. **[frontend-react/src/pages/WatchlistPage.tsx](../../frontend-react/src/pages/WatchlistPage.tsx)**
   - Added per-item freshness status badges (`data-testid="watchlist-freshness-badge-<SYMBOL>"`, `data-status`) resolved from `/watchlists` items or `marketService.getQuote(item.symbol)`.
   - Displayed truthful price or `"Price unavailable"`, source and `as_of` timestamp, `ANALYTICAL` label, loading/empty/error/retry states, and safe remove busy/error state.

5. **Unit & Component Tests**
   - Updated [frontend-react/src/services/marketService.test.ts](../../frontend-react/src/services/marketService.test.ts)
   - Updated [frontend-react/src/pages/MarketPage.test.tsx](../../frontend-react/src/pages/MarketPage.test.tsx)
   - Updated [frontend-react/src/pages/WatchlistPage.test.tsx](../../frontend-react/src/pages/WatchlistPage.test.tsx)

## 2. Quality & Test Commands Executed

Executed from `frontend-react/`:

```powershell
npm.cmd ci
npx.cmd tsc --noEmit
npm.cmd run build
npm.cmd test -- --watchAll=false --runInBand --testMatch=**/src/**/*.test.{ts,tsx}
```

### Observed Output

- **TypeScript (`npx.cmd tsc --noEmit`):** Exited with code `0`.
- **Production build (`npm.cmd run build`):**
  - `Compiled successfully.`
  - `build/static/js/main.24bf92b5.js` (`104.86 kB` gzip)
  - `build/static/css/main.21c9d311.css` (`6.04 kB` gzip)
- **Full React test suite (`npm.cmd test -- --watchAll=false --runInBand --testMatch=**/src/**/*.test.{ts,tsx}`):**
  - `Test Suites: 28 passed, 28 total`
  - `Tests: 781 passed, 781 total`
  - `Snapshots: 0 total`
  - `Time: 45.885 s`

*(Note: `--testMatch=**/src/**/*.test.{ts,tsx}` was passed locally because the scratch clone path includes `.gemini`, which Jest's default `<rootDir>` glob skips; `--runInBand` matches the repository's serial React validation runbook to avoid parallel worker timeout contention on `App.s2.journey.test.tsx`.)*
