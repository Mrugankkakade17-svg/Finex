# S2-LI01 implementation evidence

## Scope

- Added a reusable append-only audit event writer that emits allowlisted JSON
  metadata with an explicit request correlation ID.
- Added a thread-safe sliding-window API limiter. Authentication endpoints use
  a stricter per-client window; health endpoints remain available.
- Added a no-op Alembic merge revision joining the two current `dev` heads so
  database setup and the existing migration round-trip can run with one head.
  It does not alter application tables or stored data.
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
- `cd backend && python -m pytest -q` — local collection could not start because this machine's Python environment is missing `psycopg`; package-index installation was blocked.
- Current GitHub CI: Ruff lint, Ruff formatter, mypy, and the Alembic upgrade/downgrade/upgrade round-trip passed.
- Backend quality full suite: 3,125 passed, 19 deselected, 2 xfailed, and 2 xpassed.
- Backend Postgres workflow: 19 marked tests passed; the full suite reported 3,144 passed, 2 xfailed, and 2 xpassed.
- R0-S2 and S1 UAT evidence workflows passed.
- `git diff --check` — passed.

## Operational notes

The general API limiter is process-local and does not claim a shared quota
across multiple application workers. Audit events are emitted as one-line JSON
to the application's audit logger; the deployment log sink must retain that
stream for durable audit history. The merge revision changes no database schema.
