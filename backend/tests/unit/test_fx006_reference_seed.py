from decimal import Decimal

from scripts.seed_reference_data import ALLOCATION_MODELS, ALLOCATION_TARGETS, BENCHMARKS


def test_allocation_reference_models_have_complete_deterministic_weights():
    model_codes = {model["model_code"] for model in ALLOCATION_MODELS}
    assert {model["risk_category"] for model in ALLOCATION_MODELS} == {
        "CONSERVATIVE",
        "MODERATE",
        "AGGRESSIVE",
    }
    assert len(model_codes) == len(ALLOCATION_MODELS)

    targets_by_model: dict[str, dict[str, Decimal]] = {}
    for target in ALLOCATION_TARGETS:
        targets_by_model.setdefault(target["model_code"], {})[target["asset_class"]] = Decimal(
            target["target_weight"]
        )

    assert set(targets_by_model) == model_codes
    assert all(
        set(targets) == {"EQUITY", "FIXED_INCOME", "CASH"} for targets in targets_by_model.values()
    )
    assert all(
        sum(targets.values()) == Decimal("1.000000") for targets in targets_by_model.values()
    )
    assert (
        targets_by_model["CONSERVATIVE_V1"]["EQUITY"]
        < targets_by_model["MODERATE_V1"]["EQUITY"]
        < targets_by_model["AGGRESSIVE_V1"]["EQUITY"]
    )


def test_benchmark_map_is_complete_for_seeded_allocation_asset_classes():
    assert {row["asset_class"] for row in BENCHMARKS} == {"EQUITY", "FIXED_INCOME", "CASH"}
    assert len({(row["asset_class"], row["version"]) for row in BENCHMARKS}) == len(BENCHMARKS)
    assert all(row["version"] == "v1" for row in BENCHMARKS)
