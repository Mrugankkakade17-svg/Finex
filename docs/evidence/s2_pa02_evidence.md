# S2-PA02 — Second provider and last-good-value evidence

- **Task ID:** `S2-PA02`
- **Sprint:** Sprint 2
- **Branch:** `feature/s2-pa02`
- **Dependency:** S2-PA01

## Delivered

- Added an explicit `SecondaryMarketDataProvider` adapter in `backend/app/adapters/yfinance_adapter.py`.
- Exported the adapter through `backend/app/adapters/market/`.
- Updated the default `MarketService` chain to use `yfinance` followed by `secondary`.
- Added a per-symbol last-good-value cache to `MarketService`.
- A cache hit within 60 seconds is returned as `CACHED`.
- A cache hit from 60 to 300 seconds old is returned as `STALE`.
- Older entries are discarded and the chain may return `UNAVAILABLE`.
- Cached responses include the original quote timestamp and fetched timestamp.

## Review contract

The last-good-value fallback is only used after all configured providers fail. It never
replaces a live or delayed provider result. Unsupported symbols are not cached.
Only finite, positive, non-stale provider prices may enter the cache. Cached port quotes
retain the original `as_of` timestamp; missing or invalid prices are never converted to
zero. The secondary adapter identifies itself as `secondary` in instance state and errors.

## Reviewer follow-up

The review fixes add permanent coverage for the 60-second and 300-second boundaries,
expiry eviction, an empty cache after first-request provider failures, per-symbol
isolation, zero/negative/non-finite price rejection, stale-write protection, and cached
observation timestamp preservation. See
`backend/tests/unit/test_s2_pa02_market_fallback.py` and the updated S2-PA01 freshness
tests.

## Verification

Run from `backend/`:

```text
python -m ruff check .
python -m pytest tests/test_yfinance_adapter.py tests/unit/test_s2_pa01_market_freshness.py tests/unit/test_s2_pa02_market_fallback.py --no-cov -q
```

**Result:** 20 targeted tests passed.

Those results are from the original PR commit. The reviewer follow-up tests should be
run with the commands above after installing the documented Python 3.13 backend
environment.

Full non-PostgreSQL suite:

```text
2804 passed, 45 failed, 7 skipped, 9 deselected, 5 xfailed, 2 xpassed
```

The 45 failures were existing Windows launcher/script-policy tests because local
PowerShell blocks `.ps1` execution (`UnauthorizedAccess` / execution policy), not
market-adapter failures.
