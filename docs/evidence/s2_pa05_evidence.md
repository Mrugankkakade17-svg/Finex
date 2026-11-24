# S2-PA05 Paper Reconciliation Evidence

## Scope

`backend/app/services/paper_reconcile.py` implements a pure reconciliation
check for PA04 filled orders. It starts with configured initial cash in cents,
sums the stored signed `cash_delta_cents` (including PA04 fees), derives net
instrument quantities from BUY/SELL orders, and compares those values with the
account cash balance and materialized positions. It returns expected and actual
balances plus any per-instrument differences. It does not mutate state or
access a database.

Order rows have `side`, `instrument_id`, positive integer `quantity`, and signed
integer `cash_delta_cents`, matching PA04 `PaperOrderRecord`. Position input can
be an instrument to quantity mapping or rows with `instrument_id` and
`quantity`. Reconciliation uses exact integer cents and does not recompute fees.

## Verification

Run from `backend/` with the pinned requirements installed:

```text
python -m ruff check .
All checks passed!

python -m pytest -q --no-cov tests/unit/test_paper_reconcile.py
12 passed in 0.26s
```

The unit coverage includes empty accounts, fee-aware signed cash deltas, a
deterministic 250-order generated BUY/SELL sequence, net-zero trades, cash and
position discrepancies, duplicate positions, missing fields, invalid
quantities, invalid order sides, sign mismatches, and rejection of non-integer
monetary inputs.

The full backend suite was run with `python -m pytest -q` against the local
checkout's stale `origin/dev` baseline (`8f3f597`, before the current PA04/dev
work visible on GitHub):

```text
43 failed, 2782 passed, 14 skipped, 13 xfailed, 2 xpassed
Required test coverage of 70% reached. Total coverage: 84.91%
```

The new reconciliation tests passed in that full run. The failing tests were in
acceptance/evidence harnesses, but this run is not a valid full-suite result for
the current GitHub `dev` base and should not be used as one. The current GitHub
`dev` integration check subsequently passed on PR #147: the Postgres-marked
tests and full backend pytest suite succeeded, and Backend Quality Gates passed
including Ruff, mypy, and the PostgreSQL migration round-trip.

## Integration boundary

The checker is additive and consumes PA04 order records plus its account
snapshot. No route, database schema, or persistent storage was changed.
