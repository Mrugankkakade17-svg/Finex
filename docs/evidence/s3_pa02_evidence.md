# S3-PA02 FX series and valuation evidence

## Contract

`backend/app/services/fx_service.py` provides a deterministic, injected FX series. A rate represents one unit of its base currency in its quote currency. The series selects the latest observation whose date is on or before the requested valuation date. Conversion supports direct and inverse quotes and returns the applied rate, rate ID, source, as-of date, freshness label, and inversion flag. When both quote directions are available, the newer eligible observation is selected; inverse amounts divide by the original quote to avoid reciprocal-rounding loss. FX freshness labels are restricted to non-live `DataFreshness` values.

S3-PA02 adds no route, persistence, or Alembic migration. The current `dev` base already provides the migration merge point; there is no S3-PA02 migration file in this PR. The backend Postgres workflow now fails if `alembic upgrade head` fails.

## Verification

Unit coverage is in `backend/tests/unit/test_fx_service.py`: direct USD→INR valuation, inverse INR→USD valuation and division precision, newer direct/inverse selection, dated selection and ordered series access, identity conversion and same-currency lookup rejection, missing/future rates, duplicate IDs, malformed currencies, invalid/non-finite rates and amounts, non-live freshness validation, normalized/rejected labels, and rejection of `datetime` values for rate and valuation dates (including identity conversions).

- Ruff lint and format checks: passed.
- Mypy checks for Linux and Windows with Python 3.13: passed.
- `python -m pytest tests/unit/test_fx_service.py -q -o addopts=''` (from `backend`): 26 passed.
- `python -m alembic heads` (from `backend`): one head, `s3li02_goal_contributions`.
- GitHub Actions on PR code commit `7949528f6f2192f4c1c40cd59582ba8d2565768b`: all reported checks passed, including Backend Quality Gates and Backend Postgres Tests. The Postgres workflow ran `alembic upgrade head` and the Postgres-marked tests; the quality workflow ran the non-Postgres test suite.
- The last recorded local full-suite run, which was not rerun after the final FX updates, reported 3,086 passed, 26 skipped, 2 xfailed, 2 xpassed, and 45 failures. Those failures were outside FX: `tests/test_local_launcher_boundary.py` (4), `tests/unit/test_owned_s2_acceptance_launcher.py` (34), and `tests/unit/test_s1_acceptance_launcher.py` (7). No FX test failed in that run.

The local full-suite result above is historical and is not evidence of the current code commit; the latest GitHub Actions results are the verification for code commit `7949528`.
