# S3-MR01: Migration fx_006 and reference seed

## Delivered

- Added reversible Alembic revision `s3mr01_fx006` after S2-MR01's `s2mr01_fx005`.
- Added normalized allocation model headers and target-weight rows, plus a versioned benchmark map for EQUITY, FIXED_INCOME and CASH.
- Added deterministic educational reference records for Conservative (20/70/10), Moderate (50/40/10) and Aggressive (80/10/10) profiles. These illustrative examples are not investment advice.
- Added an idempotent PostgreSQL seed command at `scripts/seed_reference_data.py`. It uses `DATABASE_URL` and `ON CONFLICT` upserts; rerunning converges to the same versioned data.
- Added unit coverage for full allocation sums, monotonic equity weights and benchmark coverage; added PostgreSQL coverage for repeated seeding and database constraints.

## Verification

- `python -m ruff check . ../scripts/seed_reference_data.py` — passed.
- `python -m ruff format --check . ../scripts/seed_reference_data.py` — passed (304 backend files already formatted).
- `python -m pytest tests/unit/test_fx006_reference_seed.py -q --no-cov` — **2 passed**.
- `python -m alembic heads --verbose` — passed; `s3mr01_fx006` is the head and follows `s2mr01_fx005`.
- PostgreSQL integration and upgrade/downgrade/upgrade round-trip were not run: no database URL is configured and Docker Desktop's database engine is stopped. The PostgreSQL test is included for the CI service.
- The full non-PostgreSQL suite was started but did not complete within the local run window; it was stopped after the progress output stalled. No full-suite pass is claimed.

## Easy-language summary

This change creates shared database tables for the three educational allocation examples and a map from each supported asset group to its benchmark symbol. The seed command fills those tables safely and can be run more than once without creating duplicates. Existing user portfolios and routes are not changed.

