# SQLite paper ledger — as built

**Reviewed:** 2026-11-22
**Scope:** The local-application SQLite paper-account store and its API. This is
a source/schema review; it does not inspect a user's configured database file.

## Summary

The SQLite paper ledger is an account-opening receipt, not an order-execution
ledger. Its only supported ledger event is `OPENING`: the explicit creation of
one simulated USD account with `10000.00` opening cash. The schema and service
do not support persisted orders, fills, trades, or positions. The ledger row's
`order_id`, `trade_id`, instrument, quantity, position, and correction fields
must all be null.

This conclusion describes the shipped SQLite schema and write paths. No
deployed or developer database file was read, so this is not a census of rows
in any particular on-disk database.

## Storage selection and initialization

- `APP_PERSISTENCE` defaults to `sqlite`. In the default local setup, when no
  foundation store is injected and no other local stores are configured, the
  local foundation service lazily creates a `SQLiteLocalFoundationStore` using
  `LOCAL_DB_PATH`.
- The default path is `backend/.local/finex.sqlite3`; `LOCAL_DB_PATH` can
  select another native persistent file. SQLite URI and `:memory:` paths are
  rejected by settings validation.
- `APP_PERSISTENCE=postgresql` selects the separate
  `PostgresLocalFoundationStore`; its schema is not the SQLite file described
  here.
- Local application routes are opt-in (`LOCAL_APP_ENABLED` defaults to false)
  and also require the local-application boundary and an authorized local
  session.
- Opening the SQLite store creates the parent directory and initializes or
  validates the schema lazily. It enables SQLite foreign keys, uses a
  3-second busy timeout, bootstraps the owned schema in a transaction, and
  enables WAL only after the schema is accepted.

The owned schema version is `4`. It is stored in `schema_metadata`; supported
versions 1, 2, and 3 are upgraded transactionally to version 4 while preserving
prior rows. The version-4 foundation group adds the watchlist tables and the
two paper-account tables below. A foreign, malformed, incomplete, or future
schema is rejected rather than silently altered.

## SQLite paper tables

### `local_paper_accounts`

One explicitly opened account per local user:

- `account_id`, `opening_ledger_id`: generated UUID4 identifiers.
- `user_id`: unique owner reference to `local_users`; a user can own at most
  one account.
- `currency`: constrained to `USD`.
- `opening_cash_cents`: integer constrained to `1,000,000` cents
  (`10000.00`).
- `cash_balance_cents`: integer bounded from zero to the schema maximum. In
  the current S3 opening flow it remains `1,000,000`; no implemented SQLite
  order/fill path changes the balance.
- `created_at`: UTC timestamp.

The account's composite foreign key binds `opening_ledger_id` to the opening
receipt for the same owner and account. The deferred relationship allows both
records to be inserted together in one transaction.

### `local_paper_ledger`

The table stores the single opening receipt:

- `sequence`: auto-incremented integer bounded by the largest integer exactly
  representable by JavaScript.
- `ledger_id`: unique generated UUID4; `user_id` and `account_id` bind the row
  to its owner and account.
- `entry_type`: database check requires the literal `OPENING`.
- `cash_delta_cents` and `cash_after_cents`: integer checks require
  `1,000,000` cents for both values.
- `instrument_id`, `quantity_delta_micro_units`, `position_after_micro_units`,
  `order_id`, `trade_id`, `corrects_ledger_id`: database checks require null.
- `created_at`: UTC timestamp matching the account's creation time.
- A unique `(user_id, account_id)` constraint permits only one ledger row per
  account. Foreign keys bind the receipt to that account and its opening ID.
- `local_paper_ledger_no_update` and `local_paper_ledger_no_delete` triggers
  reject updates and deletes. The history is append-only by schema, and this
  version's uniqueness/type constraints permit only its one opening receipt.

There are **no SQLite `paper_orders`, `paper_fills`, or equivalent execution
tables**, and the local foundation transaction interface exposes no order or
fill insert operation.

## API and transaction flow

The mounted local foundation router exposes:

| Route | Behavior |
| --- | --- |
| `GET /api/v1/local-paper/account` | Reads the authenticated owner's account. Before opening, returns `account: null`; it does not create or fund an account. |
| `POST /api/v1/local-paper/account/open` | Requires an explicit supported foundation version and USD currency. Inserts the account and opening receipt together. A repeated or concurrent open returns the existing account; it does not add funds or a second row. |
| `GET /api/v1/local-paper/account/ledger` | Reads only the authenticated owner's opening receipt, with `limit` (1–100) and `after_sequence` pagination controls. Before opening, returns `404 PAPER_ACCOUNT_NOT_OPEN`. A cursor after the opening receipt yields an empty page. |

These operations require a valid local bearer session and completed onboarding.
Store reads include `user_id`; a missing or other-owner account is not exposed
to the caller. Writes use the shared SQLite transaction factory: a write
transaction begins with `BEGIN IMMEDIATE`, checks the schema, and commits the
account plus receipt once. Storage errors roll back both records; the service
does not report success for a partial opening.

## No persisted orders or fills

In the SQLite implementation, no order or fill records exist or can be created
through the local paper-ledger API:

1. The schema declares only account and ledger tables, with `entry_type` fixed
   to `OPENING` and all order/trade/position fields fixed to null.
2. The store inserts an account and its opening receipt; its ledger query
   returns `PaperOpeningRecord` values only.
3. The wire model `PaperOpeningEntry` likewise requires `OPENING` and null
   order, trade, instrument, quantity, position, and correction fields.
4. The S3 contract tests prove a fresh account read is empty, the ledger
   requires explicit opening, a successful open yields exactly one opening
   entry, repeated and concurrent opens do not duplicate it, and its update
   and delete are rejected.

There is a separate legacy module, `backend/app/routers/paper_trading.py`, with
module-global in-memory demo cash, positions, and simulated order responses
marked `FILLED`. It does not use this SQLite schema or persist rows, and
`create_app` in `backend/app/main.py` does not mount that router. Its demo
behavior must not be interpreted as SQLite paper-order or fill support.

## Evidence paths

- Schema and constraints: `backend/app/ports/adapters/sqlite_local_schema.py`
- Connection, schema bootstrap, WAL and transactions:
  `backend/app/ports/adapters/sqlite_local_store.py`
- SQLite account and ledger reads/writes:
  `backend/app/ports/adapters/sqlite_local_foundation.py`
- Domain records and opening-value validation:
  `backend/app/domain/local_foundation.py`
- Account-opening and ledger service:
  `backend/app/services/local_foundation_service.py`
- Mounted API routes and local-storage selection:
  `backend/app/routers/local_foundation.py`
- SQLite account/ledger contract tests:
  `backend/tests/contract/test_local_s3_foundation_api.py`
- Atomicity, concurrency, and immutable-ledger tests:
  `backend/tests/integration/test_local_s3_foundation_atomicity.py`
- Schema version 4 creation and preserving-upgrade tests:
  `backend/tests/unit/test_local_s3_schema.py`
- Supporting contract and data dictionary:
  `docs/features/local-application/S3-market-foundation-contract.md`,
  `docs/features/local-application/local-data-dictionary.md`

Verification results for this documentation change are recorded in
[`docs/evidence/s0_pa03_evidence.md`](../../evidence/s0_pa03_evidence.md).
