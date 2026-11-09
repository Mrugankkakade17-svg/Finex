"""Exhaustive strict S3 wire schemas; nullable fields are still required."""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self, TypedDict

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.domain.local_foundation import PUBLIC_INTEGER_MAX
from app.schemas.local_portfolio import Group, InstrumentId, Money, Name, Price, UtcText, Uuid4


class ScopeFields(TypedDict):
    scope: Literal["local_educational_application"]
    contract_version: Literal["local.v1"]
    foundation_version: Literal["market_foundation.v1"]


SCOPE: ScopeFields = {
    "scope": "local_educational_application",
    "contract_version": "local.v1",
    "foundation_version": "market_foundation.v1",
}


def _integer(value: object) -> object:
    if type(value) is not int:
        raise ValueError("An integer is required")
    return value


def _true(value: object) -> object:
    if value is not True:
        raise ValueError("A boolean true confirmation is required")
    return value


def _false(value: object) -> object:
    if value is not False:
        raise ValueError("A boolean false failure is required")
    return value


TrueValue = Annotated[Literal[True], BeforeValidator(_true)]
PublicCursor = Annotated[int, Field(ge=0, le=PUBLIC_INTEGER_MAX)]
PublicSequence = Annotated[int, Field(ge=1, le=PUBLIC_INTEGER_MAX)]
ListLimit = Annotated[Literal[10], BeforeValidator(_integer)]


class StrictWire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class FoundationScope(StrictWire):
    scope: Literal["local_educational_application"]
    contract_version: Literal["local.v1"]
    foundation_version: Literal["market_foundation.v1"]


class FoundationFieldError(StrictWire):
    field: str
    code: str


class FoundationErrorDetail(StrictWire):
    code: str
    message: str
    fieldErrors: list[FoundationFieldError]
    correlationId: Annotated[
        str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    ]


class FoundationErrorEnvelope(StrictWire):
    success: Annotated[Literal[False], BeforeValidator(_false)]
    message: str
    error_code: str
    error: FoundationErrorDetail
    detail: str

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (
            self.error_code != self.error.code
            or self.message != self.detail
            or self.message != self.error.message
        ):
            raise ValueError("Invalid safe failure envelope")
        return self


class WatchlistRequest(StrictWire):
    name: Name

    @field_validator("name", mode="before")
    @classmethod
    def normalized_name(cls, value: object) -> object:
        return value.strip() if type(value) is str else value


class EmptyFoundationRequest(StrictWire):
    pass


class PaperOpenRequest(StrictWire):
    foundation_version: Annotated[str, Field(min_length=1, max_length=80)]
    currency: Literal["USD"]


class FoundationInstrument(StrictWire):
    instrument_id: InstrumentId
    display_name: Name
    asset_class: Group
    sector: Group
    currency: Literal["USD"]


class MarketSearchData(FoundationScope):
    catalog_version: Literal["synthetic_catalog.v1"]
    query: Annotated[str, Field(max_length=80)]
    limit: Annotated[int, Field(ge=1, le=20)]
    count: Annotated[int, Field(ge=0, le=20)]
    items: Annotated[list[FoundationInstrument], Field(max_length=20)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (
            self.query != self.query.strip()
            or self.count != len(self.items)
            or self.count > self.limit
        ):
            raise ValueError("Invalid search confirmation")
        ids = [item.instrument_id for item in self.items]
        if ids != sorted(set(ids)):
            raise ValueError("Invalid catalogue ordering")
        return self


class MarketQuoteData(FoundationScope):
    catalog_version: Literal["synthetic_catalog.v1"]
    quote_snapshot_version: Literal["synthetic_quotes.v1"]
    source: Literal["finex.synthetic.portfolio"]
    source_type: Literal["SYNTHETIC"]
    fixture_as_of: Literal["2026-01-01T00:00:00Z"]
    instrument_id: InstrumentId
    currency: Literal["USD"]
    status: Literal["CACHED", "STALE", "UNAVAILABLE"]
    unit_price: Price | None
    quote_as_of: Literal["2026-01-01T00:00:00Z"] | None
    fetched_at: UtcText | None
    cache_expires_at: UtcText | None
    reason: (
        Literal[
            "SYNTHETIC_PROVIDER_STALE",
            "SYNTHETIC_QUOTE_UNAVAILABLE",
            "SYNTHETIC_PROVIDER_UNAVAILABLE",
        ]
        | None
    )

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.fetched_at is None) != (self.cache_expires_at is None):
            raise ValueError("Invalid quote retrieval pair")
        if self.fetched_at is not None and self.cache_expires_at is not None:
            if datetime.fromisoformat(self.cache_expires_at) - datetime.fromisoformat(
                self.fetched_at
            ) != timedelta(seconds=60):
                raise ValueError("Invalid quote expiry")
        if self.status == "CACHED":
            if (
                self.unit_price is None
                or self.quote_as_of is None
                or self.fetched_at is None
                or self.reason is not None
            ):
                raise ValueError("Invalid priced quote")
        elif self.status == "STALE":
            if (
                self.unit_price is None
                or self.quote_as_of is None
                or self.fetched_at is None
                or self.reason != "SYNTHETIC_PROVIDER_STALE"
            ):
                raise ValueError("Invalid stale quote")
        elif (
            self.unit_price is not None
            or self.quote_as_of is not None
            or self.reason not in {"SYNTHETIC_QUOTE_UNAVAILABLE", "SYNTHETIC_PROVIDER_UNAVAILABLE"}
        ):
            raise ValueError("Invalid unavailable quote")
        if self.reason == "SYNTHETIC_QUOTE_UNAVAILABLE" and self.fetched_at is None:
            raise ValueError("Unavailable fixture retrieval is missing")
        return self


class WatchlistSummary(StrictWire):
    watchlist_id: Uuid4
    name: Name
    created_at: UtcText
    updated_at: UtcText
    item_count: Annotated[int, Field(ge=0, le=100)]

    @model_validator(mode="after")
    def consistent_time(self) -> Self:
        if self.name != self.name.strip() or datetime.fromisoformat(
            self.updated_at
        ) < datetime.fromisoformat(self.created_at):
            raise ValueError("Invalid saved watchlist")
        return self


class WatchlistItem(FoundationInstrument):
    added_at: UtcText


class WatchlistCollectionData(FoundationScope):
    watchlist_version: Literal["watchlist.v1"]
    limit: ListLimit
    count: Annotated[int, Field(ge=0, le=10)]
    items: Annotated[list[WatchlistSummary], Field(max_length=10)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        ids = [item.watchlist_id for item in self.items]
        if self.count != len(self.items) or len(set(ids)) != len(ids):
            raise ValueError("Invalid watchlist collection")
        if self.items != sorted(
            self.items,
            key=lambda item: (datetime.fromisoformat(item.created_at), item.watchlist_id),
        ):
            raise ValueError("Invalid watchlist collection ordering")
        return self


class WatchlistData(FoundationScope, WatchlistSummary):
    watchlist_version: Literal["watchlist.v1"]
    items: Annotated[list[WatchlistItem], Field(max_length=100)]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        ids = [item.instrument_id for item in self.items]
        if self.item_count != len(self.items) or len(set(ids)) != len(ids):
            raise ValueError("Invalid watchlist item count")
        if self.items != sorted(
            self.items, key=lambda item: (datetime.fromisoformat(item.added_at), item.instrument_id)
        ):
            raise ValueError("Invalid watchlist item ordering")
        return self


class WatchlistItemData(FoundationScope):
    watchlist_version: Literal["watchlist.v1"]
    watchlist_item_version: Literal["watchlist_item.v1"]
    watchlist_id: Uuid4
    item: WatchlistItem


class WatchlistDeletedData(FoundationScope):
    watchlist_version: Literal["watchlist.v1"]
    watchlist_id: Uuid4
    deleted: TrueValue


class WatchlistItemRemovedData(FoundationScope):
    watchlist_version: Literal["watchlist.v1"]
    watchlist_item_version: Literal["watchlist_item.v1"]
    watchlist_id: Uuid4
    instrument_id: InstrumentId
    removed: TrueValue


class PaperAccount(StrictWire):
    account_id: Uuid4
    opening_ledger_id: Uuid4
    currency: Literal["USD"]
    opening_cash: Literal["10000.00"]
    cash_balance: Money
    created_at: UtcText


class PaperAccountData(FoundationScope):
    paper_account_version: Literal["paper_account.v1"]
    simulation: TrueValue
    account: PaperAccount | None


class PaperOpeningEntry(StrictWire):
    ledger_id: Uuid4
    account_id: Uuid4
    sequence: PublicSequence
    entry_type: Literal["OPENING"]
    cash_delta: Literal["10000.00"]
    cash_after: Literal["10000.00"]
    instrument_id: None
    quantity_delta: None
    position_after: None
    order_id: None
    trade_id: None
    corrects_ledger_id: None
    created_at: UtcText


class PaperLedgerData(FoundationScope):
    paper_ledger_version: Literal["paper_ledger.v1"]
    simulation: TrueValue
    account_id: Uuid4
    limit: Annotated[int, Field(ge=1, le=100)]
    after_sequence: PublicCursor
    count: Annotated[int, Field(ge=0, le=100)]
    items: Annotated[list[PaperOpeningEntry], Field(max_length=100)]
    next_cursor: PublicSequence | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        sequences = [item.sequence for item in self.items]
        if (
            self.count != len(self.items)
            or self.count > self.limit
            or sequences != sorted(set(sequences))
        ):
            raise ValueError("Invalid simulated ledger page")
        if any(
            item.account_id != self.account_id or item.sequence <= self.after_sequence
            for item in self.items
        ):
            raise ValueError("Invalid simulated ledger binding")
        if self.next_cursor is not None and (not sequences or self.next_cursor != sequences[-1]):
            raise ValueError("Invalid simulated ledger cursor")
        return self
