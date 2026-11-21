# S1-MR01 - Migrations fx_001 and fx_002 evidence

- **Task:** S1-MR01
- **Branch:** `feature/s1-mr01`
- **Target:** `origin/dev`
- **Migration head:** `s1mr01_fx002`
- **Evidence status:** Verified

## Implemented migrations

| Migration | Change |
| --- | --- |
| `fx_001` | Adds the `finex.portfolios` table and identity foreign keys |
| `fx_002` | Converts `portfolio_holdings.quantity` to `NUMERIC(38,18)` and adds portfolio/user foreign keys |

## Required reversible checks

```bash
cd backend
python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m pytest -m postgres tests/db/test_fx002.py -q
```

## Quality checks

```bash
cd backend
python -m ruff check .
python -m pytest -q
```

## Completion record

| Check | Result |
| --- | --- |
| `python -m alembic upgrade head` | PASS - `s1mr01_fx002 (head)` |
| `python -m alembic downgrade base` | PASS - base migration state reached |
| `python -m alembic upgrade head` | PASS - `s1mr01_fx002 (head)` |
| `python -m pytest -q -o addopts='' tests/db/test_fx002.py` | PASS - `1 passed` |
| `python -m ruff check .` | PASS - `All checks passed` |
| `python -m pytest -q` | Environment baseline: `2604 passed`, `26 xfailed`, `22 failed`; the failures are pre-existing bcrypt password-length incompatibilities under Python 3.14 (`password cannot be longer than 72 bytes`). |

No credentials or database dumps are committed. Existing application routes and local persistence remain unchanged.
