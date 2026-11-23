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

## Verification

Run from `backend/`:

```text
python -m ruff check .
python -m pytest tests/test_yfinance_adapter.py tests/unit/test_s2_pa01_market_freshness.py --no-cov -q
```

**Result:** 20 targeted tests passed.

Full non-PostgreSQL suite:

```text
2804 passed, 45 failed, 7 skipped, 9 deselected, 5 xfailed, 2 xpassed
```

The 45 failures were existing Windows launcher/script-policy tests because local
PowerShell blocks `.ps1` execution (`UnauthorizedAccess` / execution policy), not
market-adapter failures.
