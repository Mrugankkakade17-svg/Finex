from folio_math_parity import compare_fixtures


def test_shared_portfolio_fixtures_match_decimal_canonical_results() -> None:
    report = compare_fixtures()

    assert report["canonical_module"].endswith("calculate_portfolio_metrics")
    assert report["mismatching_fixtures"] == ["fractional_rounding"]

    comparisons = {row["fixture"]: row for row in report["comparisons"]}
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
    assert fractional["differences"] == {
        "cost_basis": {"legacy": "1.01", "canonical": "1.00"},
        "market_value": {"legacy": "2.01", "canonical": "2.02"},
        "gain_loss": {"legacy": "1.00", "canonical": "1.02"},
        "gain_loss_percent": {"legacy": "99.01", "canonical": "102.00"},
        "weights": {"legacy": ["49.75", "50.25"], "canonical": ["50.00", "50.00"]},
    }
