import copy
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings
from app.domain.local_portfolio import LocalHoldingRecord, LocalPortfolioRecord
from app.ports.adapters.postgres_local_portfolio_store import PostgresLocalPortfolioStore
from app.ports.adapters.postgres_local_store import postgres_dsn
from app.ports.adapters.synthetic_local_portfolio import SyntheticLocalPortfolioCatalog


class PortfolioRepository:
    """
    Thread-safe in-memory repository for Portfolios and Holdings.
    Enforces strict multi-tenant isolation by checking user_id on every operation.
    """

    def __init__(self) -> None:
        self._portfolios: Dict[str, Dict[str, Any]] = {}
        self._holdings: Dict[str, Dict[str, Any]] = {}
        self._settings = get_settings()
        self._postgres_store = (
            PostgresLocalPortfolioStore(self._settings.app_database_url)
            if self._settings.app_persistence == "postgresql" and self._settings.app_database_url
            else None
        )

    def _ensure_postgres_user(self, user_id: str) -> None:
        if self._postgres_store is None:
            return
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(
            postgres_dsn(self._settings.app_database_url),
            row_factory=dict_row,
        ) as connection:
            connection.execute(
                "INSERT INTO finex.local_users(user_id,alias,active,created_at) "
                "VALUES(%s,%s,true,NOW()) "
                "ON CONFLICT (user_id) DO UPDATE SET active=true",
                (user_id, f"legacy-{user_id}"),
            )

    @staticmethod
    def _instrument_details(symbol: str) -> tuple[str, str, str]:
        instrument_id = f"SYN:{symbol.strip().upper()}"
        for instrument in SyntheticLocalPortfolioCatalog().snapshot().items:
            if instrument.instrument_id == instrument_id:
                return instrument_id, instrument.asset_class, instrument.sector
        return instrument_id, "EQUITY", "GENERAL"

    def _postgres_portfolio_raw(self, record: LocalPortfolioRecord) -> Dict[str, Any]:
        return {
            "portfolio_id": record.portfolio_id,
            "user_id": record.user_id,
            "name": record.name,
            "description": record.description,
            "portfolio_type": record.portfolio_type,
            "currency": record.currency,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def _postgres_holding_raw(self, record: LocalHoldingRecord) -> Dict[str, Any]:
        symbol = record.instrument_id.removeprefix("SYN:")
        _, catalog_asset_class, catalog_sector = self._instrument_details(symbol)
        return {
            "holding_id": record.holding_id,
            "portfolio_id": record.portfolio_id,
            "user_id": record.user_id,
            "symbol": symbol,
            "asset_class": record.asset_class or catalog_asset_class,
            "sector": record.sector or catalog_sector,
            "quantity": float(record.quantity),
            "avg_buy_price": float(record.average_cost),
            "currency": record.currency,
            "notes": record.notes,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

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
        if self._postgres_store is not None:
            self._ensure_postgres_user(user_id)
            now = datetime.now(timezone.utc)
            record = LocalPortfolioRecord(
                user_id=str(user_id),
                portfolio_id=str(uuid.uuid4()),
                name=name.strip(),
                description=description.strip() if description else None,
                currency=currency.upper(),
                created_at=now,
                updated_at=now,
                portfolio_type=portfolio_type,
            )
            with self._postgres_store.transaction(write=True) as transaction:
                transaction.insert_portfolio(record)
            return self._postgres_portfolio_raw(record)
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction() as transaction:
                record = transaction.get_portfolio(str(user_id), portfolio_id)
            return self._postgres_portfolio_raw(record) if record is not None else None
        item = self._portfolios.get(portfolio_id)
        if item and str(item.get("user_id")) == str(user_id):
            return copy.deepcopy(item)
        return None

    async def list_portfolios_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists all portfolios owned by user_id."""
        if self._postgres_store is not None:
            with self._postgres_store.transaction() as transaction:
                records = transaction.list_portfolios(str(user_id), limit=21)
            return [self._postgres_portfolio_raw(record) for record in records]
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction() as transaction:
                previous = transaction.get_portfolio(str(user_id), portfolio_id)
                if previous is None:
                    return None
                updated = LocalPortfolioRecord(
                    user_id=str(user_id),
                    portfolio_id=portfolio_id,
                    name=name.strip() if name is not None else previous.name,
                    description=(
                        description.strip() if description is not None else previous.description
                    ),
                    currency=currency.upper() if currency is not None else previous.currency,
                    created_at=previous.created_at,
                    updated_at=datetime.now(timezone.utc),
                    portfolio_type=(
                        portfolio_type if portfolio_type is not None else previous.portfolio_type
                    ),
                )
                transaction.update_portfolio(updated)
            return self._postgres_portfolio_raw(updated)
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction(write=True) as transaction:
                return transaction.delete_portfolio(str(user_id), portfolio_id)
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
        if self._postgres_store is not None:
            now = datetime.now(timezone.utc)
            instrument_id, _, _ = self._instrument_details(symbol)
            quantity_text = format(
                Decimal(str(quantity)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                "f",
            )
            average_cost_text = format(
                Decimal(str(avg_buy_price)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
                "f",
            )
            with self._postgres_store.transaction(write=True) as transaction:
                parent = transaction.get_portfolio(str(user_id), str(portfolio_id))
                if parent is None:
                    return None
                record = LocalHoldingRecord(
                    user_id=str(user_id),
                    portfolio_id=str(portfolio_id),
                    holding_id=str(uuid.uuid4()),
                    instrument_id=instrument_id,
                    quantity=quantity_text,
                    average_cost=average_cost_text,
                    currency=parent.currency,
                    created_at=now,
                    updated_at=now,
                    asset_class=asset_class,
                    sector=sector.strip() if sector else "General",
                    notes=notes.strip() if notes else None,
                )
                transaction.insert_holding(record)
            return self._postgres_holding_raw(record)
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction() as transaction:
                if transaction.get_portfolio(str(user_id), portfolio_id) is None:
                    return None
                records = transaction.list_holdings(str(user_id), portfolio_id, limit=101)
            return [self._postgres_holding_raw(record) for record in records]
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction() as transaction:
                record = transaction.get_holding(str(user_id), portfolio_id, holding_id)
            return self._postgres_holding_raw(record) if record is not None else None
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction(write=True) as transaction:
                previous = transaction.get_holding(str(user_id), portfolio_id, holding_id)
                parent = transaction.get_portfolio(str(user_id), portfolio_id)
                if previous is None or parent is None:
                    return None
                quantity_text = (
                    format(
                        Decimal(str(quantity)).quantize(
                            Decimal("0.000001"), rounding=ROUND_HALF_UP
                        ),
                        "f",
                    )
                    if quantity is not None
                    else previous.quantity
                )
                cost_text = (
                    format(
                        Decimal(str(avg_buy_price)).quantize(
                            Decimal("0.0001"), rounding=ROUND_HALF_UP
                        ),
                        "f",
                    )
                    if avg_buy_price is not None
                    else previous.average_cost
                )
                updated_sector = previous.sector
                if sector is not None:
                    updated_sector = sector.strip() or "General"
                updated_notes = previous.notes
                if notes is not None:
                    updated_notes = notes.strip() or None
                updated = LocalHoldingRecord(
                    user_id=str(user_id),
                    portfolio_id=portfolio_id,
                    holding_id=holding_id,
                    instrument_id=previous.instrument_id,
                    quantity=quantity_text,
                    average_cost=cost_text,
                    currency=parent.currency,
                    created_at=previous.created_at,
                    updated_at=datetime.now(timezone.utc),
                    asset_class=asset_class if asset_class is not None else previous.asset_class,
                    sector=updated_sector,
                    notes=updated_notes,
                )
                transaction.update_holding(updated)
            return self._postgres_holding_raw(updated)
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
        if self._postgres_store is not None:
            with self._postgres_store.transaction(write=True) as transaction:
                return transaction.delete_holding(str(user_id), portfolio_id, holding_id)
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
