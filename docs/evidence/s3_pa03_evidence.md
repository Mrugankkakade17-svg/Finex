# S3-PA03 daily portfolio snapshot evidence

## Implementation

- Added `backend/app/jobs/snapshot_portfolios.py`, a run-once daily job invoked
  with `python -m app.jobs.snapshot_portfolios` from `backend`. Deployments can
  schedule this command once per UTC day.
- The job enumerates persistent PostgreSQL portfolios as `(user_id,
  portfolio_id)` pairs and asks the existing owner-scoped portfolio valuation
  service for each daily summary. A valuation failure aborts the batch before
  any rows are written.
- Added `finex.portfolio_daily_snapshots` with aggregate value/cost/gain,
  currency, status, count, and asset/sector allocation data. The unique key is
  `(portfolio_id, snapshot_date)`; reruns upsert the same day's row instead of
  creating duplicates.
- Added a reversible Alembic migration and PostgreSQL integration coverage for
  same-day upserts and separate portfolio owners. No API routes changed.

## Verification

- `python -m ruff check . ../scripts/serve-s1-web-probe.py` (from `backend`) — passed.
- `python -m ruff format --check . ../scripts/serve-s1-web-probe.py` (from `backend`) — passed (381 files formatted).
- Linux and Windows Mypy commands from `backend-quality.yml` — passed (200 source files each).
- `python -m pytest tests/unit/test_s3_pa03_snapshot_job.py tests/db/test_s3_pa03_portfolio_snapshots.py -q -o addopts=''` — 9 passed, 1 skipped. The PostgreSQL integration case skipped locally because this machine has no configured `DATABASE_URL`.
- Initial PR CI PostgreSQL run exposed an ordering assumption in the integration test: UUID-generated portfolio IDs are returned in `portfolio_id` order, not owner creation order. Updated the expected rows to use the same key ordering. Ruff passes for the changed test; the local PostgreSQL case remains skipped without `DATABASE_URL`. CI is rerunning against the updated commit.
- Alembic `upgrade head --sql` and `downgrade s3pa03_daily_snapshots:s3_pa06_merge_heads --sql` — passed; `alembic heads` reports one head.
- `python -m pytest -q` (from `backend`) — 3,084 passed, 27 skipped, 2 xfailed, 2 xpassed, 43 failed. The failures are in existing Windows launcher/evidence harness tests (`test_owned_s2_acceptance_launcher.py`, `test_s1_acceptance_launcher.py`, `test_s2_evidence_pair_validation.py`, and `test_verify_s3_foundation.py`); none are in the new S3-PA03 tests. The PostgreSQL-specific test is covered by PR CI.

## Operation

Configure `APP_PERSISTENCE=postgresql` and `APP_DATABASE_URL` (or
`DATABASE_URL`) for the scheduled process. The command exits nonzero if
PostgreSQL persistence is not configured or any portfolio cannot be valued.
