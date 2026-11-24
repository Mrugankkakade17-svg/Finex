# S2-PA04 Paper Trading Evidence

## Implementation

- Added authenticated `POST /api/v1/paper/orders` with per-user idempotency,
  regular-session checks, eligible quote validation, config-driven fees, and
  buy/sell execution.
- Added `GET /api/v1/paper/account`, `/positions`, and `/orders` for the
  authenticated user's durable account state.
- Persisted fills and mutable open positions in PostgreSQL. Each fill writes a
  matching cash delta to the existing append-only `finex.paper_ledger` in the
  same transaction. The account row is locked while calculating cash and
  positions so concurrent orders cannot overspend.
- Kept the existing `/api/v1/paper-trading` source implementation unchanged.
- Added reversible Alembic revision `s2pa04_fx006` for paper orders and
  positions. `paper_accounts` and `paper_ledger` remain owned by S2-MR01.

## Configuration

- `PAPER_TRADING_INITIAL_CASH` defaults to `50000.00` USD and seeds each new
  paper account once.
- `PAPER_TRADING_FEE_BPS` defaults to `10` basis points and is bounded from 0
  through 1000.
- Orders use the configured PostgreSQL `APP_DATABASE_URL`/`DATABASE_URL` and
  the existing market quote provider chain. A database connection and the
  S2-MR01 migrations must be available before using the endpoints.

## Quote and session rules

- Only non-stale `LIVE`, `DELAYED`, or `CACHED` quotes with a positive finite
  USD price can fill an order. `STALE` and `UNAVAILABLE` quotes never create
  orders or ledger entries.
- NYSE/NASDAQ orders are accepted only on weekdays during their regular
  09:30–16:00 America/New_York session. Exchange holidays and exceptional
  closures are not represented by this calendar.
- The API is paper-only and does not send orders to a broker.

## Verification

Added unit coverage for fee-adjusted buy and sell accounting, idempotent replay
and key misuse, closed sessions, stale/unavailable quotes, insufficient
positions, cash non-negativity under concurrent orders, and a contract test for
authentication and cross-user isolation.

Run from `backend/`:

```text
python -m ruff check .
python -m pytest -q
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

Results are recorded in the S2-PA04 pull request after CI completes.
