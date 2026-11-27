# S2-LI01 implementation evidence

## Scope

- Added a reusable append-only audit event writer that emits allowlisted JSON
  metadata with an explicit request correlation ID.
- Added a thread-safe sliding-window API limiter. Authentication endpoints use
  a stricter per-client window; health endpoints remain available.
- Kept the existing SQLite/PostgreSQL persistence selection and routes intact.
- Confirmed UAT/production settings fail during startup for a missing signing
  key or a missing credential for the selected OpenAI or market-data provider.
  Existing settings validation also requires HTTPS and explicit allowed origins.
- Documented production secrets and the rate-limit configuration in
  `backend/.env.example` and `backend/README.md`.

## Verification

- `cd backend && python -m ruff check .` — passed (`All checks passed!`).
- `cd backend && python -m ruff format --check .` — passed (371 files already formatted).
- `cd backend && python -m pytest -q tests/unit/test_s2_li01_security_controls.py -o addopts='' --confcutdir=tests/unit` — passed (12 passed).
- `cd backend && python -m pytest -q` — attempted, but collection stopped before tests ran because this machine's Python environment is missing `psycopg`. The dependency is present in `backend/requirements.txt`; installation was blocked by the package index connection.
- Latest GitHub CI: Ruff lint and formatter passed; S1 UAT and R0-S2 native evidence workflows passed.
- Full backend quality CI stopped at the repository's existing Alembic configuration because `alembic upgrade head` reports multiple heads, so its full pytest step was skipped. The separate Postgres suite's marked tests also failed on missing pre-existing `finex.users`, `finex.goals`, and related tables; no S2-LI01 database migration was added.
- `git diff --check` — passed.

## Operational notes

The general API limiter is process-local and does not claim a shared quota
across multiple application workers. Audit events are emitted as one-line JSON
to the application's audit logger; the deployment log sink must retain that
stream for durable audit history. No database schema or migration was changed.
