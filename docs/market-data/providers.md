# Market-data adapters, terms, and canonical port

**Reviewed:** 2026-11-21
**Scope:** Existing backend adapters and their interfaces; this is a source review,
not a provider integration or legal opinion.

## Decision

Use `backend/app/ports/market_data_port.py` as the canonical market-data port
for the current application. Both existing adapters implement this ABC, and
`PortfolioService` accepts and uses this interface. This is the only choice
that describes the running portfolio path without changing its routes or
injectable adapter contract.

`backend/app/ports/market_data_provider.py` is a second, currently unused
`MarketDataProvider` protocol with a different `Quote` model and method
signature. Its source comment says a yfinance provider and a 15-minute cache
are in use, but neither is present in the inspected implementation. Treat that
protocol and its comment as noncanonical; do not infer runtime behavior from
them. Removing or migrating it should be a separate change with call-site and
contract updates.

The current port exposes `symbol`, price/change values, one timestamp, and an
`is_stale` flag. It does not expose currency, source, a provider-supplied
`as_of`, or explicit `LIVE`/`DELAYED`/`CACHED` status. Consequently, this
contract is adequate for existing code compatibility but is not sufficient to
make truthful real-market freshness or licensing claims by itself.

## What the two adapters actually do

| Adapter | Actual behavior in this repository | Fallback behavior |
| --- | --- | --- |
| `MockMarketDataProvider` (`backend/app/adapters/market_data_adapter.py`) | Returns a fixed in-process fixture map. It makes no network request and does not read a market feed. Known fixture quotes are marked non-stale and stamped with the current local time; that timestamp is generation time, not an observed market timestamp. | For an unknown symbol, a positive supplied fallback price is returned as stale. With no positive fallback, the adapter returns a hard-coded `100.0`, also stale. That number is a demo placeholder, not a safe market-price fallback. |
| `YFinanceMarketDataProvider` (`backend/app/adapters/yfinance_adapter.py`) | Despite its class name, it imports no yfinance package and performs no HTTP or provider request. It returns five hard-coded prices, marked stale, plus a small deterministic search catalogue. `timeout_seconds` and `fail_mode` simulate error paths; the simulated rate-limit response uses a fixed 30-second retry hint and does not represent a Yahoo quota. | For an unknown symbol, a positive supplied fallback price is returned as stale; otherwise it raises `SymbolNotFoundException`. Its configured timeout, unavailable, and rate-limit modes are synthetic tests, not observed upstream failures. |

Neither adapter is a production market-data integration. The repository does
not declare the `yfinance` package as a backend dependency, and the adapter
name is not evidence that Yahoo data is being retrieved.

## Provider terms and operational limits

| Provider/source | Free tier and limits | Delay/freshness | Licence and permitted use | Fallback / suitability |
| --- | --- | --- | --- | --- |
| FinEx `MockMarketDataProvider` fixtures | Not an external provider: there is no provider free tier, quota, or request-rate limit. The current fixture is local and deterministic. | No market-data delay can be stated because no market data is fetched. The generated timestamp must not be interpreted as the price's as-of time. | No third-party provider licence applies to these in-repository test/demo constants. They are synthetic examples, not licensed exchange data. | Its code fallback is either the caller's positive cost-basis value or `100.0`; both are stale, and the latter is an arbitrary placeholder. Keep this adapter limited to local/demo/test use. |
| Yahoo Finance data accessed through community `yfinance` | `yfinance` is software, not a Yahoo-authorized free-tier plan. The reviewed project documentation publishes no numerical request quota. Yahoo's API terms reserve discretion to impose rate limits and prohibit excessive/abusive volume; no fixed quota, uptime, or support commitment is established here. Do not treat the adapter's simulated 30-second retry hint as a documented limit. | The reviewed yfinance documentation does not provide a service-level freshness or delay guarantee. Yahoo's displayed quote timing can vary by instrument/market and product; a UI label is not an API entitlement. The current repository adapter is entirely fixture-based and cannot establish actual quote age. | The yfinance project is Apache-2.0 licensed; that license covers the software, not Yahoo's underlying data or a right to redistribute it. The project warns that it is unofficial, intended for research/education, and that Yahoo Finance API use is intended for personal use. Yahoo's general Terms restrict automated collection without express prior permission; the separate Yahoo API terms govern authorized API use and restrict deriving income/use in commercial services unless specifically permitted or Yahoo gives express written permission. Obtain written authorization and review applicable market-data rights before any organizational, commercial, or end-user deployment. | Current code returns a hard-coded fixture for known symbols; for unknown ones it uses a positive caller-supplied fallback as stale or raises `SymbolNotFoundException`. This is not a Yahoo outage fallback. Not approved as a real or production provider based on the reviewed terms. |

**Operational conclusion:** No verified Yahoo free-tier quota, permitted delay,
or commercial data licence is established by this review. Do not describe this
adapter as live, delayed by a fixed interval, free for commercial use, or
production-ready. Before adding a real provider, select a provider/plan whose
contract explicitly permits the intended application and redistribution, and
record its quotas, market coverage, delay, attribution, retention, and fallback
requirements. Expose provider source and source timestamp and label freshness
truthfully in the application.

## Sources checked

All sources below were checked on 2026-11-21. Provider terms can change; recheck
them before integrating or deploying an upstream feed.

1. [yfinance documentation — legal disclaimer](https://ranaroussi.github.io/yfinance/):
   states that yfinance is not affiliated with Yahoo, is intended for research
   and educational use, and that Yahoo Finance API use is intended for personal
   use; directs users to Yahoo terms for data rights.
2. [yfinance project README — Legal Stuff](https://github.com/ranaroussi/yfinance#legal-stuff):
   repeats the disclaimer and links the Yahoo terms.
3. [yfinance LICENSE.txt](https://github.com/ranaroussi/yfinance/blob/main/LICENSE.txt):
   Apache License 2.0 for the yfinance software only.
4. [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html),
   especially section 2.4 (automated collection and competing use), section
   2.5 (use of services), and section 2.8 (ownership and reuse).
5. [Yahoo Developer API Terms of Use](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html):
   rate limits may be imposed at Yahoo's discretion; reasonable-volume
   restrictions apply, and commercial use/income requires specific permission
   unless the API documents permit it. The API terms direct applications to
   register and contact Yahoo about acceptable use or limit increases.

Yahoo's general Terms and the Yahoo Developer API Terms cover different
contexts. This review does not establish that the unofficial endpoints used
by yfinance are an authorized Yahoo API integration or that any particular
application is permitted.

## Repository paths reviewed

- `backend/app/adapters/market_data_adapter.py`
- `backend/app/adapters/yfinance_adapter.py`
- `backend/app/ports/market_data_port.py`
- `backend/app/ports/market_data_provider.py`
- `backend/app/services/portfolio_service.py`
- `backend/requirements.txt`
