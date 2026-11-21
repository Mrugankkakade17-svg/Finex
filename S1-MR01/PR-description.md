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
- Backend CI [run #44882516405](https://github.com/Mrugankkakade17-svg/Finex/actions/runs/44882516405) — passed against PostgreSQL 16, including migration upgrade/downgrade/upgrade, `tests/db/test_fx002.py`, Ruff, Mypy, and pytest (`2,676 passed, 26 xfailed`).

## Checklist

- [x] The changes are focused on this task.
- [x] Tests or checks pass.
- [x] No secrets or local-only files are included.
- [x] Documentation is updated when needed.

Closes #21
