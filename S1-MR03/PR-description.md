# S1-MR03: PostgreSQL persistence adapters

## Summary

Adds complete PostgreSQL implementations for:

- `LocalApplicationStore`
- `LocalRiskStore`
- `LocalPortfolioStore`
- `LocalFoundationStore`

Adds `APP_PERSISTENCE=sqlite|postgresql` configuration and wires PostgreSQL store selection in FastAPI application startup. SQLite remains the default and existing SQLite routes keep their existing lazy fallback behavior.

## Contract verification

Adds `backend/tests/contract/store_contract/test_store_contract.py`, a shared suite parameterized for SQLite and PostgreSQL.

## Evidence

See [S1-MR03 evidence](../docs/evidence/s1_mr03_evidence.md).

## Dependencies

Requires the S1-MR01 `fx_001` and `fx_002` migrations.
