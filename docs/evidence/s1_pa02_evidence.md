# S1-PA02 Portfolio Parity and Persistence Evidence

## Implementation

- Mounted the existing `/api/v1/portfolios` portfolio router in the application factory.
- Added principal-scoped JWT authentication to the route.
- Wired `PortfolioRepository` Postgres mode to `PostgresLocalPortfolioStore` with owner and parent checks.
- Persisted portfolio type, holding asset class, sector, notes, and parent-derived currency in Postgres, including idempotent upgrades for existing local portfolio tables.
- Exposed holding notes in create, update, and list responses.
- Kept the local educational portfolio path USD-only while allowing supported three-letter currencies in the PostgreSQL-backed portfolio API.
- Replaced legacy float portfolio arithmetic with half-up Decimal rounding to match the S0 canonical fractional fixture.
- Updated the C1 create path to use the authenticated principal instead of a caller-supplied `X-User-ID`.

## Verification

```text
cd backend
python -m ruff check .
python -m ruff format --check .
python -m mypy app --platform win32 --python-version 3.13
python -m pytest -q --no-cov tests/test_s1_pa02_portfolio.py tests/test_c1_api_success.py tests/integration/test_c1_api.py tests/unit/test_portfolio_service.py
python ../folio_math_parity.py
python -m pytest -q --no-cov tests/test_s1_pa02_portfolio.py tests/unit/test_portfolio_service.py tests/unit/test_local_portfolio_domain.py tests/contract/store_contract/test_store_contract.py
python -m pytest -q --no-cov -m postgres tests/test_s1_pa02_portfolio.py
```

## Results

```text
Ruff check: passed
Ruff format: passed
Mypy (Windows target): passed
PA02 follow-up portfolio/domain/store suite: 136 passed, 5 skipped
PostgreSQL-specific PA02 test: skipped locally because APP_DATABASE_URL/DATABASE_URL is not configured
S0 portfolio parity: 0 mismatching fixtures
```

The PostgreSQL-marked round-trip test creates, reads, and updates non-USD portfolios and holdings
with custom asset class, sector, and notes. It is run by the PostgreSQL CI workflow when a database
URL is available.
