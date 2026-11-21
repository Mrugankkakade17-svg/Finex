# S0-PA03 — SQLite paper ledger evidence

## Result

The local SQLite paper ledger is currently an explicit paper-account opening
receipt, not an order/fill ledger. Schema version 4 permits one account and one
immutable `OPENING` entry per user, with `USD 10000.00` opening cash. The schema
has no order or fill tables, and the ledger checks require order/trade,
instrument, quantity, position, and correction fields to be null.

This is an implementation/schema finding. No developer or deployed database
file was inspected.

## Evidence sources

- [`docs/features/paper-ledger/as-built.md`](../features/paper-ledger/as-built.md)
  documents the schema, route behavior, transaction boundaries, data ownership,
  and the distinction from the unmounted in-memory demo router.
- `backend/app/ports/adapters/sqlite_local_schema.py` defines the account and
  ledger tables, constraints, and immutable-row triggers.
- `backend/app/ports/adapters/sqlite_local_foundation.py` writes one account
  and opening receipt and reads ledger rows by owner and account.
- Contract, atomicity, and schema tests cover empty state, explicit opening,
  pagination, repeated/concurrent opens, immutable history, and schema
  bootstrap/upgrades.

## Verification

Run from `backend/`:

```powershell
python -m ruff check .
python -m pytest -q --no-cov tests\contract\test_local_s3_foundation_api.py tests\integration\test_local_s3_foundation_atomicity.py tests\unit\test_local_s3_schema.py
python -m pytest -q
```

- `python -m ruff check .`: PASS.
- Focused SQLite foundation/schema tests: **121 passed** in 89.16 seconds.
  Pytest reported 412 existing FastAPI `on_event` deprecation warnings.
- Full backend suite: **2,723 passed, 45 failed, 14 skipped, 13 xfailed,
  2 xpassed** in 20:17; coverage was **84.81%** (above the 70% threshold).
  The 45 failures are confined to Windows PowerShell launcher tests. Their
  subprocesses cannot load `.ps1` files because this host's PowerShell
  execution policy disables script execution. No SQLite foundation/schema
  tests failed.
