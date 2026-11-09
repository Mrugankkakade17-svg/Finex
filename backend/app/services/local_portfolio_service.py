"""Same-unit authorization and bounded owned manual portfolio CRUD; no pilot fallback."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4

from app.core.exceptions import FinExException
from app.domain.local_application import Clock, LocalStoreUnavailable
from app.domain.local_portfolio import (
    HOLDING_LIMIT,
    PORTFOLIO_LIMIT,
    LocalCatalogUnavailable,
    LocalHoldingRecord,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteSnapshot,
    LocalPortfolioRecord,
    LocalQuoteUnavailable,
    canonical_uuid4,
    validate_holding_record,
    validate_portfolio_record,
)
from app.ports.adapters.synthetic_local_portfolio import (
    SyntheticLocalPortfolioCatalog,
    SyntheticLocalPortfolioQuotes,
    validate_catalogue_snapshot,
    validate_quote_snapshot,
)
from app.ports.local_portfolio_quotes import LocalPortfolioCatalogPort, LocalPortfolioQuotePort
from app.ports.local_portfolio_store import LocalPortfolioStore, LocalPortfolioTransaction
from app.schemas.local_portfolio import (
    LocalHolding,
    LocalHoldingCreateRequest,
    LocalHoldingDeletion,
    LocalHoldingList,
    LocalHoldingUpdateRequest,
    LocalPortfolio,
    LocalPortfolioCatalog,
    LocalPortfolioCatalogItem,
    LocalPortfolioDeletion,
    LocalPortfolioList,
    LocalPortfolioMetrics,
    LocalPortfolioRequest,
)
from app.services.local_authorization import authorized_transaction, utc_clock, utc_now
from app.services.local_portfolio_math import calculate_portfolio_metrics


def _error(code: str, status: int, message: str) -> FinExException:
    return FinExException(message=message, error_code=code, status_code=status)


def _count(value: int, limit: int) -> int:
    if type(value) is not int or not 0 <= value <= limit:
        raise LocalStoreUnavailable()
    return value


def _portfolio_dto(row: LocalPortfolioRecord) -> LocalPortfolio:
    return LocalPortfolio(
        scope="local_educational_application",
        contract_version="local.v1",
        portfolio_version="portfolio.v1",
        portfolio_id=row.portfolio_id,
        name=row.name,
        description=row.description,
        currency="USD",
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _instrument(
    snapshot: LocalPortfolioCatalogSnapshot, instrument_id: str, *, creating: bool = False
) -> LocalPortfolioInstrument:
    found = next((row for row in snapshot.items if row.instrument_id == instrument_id), None)
    if found is None:
        if creating:
            raise _error("UNSUPPORTED_INSTRUMENT", 422, "Use a supported synthetic instrument.")
        raise LocalCatalogUnavailable()
    return found


def _holding_dto(row: LocalHoldingRecord, catalogue: LocalPortfolioCatalogSnapshot) -> LocalHolding:
    item = _instrument(catalogue, row.instrument_id)
    return LocalHolding(
        scope="local_educational_application",
        contract_version="local.v1",
        holding_version="holding.v1",
        catalog_version="synthetic_catalog.v1",
        portfolio_id=row.portfolio_id,
        holding_id=row.holding_id,
        instrument_id=item.instrument_id,
        display_name=item.display_name,
        asset_class=item.asset_class,
        sector=item.sector,
        currency="USD",
        quantity=row.quantity,
        average_cost=row.average_cost,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class LocalPortfolioService:
    def __init__(
        self,
        store: LocalPortfolioStore,
        clock: Clock = utc_clock,
        *,
        catalogue: LocalPortfolioCatalogPort | None = None,
        quotes: LocalPortfolioQuotePort | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.catalogue_port: LocalPortfolioCatalogPort = (
            SyntheticLocalPortfolioCatalog() if catalogue is None else catalogue
        )
        self.quotes_port: LocalPortfolioQuotePort = (
            SyntheticLocalPortfolioQuotes() if quotes is None else quotes
        )

    @contextmanager
    def _unit(
        self, token: str, *, write: bool = False
    ) -> Iterator[tuple[str, LocalPortfolioTransaction]]:
        try:
            with authorized_transaction(
                self.store, token, self.clock, write=write, onboarding_required=True
            ) as (session, transaction):
                yield session.user.id, transaction
        except FinExException:
            raise
        except LocalCatalogUnavailable:
            raise _error(
                "LOCAL_CATALOG_UNAVAILABLE", 503, "The local synthetic catalogue is unavailable."
            ) from None
        except LocalQuoteUnavailable:
            raise _error(
                "LOCAL_QUOTE_UNAVAILABLE", 503, "The local synthetic quote snapshot is unavailable."
            ) from None
        except Exception:
            # Store/clock/response failures cannot expose a token, private source, SQL or path.
            raise LocalStoreUnavailable() from None

    def _catalogue(self) -> LocalPortfolioCatalogSnapshot:
        try:
            return validate_catalogue_snapshot(self.catalogue_port.snapshot())
        except Exception:
            raise LocalCatalogUnavailable() from None

    def _quotes(self, requested: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        try:
            return validate_quote_snapshot(self.quotes_port.snapshot(requested), requested)
        except Exception:
            raise LocalQuoteUnavailable() from None

    @staticmethod
    def _parent(
        transaction: LocalPortfolioTransaction, user_id: str, pid: str
    ) -> LocalPortfolioRecord:
        canonical_uuid4(pid)
        row = transaction.get_portfolio(user_id, pid)
        if row is None:
            raise _error("LOCAL_PORTFOLIO_NOT_FOUND", 404, "The local portfolio was not found.")
        validate_portfolio_record(row, user_id=user_id)
        if row.portfolio_id != pid:
            raise LocalStoreUnavailable()
        return row

    @staticmethod
    def _child(
        transaction: LocalPortfolioTransaction, user_id: str, pid: str, hid: str
    ) -> LocalHoldingRecord:
        canonical_uuid4(hid)
        row = transaction.get_holding(user_id, pid, hid)
        if row is None:
            raise _error("LOCAL_HOLDING_NOT_FOUND", 404, "The local holding was not found.")
        validate_holding_record(row, user_id=user_id, portfolio_id=pid)
        if row.holding_id != hid:
            raise LocalStoreUnavailable()
        return row

    @staticmethod
    def _portfolio_rows(
        transaction: LocalPortfolioTransaction, user_id: str
    ) -> tuple[LocalPortfolioRecord, ...]:
        rows = transaction.list_portfolios(user_id, limit=PORTFOLIO_LIMIT + 1)
        if type(rows) is not list or len(rows) > PORTFOLIO_LIMIT:
            raise LocalStoreUnavailable()
        for row in rows:
            validate_portfolio_record(row, user_id=user_id)
        if len({row.portfolio_id for row in rows}) != len(rows) or (
            _count(transaction.count_portfolios(user_id), PORTFOLIO_LIMIT) != len(rows)
        ):
            raise LocalStoreUnavailable()
        return tuple(sorted(rows, key=lambda row: (row.created_at, row.portfolio_id)))

    @staticmethod
    def _holding_rows(
        transaction: LocalPortfolioTransaction, user_id: str, pid: str
    ) -> tuple[LocalHoldingRecord, ...]:
        rows = transaction.list_holdings(user_id, pid, limit=HOLDING_LIMIT + 1)
        if type(rows) is not list or len(rows) > HOLDING_LIMIT:
            raise LocalStoreUnavailable()
        for row in rows:
            validate_holding_record(row, user_id=user_id, portfolio_id=pid)
        if len({row.holding_id for row in rows}) != len(rows) or (
            len({row.instrument_id for row in rows}) != len(rows)
            or _count(transaction.count_holdings(user_id, pid), HOLDING_LIMIT) != len(rows)
        ):
            raise LocalStoreUnavailable()
        return tuple(sorted(rows, key=lambda row: (row.created_at, row.holding_id)))

    def catalogue(self, token: str) -> LocalPortfolioCatalog:
        with self._unit(token):
            snapshot = self._catalogue()
            return LocalPortfolioCatalog(
                scope="local_educational_application",
                contract_version="local.v1",
                catalog_version="synthetic_catalog.v1",
                currency="USD",
                items=[
                    LocalPortfolioCatalogItem(
                        instrument_id=row.instrument_id,
                        display_name=row.display_name,
                        asset_class=row.asset_class,
                        sector=row.sector,
                        currency="USD",
                    )
                    for row in sorted(snapshot.items, key=lambda item: item.instrument_id)
                ],
                count=len(snapshot.items),
            )

    def create_portfolio(self, token: str, payload: LocalPortfolioRequest) -> LocalPortfolio:
        with self._unit(token, write=True) as (user_id, transaction):
            count = _count(transaction.count_portfolios(user_id), PORTFOLIO_LIMIT)
            if count == PORTFOLIO_LIMIT:
                raise _error(
                    "PORTFOLIO_LIMIT_REACHED", 409, "The local portfolio limit was reached."
                )
            now = utc_now(self.clock)
            row = LocalPortfolioRecord(
                user_id, str(uuid4()), payload.name, payload.description, payload.currency, now, now
            )
            validate_portfolio_record(row, user_id=user_id)
            saved = transaction.insert_portfolio(row)
            validate_portfolio_record(saved, user_id=user_id)
            if saved != row:
                raise LocalStoreUnavailable()
            return _portfolio_dto(saved)

    def portfolios(self, token: str) -> LocalPortfolioList:
        with self._unit(token) as (user_id, transaction):
            rows = self._portfolio_rows(transaction, user_id)
            return LocalPortfolioList(
                scope="local_educational_application",
                contract_version="local.v1",
                portfolio_version="portfolio.v1",
                items=[_portfolio_dto(row) for row in rows],
                count=len(rows),
            )

    def portfolio(self, token: str, pid: str) -> LocalPortfolio:
        with self._unit(token) as (user_id, transaction):
            return _portfolio_dto(self._parent(transaction, user_id, pid))

    def update_portfolio(
        self, token: str, pid: str, payload: LocalPortfolioRequest
    ) -> LocalPortfolio:
        with self._unit(token, write=True) as (user_id, transaction):
            old = self._parent(transaction, user_id, pid)
            if (old.name, old.description, old.currency) == (
                payload.name,
                payload.description,
                payload.currency,
            ):
                return _portfolio_dto(old)
            updated = replace(
                old,
                name=payload.name,
                description=payload.description,
                currency=payload.currency,
                updated_at=utc_now(self.clock),
            )
            validate_portfolio_record(updated, user_id=user_id)
            saved = transaction.update_portfolio(updated)
            validate_portfolio_record(saved, user_id=user_id)
            if saved != updated:
                raise LocalStoreUnavailable()
            return _portfolio_dto(saved)

    def delete_portfolio(self, token: str, pid: str) -> LocalPortfolioDeletion:
        with self._unit(token, write=True) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            if transaction.delete_portfolio(user_id, pid) is not True:
                raise LocalStoreUnavailable()
            return LocalPortfolioDeletion(
                scope="local_educational_application",
                contract_version="local.v1",
                portfolio_version="portfolio.v1",
                portfolio_id=pid,
                entity_type="portfolio",
                deleted=True,
            )

    def create_holding(
        self, token: str, pid: str, payload: LocalHoldingCreateRequest
    ) -> LocalHolding:
        with self._unit(token, write=True) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            catalogue = self._catalogue()
            _instrument(catalogue, payload.instrument_id, creating=True)
            duplicate = transaction.get_holding_by_instrument(user_id, pid, payload.instrument_id)
            if duplicate is not None:
                validate_holding_record(duplicate, user_id=user_id, portfolio_id=pid)
                if duplicate.instrument_id != payload.instrument_id:
                    raise LocalStoreUnavailable()
                raise _error(
                    "HOLDING_ALREADY_EXISTS", 409, "That instrument already has a holding."
                )
            count = _count(transaction.count_holdings(user_id, pid), HOLDING_LIMIT)
            if count == HOLDING_LIMIT:
                raise _error("HOLDING_LIMIT_REACHED", 409, "The local holding limit was reached.")
            now = utc_now(self.clock)
            row = LocalHoldingRecord(
                user_id,
                pid,
                str(uuid4()),
                payload.instrument_id,
                payload.quantity,
                payload.average_cost,
                payload.currency,
                now,
                now,
            )
            validate_holding_record(row, user_id=user_id, portfolio_id=pid)
            saved = transaction.insert_holding(row)
            validate_holding_record(saved, user_id=user_id, portfolio_id=pid)
            if saved != row:
                raise LocalStoreUnavailable()
            return _holding_dto(saved, catalogue)

    def holdings(self, token: str, pid: str) -> LocalHoldingList:
        with self._unit(token) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            rows = self._holding_rows(transaction, user_id, pid)
            catalogue = self._catalogue()
            return LocalHoldingList(
                scope="local_educational_application",
                contract_version="local.v1",
                holding_version="holding.v1",
                catalog_version="synthetic_catalog.v1",
                portfolio_id=pid,
                items=[_holding_dto(row, catalogue) for row in rows],
                count=len(rows),
            )

    def holding(self, token: str, pid: str, hid: str) -> LocalHolding:
        with self._unit(token) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            row = self._child(transaction, user_id, pid, hid)
            return _holding_dto(row, self._catalogue())

    def update_holding(
        self, token: str, pid: str, hid: str, payload: LocalHoldingUpdateRequest
    ) -> LocalHolding:
        with self._unit(token, write=True) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            old = self._child(transaction, user_id, pid, hid)
            catalogue = self._catalogue()
            _instrument(catalogue, old.instrument_id)
            if (old.quantity, old.average_cost, old.currency) == (
                payload.quantity,
                payload.average_cost,
                payload.currency,
            ):
                return _holding_dto(old, catalogue)
            updated = replace(
                old,
                quantity=payload.quantity,
                average_cost=payload.average_cost,
                currency=payload.currency,
                updated_at=utc_now(self.clock),
            )
            validate_holding_record(updated, user_id=user_id, portfolio_id=pid)
            saved = transaction.update_holding(updated)
            validate_holding_record(saved, user_id=user_id, portfolio_id=pid)
            if saved != updated:
                raise LocalStoreUnavailable()
            return _holding_dto(saved, catalogue)

    def delete_holding(self, token: str, pid: str, hid: str) -> LocalHoldingDeletion:
        with self._unit(token, write=True) as (user_id, transaction):
            self._parent(transaction, user_id, pid)
            row = self._child(transaction, user_id, pid, hid)
            _instrument(self._catalogue(), row.instrument_id)
            if transaction.delete_holding(user_id, pid, hid) is not True:
                raise LocalStoreUnavailable()
            return LocalHoldingDeletion(
                scope="local_educational_application",
                contract_version="local.v1",
                holding_version="holding.v1",
                portfolio_id=pid,
                holding_id=hid,
                entity_type="holding",
                deleted=True,
            )

    def metrics(self, token: str, pid: str) -> LocalPortfolioMetrics:
        with self._unit(token) as (user_id, transaction):
            parent = self._parent(transaction, user_id, pid)
            rows = self._holding_rows(transaction, user_id, pid)
            catalogue = self._catalogue()
            for row in rows:
                _instrument(catalogue, row.instrument_id)
            quotes = self._quotes(tuple(row.instrument_id for row in rows)) if rows else None
            return calculate_portfolio_metrics(parent, rows, catalogue, quotes, utc_now(self.clock))
