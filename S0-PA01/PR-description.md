## What changed?

- Added `folio_math_parity.py` to compare the legacy float portfolio math module
  and the canonical Decimal portfolio math module on shared fixtures.
- Selected `app.services.local_portfolio_math.calculate_portfolio_metrics` as
  the canonical implementation because it uses exact Decimal arithmetic and a
  frozen local decimal context.
- Added a focused unit test for exact matches and listed differences.
- Documented the fractional-rounding difference and verification evidence.

## Why?

Implements S0-PA01 by establishing the authoritative portfolio math
implementation and making float-versus-Decimal differences explicit without
changing existing routes or persistent storage.

## How was it checked?

- `python folio_math_parity.py` — PASS.
- Portfolio-focused pytest — 23 passed.
- `cd backend && python -m ruff check .` — PASS.
- Backend Ruff format check for the new Python files — PASS.

Closes #16
