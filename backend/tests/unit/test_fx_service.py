from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.fx_service import FxRate, FxSeries, FxService

D1 = date(2026, 1, 1)
D2 = date(2026, 1, 2)


def make_rate(
    rate_id="usd-inr-1",
    day=D1,
    rate="83.25",
    pair=("USD", "INR"),
    source="fixture-bank",
    freshness="DELAYED",
):
    return FxRate(rate_id, pair[0], pair[1], Decimal(rate), day, source, freshness)


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


def test_inverse_amount_uses_direct_division_by_original_rate():
    amount = Decimal("123456789012345678901234567890")
    series = FxSeries([make_rate(rate="7", pair=("INR", "USD"))])
    result = series.convert(amount, "USD", "INR", D1)
    assert result.amount == amount / Decimal("7")


def test_series_uses_latest_rate_not_after_valuation_date():
    series = FxSeries([make_rate("older", D1, "82"), make_rate("newer", D2, "84")])
    assert series.get_rate("USD", "INR", D1).rate_id == "older"
    assert series.get_rate("USD", "INR", D2).rate_id == "newer"


def test_rates_returns_direct_series_in_ascending_date_order():
    series = FxSeries([make_rate("newer", D2), make_rate("older", D1)])
    assert tuple(rate.rate_id for rate in series.rates("usd", "inr")) == ("older", "newer")
    assert series.rates("INR", "USD") == ()


def test_same_currency_get_rate_is_rejected():
    with pytest.raises(ValueError, match="Identical currencies"):
        FxSeries().get_rate("USD", "USD", D1)


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


def test_identical_currencies_are_rejected_for_rates():
    with pytest.raises(ValueError, match="must differ"):
        make_rate(pair=("USD", "USD"))


@pytest.mark.parametrize("freshness", ["LIVE", "BROKEN"])
def test_live_and_unknown_freshness_labels_are_rejected(freshness):
    with pytest.raises(ValueError, match="non-live"):
        make_rate(freshness=freshness)


def test_rate_id_and_source_are_trimmed_and_empty_labels_are_rejected():
    rate = make_rate(rate_id="  rate-1  ", source="  fixture  ")
    assert rate.rate_id == "rate-1"
    assert rate.source == "fixture"
    with pytest.raises(ValueError, match="rate ID and source"):
        make_rate(rate_id="   ")
    with pytest.raises(ValueError, match="rate ID and source"):
        make_rate(source="   ")


@pytest.mark.parametrize("amount", ["not-a-number", Decimal("NaN"), Decimal("Infinity"), None])
def test_conversion_rejects_invalid_amounts(amount):
    with pytest.raises(ValueError, match="Amount must be a finite decimal"):
        FxSeries([make_rate()]).convert(amount, "USD", "INR", D1)


def test_newer_inverse_rate_is_selected_when_both_directions_exist():
    series = FxSeries(
        [
            make_rate("direct-older", D1, "80", ("USD", "INR")),
            make_rate("inverse-newer", D2, "0.012", ("INR", "USD")),
        ]
    )
    result = series.convert("12", "USD", "INR", D2)
    assert result.rate_id == "inverse-newer"
    assert result.inverted
    assert result.amount == Decimal("12") / Decimal("0.012")


def test_newer_direct_rate_is_selected_over_older_inverse_rate():
    series = FxSeries(
        [
            make_rate("direct-newer", D2, "84", ("USD", "INR")),
            make_rate("inverse-older", D1, "0.012", ("INR", "USD")),
        ]
    )
    result = series.convert("2", "USD", "INR", D2)
    assert result.rate_id == "direct-newer"
    assert not result.inverted
    assert result.amount == Decimal("168")


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
