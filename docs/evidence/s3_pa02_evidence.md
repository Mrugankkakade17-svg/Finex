# S3-PA02 FX series and valuation evidence

## Contract

`backend/app/services/fx_service.py` provides a deterministic, injected FX series. A rate represents one unit of its base currency in its quote currency. The series selects the latest observation whose date is on or before the requested valuation date. Conversion supports direct and inverse quotes and returns the applied rate, rate ID, source, as-of date, freshness label, and inversion flag. When both quote directions are available, the newer eligible observation is selected; inverse amounts divide by the original quote to avoid reciprocal-rounding loss. FX freshness labels are restricted to non-live `DataFreshness` values. No network provider, persistence, route, or schema migration is introduced by S3-PA02. The current dev base provides the migration merge point; the duplicate S3-PA02 merge migration was removed. The Postgres workflow fails if `alembic upgrade head` fails.

## Verification

Unit coverage is in `backend/tests/unit/test_fx_service.py`: direct USD→INR valuation, inverse INR→USD valuation and division precision, newer direct/inverse selection, dated selection and ordered series access, identity conversion and same-currency lookup rejection, missing/future rates, duplicate IDs, malformed currencies, invalid/non-finite rates and amounts, non-live freshness validation, normalized/rejected labels, and rejection of `datetime` values for rate and valuation dates (including identity conversions).

- Ruff lint and format checks: passed.
- Mypy checks for Linux and Windows with Python 3.13: passed.
- `python -m pytest tests/unit/test_fx_service.py -q -o addopts=''` (from `backend`): 26 passed.
- `python -m alembic heads` (from `backend`): one head, `s3li02_goal_contributions`.
- GitHub Actions on commit `798107c`: Backend Quality Gates passed, including the PostgreSQL migration round-trip and non-Postgres Pytest suite; Backend Postgres Tests passed, including `alembic upgrade head`, Postgres-marked tests, and the full Pytest suite.

All FX focused tests and the current backend CI suites pass.
