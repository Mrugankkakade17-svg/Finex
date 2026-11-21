# S1-MR01 - Migrations fx_001 and fx_002 evidence

- **Task:** S1-MR01
- **Branch:** `feature/s1-mr01`
- **Target:** `origin/dev`
- **Migration head:** `s1mr01_fx002`
- **Evidence status:** Live PostgreSQL verification pending in backend CI

## Implemented migrations

| Migration | Change |
| --- | --- |
| `fx_001` | Adds the `finex.portfolios` table and identity foreign keys |
| `fx_002` | Converts `portfolio_holdings.quantity` to `NUMERIC(38,18)` and enforces portfolio/user ownership with a composite foreign key |

## CI database checks

```bash
cd backend
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
python -m pytest -m postgres tests/db/test_fx002.py -q
```

The backend quality workflow runs these commands against an isolated PostgreSQL
16 service. The test verifies valid ownership, rejects a nonexistent portfolio,
and rejects a holding whose user does not own the referenced portfolio. Test
records are rolled back.

## Local checks

- `python -m ruff check .`: PASS.
- `python -m ruff format --check .`: PASS.
- Offline Alembic upgrade and downgrade SQL generation: PASS.
- `python -m pytest -q -m "not postgres"`: 2,625 passed, 26 xfailed,
  2 deselected; coverage 86.20%.
- Authentication regression subset: 52 passed after restoring the
  repository-pinned bcrypt 4.2.1.

The PostgreSQL service is unavailable on the local machine, so the contract test
and live migration round-trip have not been claimed as locally verified. No
credentials or database dumps are committed.
