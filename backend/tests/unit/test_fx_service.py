from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.fx_service import FxRate, FxSeries, FxService

D1 = date(2026, 1, 1)
D2 = date(2026, 1, 2)


def make_rate(rate_id="usd-inr-1", day=D1, rate="83.25", pair=("USD", "INR")):
    return FxRate(rate_id, pair[0], pair[1], Decimal(rate), day, "fixture-bank", "DELAYED")


def test_usd_to_inr_uses_dated_rate_and_returns_lineage():
    service = FxService(FxSeries([make_rate()]))
    converted = service.value_inr("12.50", "usd", D2)
    assert converted.amount == Decimal("1040.6250")
    assert converted.rate == Decimal("83.25")
    assert (converted.rate_id, converted.source, converted.as_of) == (
        "usd-inr-1",
        "fixture-bank",
        D1,
    )
    assert converted.freshness == "DELAYED"
    assert not converted.inverted


def test_inr_to_usd_inverts_the_same_usd_inr_quote():
    service = FxService(FxSeries([make_rate()]))
    result = service.value_usd("83.25", "INR", D1)
    assert abs(result.amount - Decimal("1")) < Decimal("1e-27")
    assert result.inverted
    assert result.rate_id == "usd-inr-1"


def test_series_uses_latest_rate_not_after_valuation_date():
    series = FxSeries([make_rate("older", D1, "82"), make_rate("newer", D2, "84")])
    assert series.get_rate("USD", "INR", D1).rate_id == "older"
    assert series.get_rate("USD", "INR", D2).rate_id == "newer"


def test_same_currency_conversion_is_identity_and_does_not_need_series():
    result = FxService(FxSeries()).convert("3.20", "usd", "USD", D1)
    assert result.amount == Decimal("3.20")
    assert result.rate == Decimal("1")
    assert result.rate_id == "identity"


@pytest.mark.parametrize("bad", ["0", "-1", "NaN", "Infinity"])
def test_rate_must_be_finite_and_positive(bad):
    with pytest.raises(ValueError):
        make_rate(rate=bad)


def test_missing_or_future_only_rate_is_explicit():
    service = FxService(FxSeries([make_rate(day=D2)]))
    with pytest.raises(LookupError, match="No USD/INR FX rate"):
        service.value_inr("1", "USD", D1)


def test_duplicate_ids_and_malformed_currency_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        FxSeries([make_rate(), make_rate()])
    with pytest.raises(ValueError, match="three-letter"):
        make_rate(pair=("US", "INR"))


def test_rate_rejects_datetime_as_as_of_date():
    with pytest.raises(ValueError, match="date-only"):
        make_rate(day=datetime(2026, 1, 1))


def test_conversion_rejects_datetime_valuation_date():
    service = FxService(FxSeries([make_rate()]))
    with pytest.raises(ValueError, match="date-only"):
        service.convert("1", "USD", "INR", datetime(2026, 1, 1))


def test_identity_conversion_rejects_datetime_valuation_date():
    service = FxService(FxSeries())
    with pytest.raises(ValueError, match="date-only"):
        service.convert("1", "USD", "USD", datetime(2026, 1, 1))
