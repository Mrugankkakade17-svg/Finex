## What changed?

- Added reversible Alembic migrations `fx_001` and `fx_002`.
- Added `finex.portfolios` and identity foreign keys.
- Changed holdings quantity to `NUMERIC(38,18)`.
- Added a composite foreign key requiring each holding's user to own its portfolio.
- Added PostgreSQL contract coverage for invalid and cross-user portfolio references.
- Updated the evidence record and backend CI to run migrations and PostgreSQL tests against an isolated PostgreSQL 16 service.

## Why?

Implements S1-MR01 (#21), establishing persistent portfolio ownership and exact numeric holding quantities without changing existing routes.

## How was it checked?

Commands below were run from `backend/`.

- `python -m ruff check alembic/versions/fx_002_holdings_numeric_fk.py tests/db/test_fx002.py` — passed.
- `python -m ruff format --check alembic/versions/fx_002_holdings_numeric_fk.py tests/db/test_fx002.py` — passed.
- `python -m alembic upgrade head --sql` — passed.
- `python -m alembic downgrade s1mr01_fx002:s1mr01_fx001 --sql` — passed.
- Live PostgreSQL migration round-trip and `tests/db/test_fx002.py` — pending in backend CI.

## Checklist

- [x] The changes are focused on this task.
- [ ] Tests or checks pass; live PostgreSQL verification is pending in CI.
- [x] No secrets or local-only files are included.
- [x] Documentation is updated when needed.

Closes #21
