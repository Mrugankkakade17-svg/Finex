import copy
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class PortfolioRepository:
    """
    Thread-safe in-memory repository for Portfolios and Holdings.
    Enforces strict multi-tenant isolation by checking user_id on every operation.
    """

    def __init__(self) -> None:
        self._portfolios: Dict[str, Dict[str, Any]] = {}
        self._holdings: Dict[str, Dict[str, Any]] = {}

    def clear(self) -> None:
        """Clear all stored portfolios and holdings (for testing)."""
        self._portfolios.clear()
        self._holdings.clear()

    # -----------------------------------------------------------------------
    # Portfolio CRUD (Multi-tenant scoped)
    # -----------------------------------------------------------------------

    async def create_portfolio(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        portfolio_type: str = "INDIVIDUAL",
        currency: str = "USD",
    ) -> Dict[str, Any]:
        """Creates a portfolio owned by user_id."""
        pid = f"port_{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        item: Dict[str, Any] = {
            "portfolio_id": pid,
            "user_id": str(user_id),
            "name": name.strip(),
            "description": description.strip() if description else None,
            "portfolio_type": portfolio_type,
            "currency": currency.upper(),
            "created_at": now,
            "updated_at": now,
        }

        self._portfolios[pid] = item
        return copy.deepcopy(item)

    async def get_portfolio_by_id(
        self, portfolio_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Returns portfolio only if owned by user_id."""
        item = self._portfolios.get(portfolio_id)
        if item and str(item.get("user_id")) == str(user_id):
            return copy.deepcopy(item)
        return None

    async def list_portfolios_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists all portfolios owned by user_id."""
        results = [
            copy.deepcopy(p)
            for p in self._portfolios.values()
            if str(p.get("user_id")) == str(user_id)
        ]
        results.sort(key=lambda x: x.get("created_at") or datetime.min)
        return results

    async def update_portfolio(
        self,
        portfolio_id: str,
        user_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        portfolio_type: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Updates portfolio fields if owned by user_id."""
        item = self._portfolios.get(portfolio_id)
        if not item or str(item.get("user_id")) != str(user_id):
            return None

        if name is not None:
            item["name"] = name.strip()
        if description is not None:
            item["description"] = description.strip() if description else None
        if portfolio_type is not None:
            item["portfolio_type"] = portfolio_type
        if currency is not None:
            item["currency"] = currency.upper()

        item["updated_at"] = datetime.now()
        return copy.deepcopy(item)

    async def delete_portfolio(self, portfolio_id: str, user_id: str) -> bool:
        """Deletes portfolio and cascaded holdings if owned by user_id."""
        item = self._portfolios.get(portfolio_id)
        if not item or str(item.get("user_id")) != str(user_id):
            return False

        # Delete portfolio
        del self._portfolios[portfolio_id]

        # Cascade delete holdings
        to_delete = [
            hid
            for hid, h in self._holdings.items()
            if str(h.get("portfolio_id")) == str(portfolio_id)
        ]
        for hid in to_delete:
            self._holdings.pop(hid, None)

        return True

    # -----------------------------------------------------------------------
    # Holdings CRUD (Multi-tenant scoped)
    # -----------------------------------------------------------------------

    async def add_holding(
        self,
        portfolio_id: str,
        user_id: str,
        symbol: str,
        asset_class: str,
        sector: Optional[str],
        quantity: float,
        avg_buy_price: float,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Adds a holding to a portfolio verified to belong to user_id."""
        p = self._portfolios.get(portfolio_id)
        if not p or str(p.get("user_id")) != str(user_id):
            return None

        hid = f"hold_{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        holding: Dict[str, Any] = {
            "holding_id": hid,
            "portfolio_id": str(portfolio_id),
            "user_id": str(user_id),
            "symbol": symbol.strip().upper(),
            "asset_class": asset_class,
            "sector": sector.strip() if sector else "General",
            "quantity": float(quantity),
            "avg_buy_price": float(avg_buy_price),
            "notes": notes.strip() if notes else None,
            "created_at": now,
            "updated_at": now,
        }

        self._holdings[hid] = holding
        return copy.deepcopy(holding)

    async def list_holdings(
        self, portfolio_id: str, user_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Lists holdings for portfolio belonging to user_id."""
        p = self._portfolios.get(portfolio_id)
        if not p or str(p.get("user_id")) != str(user_id):
            return None

        results = [
            copy.deepcopy(h)
            for h in self._holdings.values()
            if str(h.get("portfolio_id")) == str(portfolio_id)
            and str(h.get("user_id")) == str(user_id)
        ]
        results.sort(key=lambda x: x.get("created_at") or datetime.min)
        return results

    async def get_holding(
        self, holding_id: str, portfolio_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Returns holding if it belongs to the given portfolio and user."""
        h = self._holdings.get(holding_id)
        if (
            h
            and str(h.get("portfolio_id")) == str(portfolio_id)
            and str(h.get("user_id")) == str(user_id)
        ):
            return copy.deepcopy(h)
        return None

    async def update_holding(
        self,
        holding_id: str,
        portfolio_id: str,
        user_id: str,
        quantity: Optional[float] = None,
        avg_buy_price: Optional[float] = None,
        sector: Optional[str] = None,
        asset_class: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Updates a holding with ownership check."""
        h = self._holdings.get(holding_id)
        if (
            not h
            or str(h.get("portfolio_id")) != str(portfolio_id)
            or str(h.get("user_id")) != str(user_id)
        ):
            return None

        if quantity is not None:
            h["quantity"] = float(quantity)
        if avg_buy_price is not None:
            h["avg_buy_price"] = float(avg_buy_price)
        if sector is not None:
            h["sector"] = sector.strip() if sector else "General"
        if asset_class is not None:
            h["asset_class"] = asset_class
        if notes is not None:
            h["notes"] = notes.strip() if notes else None

        h["updated_at"] = datetime.now()
        return copy.deepcopy(h)

    async def delete_holding(self, holding_id: str, portfolio_id: str, user_id: str) -> bool:
        """Deletes a holding with ownership check."""
        h = self._holdings.get(holding_id)
        if (
            not h
            or str(h.get("portfolio_id")) != str(portfolio_id)
            or str(h.get("user_id")) != str(user_id)
        ):
            return False

        del self._holdings[holding_id]
        return True


# Global singleton instance
portfolio_repository = PortfolioRepository()
