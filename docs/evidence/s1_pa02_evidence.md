# S1-PA02 Portfolio Parity and Persistence Evidence

## Implementation

- Mounted the existing `/api/v1/portfolios` portfolio router in the application factory.
- Added principal-scoped JWT authentication to the route.
- Wired `PortfolioRepository` Postgres mode to `PostgresLocalPortfolioStore` with owner and parent checks.
- Replaced legacy float portfolio arithmetic with half-up Decimal rounding to match the S0 canonical fractional fixture.
- Updated the C1 create path to use the authenticated principal instead of a caller-supplied `X-User-ID`.

## Verification

```text
cd backend
python -m ruff check .
python -m pytest -q --no-cov tests/test_s1_pa02_portfolio.py tests/test_c1_api_success.py tests/integration/test_c1_api.py tests/unit/test_portfolio_service.py
python ../folio_math_parity.py
```

## Results

```text
Ruff: passed
Focused tests: 13 passed
S0 portfolio parity: 0 mismatching fixtures
```
