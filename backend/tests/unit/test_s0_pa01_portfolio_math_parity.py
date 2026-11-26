from folio_math_parity import SHARED_FIXTURES, compare_fixtures


def test_shared_portfolio_fixtures_match_decimal_canonical_results() -> None:
    report = compare_fixtures()

    assert report["canonical_module"].endswith("calculate_portfolio_metrics")
    assert report["mismatching_fixtures"] == []

    comparisons = {row["fixture"]: row for row in report["comparisons"]}
    for fixture_name, holdings in SHARED_FIXTURES:
        fixture_prices = [holding.current_price for holding in holdings]
        assert comparisons[fixture_name]["prices_used"] == {
            "legacy": fixture_prices,
            "canonical": fixture_prices,
        }

    assert comparisons["gain"]["canonical"] == {
        "cost_basis": "1500.00",
        "market_value": "2000.00",
        "gain_loss": "500.00",
        "gain_loss_percent": "33.33",
        "weights": ["100.00"],
    }
    assert comparisons["loss"]["canonical"]["gain_loss"] == "-500.00"
    assert comparisons["two_asset"]["canonical"]["gain_loss_percent"] == "14.29"
    assert comparisons["two_asset"]["canonical"]["weights"] == ["50.00", "50.00"]

    fractional = comparisons["fractional_rounding"]
    assert fractional["differences"] == {}
    assert fractional["legacy"]["cost_basis"] == fractional["canonical"]["cost_basis"] == "1.00"
    assert fractional["legacy"]["market_value"] == fractional["canonical"]["market_value"] == "2.02"
    assert fractional["legacy"]["gain_loss"] == fractional["canonical"]["gain_loss"] == "1.02"
    assert (
        fractional["legacy"]["gain_loss_percent"]
        == fractional["canonical"]["gain_loss_percent"]
        == "102.00"
    )
    assert (
        fractional["legacy"]["weights"] == fractional["canonical"]["weights"] == ["50.00", "50.00"]
    )
