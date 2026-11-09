"""Exhaustive strict local manual-portfolio DTOs; no invented wire authority."""

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.domain.local_portfolio import (
    canonical_instrument_id,
    canonical_uuid4,
    cost_units,
    price_units,
    quantity_units,
)


def _quantity(value: str) -> str:
    quantity_units(value)
    return value


def _cost(value: str) -> str:
    cost_units(value)
    return value


def _price(value: str) -> str:
    price_units(value)
    return value


def _number(value: str, *, places: int, lower: int, upper: int) -> str:
    if re.fullmatch(rf"-?(?:0|[1-9][0-9]{{0,18}})\.[0-9]{{{places}}}", value) is None:
        raise ValueError("A canonical bounded decimal string is required.")
    number = Decimal(value)
    if number < lower or number > upper or (number == 0 and value.startswith("-")):
        raise ValueError("A canonical bounded decimal string is required.")
    return value


def _money(value: str) -> str:
    return _number(value, places=2, lower=0, upper=100_000_000_000_000)


def _signed_money(value: str) -> str:
    return _number(value, places=2, lower=-100_000_000_000_000, upper=100_000_000_000_000)


def _percentage(value: str) -> str:
    return _number(value, places=2, lower=0, upper=100)


def _gain_percentage(value: str) -> str:
    return _number(value, places=2, lower=-100, upper=1_000_000_000_000_000_000)


def _hhi(value: str) -> str:
    return _number(value, places=6, lower=0, upper=1)


def _utc(value: str) -> str:
    if (
        re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]{1,6})?(?:Z|\+00:00)",
            value,
        )
        is None
    ):
        raise ValueError("A UTC timestamp is required.")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("A UTC timestamp is required.")
    return value


def _true(value: object) -> object:
    if value is not True:
        raise ValueError("A boolean true deletion confirmation is required.")
    return value


class _StrictWire(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


Quantity = Annotated[str, AfterValidator(_quantity)]
Cost = Annotated[str, AfterValidator(_cost)]
Price = Annotated[str, AfterValidator(_price)]
Money = Annotated[str, AfterValidator(_money)]
SignedMoney = Annotated[str, AfterValidator(_signed_money)]
Percentage = Annotated[str, AfterValidator(_percentage)]
GainPercentage = Annotated[str, AfterValidator(_gain_percentage)]
Hhi = Annotated[str, AfterValidator(_hhi)]
UtcText = Annotated[str, AfterValidator(_utc)]
Uuid4 = Annotated[str, AfterValidator(canonical_uuid4)]
InstrumentId = Annotated[str, AfterValidator(canonical_instrument_id)]
Group = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,31}$")]
Name = Annotated[str, Field(min_length=1, max_length=100)]


class LocalPortfolioScope(_StrictWire):
    scope: Literal["local_educational_application"]
    contract_version: Literal["local.v1"]


class LocalPortfolioRequest(_StrictWire):
    portfolio_version: Literal["portfolio.v1"]
    name: Name
    description: Annotated[str, Field(max_length=500)] | None
    currency: Literal["USD"]

    @field_validator("name", "description", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LocalHoldingUpdateRequest(_StrictWire):
    holding_version: Literal["holding.v1"]
    quantity: Quantity
    average_cost: Cost
    currency: Literal["USD"]


class LocalHoldingCreateRequest(LocalHoldingUpdateRequest):
    instrument_id: InstrumentId


class LocalPortfolioCatalogItem(_StrictWire):
    instrument_id: InstrumentId
    display_name: Name
    asset_class: Group
    sector: Group
    currency: Literal["USD"]

    @field_validator("display_name")
    @classmethod
    def trimmed_name(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("A normalized display name is required.")
        return value


class LocalPortfolioCatalog(LocalPortfolioScope):
    catalog_version: Literal["synthetic_catalog.v1"]
    currency: Literal["USD"]
    items: Annotated[list[LocalPortfolioCatalogItem], Field(min_length=1, max_length=128)]
    count: Annotated[int, Field(ge=1, le=128)]

    @model_validator(mode="after")
    def exact_count(self) -> Self:
        ids = [row.instrument_id for row in self.items]
        if self.count != len(ids) or ids != sorted(set(ids)):
            raise ValueError("The catalogue must be sorted, unique and complete.")
        return self


class LocalPortfolio(LocalPortfolioScope):
    portfolio_version: Literal["portfolio.v1"]
    portfolio_id: Uuid4
    name: Name
    description: Annotated[str, Field(max_length=500)] | None
    currency: Literal["USD"]
    created_at: UtcText
    updated_at: UtcText

    @model_validator(mode="after")
    def normalized_record(self) -> Self:
        if (
            self.name != self.name.strip()
            or (self.description is not None and self.description != self.description.strip())
            or datetime.fromisoformat(self.updated_at) < datetime.fromisoformat(self.created_at)
        ):
            raise ValueError("A normalized portfolio record is required.")
        return self


class LocalPortfolioList(LocalPortfolioScope):
    portfolio_version: Literal["portfolio.v1"]
    items: Annotated[list[LocalPortfolio], Field(max_length=20)]
    count: Annotated[int, Field(ge=0, le=20)]

    @model_validator(mode="after")
    def exact_count(self) -> Self:
        if self.count != len(self.items) or len({r.portfolio_id for r in self.items}) != self.count:
            raise ValueError("A complete, unique bounded portfolio list is required.")
        return self


class LocalHolding(LocalPortfolioScope, LocalPortfolioCatalogItem):
    holding_version: Literal["holding.v1"]
    catalog_version: Literal["synthetic_catalog.v1"]
    portfolio_id: Uuid4
    holding_id: Uuid4
    quantity: Quantity
    average_cost: Cost
    created_at: UtcText
    updated_at: UtcText

    @model_validator(mode="after")
    def ordered_times(self) -> Self:
        if datetime.fromisoformat(self.updated_at) < datetime.fromisoformat(self.created_at):
            raise ValueError("Holding timestamps must be ordered.")
        return self


class LocalHoldingList(LocalPortfolioScope):
    holding_version: Literal["holding.v1"]
    catalog_version: Literal["synthetic_catalog.v1"]
    portfolio_id: Uuid4
    items: Annotated[list[LocalHolding], Field(max_length=100)]
    count: Annotated[int, Field(ge=0, le=100)]

    @model_validator(mode="after")
    def exact_binding(self) -> Self:
        if self.count != len(self.items) or (
            len({r.holding_id for r in self.items}) != self.count
            or len({r.instrument_id for r in self.items}) != self.count
            or any(r.portfolio_id != self.portfolio_id for r in self.items)
        ):
            raise ValueError("A complete, unique owned holding list is required.")
        return self


class LocalPortfolioDeletion(LocalPortfolioScope):
    portfolio_version: Literal["portfolio.v1"]
    portfolio_id: Uuid4
    entity_type: Literal["portfolio"]
    deleted: Annotated[Literal[True], BeforeValidator(_true)]


class LocalHoldingDeletion(LocalPortfolioScope):
    holding_version: Literal["holding.v1"]
    portfolio_id: Uuid4
    holding_id: Uuid4
    entity_type: Literal["holding"]
    deleted: Annotated[Literal[True], BeforeValidator(_true)]


class LocalPortfolioMetricQuote(_StrictWire):
    unit_price: Price | None
    data_status: Literal["CACHED", "UNAVAILABLE"]
    quote_as_of: Literal["2026-01-01T00:00:00Z"] | None
    reason: Literal["SYNTHETIC_QUOTE_UNAVAILABLE"] | None

    @model_validator(mode="after")
    def honest_quote(self) -> Self:
        if self.data_status == "CACHED":
            valid = (
                self.unit_price is not None and self.quote_as_of is not None and self.reason is None
            )
        else:
            valid = self.unit_price is None and self.quote_as_of is None and self.reason is not None
        if not valid:
            raise ValueError("An honest synthetic quote status is required.")
        return self


class LocalPortfolioMetricHolding(LocalPortfolioCatalogItem):
    holding_version: Literal["holding.v1"]
    portfolio_id: Uuid4
    holding_id: Uuid4
    quantity: Quantity
    average_cost: Cost
    cost_basis: Money
    quote: LocalPortfolioMetricQuote
    market_value: Money | None
    gain_loss: SignedMoney | None
    gain_loss_percent: GainPercentage | None
    weight_percent: Percentage | None

    @model_validator(mode="after")
    def honest_values(self) -> Self:
        if self.quote.data_status == "UNAVAILABLE":
            if any(
                value is not None
                for value in (
                    self.market_value,
                    self.gain_loss,
                    self.gain_loss_percent,
                    self.weight_percent,
                )
            ):
                raise ValueError("An unavailable quote cannot invent financial values.")
        elif self.market_value is None or self.gain_loss is None:
            raise ValueError("A priced holding must include its value and gain.")
        if self.cost_basis == "0.00" and self.gain_loss_percent is not None:
            raise ValueError("Zero cost has no gain percentage.")
        if (
            self.quote.data_status == "CACHED"
            and self.cost_basis != "0.00"
            and self.gain_loss_percent is None
        ):
            raise ValueError("A priced positive-cost holding requires its gain percentage.")
        return self


class LocalPortfolioAllocation(_StrictWire):
    group: Group
    market_value: Money
    weight_percent: Percentage | None


class LocalPortfolioTotals(_StrictWire):
    cost_basis: Money
    market_value: Money | None
    gain_loss: SignedMoney | None
    gain_loss_percent: GainPercentage | None
    allocation_by_asset_class: (
        Annotated[list[LocalPortfolioAllocation], Field(max_length=100)] | None
    )
    allocation_by_sector: Annotated[list[LocalPortfolioAllocation], Field(max_length=100)] | None
    concentration_percent: Percentage | None
    hhi: Hhi | None
    educational_spread_percent: Percentage | None

    @model_validator(mode="after")
    def honest_values(self) -> Self:
        if self.market_value is None:
            if any(
                value is not None
                for value in (
                    self.gain_loss,
                    self.gain_loss_percent,
                    self.allocation_by_asset_class,
                    self.allocation_by_sector,
                    self.concentration_percent,
                    self.hhi,
                    self.educational_spread_percent,
                )
            ):
                raise ValueError("Missing total value cannot produce value-derived outputs.")
        else:
            if (
                self.gain_loss is None
                or self.allocation_by_asset_class is None
                or self.allocation_by_sector is None
            ):
                raise ValueError("Known total value requires gain and known allocations.")
            if (self.cost_basis == "0.00") != (self.gain_loss_percent is None):
                raise ValueError("A known gain percentage exists exactly when cost is positive.")
            ratios = (self.concentration_percent, self.hhi, self.educational_spread_percent)
            if self.market_value == "0.00":
                if any(value is not None for value in ratios):
                    raise ValueError("Zero total value has no value-based ratios.")
            elif any(value is None for value in ratios):
                raise ValueError("Positive known total value requires its value-based ratios.")
        for allocations in (self.allocation_by_asset_class, self.allocation_by_sector):
            if allocations is not None:
                groups = [row.group for row in allocations]
                if groups != sorted(set(groups)) or any(
                    (row.weight_percent is None) != (self.market_value == "0.00")
                    for row in allocations
                ):
                    raise ValueError("Allocations must be sorted, unique and honestly weighted.")
        return self


class LocalPortfolioMetrics(LocalPortfolioScope):
    metrics_version: Literal["portfolio_metrics.v1"]
    formula_version: Literal["manual_portfolio_math.v1"]
    catalog_version: Literal["synthetic_catalog.v1"]
    quote_snapshot_version: Literal["synthetic_quotes.v1"]
    portfolio_id: Uuid4
    currency: Literal["USD"]
    valuation_status: Literal["COMPLETE", "EMPTY", "INCOMPLETE", "UNAVAILABLE"]
    source: Literal["finex.synthetic.portfolio"]
    source_type: Literal["SYNTHETIC"]
    fixture_as_of: Literal["2026-01-01T00:00:00Z"]
    calculated_at: UtcText
    missing_instrument_ids: Annotated[list[InstrumentId], Field(max_length=100)]
    limitations: list[str]
    holdings: Annotated[list[LocalPortfolioMetricHolding], Field(max_length=100)]
    totals: LocalPortfolioTotals

    @field_validator("limitations")
    @classmethod
    def exact_limitations(cls, value: list[str]) -> list[str]:
        if value != [
            "SYNTHETIC_QUOTES_NOT_MARKET_DATA",
            "MANUAL_HOLDINGS_NOT_BROKER_POSITIONS",
            "SPREAD_IS_ALLOCATION_ONLY",
            "NO_FUND_LOOKTHROUGH_OR_SUITABILITY",
        ]:
            raise ValueError("Exact educational limitations are required.")
        return value

    @model_validator(mode="after")
    def exact_valuation_state(self) -> Self:
        missing = sorted(
            row.instrument_id for row in self.holdings if row.quote.data_status == "UNAVAILABLE"
        )
        if self.missing_instrument_ids != missing or (
            len({row.holding_id for row in self.holdings}) != len(self.holdings)
            or len({row.instrument_id for row in self.holdings}) != len(self.holdings)
            or any(row.portfolio_id != self.portfolio_id for row in self.holdings)
        ):
            raise ValueError("Metrics must bind to one exact owned holding snapshot.")
        expected = (
            "EMPTY"
            if not self.holdings
            else "COMPLETE"
            if not missing
            else "UNAVAILABLE"
            if len(missing) == len(self.holdings)
            else "INCOMPLETE"
        )
        if self.valuation_status != expected:
            raise ValueError("The valuation status must describe the actual quote snapshot.")
        if expected in {"UNAVAILABLE", "INCOMPLETE"}:
            if self.totals.market_value is not None or any(
                row.weight_percent is not None for row in self.holdings
            ):
                raise ValueError("Incomplete prices cannot invent a complete allocation.")
        elif self.totals.market_value is None:
            raise ValueError("A complete or empty portfolio has a known total value.")
        if self.totals.market_value is not None and any(
            (row.weight_percent is None) != (self.totals.market_value == "0.00")
            for row in self.holdings
        ):
            raise ValueError("Known positive values require actual holding weights.")
        if expected == "EMPTY" and (
            self.totals.cost_basis != "0.00"
            or self.totals.market_value != "0.00"
            or self.totals.gain_loss != "0.00"
            or self.totals.allocation_by_asset_class != []
            or self.totals.allocation_by_sector != []
        ):
            raise ValueError("An empty portfolio must have honest zero totals.")
        return self
