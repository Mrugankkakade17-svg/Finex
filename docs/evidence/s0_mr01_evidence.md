# S0-MR01 — PostgreSQL 16 + pgvector evidence

- **Branch:** `feature/s0-mr01`
- **Selected host:** Neon Serverless Postgres Free
- **Target version:** PostgreSQL 16
- **Evidence status:** Verified. The disposable PostgreSQL 16 host, pgvector check, migration round-trip, Ruff check, and backend tests passed.

> Complete this record after creating the disposable Neon project and running the commands in the repository-root `host.md`. Do not paste connection strings, passwords, tokens, or other secrets.

## 1. Host verification

- Neon project created: `finex-s0-validation-pg16`
- PostgreSQL server version output from `SELECT version();`: `PostgreSQL 16.16 (b5be8fd)`
- Database name (non-secret): `neondb`
- Connection mode used for migrations (direct/pooled): `direct`
- Version result: **PASS**; the host is PostgreSQL 16.

## 2. pgvector verification

Command executed:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

Actual output:

```text
vector 0.8.7
```

Result: **PASS**

## 3. Alembic reversible migration verification

Run from `backend/` against the disposable database.

| Command | Actual result / output |
| --- | --- |
| `python -m alembic heads` | `c9e7b5a2566a (head)` |
| `python -m alembic upgrade head` | **PASS**; all four migration steps applied |
| `python -m alembic current` | `c9e7b5a2566a (head) (mergepoint)` |
| `python -m alembic downgrade base` | **PASS**; all migration steps reverted |
| `python -m alembic upgrade head` | **PASS**; all four migration steps reapplied |
| `python -m alembic current` | `c9e7b5a2566a (head) (mergepoint)` |

## 4. Quality checks

| Command | Actual result |
| --- | --- |
| `python -m ruff check .` | **PASS** — All checks passed |
| `python -m pytest -q` | **PASS** — 2625 passed, 2444 warnings, 85.52% coverage, exit code 0 |

## 5. Compatibility checks

- Existing SQLite local persistence unchanged: **PASS** — no application persistence files or adapters changed
- Frozen routes unchanged: **PASS** — backend contract and integration tests passed
- No credentials or database dumps committed: **PASS** — `backend/.env` remains local and ignored
- User isolation and existing tests: **PASS** — full backend suite passed

## 6. Reviewer

- Secondary reviewer: Payal
- Review status: `[pending reviewer approval]`
- PR: [#113](https://github.com/Mrugankkakade17-svg/Finex/pull/113)

## Completion statement

The technical implementation and verification for S0-MR01 are complete. Final task closure still depends on reviewer approval of PR #113.
