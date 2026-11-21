## What changed?

- Added CI workflow `.github/workflows/backend-postgres.yml` (and `.github/workflows/postgres.yml`) with a `pgvector/pgvector:pg16` service container.
- Configured health-checked PostgreSQL 16 container with `DATABASE_URL` environment variable.
- Added automated step verifying PostgreSQL 16 server version and `pgvector` extension readiness.
- Registered the `postgres` pytest marker in `backend/pyproject.toml`.
- Added test suite `backend/tests/db/test_pgvector.py` covering PostgreSQL 16 version check, `pgvector` extension creation, vector embedding cosine distance operations, and database transaction isolation.
- Created task deliverables directory `S1-MR04/` containing all generated artifacts and evidence.
- Added comprehensive evidence document in `docs/evidence/s1_mr04_evidence.md`.

## Why?

Implements S1-MR04 (#24) to establish continuous integration verification for PostgreSQL 16 and pgvector capabilities under the locked FinEx architectural contracts without modifying existing routes or introducing breaking changes.

## How was it checked?

- `cd backend && python -m ruff check .` — PASS
- `cd backend && python -m ruff format --check .` — PASS
- `cd backend && python -m pytest -q` — PASS
- Workflow configuration validated against GitHub Actions schema for service container orchestration.
- Verified zero breaking changes to existing routes or persistent storage.
- No secrets committed.

## Checklist

- [x] The changes are focused on this task.
- [x] Tests and quality checks pass.
- [x] No secrets or local-only files are included.
- [x] Documentation and evidence updated.
- [x] PR targeted to `origin/dev`.
- [x] Reviewer requested: Payal (@payalmude14-star).

Closes #24
