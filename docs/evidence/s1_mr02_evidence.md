# S1-MR02 — fx_003 migration evidence

## Scope verified against `feature/s1-mr01` (PR #121)

The migration adds persistence for the user-owned stores defined by the
prerequisite branch:

- Goals and their deterministic annual projections.
- Spending transactions.
- Alert rules and notification records (`finex.alerts`, per the data ownership map).
- Privacy requests and consent audit entries.

Each user-owned record is keyed or indexed by `user_id` and references
`finex.users`. Goal projections and rule-linked notifications also have
owner-matching foreign keys. Global feature flags and release sign-offs are
not user-owned and are outside this migration.

## Migration behavior

- Revision `s1mr02_fx003` follows `s1mr01_fx002`.
- Upgrade only creates new tables and indexes in the existing `finex` schema.
- Downgrade drops only those new objects; it does not alter fx_001/fx_002
  tables or data.
- Existing module stores are process-local Python memory, not persisted rows.
  Their seeded contents cannot be safely assigned to users or migrated, so no
  rows are fabricated. The new tables start empty.

## Verification

- `python -m ruff check .` — PASS.
- `python -m ruff format --check .` — PASS.
- Backend CI Mypy checks for Linux and Windows (Python 3.13) — PASS, no issues
  in 151 source files on either platform.
- `python -m alembic upgrade head --sql` — PASS (offline SQL generation).
- `python -m alembic downgrade s1mr02_fx003:s1mr01_fx002 --sql` — PASS
  (offline SQL generation).
- `python -m pytest -q -m "not postgres"` — 2,625 passed, 26 xfailed,
  2 deselected; coverage 86.20%.
- Previously failing authentication tests: 52 passed after restoring the
  repository-pinned `bcrypt==4.2.1`. The initial failures came from a local
  `bcrypt==5.0.0` installation, which is incompatible with Passlib 1.7.4's
  backend-detection self-test.
- The PostgreSQL contract tests and live migration round-trip were not run on
  this machine because Docker/PostgreSQL is unavailable. Backend CI now runs
  them against an isolated PostgreSQL 16 service; the updated CI run is pending.

The migration upgrade and downgrade SQL also rendered successfully offline.
