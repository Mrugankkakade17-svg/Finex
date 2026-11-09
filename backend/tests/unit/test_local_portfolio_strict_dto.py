"""Tests-first wire assertions; only synthetic input and no application database."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import local_portfolio as portfolio_wire
from app.schemas.local_portfolio import (
    LocalHoldingCreateRequest,
    LocalHoldingUpdateRequest,
    LocalPortfolioRequest,
    LocalPortfolioTotals,
)


def portfolio_input() -> dict[str, object]:
    return {
        "portfolio_version": "portfolio.v1",
        "name": "  Synthetic example  ",
        "description": "  training only  ",
        "currency": "USD",
    }


def holding_input() -> dict[str, object]:
    return {
        "holding_version": "holding.v1",
        "instrument_id": "SYN:AAPL",
        "quantity": "10.000000",
        "average_cost": "150.0000",
        "currency": "USD",
    }


def test_names_are_normalized_before_bounds_and_empty_description_is_not_null() -> None:
    result = LocalPortfolioRequest.model_validate(portfolio_input())
    assert (result.name, result.description) == ("Synthetic example", "training only")
    assert (
        LocalPortfolioRequest.model_validate(
            {**portfolio_input(), "name": " " * 200 + "x" * 100, "description": "   "}
        ).description
        == ""
    )


@pytest.mark.parametrize("field", ["portfolio_version", "description", "currency", "name"])
def test_all_portfolio_request_fields_are_required(field: str) -> None:
    body = portfolio_input()
    del body[field]
    with pytest.raises(ValidationError):
        LocalPortfolioRequest.model_validate(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "   "),
        ("name", "x" * 101),
        ("name", 123),
        ("description", False),
        ("description", "x" * 501),
        ("currency", "EUR"),
        ("portfolio_version", "v0"),
        ("owner_id", "synthetic-other"),
        ("scope", "local_educational_application"),
    ],
)
def test_invalid_portfolio_wire_fields_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        LocalPortfolioRequest.model_validate({**portfolio_input(), field: value})


@pytest.mark.parametrize(
    "quantity",
    [
        0,
        True,
        1.0,
        "0.000000",
        "1000000.000001",
        "1000001.000000",
        "01.000000",
        "1.00000",
        "1.0000000",
        " 1.000000",
        "+1.000000",
        "-1.000000",
        "1e0",
        "NaN",
    ],
)
def test_quantity_requires_exact_bounded_text(quantity: object) -> None:
    with pytest.raises(ValidationError):
        LocalHoldingCreateRequest.model_validate({**holding_input(), "quantity": quantity})


@pytest.mark.parametrize(
    "cost",
    [
        True,
        0,
        1.0,
        "-0.0000",
        "+1.0000",
        "01.0000",
        "1.000",
        "1.00000",
        "1000000.0001",
        "1000001.0000",
        "Infinity",
        "1e3",
        " 0.0000",
    ],
)
def test_average_cost_requires_exact_bounded_text(cost: object) -> None:
    with pytest.raises(ValidationError):
        LocalHoldingCreateRequest.model_validate({**holding_input(), "average_cost": cost})


@pytest.mark.parametrize("field", ["holding_version", "quantity", "average_cost", "currency"])
def test_update_requires_full_replacement_and_rejects_instrument(field: str) -> None:
    body = holding_input()
    del body["instrument_id"]
    missing = dict(body)
    del missing[field]
    with pytest.raises(ValidationError):
        LocalHoldingUpdateRequest.model_validate(missing)
    with pytest.raises(ValidationError):
        LocalHoldingUpdateRequest.model_validate({**body, "instrument_id": "SYN:MSFT"})


@pytest.mark.parametrize("instrument", ["AAPL", "syn:AAPL", "SYN:aapl", "SYN:1A", "SYN:A\n"])
def test_malformed_instrument_transport_is_rejected(instrument: str) -> None:
    with pytest.raises(ValidationError):
        LocalHoldingCreateRequest.model_validate({**holding_input(), "instrument_id": instrument})


def test_canonical_adjacent_bounds_and_semantic_unknown_id_survive_transport() -> None:
    for quantity in ("0.000001", "1000000.000000"):
        for cost in ("0.0000", "1000000.0000"):
            result = LocalHoldingCreateRequest.model_validate(
                {
                    **holding_input(),
                    "instrument_id": "SYN:OTHER",
                    "quantity": quantity,
                    "average_cost": cost,
                }
            )
            assert result.quantity == quantity and result.average_cost == cost


def test_totals_have_required_nullable_fields_and_no_numeric_coercion() -> None:
    values = {
        "cost_basis": "0.00",
        "market_value": "0.00",
        "gain_loss": "0.00",
        "gain_loss_percent": None,
        "allocation_by_asset_class": [],
        "allocation_by_sector": [],
        "concentration_percent": None,
        "hhi": None,
        "educational_spread_percent": None,
    }
    assert LocalPortfolioTotals.model_validate(values).model_dump() == values
    for field in values:
        missing = dict(values)
        del missing[field]
        with pytest.raises(ValidationError):
            LocalPortfolioTotals.model_validate(missing)
    for bad in (0, "-0.00", "00.00", "1.0", "NaN"):
        with pytest.raises(ValidationError):
            LocalPortfolioTotals.model_validate({**values, "cost_basis": bad})


def test_request_models_do_not_create_a_timestamp_or_authority_field() -> None:
    assert "created_at" not in LocalPortfolioRequest.model_fields
    assert "user_id" not in LocalHoldingCreateRequest.model_fields
    assert datetime.now(timezone.utc).utcoffset() is not None


@pytest.mark.parametrize(
    "model",
    [
        portfolio_wire.LocalPortfolioScope,
        portfolio_wire.LocalPortfolioCatalogItem,
        portfolio_wire.LocalPortfolioCatalog,
        portfolio_wire.LocalPortfolio,
        portfolio_wire.LocalPortfolioList,
        portfolio_wire.LocalHolding,
        portfolio_wire.LocalHoldingList,
        portfolio_wire.LocalPortfolioDeletion,
        portfolio_wire.LocalHoldingDeletion,
        portfolio_wire.LocalPortfolioMetricQuote,
        portfolio_wire.LocalPortfolioMetricHolding,
        portfolio_wire.LocalPortfolioAllocation,
        portfolio_wire.LocalPortfolioTotals,
        portfolio_wire.LocalPortfolioMetrics,
    ],
)
def test_every_wire_response_field_is_required_without_invented_authority(model) -> None:
    schema = model.model_json_schema()
    assert set(schema.get("required", [])) == set(schema["properties"])


@pytest.mark.parametrize("wrong", [1, 1.0, "true", False])
def test_deletion_requires_json_true_not_equal_numeric_values(wrong: object) -> None:
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolioDeletion.model_validate(
            {
                "scope": "local_educational_application",
                "contract_version": "local.v1",
                "portfolio_version": "portfolio.v1",
                "portfolio_id": "00000000-0000-4000-8000-000000000001",
                "entity_type": "portfolio",
                "deleted": wrong,
            }
        )


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-01-01T01:00:00+01:00",
        "2026-13-01T00:00:00Z",
        "today",
        False,
    ],
)
def test_response_record_time_is_strict_utc(stamp: object) -> None:
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolio.model_validate(
            {
                "scope": "local_educational_application",
                "contract_version": "local.v1",
                "portfolio_version": "portfolio.v1",
                "currency": "USD",
                "name": "Training",
                "description": None,
                "portfolio_id": "00000000-0000-4000-8000-000000000001",
                "created_at": stamp,
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )


def metric_holding_body() -> dict[str, object]:
    return {
        "holding_version": "holding.v1",
        "portfolio_id": "00000000-0000-4000-8000-000000000001",
        "holding_id": "00000000-0000-4000-8000-000000000002",
        "instrument_id": "SYN:AAPL",
        "display_name": "Synthetic",
        "asset_class": "EQUITY",
        "sector": "GENERAL",
        "currency": "USD",
        "quantity": "1.000000",
        "average_cost": "0.0000",
        "cost_basis": "0.00",
        "quote": {
            "unit_price": "200.0000",
            "data_status": "CACHED",
            "quote_as_of": "2026-01-01T00:00:00Z",
            "reason": None,
        },
        "market_value": "200.00",
        "gain_loss": "200.00",
        "gain_loss_percent": None,
        "weight_percent": "100.00",
    }


@pytest.mark.parametrize(
    "field", ["market_value", "gain_loss", "gain_loss_percent", "weight_percent"]
)
def test_unavailable_metric_row_has_no_invented_financial_outputs(field: str) -> None:
    body = metric_holding_body()
    body.update(
        {
            "quote": {
                "unit_price": None,
                "data_status": "UNAVAILABLE",
                "quote_as_of": None,
                "reason": "SYNTHETIC_QUOTE_UNAVAILABLE",
            },
            "market_value": None,
            "gain_loss": None,
            "gain_loss_percent": None,
            "weight_percent": None,
        }
    )
    body[field] = "1.00"
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolioMetricHolding.model_validate(body)


def test_zero_cost_metric_row_cannot_claim_a_gain_percentage() -> None:
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolioMetricHolding.model_validate(
            {**metric_holding_body(), "gain_loss_percent": "1.00"}
        )


@pytest.mark.parametrize(
    "field",
    [
        "gain_loss",
        "gain_loss_percent",
        "allocation_by_asset_class",
        "allocation_by_sector",
        "concentration_percent",
        "hhi",
        "educational_spread_percent",
    ],
)
def test_missing_total_value_cannot_have_value_derived_outputs(field: str) -> None:
    body: dict[str, object] = {
        "cost_basis": "1.00",
        "market_value": None,
        "gain_loss": None,
        "gain_loss_percent": None,
        "allocation_by_asset_class": None,
        "allocation_by_sector": None,
        "concentration_percent": None,
        "hhi": None,
        "educational_spread_percent": None,
    }
    body[field] = (
        [] if field.startswith("allocation_") else ("0.000000" if field == "hhi" else "0.00")
    )
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolioTotals.model_validate(body)


@pytest.mark.parametrize("field", ["asset_class", "sector"])
@pytest.mark.parametrize("wrong", ["EQUITY\n", "EQUITY\r", "Equity", "ＥQUITY"])
def test_group_labels_match_the_entire_ascii_wire_value(field: str, wrong: str) -> None:
    with pytest.raises(ValidationError):
        portfolio_wire.LocalPortfolioMetricHolding.model_validate(
            {**metric_holding_body(), field: wrong}
        )
