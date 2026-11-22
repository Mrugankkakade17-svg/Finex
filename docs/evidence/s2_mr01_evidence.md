# S2-MR01 — fx_004 and fx_005 migration evidence

- **Task:** S2-MR01
- **Branch:** `feature/s2-mr01`
- **Target:** `origin/dev`
- **Migration chain:** `s1mi01_ai_feedback` → `s2mr01_fx004` → `s2mr01_fx005`
- **Evidence status:** Backend quality and PostgreSQL CI checks passed.

## What changed

`fx_004` adds user-owned USD paper accounts and an integer-cents ledger. A composite
foreign key ensures each ledger entry belongs to the same user as its account.

`fx_005` adds PostgreSQL triggers that reject ledger updates and deletes. Before an
entry is added, the trigger locks its account and checks the resulting balance, so a
debit below zero is rejected and concurrent debits are serialized per account.

## Verification results

- `python -m ruff check . ../scripts/serve-s1-web-probe.py`: **passed in CI**.
- `python -m ruff format --check . ../scripts/serve-s1-web-probe.py`: **passed in CI**.
- Mypy type check: **passed in CI**.
- Alembic PostgreSQL migration round-trip: **passed in CI**.
- PostgreSQL contract test `tests/db/test_fx005.py`: **passed**; validates deposits,
  debits, negative-balance rejection, and UPDATE/DELETE rejection.
- PostgreSQL full suite: **2,783 passed, 13 xfailed, 2 xpassed**.
- Quality job full suite: **2,775 passed, 8 deselected, 13 xfailed, 2 xpassed**.
- Earlier local full suite: **2,771 passed, 12 skipped, 13 xfailed, 2 xpassed**;
  coverage **83.59%**.

The initial quality failure was due to extra trailing blank lines in the files as
uploaded through GitHub. Those endings were corrected; current CI checks passed.
