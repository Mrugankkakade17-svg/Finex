"""Test-first exact units and record corruption guards, without prospective SQL."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.local_portfolio import (
    LocalHoldingRecord,
    LocalPortfolioRecord,
    canonical_instrument_id,
    canonical_uuid4,
    cost_text,
    cost_units,
    price_units,
    quantity_text,
    quantity_units,
    validate_holding_record,
    validate_portfolio_record,
)

PID = "00000000-0000-4000-8000-000000000191"
HID = "00000000-0000-4000-8000-000000000192"
NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)
PORTFOLIO = LocalPortfolioRecord("synthetic-owner", PID, "Training", None, "USD", NOW, NOW)
HOLDING = LocalHoldingRecord(
    "synthetic-owner", PID, HID, "SYN:AAPL", "0.005025", "100.0000", "USD", NOW, NOW
)


@pytest.mark.parametrize(
    "text,units",
    [
        ("0.000001", 1),
        ("0.005025", 5025),
        ("12.000000", 12000000),
        ("1000000.000000", 1000000000000),
    ],
)
def test_quantity_conversion_is_exact_and_reversible(text: str, units: int) -> None:
    assert quantity_units(text) == units
    assert quantity_text(units) == text


@pytest.mark.parametrize(
    "text,units",
    [("0.0000", 0), ("0.0001", 1), ("150.0000", 1500000), ("1000000.0000", 10000000000)],
)
def test_cost_conversion_is_exact_and_reversible(text: str, units: int) -> None:
    assert cost_units(text) == units
    assert cost_text(units) == text


@pytest.mark.parametrize(
    "value",
    [
        1,
        1.0,
        True,
        None,
        "",
        "0.000000",
        "1000000.000001",
        "01.000000",
        "+1.000000",
        "-1.000000",
        "1.0",
        "1.0000000",
        "1e0",
        " 1.000000",
        "1.000000\n",
        "١.000000",
        "1.００００００",
        "NaN",
        "Infinity",
    ],
)
def test_invalid_quantity_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        quantity_units(value)


@pytest.mark.parametrize(
    "value",
    [
        0,
        0.0,
        False,
        None,
        "",
        "1000000.0001",
        "01.0000",
        "+0.0000",
        "-0.0000",
        "1.0",
        "1.00000",
        "1e0",
        " 1.0000",
        "1.0000\n",
        "١.0000",
        "NaN",
        "Infinity",
    ],
)
def test_invalid_cost_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        cost_units(value)


@pytest.mark.parametrize("value", ["0.0000", "-0.0000", "1000000.0001", 1, False])
def test_available_price_requires_positive_canonical_units(value: object) -> None:
    with pytest.raises(ValueError):
        price_units(value)


def test_available_price_keeps_half_cent_precision() -> None:
    assert price_units("2.0050") == 20050


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -1, 0, 1000000000001])
def test_quantity_stored_units_require_nonboolean_bounded_integer(value: object) -> None:
    with pytest.raises(ValueError):
        quantity_text(value)


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -1, 10000000001])
def test_cost_stored_units_require_nonboolean_bounded_integer(value: object) -> None:
    with pytest.raises(ValueError):
        cost_text(value)


@pytest.mark.parametrize("value", [PID, HID])
def test_resource_identifiers_are_canonical_uuid4(value: str) -> None:
    assert canonical_uuid4(value) == value


@pytest.mark.parametrize(
    "value",
    [
        PID.upper().replace("191", "19A"),
        PID + "\n",
        PID.replace("-4000-", "-1000-"),
        PID.replace("-8000-", "-0000-"),
        PID.replace("-", ""),
        UUID(PID),
        None,
        True,
    ],
)
def test_malformed_resource_identifiers_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        canonical_uuid4(value)


@pytest.mark.parametrize("value", ["SYN:AAPL", "SYN:OTHER", "SYN:A" + "0" * 31])
def test_well_formed_unsupported_instrument_is_not_domain_support_validation(value: str) -> None:
    assert canonical_instrument_id(value) == value


@pytest.mark.parametrize(
    "value",
    [
        "SYN:aapl",
        "SYN:AAPL\n",
        "SYN:1",
        "SYN:A" + "0" * 32,
        " AAPL",
        "AAPL",
        "SYN:Ä",
        "SYN:",
        1,
        False,
        None,
    ],
)
def test_instrument_ids_use_full_ascii_canonical_match(value: object) -> None:
    with pytest.raises(ValueError):
        canonical_instrument_id(value)


def test_valid_records_preserve_identity_and_support_nonuuid_internal_owner() -> None:
    assert validate_portfolio_record(PORTFOLIO, user_id="synthetic-owner") is PORTFOLIO
    assert validate_holding_record(HOLDING, user_id="synthetic-owner", portfolio_id=PID) is HOLDING
    assert validate_portfolio_record(replace(PORTFOLIO, description="")) is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": ""},
        {"user_id": "other"},
        {"portfolio_id": "bad"},
        {"name": " Training "},
        {"name": ""},
        {"name": "x" * 101},
        {"name": False},
        {"description": False},
        {"description": " x "},
        {"description": "x" * 501},
        {"currency": "EUR"},
        {"created_at": NOW.replace(tzinfo=None)},
        {"updated_at": NOW - timedelta(seconds=1)},
        {"updated_at": NOW.astimezone(timezone(timedelta(hours=1)))},
        {"updated_at": "bad"},
    ],
)
def test_portfolio_record_corruption_is_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        validate_portfolio_record(replace(PORTFOLIO, **changes), user_id="synthetic-owner")


@pytest.mark.parametrize(
    "changes",
    [
        {"user_id": "other"},
        {"portfolio_id": HID},
        {"holding_id": "bad"},
        {"instrument_id": "SYN:AAPL\n"},
        {"quantity": "0.000000"},
        {"quantity": True},
        {"average_cost": "-0.0000"},
        {"average_cost": 1},
        {"currency": "EUR"},
        {"created_at": NOW.replace(tzinfo=None)},
        {"updated_at": NOW - timedelta(seconds=1)},
    ],
)
def test_holding_record_corruption_is_rejected(changes: dict) -> None:
    with pytest.raises(ValueError):
        validate_holding_record(
            replace(HOLDING, **changes), user_id="synthetic-owner", portfolio_id=PID
        )
