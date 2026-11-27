# S2-PA06 Watchlist API Implementation Evidence

- **Task:** S2-PA06 — Add Postgres-backed watchlist endpoints; keep /local- watchlists
- **Branch:** `feature/s2-pa06`
- **Target:** `dev`
- **Issue:** #42

## 1. Implementation Overview

### A. Production Watchlist API (`/api/v1/watchlists`)
- Implemented dedicated production watchlist router in `backend/app/routers/watchlists.py`, mounted at `/api/v1/watchlists`.
- Endpoints delivered:
  - `POST /api/v1/watchlists`: Create a user-owned watchlist (HTTP 201).
  - `GET /api/v1/watchlists`: List all watchlists owned by the authenticated user with item counts (HTTP 200).
  - `GET /api/v1/watchlists/{watchlist_id}`: Retrieve a specific watchlist including all items (HTTP 200).
  - `PUT /api/v1/watchlists/{watchlist_id}`: Update a watchlist name (HTTP 200).
  - `DELETE /api/v1/watchlists/{watchlist_id}`: Delete a watchlist and all child items (HTTP 200).
  - `POST /api/v1/watchlists/{watchlist_id}/items`: Add an instrument to a watchlist (HTTP 201).
  - `PUT /api/v1/watchlists/{watchlist_id}/items/{instrument_id}`: Idempotently add/save an instrument (HTTP 200).
  - `GET /api/v1/watchlists/{watchlist_id}/items`: List all items in a watchlist (HTTP 200).
  - `DELETE /api/v1/watchlists/{watchlist_id}/items/{instrument_id}`: Remove an instrument from a watchlist (HTTP 200).

### B. Authentication & Security Boundary Separation
- Endpoints use `CurrentPrincipal = Depends(get_current_principal)`, supporting valid registered-user JWT Bearer tokens.
- User identity is derived strictly from the trusted JWT context (`principal.user_id`).
- Unauthenticated requests return HTTP 401 Unauthorized.
- Production watchlist routes do **not** inherit `require_local_application` and are fully accessible across remote and production networks.
- Enforces strict multi-tenant isolation: any attempt to access or mutate another user's watchlist returns HTTP 404 Not Found to prevent resource enumeration.

### C. PostgreSQL Persistence & Schema Migration
- Added reversible Alembic migration: `backend/alembic/versions/fx_009_s2_pa06_watchlists.py` (revision `s2pa06_watchlists` branching linearly from `s3_fx006_checkpoint`).
- Tables created in schema `finex`:
  - `finex.watchlists`: `user_id` (FK to `finex.users.user_id` ON DELETE CASCADE), `watchlist_id` (PK), `name`, `created_at`, `updated_at`.
  - `finex.watchlist_items`: `user_id` (FK to `finex.users.user_id`), `watchlist_id` (FK to `finex.watchlists`), `instrument_id`, `added_at`, PK `(watchlist_id, instrument_id)`.
- Implemented `WatchlistRepository` supporting both PostgreSQL (via SQLAlchemy / `psycopg`) and SQLite (for local offline testing).

### D. Local-Watchlist Compatibility Preservation
- Preserved `/api/v1/local-watchlists` in `backend/app/routers/local_foundation.py` without modifying its response envelopes, synthetic persona sessions, or loopback boundary checks.
- Zero breaking changes to existing local-market, local-portfolio, or local-foundation endpoints.

## 2. Verification Evidence

### Quality Gates
- `python -m ruff check . ../scripts/serve-s1-web-probe.py` — **PASS** (0 lint errors).
- `python -m ruff format --check . ../scripts/serve-s1-web-probe.py` — **PASS** (356 files already formatted).

### Automated Test Coverage
- `tests/contract/test_watchlist_api.py`: Full CRUD, unauthenticated 401 rejections, multi-tenant cross-user isolation, item idempotency, and input validation.
- `tests/integration/test_watchlists_postgres.py`: Verified with `@pytest.mark.postgres` against live PostgreSQL instance, validating real table persistence, cross-user isolation, cascading deletes, and referential integrity to `finex.users`.
- `tests/contract/test_local_s3_foundation_*.py`: Confirmed backward compatibility of all existing local foundation routes.
