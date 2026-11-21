## What is done

- Added reversible Alembic migrations `fx_001` and `fx_002`.
- Added the `finex.portfolios` table with a cascade foreign key to users.
- Added identity foreign keys for existing profile records.
- Changed `finex.portfolio_holdings.quantity` from floating point to `NUMERIC(38,18)`.
- Added portfolio and user foreign keys to portfolio holdings, including a composite owner-matching foreign key so a holding cannot reference another user's portfolio.
- Added the `tests/db/test_fx002.py` PostgreSQL contract test.
- Updated the SQLAlchemy holding model to match the database type.
- Added the Sprint 1 evidence record.

## Why

This implements S1-MR01 as the authoritative database foundation for user, profile, and portfolio ownership while enforcing exact decimal storage and referential integrity.

## How was it checked

- Run `python -m alembic upgrade head --sql` (offline SQL generation).
- Run `python -m alembic downgrade s1mr01_fx002:s1mr01_fx001 --sql` (offline SQL generation).
- Backend CI now runs migrations up/down/up and PostgreSQL contract tests against an isolated PostgreSQL 16 service.
- Run `python -m ruff check .`.
- Run `python -m pytest -q -m "not postgres"` (2,625 passed, 26 xfailed, 2 deselected; 86.20% coverage after restoring the pinned bcrypt dependency).

## Checklist

- [x] The changes are focused on this task.
- [ ] Migration and contract checks pass (live PostgreSQL verification is pending in CI).
- [x] No secrets or local-only files are included.
- [x] Documentation is updated when needed.

Closes #21
