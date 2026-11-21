# S0-PA01 — Portfolio math parity evidence

## Result

The canonical portfolio math implementation is
`app.services.local_portfolio_math.calculate_portfolio_metrics`.

It uses `Decimal`, `ROUND_HALF_UP`, a frozen local decimal context, and canonical
bounded decimal strings. The older `app.services.portfolio_math` implementation
uses binary floats and remains available for frozen legacy routes.

## Shared fixtures

`folio_math_parity.py` compares both implementations on gain, loss, two-asset,
and fractional-rounding fixtures.

## Verification

Run from the repository root:

```bash
python folio_math_parity.py
```

Run from `backend/`:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

The parity test requires every shared fixture to match at cent precision and
records each difference. The current fractional-rounding fixture is intentionally
listed rather than normalized: the legacy float module aggregates raw values,
while the canonical Decimal module rounds each holding to cents first.

## Scoped verification

- `python folio_math_parity.py`: PASS; gain, loss, and two-asset fixtures match.
- Portfolio-focused pytest: 23 passed.
- Backend Ruff: PASS.
- Full backend pytest: collection and execution progressed after installing the
  repository-pinned `psycopg[binary]`; launcher-only baseline failures remained
  due to this Windows host's PowerShell execution policy and 30-second
  fault-injection wrappers. No portfolio-math parity failures occurred.
