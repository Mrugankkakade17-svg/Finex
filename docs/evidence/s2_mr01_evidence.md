# S2-MR01 — fx_004 and fx_005 migration evidence

- **Task:** S2-MR01
- **Branch:** `feature/s2-mr01`
- **Target:** `origin/dev`
- **Migration chain:** `s1mi01_ai_feedback` → `s2mr01_fx004` → `s2mr01_fx005`
- **Evidence status:** Static checks passed; PostgreSQL execution remains pending.

## What changed

`fx_004` adds user-owned USD paper accounts and an integer-cents ledger. A composite
foreign key ensures each ledger entry belongs to the same user as its account.

`fx_005` adds PostgreSQL triggers that reject ledger updates and deletes. Before an
entry is added, the trigger locks its account and checks the resulting balance, so a
debit below zero is rejected and concurrent debits are serialized per account.

## Verification results

- `python -m ruff check .`: **passed**.
- `python -m pytest -q`: **2,771 passed, 12 skipped, 13 xfailed, 2 xpassed**;
  coverage **83.59%** (above the 70% requirement).
- `python -m alembic heads`: **passed**; `s2mr01_fx005` is the sole head.
- Offline Alembic upgrade SQL generation: **passed**.
- Offline `fx_005` → `fx_004` downgrade SQL generation: **passed**.
- Offline `fx_004` → `fx_005` upgrade SQL generation: **passed**.
- `python -m pytest -m postgres tests/db/test_fx005.py -q`: **not executed against PostgreSQL**;
  this environment has no `DATABASE_URL`, so PostgreSQL tests are skipped by the fixture.

`backend/tests/db/test_fx005.py` covers deposits, debits, the computed balance,
negative-balance rejection, and UPDATE/DELETE rejection when run against PostgreSQL.
The generated SQL checks do not replace a live PostgreSQL round trip.

