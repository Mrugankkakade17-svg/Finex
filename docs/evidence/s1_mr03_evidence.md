# S1-MR03 Evidence

## Scope

S1-MR03 now provides real PostgreSQL implementations for all four local stores:

- `LocalApplicationStore`
- `LocalRiskStore`
- `LocalPortfolioStore`
- `LocalFoundationStore`

The adapters use PostgreSQL transactions and the `finex` schema. Runtime selection is controlled by `APP_PERSISTENCE=sqlite|postgresql`; SQLite remains the default and existing behavior is preserved.

## Verification commands

Run from `backend/`:

```powershell
python -m ruff check app tests
python -m pytest tests/contract/store_contract -m "not postgres" -q
python -m pytest tests/contract/store_contract -m postgres -q
python -m pytest -q
```

## Recorded results

- `python -m ruff check app tests` — passed (`All checks passed!`)
- `python -m pytest tests/contract/store_contract -q --no-cov` — passed
  - 8 tests passed across 4 shared contract cases on SQLite and PostgreSQL
- `python -m pytest -q` — passed
  - 2633 tests passed
  - Coverage: 82.61% (required 70%)

## SQLite and PostgreSQL contract suite

`backend/tests/contract/store_contract/test_store_contract.py` contains one shared suite that exercises application, risk, portfolio, and foundation persistence contracts. It is parameterized across SQLite and PostgreSQL. PostgreSQL contract execution requires `APP_DATABASE_URL` or `DATABASE_URL`.

## Dependency

This implementation depends on the S1-MR01 migrations `fx_001` and `fx_002`. The PostgreSQL adapter creates its small owned `finex.local_*` contract tables lazily and is not a substitute for those migrations.
