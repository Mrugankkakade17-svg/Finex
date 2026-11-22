# S2-MR01 — fx_004 and fx_005 migration evidence

- **Task:** S2-MR01
- **Branch:** `feature/s2-mr01`
- **Target:** `origin/dev`
- **Migration chain:** `s1mi01_ai_feedback` → `s2mr01_fx004` → `s2mr01_fx005`
- **Evidence status:** Static checks passed; PostgreSQL CI results are pending.

## What changed

`fx_004` adds user-owned USD paper accounts and an integer-cents ledger. A composite
foreign key ensures each ledger entry belongs to the same user as its account.

`fx_005` adds PostgreSQL triggers that reject ledger updates and deletes. Before an
entry is added, the trigger locks its account and checks the resulting balance, so a
debit below zero is rejected and concurrent debits are serialized per account.

## Verification results

- `python -m ruff check .`: **passed**.
- `python -m ruff format --check . ../scripts/serve-s1-web-probe.py`: **passed**;
  301 files are formatted.
- `python -m pytest -q`: **2,771 passed, 12 skipped, 13 xfailed, 2 xpassed**;
  coverage **83.59%** (above the 70% requirement).
- `python -m alembic heads`: **passed**; `s2mr01_fx005` is the sole head.
- Offline Alembic upgrade SQL generation: **passed**.
- Offline `fx_005` → `fx_004` downgrade and `fx_004` → `fx_005` upgrade SQL generation:
  **passed**.
- Live PostgreSQL migration round-trip and `tests/db/test_fx005.py`: awaiting the
  PR's PostgreSQL 16 CI job; there is no `DATABASE_URL` configured in this local environment.

The PostgreSQL contract test covers deposits, debits, computed balance, negative-balance
rejection, and UPDATE/DELETE rejection.

