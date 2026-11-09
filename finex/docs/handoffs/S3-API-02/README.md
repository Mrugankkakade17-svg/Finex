# Sprint 3 API Track Handoff: S3-API-02 (Portfolio CRUD & Valuation Service)

## Overview
- **Track**: API / Backend
- **Ticket / Task ID**: `S3-API-02`
- **Owner**: Palak (Cohort Delta)
- **Reviewers**: Disha, Mitali
- **Base Branch**: `dev`
- **Feature Branch**: `feature/S3-API-02-portfolio-service`
- **Status**: Complete & Verified (228/228 Backend Tests Passing)

---

## 1. Scope & Deliverables
The goal of `S3-API-02` is to implement the core multi-tenant Portfolio Management & Valuation Service for FinEx. It provides complete CRUD operations for user portfolios and individual asset holdings, connects to a decoupled market data provider port, and calculates deterministic portfolio valuations, profit/loss metrics, and asset/sector allocation breakdowns.

### Key Components Implemented:
1. **Pydantic Schemas (`backend/app/schemas/portfolio.py`)**:
   - `PortfolioCreate`, `PortfolioUpdate`, `PortfolioResponse`
   - `HoldingCreate`, `HoldingUpdate`, `HoldingResponse`
   - `AllocationItem`, `PortfolioSummaryResponse`
   - Enums: `AssetClass` (`EQUITY`, `FIXED_INCOME`, `CASH`, `COMMODITY`, `CRYPTO`, `REAL_ESTATE`, `ALTERNATIVE`), `PortfolioType` (`GROWTH`, `BALANCED`, `INCOME`, `RETIREMENT`, `TRADING`, `INDIVIDUAL`).
   - String trim validators, uppercase normalization, and positive quantity/price validations.
2. **Ports & Market Data Adapters (`backend/app/ports/market_data_port.py`, `backend/app/adapters/market_data_adapter.py`)**:
   - `MarketDataProvider` abstract protocol interface.
   - `MockMarketDataProvider` with 15+ deterministic symbol fixtures (`AAPL`, `MSFT`, `GOOGL`, `AMZN`, `NVDA`, `TSLA`, `SPY`, `QQQ`, `BND`, `AGG`, `CASH`, `BTC`, `ETH`, `GLD`).
   - **Safe Fallback Rule**: Missing/obscure quotes fallback to `avg_buy_price` with `is_stale=True` flag and `data_status="STALE"` without zeroing out prices.
3. **Valuation & Math Engine (`backend/app/services/portfolio_math.py`)**:
   - Pure, deterministic calculation functions:
     - `calculate_holding_metrics`: computes cost, market value, unrealized gain/loss ($ and %), and portfolio weight %.
     - `compute_portfolio_valuations`: aggregations across all holdings.
     - `calculate_allocations`: grouped asset class and sector allocations summing to 100%.
4. **Multi-Tenant Repository (`backend/app/repositories/portfolio_repository.py`)**:
   - In-memory data store with thread-safe operations.
   - Strict tenant isolation: every query (`find_by_id`, `list_by_user`, `update`, `delete`, `holdings`) mandates `user_id == current_user_id`. Cross-user access returns `None` / `404 Not Found`.
5. **Domain Service (`backend/app/services/portfolio_service.py`)**:
   - Business orchestration layer: quote fetching, portfolio summaries, top/worst performer ranking, valuation enrichment.
6. **REST API Router (`backend/app/routers/portfolio.py`)**:
   - Mounted at `/api/v1/portfolios` on FastAPI app instance.
   - Full standard `APIResponse.success()` and `APIResponse.error()` envelopes with correlation ID tracing.
   - Securely protected via `get_current_user` JWT authentication dependency.

---

## 2. API Endpoints Reference

### 2.1 Portfolio Endpoints
| Method | Path | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/v1/portfolios` | Yes (Bearer JWT) | Create a new user portfolio |
| `GET` | `/api/v1/portfolios` | Yes (Bearer JWT) | List all portfolios owned by the authenticated user |
| `GET` | `/api/v1/portfolios/{id}` | Yes (Bearer JWT) | Get portfolio details and current valuation |
| `PUT` | `/api/v1/portfolios/{id}` | Yes (Bearer JWT) | Update portfolio name and/or description |
| `DELETE` | `/api/v1/portfolios/{id}` | Yes (Bearer JWT) | Delete portfolio and all associated holdings |

### 2.2 Holding Endpoints
| Method | Path | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/v1/portfolios/{id}/holdings` | Yes (Bearer JWT) | Add a holding (symbol, asset class, sector, qty, avg buy price) |
| `GET` | `/api/v1/portfolios/{id}/holdings` | Yes (Bearer JWT) | List all holdings with live market prices and metrics |
| `PUT` | `/api/v1/portfolios/{id}/holdings/{holding_id}` | Yes (Bearer JWT) | Update holding quantity or average buy price |
| `DELETE` | `/api/v1/portfolios/{id}/holdings/{holding_id}` | Yes (Bearer JWT) | Remove a holding from portfolio |

### 2.3 Valuation & Summary Endpoint
| Method | Path | Auth Required | Description |
|---|---|---|---|
| `GET` | `/api/v1/portfolios/{id}/summary` | Yes (Bearer JWT) | Comprehensive portfolio analytics: total value, total cost, gain/loss ($ and %), asset allocation %, sector allocation %, top performers |

---

## 3. Sample Response Payloads

### `GET /api/v1/portfolios/{id}/summary`
```json
{
  "message": "Portfolio summary retrieved successfully",
  "data": {
    "portfolio_id": "port_a1b2c3d4",
    "name": "Global Growth Strategy",
    "currency": "USD",
    "total_value": 3612.50,
    "total_cost": 3500.00,
    "total_gain_loss": 112.50,
    "total_gain_loss_pct": 3.21,
    "holdings_count": 2,
    "data_status": "LIVE",
    "asset_allocation": [
      {
        "category": "EQUITY",
        "value": 1885.00,
        "percentage": 52.18
      },
      {
        "category": "FIXED_INCOME",
        "value": 1727.50,
        "percentage": 47.82
      }
    ],
    "sector_allocation": [
      {
        "category": "Technology",
        "value": 1885.00,
        "percentage": 52.18
      },
      {
        "category": "Fixed Income",
        "value": 1727.50,
        "percentage": 47.82
      }
    ],
    "top_performers": [
      {
        "holding_id": "hold_x9y8z7",
        "portfolio_id": "port_a1b2c3d4",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "sector": "Technology",
        "quantity": 10.0,
        "avg_buy_price": 150.0,
        "current_price": 188.50,
        "total_cost": 1500.0,
        "current_value": 1885.0,
        "unrealized_gain_loss": 385.0,
        "unrealized_gain_loss_pct": 25.67,
        "weight_pct": 52.18,
        "is_stale": false,
        "created_at": "2026-08-28T01:54:05.123456",
        "updated_at": "2026-08-28T01:54:05.123456"
      }
    ]
  },
  "meta": {
    "correlationId": "req_8f1c4e92",
    "apiVersion": "v1",
    "dataAsOf": null,
    "dataStatus": "LIVE"
  }
}
```

---

## 4. Test Verification & Results

### Portfolio Test Suite (`backend/tests/unit/test_portfolio_service.py` & `backend/tests/contract/test_portfolio_contract.py`)
- **13 of 13 tests passed in 2.61s**:
  - `test_holding_metrics_gain`: PASSED
  - `test_holding_metrics_loss`: PASSED
  - `test_portfolio_valuations_deterministic`: PASSED
  - `test_calculate_allocations_asset_class`: PASSED
  - `test_create_and_get_portfolio`: PASSED
  - `test_multi_tenant_isolation`: PASSED
  - `test_add_holding_and_summary_calculation`: PASSED
  - `test_update_and_delete_portfolio`: PASSED
  - `test_missing_quote_safe_fallback`: PASSED
  - `test_create_and_get_portfolio_contract`: PASSED
  - `test_holdings_crud_and_summary_contract`: PASSED
  - `test_multi_tenant_security_contract`: PASSED
  - `test_unauthenticated_requests_rejected`: PASSED

### Full Backend Suite Regression Check
- **228 of 228 non-DB tests passed in 14.52s**.

---

## 5. Downstream Integration Notes
- **Frontend / Flutter Mobile**:
  - Consume `/api/v1/portfolios` to list and create user portfolios.
  - Consume `/api/v1/portfolios/{id}/summary` for the Portfolio Dashboard donut chart and gain/loss cards.
- **Databricks Pipeline Integration (`S3-DAT-02`)**:
  - Implement a `DatabricksMarketDataProvider(MarketDataProvider)` adapter when the real-time Delta Lake quote tables are live in later sprints.
