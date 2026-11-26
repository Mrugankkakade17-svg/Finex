# S3-PA02 FX series and valuation evidence

## Contract

`backend/app/services/fx_service.py` provides a deterministic, injected FX series. A rate represents one unit of its base currency in its quote currency. The series selects the latest observation whose date is on or before the requested valuation date. Conversion supports direct and inverse quotes and returns the applied rate, rate ID, source, as-of date, freshness label, and inversion flag. Amount arithmetic uses `Decimal`; no network provider, persistence, route, or migration is introduced.

## Verification

Unit coverage is in `backend/tests/unit/test_fx_service.py`: direct USD→INR valuation, inverse INR→USD valuation, dated selection, identity conversion, missing/future rates, duplicate IDs, malformed currencies, and invalid/non-finite rates.

- `python -m ruff check .` (from `backend`): passed.
- `python -m pytest -q` (from `backend`): 3,105 passed, 25 skipped, 2 xfailed, 2 xpassed, 2 failed. Both failures are pre-existing SQLite concurrent schema-upgrade cases in `tests/unit/test_local_s3_schema.py` for prior schema versions `[1]` and `[2]`; the FX tests pass after fixes.
- `python -m pytest backend/tests/unit/test_fx_service.py -q -o addopts=''`: 10 passed.
- `python -m ruff check backend`: passed.

The first full run exposed two assertions in the new FX tests; the inverse precision expectation and missing inverse-rate error were corrected, and the focused suite now passes. The full suite was not rerun after those corrections; the SQLite concurrency failures remain the only unrelated failures observed in the full run.
