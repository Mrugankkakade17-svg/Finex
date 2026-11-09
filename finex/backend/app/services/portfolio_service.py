from typing import List, Optional

from app.adapters.market_data_adapter import MockMarketDataProvider
from app.core.exceptions import FinExException
from app.ports.market_data_port import MarketDataProvider
from app.repositories.portfolio_repository import (
    PortfolioRepository,
)
from app.repositories.portfolio_repository import (
    portfolio_repository as default_repo,
)
from app.schemas.envelope import DataStatus
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioSummaryResponse,
    PortfolioUpdate,
)
from app.services.portfolio_math import (
    calculate_allocations,
    compute_portfolio_valuations,
)


class PortfolioService:
    """
    Core domain service managing multi-tenant portfolio lifecycles,
    market quote enrichment, valuation math, and allocation snapshots.
    """

    def __init__(
        self,
        repository: Optional[PortfolioRepository] = None,
        market_data_provider: Optional[MarketDataProvider] = None,
    ):
        self.repo = repository or default_repo
        self.market_provider = market_data_provider or MockMarketDataProvider()

    # -----------------------------------------------------------------------
    # Portfolio Operations
    # -----------------------------------------------------------------------

    async def create_portfolio(self, user_id: str, data: PortfolioCreate) -> PortfolioResponse:
        """Creates a new portfolio for the user."""
        raw = await self.repo.create_portfolio(
            user_id=user_id,
            name=data.name,
            description=data.description,
            portfolio_type=data.portfolio_type.value,
            currency=data.currency,
        )
        return PortfolioResponse(
            portfolio_id=raw["portfolio_id"],
            user_id=raw["user_id"],
            name=raw["name"],
            description=raw["description"],
            portfolio_type=raw["portfolio_type"],
            currency=raw["currency"],
            total_value=0.0,
            total_cost=0.0,
            total_gain_loss=0.0,
            total_gain_loss_pct=0.0,
            holdings_count=0,
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
        )

    async def get_portfolio(self, portfolio_id: str, user_id: str) -> PortfolioResponse:
        """Fetches a portfolio and computes its current valuation."""
        raw = await self.repo.get_portfolio_by_id(portfolio_id, user_id)
        if not raw:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or access denied.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )

        holdings_raw = await self.repo.list_holdings(portfolio_id, user_id) or []

        # Fetch market prices for valuation
        symbols = [str(h["symbol"]).strip().upper() for h in holdings_raw]
        fallback_map = {
            str(h["symbol"]).strip().upper(): float(h["avg_buy_price"]) for h in holdings_raw
        }
        quotes = await self.market_provider.get_quotes(symbols, fallback_prices=fallback_map)
        quotes_map = {sym: q.price for sym, q in quotes.items()}

        total_val, total_cost, gain_loss, gain_loss_pct, _ = compute_portfolio_valuations(
            holdings_raw, quotes_map
        )

        return PortfolioResponse(
            portfolio_id=raw["portfolio_id"],
            user_id=raw["user_id"],
            name=raw["name"],
            description=raw["description"],
            portfolio_type=raw["portfolio_type"],
            currency=raw["currency"],
            total_value=total_val,
            total_cost=total_cost,
            total_gain_loss=gain_loss,
            total_gain_loss_pct=gain_loss_pct,
            holdings_count=len(holdings_raw),
            created_at=raw["created_at"],
            updated_at=raw["updated_at"],
        )

    async def list_portfolios(self, user_id: str) -> List[PortfolioResponse]:
        """Lists all portfolios for a user with calculated valuations."""
        raw_list = await self.repo.list_portfolios_by_user(user_id)
        results: List[PortfolioResponse] = []

        for raw in raw_list:
            pid = raw["portfolio_id"]
            holdings = await self.repo.list_holdings(pid, user_id) or []

            symbols = [str(h["symbol"]).strip().upper() for h in holdings]
            fallback_map = {
                str(h["symbol"]).strip().upper(): float(h["avg_buy_price"]) for h in holdings
            }
            quotes = await self.market_provider.get_quotes(symbols, fallback_prices=fallback_map)
            quotes_map = {sym: q.price for sym, q in quotes.items()}

            total_val, total_cost, gain_loss, gain_loss_pct, _ = compute_portfolio_valuations(
                holdings, quotes_map
            )

            results.append(
                PortfolioResponse(
                    portfolio_id=raw["portfolio_id"],
                    user_id=raw["user_id"],
                    name=raw["name"],
                    description=raw["description"],
                    portfolio_type=raw["portfolio_type"],
                    currency=raw["currency"],
                    total_value=total_val,
                    total_cost=total_cost,
                    total_gain_loss=gain_loss,
                    total_gain_loss_pct=gain_loss_pct,
                    holdings_count=len(holdings),
                    created_at=raw["created_at"],
                    updated_at=raw["updated_at"],
                )
            )

        return results

    async def update_portfolio(
        self, portfolio_id: str, user_id: str, data: PortfolioUpdate
    ) -> PortfolioResponse:
        """Updates portfolio metadata."""
        updated = await self.repo.update_portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
            portfolio_type=data.portfolio_type.value if data.portfolio_type else None,
            currency=data.currency,
        )
        if not updated:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or update unauthorized.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )

        return await self.get_portfolio(portfolio_id, user_id)

    async def delete_portfolio(self, portfolio_id: str, user_id: str) -> bool:
        """Deletes a portfolio and cascaded holdings."""
        deleted = await self.repo.delete_portfolio(portfolio_id, user_id)
        if not deleted:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or delete unauthorized.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )
        return True

    # -----------------------------------------------------------------------
    # Holdings Operations
    # -----------------------------------------------------------------------

    async def add_holding(
        self, portfolio_id: str, user_id: str, data: HoldingCreate
    ) -> HoldingResponse:
        """Adds a new holding and enriches it with market quote."""
        holding = await self.repo.add_holding(
            portfolio_id=portfolio_id,
            user_id=user_id,
            symbol=data.symbol,
            asset_class=data.asset_class.value,
            sector=data.sector,
            quantity=data.quantity,
            avg_buy_price=data.avg_buy_price,
            notes=data.notes,
        )
        if not holding:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or access denied.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )

        # Get current quote
        quote = await self.market_provider.get_quote(data.symbol, fallback_price=data.avg_buy_price)

        total_cost = round(holding["quantity"] * holding["avg_buy_price"], 2)
        current_value = round(holding["quantity"] * quote.price, 2)
        gain_loss = round(current_value - total_cost, 2)
        gain_loss_pct = round((gain_loss / total_cost) * 100, 2) if total_cost > 0 else 0.0

        return HoldingResponse(
            holding_id=holding["holding_id"],
            portfolio_id=holding["portfolio_id"],
            user_id=holding["user_id"],
            symbol=holding["symbol"],
            asset_class=holding["asset_class"],
            sector=holding["sector"],
            quantity=holding["quantity"],
            avg_buy_price=holding["avg_buy_price"],
            current_price=quote.price,
            current_value=current_value,
            total_cost=total_cost,
            unrealized_gain_loss=gain_loss,
            unrealized_gain_loss_pct=gain_loss_pct,
            weight_pct=100.0,
            is_stale=quote.is_stale,
            created_at=holding["created_at"],
            updated_at=holding["updated_at"],
        )

    async def list_holdings(self, portfolio_id: str, user_id: str) -> List[HoldingResponse]:
        """Lists holdings with real-time valuation and weight metrics."""
        holdings = await self.repo.list_holdings(portfolio_id, user_id)
        if holdings is None:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or access denied.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )

        symbols = [str(h["symbol"]).strip().upper() for h in holdings]
        fallback_map = {
            str(h["symbol"]).strip().upper(): float(h["avg_buy_price"]) for h in holdings
        }
        quotes = await self.market_provider.get_quotes(symbols, fallback_prices=fallback_map)
        quotes_map = {sym: q.price for sym, q in quotes.items()}

        _, _, _, _, evaluated = compute_portfolio_valuations(holdings, quotes_map)
        return evaluated

    async def update_holding(
        self,
        holding_id: str,
        portfolio_id: str,
        user_id: str,
        data: HoldingUpdate,
    ) -> HoldingResponse:
        """Updates a holding's quantity or price."""
        updated = await self.repo.update_holding(
            holding_id=holding_id,
            portfolio_id=portfolio_id,
            user_id=user_id,
            quantity=data.quantity,
            avg_buy_price=data.avg_buy_price,
            sector=data.sector,
            asset_class=data.asset_class.value if data.asset_class else None,
            notes=data.notes,
        )
        if not updated:
            raise FinExException(
                message=f"Holding '{holding_id}' not found or unauthorized.",
                error_code="HOLDING_NOT_FOUND",
                status_code=404,
            )

        quote = await self.market_provider.get_quote(
            updated["symbol"], fallback_price=updated["avg_buy_price"]
        )

        total_cost = round(updated["quantity"] * updated["avg_buy_price"], 2)
        current_value = round(updated["quantity"] * quote.price, 2)
        gain_loss = round(current_value - total_cost, 2)
        gain_loss_pct = round((gain_loss / total_cost) * 100, 2) if total_cost > 0 else 0.0

        return HoldingResponse(
            holding_id=updated["holding_id"],
            portfolio_id=updated["portfolio_id"],
            user_id=updated["user_id"],
            symbol=updated["symbol"],
            asset_class=updated["asset_class"],
            sector=updated["sector"],
            quantity=updated["quantity"],
            avg_buy_price=updated["avg_buy_price"],
            current_price=quote.price,
            current_value=current_value,
            total_cost=total_cost,
            unrealized_gain_loss=gain_loss,
            unrealized_gain_loss_pct=gain_loss_pct,
            weight_pct=100.0,
            is_stale=quote.is_stale,
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
        )

    async def delete_holding(self, holding_id: str, portfolio_id: str, user_id: str) -> bool:
        """Deletes a holding from a portfolio."""
        deleted = await self.repo.delete_holding(holding_id, portfolio_id, user_id)
        if not deleted:
            raise FinExException(
                message=f"Holding '{holding_id}' not found or delete unauthorized.",
                error_code="HOLDING_NOT_FOUND",
                status_code=404,
            )
        return True

    # -----------------------------------------------------------------------
    # Summary & Allocations Endpoint
    # -----------------------------------------------------------------------

    async def get_portfolio_summary(
        self, portfolio_id: str, user_id: str
    ) -> PortfolioSummaryResponse:
        """
        Generates full summary: total value, total cost, gain/loss,
        asset class breakdown %, sector breakdown %, and top performers.
        """
        p = await self.repo.get_portfolio_by_id(portfolio_id, user_id)
        if not p:
            raise FinExException(
                message=f"Portfolio '{portfolio_id}' not found or access denied.",
                error_code="PORTFOLIO_NOT_FOUND",
                status_code=404,
            )

        holdings = await self.repo.list_holdings(portfolio_id, user_id) or []

        symbols = [str(h["symbol"]).strip().upper() for h in holdings]
        fallback_map = {
            str(h["symbol"]).strip().upper(): float(h["avg_buy_price"]) for h in holdings
        }
        quotes = await self.market_provider.get_quotes(symbols, fallback_prices=fallback_map)
        quotes_map = {sym: q.price for sym, q in quotes.items()}

        total_val, total_cost, gain_loss, gain_loss_pct, evaluated_holdings = (
            compute_portfolio_valuations(holdings, quotes_map)
        )

        asset_alloc = calculate_allocations(evaluated_holdings, "asset_class", total_val)
        sector_alloc = calculate_allocations(evaluated_holdings, "sector", total_val)

        # Check if any quotes were stale
        has_stale = any(q.is_stale for q in quotes.values())
        data_status: DataStatus = "DELAYED" if has_stale else "LIVE"

        # Top performers sorted by unrealized_gain_loss_pct descending
        top_performers = sorted(
            evaluated_holdings,
            key=lambda x: x.unrealized_gain_loss_pct,
            reverse=True,
        )

        return PortfolioSummaryResponse(
            portfolio_id=p["portfolio_id"],
            name=p["name"],
            currency=p["currency"],
            total_value=total_val,
            total_cost=total_cost,
            total_gain_loss=gain_loss,
            total_gain_loss_pct=gain_loss_pct,
            holdings_count=len(holdings),
            data_status=data_status,
            asset_allocation=asset_alloc,
            sector_allocation=sector_alloc,
            top_performers=top_performers[:5],
        )


# Global singleton service
portfolio_service = PortfolioService()
