# S2-PA03 implementation evidence

- **Task:** S2-PA03 — Instrument master, search, OHLCV history, market calendar
- **Branch:** `feature/s2-pa03`
- **Target:** `dev`
- **Base:** `origin/dev` at `7f20f5a`

## Delivered

- Added `/api/v1/market/instruments` search across the existing
  `finex_dev.market.instruments` table, with a deterministic bootstrap catalogue
  fallback and exchange-derived currencies for NSE, BSE, NYSE, and NASDAQ.
- Added `/api/v1/market/instruments/{symbol}/ohlcv` daily history from the
  existing `finex_dev.market.prices` table. Rows are validated for positive
  prices, OHLC bounds, and nonnegative volume; missing ranges and database
  failures return explicit error envelopes.
- Added `/api/v1/market/calendar/{exchange}` with regular session hours and
  timezone-aware OPEN / MARKET_CLOSED status for NSE, BSE, NYSE, and NASDAQ.
- Added an idempotent instrument seed script. Registered the new router without
  changing existing route implementations.
- Added unit and HTTP contract tests for exchange-local session boundaries,
  search metadata, OHLCV loading, and route coexistence.

## Verification

Executed from `backend/`:

```text
python -m ruff check .
All checks passed!

python -m pytest -q
2833 passed, 15 skipped, 5 xfailed, 2 xpassed
Total coverage: 84.05% (required: 70%)
```

The two xpassed cases are existing expected-failure tests whose conditions did
not fail in this run. The suite emitted existing FastAPI deprecation warnings.

## Operational limits

- The existing market DDL has no holiday or early-close table. Calendar results
  model regular weekday sessions and can report OPEN on an exchange holiday.
- This check used mocked HTTP history rows and did not connect to Databricks.
  Seed execution and production warehouse behavior remain environment gates.
