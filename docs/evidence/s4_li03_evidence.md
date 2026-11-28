# S4-LI03 Digital Twin Evidence

## Delivered

- Added authenticated `GET /api/v1/twin` in `backend/app/routers/twin.py` and registered it in the FastAPI application.
- Added `backend/app/services/twin_service.py` to build user-scoped figures from manual portfolios, persistent paper accounts, and saved spending transactions.
- Manual portfolio values are grouped by currency and labelled by source. Paper equity remains its own labelled figure. The response deliberately does not publish a combined net-worth total because currency conversion and liability data are unavailable.
- Runway is an estimate using persistent paper cash and expenses observed over the inclusive trailing 90-day period. The response exposes the cash label, period, monthly expense estimate, and as-of date. No spending history yields an unknown runway rather than an infinite value.
- Liabilities are explicitly marked incomplete and unknown because FinEx currently has no liability records. The legacy shared in-memory simulation is excluded because it has no owner scope.
- Added deterministic unit coverage for runway math, empty history, source labels, currency grouping, exclusion of unowned data, and invalid inputs.

## Verification

Commands run from `backend/`:

```text
python -m ruff check .
All checks passed!

python -m pytest -q -o addopts='' tests/unit/test_twin_service.py
4 passed in 0.27s
```

The required full command `python -m pytest -q` was attempted. Collection stopped with 55 import errors because the available environment is Python 3.14, the repository bootstrap requires Python 3.13, and `databricks-sql-connector` is missing. Installing the pinned requirements under Python 3.14 also failed while building `pydantic-core` (Rust toolchain setup was denied by the environment). No PostgreSQL integration test was run because no configured database was available.

## Contract notes

- The route requires the existing authenticated `Principal` and passes only its `user_id` to each data source.
- No database schema or migration changes were needed.
- Figures remain individually labelled and are not added across account types or currencies.

