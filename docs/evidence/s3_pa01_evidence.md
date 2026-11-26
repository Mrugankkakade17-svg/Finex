# S3-PA01 Portfolio Analytics Evidence

## Implementation

- Added `GET /api/v1/portfolios/{portfolio_id}/analytics`. It uses the existing authenticated, owner-scoped holdings service and returns the existing FinEx success envelope.
- Added a deterministic calculation service for cumulative and annualized returns, annualized volatility, Sharpe ratio, benchmark beta, one-day historical and normal-parametric VaR, HHI, and stable top-N ranking.
- Added `INSUFFICIENT_DATA` behavior: history-dependent metrics remain `null` unless every position has aligned daily close prices with enough observations; concentration and top-N remain available from the current owned snapshot.
- Loads 1 year of daily close prices from the S2-PA03 market warehouse, selects an exchange matching the portfolio currency, and aligns positions and benchmark on shared dates. Missing or unavailable history degrades to `INSUFFICIENT_DATA`.
- Historical VaR uses the empirical loss quantile with linear interpolation. Parametric VaR uses the documented 95%/99% standard-normal quantiles. VaR is a one-day monetary loss at current portfolio value.
- Risk-free rate configuration: `ANALYTICS_RISK_FREE_RATE`, `ANALYTICS_RISK_FREE_RATE_SOURCE`, and `ANALYTICS_RISK_FREE_RATE_AS_OF`. The default is zero and explicitly marked unconfigured; it is not represented as an external market observation.
- No storage schema or migration was added. Existing portfolio routes remain unchanged.

## Hand-computed fixtures

1. Current values 200, 100, and 300 have total 600, weights 1/3, 1/6, and 1/2; HHI is `1/9 + 1/36 + 1/4 = 0.388888…`, displayed as `0.388889`. Top three order is MSFT, AAPL, BND.
2. One holding at prices 100, 110, 100 has daily returns 10% and -9.090909%. Its cumulative return is zero. Against benchmark prices 100, 105, 100, beta is approximately 1.955654 (sample covariance divided by sample variance); the interpolated 95% historical loss quantile times current value 100 is approximately 8.14.
3. With fewer than two daily returns, or any absent/misaligned position series, performance and VaR outputs are null and status is `INSUFFICIENT_DATA`.

## Verification log

- `backend/.venv/Scripts/python.exe -m ruff check .` — passed (`All checks passed!`).
- `backend/.venv/Scripts/python.exe -m ruff check .` — passed (`All checks passed!`).
- `backend/.venv/Scripts/python.exe -m pytest -q` — passed against merged `dev`: 3,087 passed, 25 skipped, 2 xfailed, 2 xpassed; 81.89% coverage. The repository virtual environment initially lacked `python-multipart` (already declared in requirements); after installing that declared dependency into `.venv`, the complete suite collected and passed.
- Focused service and endpoint contract run after market-history integration — 12 passed, covering hand-calculated math, market-query configuration, date alignment, insufficient history, response envelope, current HHI/top-N, and cross-user isolation.
