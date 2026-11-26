# S2-MR01 — fx_004 and fx_005 migration evidence

- **Task:** S2-MR01
- **Branch:** `feature/s2-mr01`
- **Target:** `origin/dev`
- **Migration chain:** `s1mi01_ai_feedback` → `s2mr01_fx004` → `s2mr01_fx005`
- **Status:** Backend quality and PostgreSQL checks passed after addressing the review comment.

## What changed

`fx_004` adds user-owned USD paper accounts and a ledger that records amounts as integer cents. A composite foreign key keeps each ledger entry linked to the same owner as its account.

`fx_005` adds database triggers that reject updates, deletes, and truncation of the ledger. Before each new entry, a trigger locks the account and checks that the resulting balance is not negative.

The PostgreSQL test covers deposits and debits, negative-balance rejection, and rejection of UPDATE, DELETE, and TRUNCATE.

## Verification results

- Ruff lint: **passed**.
- Ruff format check: **passed**.
- Mypy type check: **passed**.
- PostgreSQL migration round-trip: **passed**.
- PostgreSQL contract tests: **8 passed**, including the S2-MR01 ledger test.
- PostgreSQL full suite: **2,829 passed, 13 xfailed, 2 xpassed**.
- Quality job full suite: **2,821 passed, 8 deselected, 13 xfailed, 2 xpassed**.

The PR reviewer identified that row-level triggers do not protect against TRUNCATE. The statement-level guard and regression test were added, and the updated backend CI checks passed.
