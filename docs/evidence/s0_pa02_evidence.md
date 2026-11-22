# S0-PA02 — Provider terms and canonical market-data port

## Result

`backend/app/ports/market_data_port.py` is recorded as the canonical current
port because both adapters implement it and `PortfolioService` consumes it.
`backend/app/ports/market_data_provider.py` is a separate, unused protocol and
is documented as noncanonical; no route or runtime behavior was changed.

The provider review found that both named adapters return deterministic local
fixtures. `YFinanceMarketDataProvider` does not call Yahoo or import yfinance.
The reviewed yfinance documentation identifies the library as unofficial and
for research/education/personal use; Yahoo's terms do not establish a
commercial data entitlement, and its API terms leave rate limits discretionary.
See [providers.md](../market-data/providers.md) for adapter behavior, fallback
details, source links, and the production-use caveats.

## Verification

Sources were checked on 2026-11-21:

- yfinance documentation, README, and Apache-2.0 software license.
- Yahoo Terms of Service and Yahoo Developer API Terms of Use.
- Both backend market adapters, both market-data ports, `PortfolioService`,
  and backend requirements.

Required backend quality commands:

- `python -m ruff check .` (from `backend/`): PASS.
- `python -m pytest -q --no-cov tests\test_yfinance_adapter.py tests\unit\test_portfolio_service.py`
  (from `backend/`): PASS, 12 passed.
- `python -m pytest -q` (from `backend/`): 45 failed, 2,680 passed, 14 skipped,
  24 xfailed, 2 xpassed; coverage was 84.57%. The failures are in launcher
  tests that invoke `.ps1` scripts and are blocked by this host's PowerShell
  execution policy (`running scripts is disabled`), not by market-data tests.

This task adds documentation only; it does not change application code,
provider behavior, APIs, or persistent storage.
