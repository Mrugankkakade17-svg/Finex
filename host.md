# S0-MR01 — PostgreSQL host setup

## Selected free host

**Neon Serverless Postgres (Free plan), PostgreSQL 16.** Neon is selected for the disposable development/migration-validation database because it offers managed PostgreSQL and documents pgvector availability on every plan. The free tier has usage limits; check the current plan limits before using it for anything beyond development.

- Create a project at https://console.neon.tech/
- Project name: `finex-s0-validation`
- PostgreSQL version: **16** (select it explicitly)
- **Tip:** Neon defaults new projects to its latest PostgreSQL version (for example, PostgreSQL 18), so choose **PostgreSQL 16** from the version dropdown when creating the project.
- Region: choose the closest available region to the team/application deployment.
- Use a disposable development database/branch for the destructive Alembic rollback test.
- Do not use this database as a replacement for the application's existing local SQLite store.

Provider references:
- Free plan limits: https://neon.com/docs/introduction/plans
- Enable pgvector: https://neon.com/docs/extensions/pgvector

## Enable and verify pgvector

Connect to the newly created database using Neon SQL Editor (or `psql`) and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';
```

The second query must return exactly one row named `vector`. Save the actual output in `docs/evidence/s0_mr01_evidence.md`. Do not mark this check complete until it has been run against the selected project.

## Configure the backend connection

1. Copy the Neon connection string from **Connect** in the Neon console.
2. Keep the password private. Do not paste it into source files, issue comments, screenshots, or commits.
3. Put the connection string in the ignored `backend/.env` file as `DATABASE_URL`, using SQLAlchemy's asyncpg driver form:

```dotenv
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require
```

Replace the placeholders with the connection details from Neon. Preserve URL-escaping for special characters in the username/password. Use the direct connection string for schema migrations if the provider exposes both pooled and direct URLs.

The repository already declares `asyncpg`, `SQLAlchemy`, and `alembic` in `backend/requirements.txt`; no additional driver dependency is required for this task.

## Validate the existing migration lineage

Run these commands from the repository root in PowerShell:

```powershell
cd backend
python -m alembic heads
python -m alembic upgrade head
python -m alembic current
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic current
python -m ruff check .
python -m pytest -q
```

Expected migration behavior:

- `alembic heads` reports one head: `c9e7b5a2566a`.
- First `upgrade head` applies the existing S1/S2 schema migrations.
- `downgrade base` returns the disposable database to the base revision and removes the objects created by those migrations.
- Final `upgrade head` reapplies the same lineage cleanly.
- Final `alembic current` reports `c9e7b5a2566a (head)`.

**Safety:** `downgrade base` is destructive. Run the full round-trip only on a newly created, disposable validation database with no user data. Never run it against a shared, staging, or production database.

## Scope and compatibility

This task provisions a PostgreSQL 16 target for the existing Alembic migrations and verifies pgvector availability. It does not switch application routes or local persistence from SQLite to PostgreSQL, change database adapters, add vector columns, or alter frozen API contracts. Those changes require separate reviewed work.

## Completion status

The live host setup and pgvector check are verified. PostgreSQL 16.16, `vector 0.8.7`, and the Alembic round-trip results are recorded in `docs/evidence/s0_mr01_evidence.md`.
