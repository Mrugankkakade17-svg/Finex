"""Current-authorized owned S3 state; no implicit funding or order execution."""

from dataclasses import dataclass, replace
from uuid import uuid4

from app.core.exceptions import FinExException
from app.domain.local_application import Clock, LocalStoreUnavailable
from app.domain.local_foundation import (
    FOUNDATION_VERSION,
    OPENING_CENTS,
    WATCHLIST_ITEM_LIMIT,
    WATCHLIST_LIMIT,
    PaperAccountRecord,
    PaperOpeningRecord,
    WatchlistItemRecord,
    WatchlistRecord,
    money_text,
    validate_account,
    validate_item,
    validate_opening,
    validate_watchlist,
)
from app.domain.local_portfolio import LocalCatalogUnavailable, LocalPortfolioInstrument
from app.ports.adapters.synthetic_local_portfolio import (
    SyntheticLocalPortfolioCatalog,
    SyntheticLocalPortfolioQuotes,
    validate_catalogue_snapshot,
)
from app.ports.local_foundation_store import LocalFoundationStore, LocalFoundationTransaction
from app.ports.local_portfolio_quotes import LocalPortfolioCatalogPort, LocalPortfolioQuotePort
from app.schemas.envelope import DataStatus
from app.schemas.local_foundation import (
    SCOPE,
    FoundationInstrument,
    FoundationScope,
    MarketSearchData,
    PaperAccount,
    PaperAccountData,
    PaperLedgerData,
    PaperOpeningEntry,
    PaperOpenRequest,
    WatchlistCollectionData,
    WatchlistData,
    WatchlistDeletedData,
    WatchlistItem,
    WatchlistItemData,
    WatchlistItemRemovedData,
    WatchlistRequest,
    WatchlistSummary,
)
from app.services.local_authorization import authorized_transaction, utc_clock, utc_now
from app.services.local_foundation_quotes import LocalFoundationQuotes


@dataclass(frozen=True)
class FoundationResult:
    data: FoundationScope
    data_as_of: str | None = None
    data_status: DataStatus = "CACHED"


def failure(code: str, message: str, status: int = 404) -> FinExException:
    return FinExException(message, code, status)


class LocalFoundationService:
    def __init__(
        self,
        store: LocalFoundationStore,
        clock: Clock = utc_clock,
        *,
        catalogue: LocalPortfolioCatalogPort | None = None,
        quotes: LocalPortfolioQuotePort | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._catalogue = catalogue if catalogue is not None else SyntheticLocalPortfolioCatalog()
        self._quotes = LocalFoundationQuotes(
            quotes if quotes is not None else SyntheticLocalPortfolioQuotes(), clock
        )

    def _catalog(self) -> dict[str, LocalPortfolioInstrument]:
        try:
            snapshot = validate_catalogue_snapshot(self._catalogue.snapshot())
            return {item.instrument_id: item for item in snapshot.items}
        except Exception:
            raise LocalCatalogUnavailable() from None

    @staticmethod
    def _supported(
        catalogue: dict[str, LocalPortfolioInstrument], instrument_id: str
    ) -> LocalPortfolioInstrument:
        if instrument_id not in catalogue:
            raise failure("INSTRUMENT_NOT_FOUND", "This synthetic instrument is not supported.")
        return catalogue[instrument_id]

    @staticmethod
    def _instrument(item: LocalPortfolioInstrument) -> FoundationInstrument:
        return FoundationInstrument(
            instrument_id=item.instrument_id,
            display_name=item.display_name,
            asset_class=item.asset_class,
            sector=item.sector,
            currency="USD",
        )

    def search(self, token: str, query: str, limit: int) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True):
            needle = query.casefold()
            found = sorted(
                (
                    item
                    for item in self._catalog().values()
                    if needle in item.instrument_id.casefold()
                    or needle in item.display_name.casefold()
                ),
                key=lambda item: item.instrument_id,
            )[:limit]
            result = MarketSearchData(
                **SCOPE,
                catalog_version="synthetic_catalog.v1",
                query=query,
                limit=limit,
                count=len(found),
                items=[self._instrument(item) for item in found],
            )
        return FoundationResult(result, "2026-01-01T00:00:00Z")

    def quote(self, token: str, instrument_id: str) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True):
            self._supported(self._catalog(), instrument_id)
            result = self._quotes.quote(instrument_id)
        status: DataStatus = "CACHED" if result.unit_price is not None else "UNAVAILABLE"
        return FoundationResult(result, result.quote_as_of, status)

    @staticmethod
    def _watchlist(
        transaction: LocalFoundationTransaction, owner: str, watchlist_id: str
    ) -> WatchlistRecord:
        record = transaction.watchlist(owner, watchlist_id)
        if record is None:
            raise failure("WATCHLIST_NOT_FOUND", "The owned watchlist was not found.")
        validate_watchlist(record, owner)
        if record.watchlist_id != watchlist_id:
            raise LocalStoreUnavailable()
        return record

    @staticmethod
    def _items(
        transaction: LocalFoundationTransaction, record: WatchlistRecord
    ) -> list[WatchlistItemRecord]:
        items = transaction.items(record.user_id, record.watchlist_id, WATCHLIST_ITEM_LIMIT + 1)
        if type(items) is not list or len(items) > WATCHLIST_ITEM_LIMIT:
            raise LocalStoreUnavailable()
        for item in items:
            validate_item(item, record.user_id)
            if (
                item.watchlist_id != record.watchlist_id
                or not record.created_at <= item.added_at <= record.updated_at
            ):
                raise LocalStoreUnavailable()
        identifiers = [item.instrument_id for item in items]
        if len(set(identifiers)) != len(identifiers) or items != sorted(
            items, key=lambda item: (item.added_at, item.instrument_id)
        ):
            raise LocalStoreUnavailable()
        return items

    @staticmethod
    def _summary(record: WatchlistRecord, count: int) -> WatchlistSummary:
        return WatchlistSummary(
            watchlist_id=record.watchlist_id,
            name=record.name,
            created_at=record.created_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
            item_count=count,
        )

    def _item_dto(
        self, item: WatchlistItemRecord, catalogue: dict[str, LocalPortfolioInstrument]
    ) -> WatchlistItem:
        source = self._supported(catalogue, item.instrument_id)
        return WatchlistItem(
            instrument_id=source.instrument_id,
            display_name=source.display_name,
            asset_class=source.asset_class,
            sector=source.sector,
            currency="USD",
            added_at=item.added_at.isoformat(),
        )

    def _full(
        self, transaction: LocalFoundationTransaction, record: WatchlistRecord
    ) -> WatchlistData:
        items = self._items(transaction, record)
        catalogue = self._catalog() if items else {}
        return WatchlistData(
            **SCOPE,
            watchlist_version="watchlist.v1",
            watchlist_id=record.watchlist_id,
            name=record.name,
            created_at=record.created_at.isoformat(),
            updated_at=record.updated_at.isoformat(),
            item_count=len(items),
            items=[self._item_dto(item, catalogue) for item in items],
        )

    @staticmethod
    def _watchlists(transaction: LocalFoundationTransaction, owner: str) -> list[WatchlistRecord]:
        records = transaction.watchlists(owner, WATCHLIST_LIMIT + 1)
        if type(records) is not list or len(records) > WATCHLIST_LIMIT:
            raise LocalStoreUnavailable()
        for record in records:
            validate_watchlist(record, owner)
        if len({record.watchlist_id for record in records}) != len(records) or records != sorted(
            records, key=lambda record: (record.created_at, record.watchlist_id)
        ):
            raise LocalStoreUnavailable()
        return records

    def lists(self, token: str) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            records = self._watchlists(transaction, session.user.id)
            result = WatchlistCollectionData(
                **SCOPE,
                watchlist_version="watchlist.v1",
                limit=10,
                count=len(records),
                items=[
                    self._summary(record, len(self._items(transaction, record)))
                    for record in records
                ],
            )
        return FoundationResult(result)

    def create_list(self, token: str, payload: WatchlistRequest) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            records = self._watchlists(transaction, session.user.id)
            if len(records) == WATCHLIST_LIMIT:
                raise failure(
                    "WATCHLIST_LIMIT", "An owned learner can keep at most 10 watchlists.", 409
                )
            now = utc_now(self._clock)
            record = WatchlistRecord(session.user.id, str(uuid4()), payload.name, now, now)
            transaction.insert_watchlist(record)
            saved = self._watchlist(transaction, session.user.id, record.watchlist_id)
            if saved != record:
                raise LocalStoreUnavailable()
            result = self._full(transaction, saved)
        return FoundationResult(result, saved.updated_at.isoformat())

    def list(self, token: str, watchlist_id: str) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            record = self._watchlist(transaction, session.user.id, watchlist_id)
            result = self._full(transaction, record)
        return FoundationResult(result, record.updated_at.isoformat())

    def _updated(self, record: WatchlistRecord, *, name: str | None = None) -> WatchlistRecord:
        now = utc_now(self._clock)
        if now < record.updated_at:
            raise LocalStoreUnavailable()
        return replace(record, name=name if name is not None else record.name, updated_at=now)

    @staticmethod
    def _save_list(transaction: LocalFoundationTransaction, record: WatchlistRecord) -> None:
        if (
            transaction.update_watchlist(record) is not True
            or transaction.watchlist(record.user_id, record.watchlist_id) != record
        ):
            raise LocalStoreUnavailable()

    def update_list(
        self, token: str, watchlist_id: str, payload: WatchlistRequest
    ) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            record = self._watchlist(transaction, session.user.id, watchlist_id)
            if record.name != payload.name:
                record = self._updated(record, name=payload.name)
                self._save_list(transaction, record)
            result = self._full(transaction, record)
        return FoundationResult(result, record.updated_at.isoformat())

    def delete_list(self, token: str, watchlist_id: str) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            record = self._watchlist(transaction, session.user.id, watchlist_id)
            now = self._updated(record).updated_at
            if (
                transaction.delete_watchlist(session.user.id, watchlist_id) is not True
                or transaction.watchlist(session.user.id, watchlist_id) is not None
                or transaction.items(session.user.id, watchlist_id, 101)
            ):
                raise LocalStoreUnavailable()
            result = WatchlistDeletedData(
                **SCOPE, watchlist_version="watchlist.v1", watchlist_id=watchlist_id, deleted=True
            )
        return FoundationResult(result, now.isoformat())

    def add_item(self, token: str, watchlist_id: str, instrument_id: str) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            record = self._watchlist(transaction, session.user.id, watchlist_id)
            catalogue = self._catalog()
            self._supported(catalogue, instrument_id)
            items = self._items(transaction, record)
            item = next((item for item in items if item.instrument_id == instrument_id), None)
            if item is None:
                if len(items) == WATCHLIST_ITEM_LIMIT:
                    raise failure(
                        "WATCHLIST_ITEM_LIMIT",
                        "An owned watchlist can keep at most 100 instruments.",
                        409,
                    )
                record = self._updated(record)
                item = WatchlistItemRecord(
                    session.user.id, watchlist_id, instrument_id, record.updated_at
                )
                transaction.insert_item(item)
                self._save_list(transaction, record)
                if transaction.item(session.user.id, watchlist_id, instrument_id) != item:
                    raise LocalStoreUnavailable()
            result = WatchlistItemData(
                **SCOPE,
                watchlist_version="watchlist.v1",
                watchlist_item_version="watchlist_item.v1",
                watchlist_id=watchlist_id,
                item=self._item_dto(item, catalogue),
            )
        return FoundationResult(result, item.added_at.isoformat())

    def remove_item(self, token: str, watchlist_id: str, instrument_id: str) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            record = self._watchlist(transaction, session.user.id, watchlist_id)
            self._supported(self._catalog(), instrument_id)
            items = self._items(transaction, record)
            if any(item.instrument_id == instrument_id for item in items):
                if (
                    transaction.delete_item(session.user.id, watchlist_id, instrument_id)
                    is not True
                ):
                    raise LocalStoreUnavailable()
                record = self._updated(record)
                self._save_list(transaction, record)
                if transaction.item(session.user.id, watchlist_id, instrument_id) is not None:
                    raise LocalStoreUnavailable()
            result = WatchlistItemRemovedData(
                **SCOPE,
                watchlist_version="watchlist.v1",
                watchlist_item_version="watchlist_item.v1",
                watchlist_id=watchlist_id,
                instrument_id=instrument_id,
                removed=True,
            )
        return FoundationResult(result, record.updated_at.isoformat())

    @staticmethod
    def _account(transaction: LocalFoundationTransaction, owner: str) -> PaperAccountRecord | None:
        account = transaction.account(owner)
        if account is not None:
            validate_account(account, owner)
            entry = transaction.opening(owner, account.account_id, account.opening_ledger_id)
            if entry is None:
                raise LocalStoreUnavailable()
            validate_opening(entry, owner)
            if (
                entry.account_id != account.account_id
                or entry.ledger_id != account.opening_ledger_id
                or entry.created_at != account.created_at
                or entry.cash_after_cents != account.cash_balance_cents
            ):
                raise LocalStoreUnavailable()
        return account

    @staticmethod
    def _account_dto(account: PaperAccountRecord | None) -> PaperAccountData:
        record = (
            PaperAccount(
                account_id=account.account_id,
                opening_ledger_id=account.opening_ledger_id,
                currency="USD",
                opening_cash="10000.00",
                cash_balance=money_text(account.cash_balance_cents),
                created_at=account.created_at.isoformat(),
            )
            if account is not None
            else None
        )
        return PaperAccountData(
            **SCOPE, paper_account_version="paper_account.v1", simulation=True, account=record
        )

    def account(self, token: str) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            account = self._account(transaction, session.user.id)
            result = self._account_dto(account)
        return FoundationResult(
            result, account.created_at.isoformat() if account is not None else None
        )

    def open_account(self, token: str, payload: PaperOpenRequest) -> FoundationResult:
        with authorized_transaction(
            self._store, token, self._clock, write=True, onboarding_required=True
        ) as (session, transaction):
            if payload.foundation_version != FOUNDATION_VERSION:
                raise failure(
                    "MARKET_FOUNDATION_VERSION_MISMATCH",
                    "The supported market foundation version is required.",
                    409,
                )
            account = self._account(transaction, session.user.id)
            if account is None:
                now = utc_now(self._clock)
                account = PaperAccountRecord(
                    session.user.id,
                    str(uuid4()),
                    str(uuid4()),
                    "USD",
                    OPENING_CENTS,
                    OPENING_CENTS,
                    now,
                )
                entry = PaperOpeningRecord(
                    session.user.id,
                    account.account_id,
                    account.opening_ledger_id,
                    0,
                    OPENING_CENTS,
                    OPENING_CENTS,
                    now,
                )
                transaction.insert_account_with_opening(account, entry)
                saved = self._account(transaction, session.user.id)
                if saved != account:
                    raise LocalStoreUnavailable()
            result = self._account_dto(account)
        return FoundationResult(result, account.created_at.isoformat())

    def ledger(self, token: str, limit: int, after_sequence: int) -> FoundationResult:
        with authorized_transaction(self._store, token, self._clock, onboarding_required=True) as (
            session,
            transaction,
        ):
            account = self._account(transaction, session.user.id)
            if account is None:
                raise failure(
                    "PAPER_ACCOUNT_NOT_OPEN",
                    "Explicitly open the simulated account before reading its ledger.",
                )
            opening = transaction.opening(
                session.user.id, account.account_id, account.opening_ledger_id
            )
            if opening is None:
                raise LocalStoreUnavailable()
            records = transaction.ledger(
                session.user.id, account.account_id, after_sequence, limit + 1
            )
            if type(records) is not list or len(records) > limit + 1:
                raise LocalStoreUnavailable()
            for record in records:
                validate_opening(record, session.user.id)
                if (
                    record != opening
                    or record.account_id != account.account_id
                    or record.ledger_id != account.opening_ledger_id
                    or record.sequence <= after_sequence
                ):
                    raise LocalStoreUnavailable()
            sequences = [record.sequence for record in records]
            if sequences != sorted(set(sequences)):
                raise LocalStoreUnavailable()
            items = [
                PaperOpeningEntry(
                    ledger_id=record.ledger_id,
                    account_id=record.account_id,
                    sequence=record.sequence,
                    entry_type="OPENING",
                    cash_delta="10000.00",
                    cash_after="10000.00",
                    instrument_id=None,
                    quantity_delta=None,
                    position_after=None,
                    order_id=None,
                    trade_id=None,
                    corrects_ledger_id=None,
                    created_at=record.created_at.isoformat(),
                )
                for record in records[:limit]
            ]
            result = PaperLedgerData(
                **SCOPE,
                paper_ledger_version="paper_ledger.v1",
                simulation=True,
                account_id=account.account_id,
                limit=limit,
                after_sequence=after_sequence,
                count=len(items),
                items=items,
                next_cursor=items[-1].sequence if len(records) > limit else None,
            )
        return FoundationResult(result, items[-1].created_at if items else None)
