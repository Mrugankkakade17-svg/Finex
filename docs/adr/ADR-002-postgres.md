# ADR-002: PostgreSQL host and pgvector for S0 validation

- **Status:** Accepted and verified (see `docs/evidence/s0_mr01_evidence.md`)
- **Date:** 2026-11-18
- **Task:** S0-MR01

## Context

S0-MR01 requires a PostgreSQL 16 host with pgvector and a reversible Alembic migration check (`upgrade head`, `downgrade base`, `upgrade head`). The repository already contains an Alembic environment, an existing migration merge revision (`c9e7b5a2566a`), and the async PostgreSQL dependencies (`asyncpg`, SQLAlchemy, Alembic).

The current local application documentation and adapters also preserve native SQLite persistence. This task must not silently replace that persistence or change frozen routes.

## Decision

Use **Neon Serverless Postgres Free plan**, explicitly selecting **PostgreSQL 16**, as the disposable S0 validation host.

Enable pgvector in the target database with:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Verify it with:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

Neon's documentation states that pgvector is available on every plan and is enabled per database using the SQL above. The Free plan is suitable for development/migration validation within its published quotas, not a production availability or compliance commitment.

## Consequences

- No self-managed server installation or Docker dependency is required for the hosted validation database.
- Backend migrations use the existing `DATABASE_URL` setting and asyncpg driver.
- The provider connection secret remains in ignored local environment configuration and must never be committed.
- The Alembic round-trip is run only on a disposable database because `downgrade base` removes migration-managed schema objects.
- Local SQLite persistence and all existing routes remain unchanged.
- The existing single Alembic head/merge lineage is preserved; this task does not introduce a parallel migration tree.

## Verification record

Live host creation on Neon (`finex-s0-validation-pg16`, PostgreSQL 16.16), installation of `vector 0.8.7`, and the Alembic round-trip (`upgrade head -> downgrade base -> upgrade head`) were verified. The actual SQL and command results are recorded in `docs/evidence/s0_mr01_evidence.md`.

## References

- Neon Free plan: https://neon.com/docs/introduction/plans
- Neon pgvector setup: https://neon.com/docs/extensions/pgvector
- PostgreSQL extension installation semantics: https://www.postgresql.org/docs/current/sql-createextension.html
