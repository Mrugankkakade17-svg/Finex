# S3-PA02 FX series and valuation evidence

## Contract

`backend/app/services/fx_service.py` provides a deterministic, injected FX series. A rate represents one unit of its base currency in its quote currency. The series selects the latest observation whose date is on or before the requested valuation date. Conversion supports direct and inverse quotes and returns the applied rate, rate ID, source, as-of date, freshness label, and inversion flag. Amount arithmetic uses `Decimal`; no network provider, persistence, route, or migration is introduced.

## Verification

Unit coverage is in `backend/tests/unit/test_fx_service.py`: direct USD→INR valuation, inverse INR→USD valuation, dated selection, identity conversion, missing/future rates, duplicate IDs, malformed currencies, invalid/non-finite rates, and rejection of `datetime` values for rate and valuation dates (including identity conversions).

- `.venv\\Scripts\\python -m ruff check .` (from `backend`): passed (`All checks passed!`).
- `.venv\\Scripts\\python -m pytest tests/unit/test_fx_service.py -q -o addopts=''` (from `backend`): 13 passed.
- `.venv\\Scripts\\python -m pytest -q` (from `backend`): 3,057 passed, 25 skipped, 2 xfailed, 2 xpassed, 43 failed; coverage 81.74%. The failures are in unrelated existing tests in `test_owned_s2_acceptance_launcher.py` (32), `test_s1_acceptance_launcher.py` (2), `test_s2_evidence_pair_validation.py` (4), and `test_verify_s3_foundation.py` (5). The FX tests passed in this run.

The complete backend suite was rerun after adding the date-only validation and regression tests. Its 43 failures are in launcher/evidence tests listed above; no FX test failed. The focused FX suite and Ruff both pass.
