# S0-MR01 — PostgreSQL 16 + pgvector evidence

- **Branch:** `feature/s0-mr01`
- **Selected host:** Neon Serverless Postgres Free
- **Target version:** PostgreSQL 16
- **Evidence status:** Pending live execution — no successful host/SQL/migration output is claimed by this document.

> Complete this record after creating the disposable Neon project and running the commands in the repository-root `host.md`. Do not paste connection strings, passwords, tokens, or other secrets.

## 1. Host verification

- Neon project created: `[pending]`
- PostgreSQL server version output from `SELECT version();`: `[paste output]`
- Database name (non-secret): `[record name]`
- Connection mode used for migrations (direct/pooled): `[record mode]`

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
[paste the actual returned row showing extname=vector and extversion]
```

Result: `[PASS only after the query returns the vector row / otherwise FAIL]`

## 3. Alembic reversible migration verification

Run from `backend/` against the disposable database.

| Command | Actual result / output |
| --- | --- |
| `python -m alembic heads` | [paste output; expected one head c9e7b5a2566a] |
| `python -m alembic upgrade head` | [paste output] |
| `python -m alembic current` | [paste output; expected c9e7b5a2566a (head)] |
| `python -m alembic downgrade base` | [paste output] |
| `python -m alembic upgrade head` | [paste output] |
| `python -m alembic current` | [paste output; expected c9e7b5a2566a (head)] |

## 4. Quality checks

| Command | Actual result |
| --- | --- |
| `python -m ruff check .` | [paste exit code and summary] |
| `python -m pytest -q` | [paste passed/failed/skipped counts and exit code] |

## 5. Compatibility checks

- Existing SQLite local persistence unchanged: `[verify and record]`
- Frozen routes unchanged: `[record relevant regression/contract test result]`
- No credentials or database dumps committed: `[verify]`
- User isolation and existing tests: `[record relevant test results]`

## 6. Reviewer

- Secondary reviewer: Payal
- Review status: `[pending]`
- PR: `[add URL]`

## Completion statement

Do not mark S0-MR01 complete until the PostgreSQL version, pgvector query, Alembic upgrade/downgrade/upgrade round-trip, required backend quality commands, compatibility checks, and reviewer approval have actual recorded results.
