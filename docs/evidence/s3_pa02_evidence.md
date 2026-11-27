# S3-PA02 FX series and valuation evidence

## Contract

`backend/app/services/fx_service.py` provides a deterministic, injected FX series. A rate represents one unit of its base currency in its quote currency. The series selects the latest observation whose date is on or before the requested valuation date. Conversion supports direct and inverse quotes and returns the applied rate, rate ID, source, as-of date, freshness label, and inversion flag. When both quote directions are available, the newer eligible observation is selected; inverse amounts divide by the original quote to avoid reciprocal-rounding loss. FX freshness labels are restricted to non-live `DataFreshness` values. No network provider, persistence, or route is introduced. One no-op Alembic merge migration joins the current branch heads without changing schema, and the Postgres workflow now fails if `alembic upgrade head` fails.

## Verification

Unit coverage is in `backend/tests/unit/test_fx_service.py`: direct USD→INR valuation, inverse INR→USD valuation and division precision, newer direct/inverse selection, dated selection and ordered series access, identity conversion and same-currency lookup rejection, missing/future rates, duplicate IDs, malformed currencies, invalid/non-finite rates and amounts, non-live freshness validation, normalized/rejected labels, and rejection of `datetime` values for rate and valuation dates (including identity conversions).

- `python -m ruff check .` (from `backend`): passed (`All checks passed!`).
- `python -m pytest tests/unit/test_fx_service.py -q -o addopts=''` (from `backend`): 26 passed.
- `python -m alembic heads` (from `backend`): one head, `s3pa02_all_heads`.
- `python -m pytest -q` (from `backend`): 3,086 passed, 26 skipped, 2 xfailed, 2 xpassed, 45 failed; 2,337 warnings. All reported failures are outside the FX service, in `tests/test_local_launcher_boundary.py` (4), `tests/unit/test_owned_s2_acceptance_launcher.py` (34), and `tests/unit/test_s1_acceptance_launcher.py` (7).

The focused FX suite and Ruff pass. The full-suite failures are reported explicitly above and are confined to unrelated launcher tests.
