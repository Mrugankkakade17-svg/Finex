## What is done

- Added reversible Alembic migrations `fx_001` and `fx_002`.
- Added the `finex.portfolios` table with a cascade foreign key to users.
- Added identity foreign keys for existing profile records.
- Changed `finex.portfolio_holdings.quantity` from floating point to `NUMERIC(38,18)`.
- Added portfolio and user foreign keys to portfolio holdings.
- Added the `tests/db/test_fx002.py` PostgreSQL contract test.
- Updated the SQLAlchemy holding model to match the database type.
- Added the Sprint 1 evidence record.

## Why

This implements S1-MR01 as the authoritative database foundation for user, profile, and portfolio ownership while enforcing exact decimal storage and referential integrity.

## How was it checked

- Run `python -m alembic upgrade head`.
- Run `python -m alembic downgrade base`.
- Run `python -m alembic upgrade head`.
- Run `python -m pytest -m postgres tests/db/test_fx002.py -q`.
- Run `python -m ruff check .`.
- Run `python -m pytest -q` (migration contract passes; local Python 3.14 bcrypt baseline has 22 unrelated password-length failures).

## Checklist

- [x] The changes are focused on this task.
- [x] Migration and contract checks pass.
- [x] No secrets or local-only files are included.
- [x] Documentation is updated when needed.

Closes #21
