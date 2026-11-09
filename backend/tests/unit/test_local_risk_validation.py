"""Small factory/validation seams preserve the approved pilot authority."""

from copy import deepcopy
from pathlib import Path

import pytest
from ai.risk.contract import RiskContractError, evaluate_risk_contract, validate_risk_input
from ai.risk.scoring import RiskScoringEngine

SNAPSHOT_CORRUPTIONS = [
    "score_bool",
    "score_float",
    "score_string",
    "score_nonfinite",
    "raw_min_bool",
    "raw_min_string",
    "raw_max_nonfinite",
    "weight_bool",
    "weight_string",
    "weight_nonfinite",
    "threshold_bool",
    "threshold_string",
    "threshold_nonfinite",
    "position_bool",
    "position_float",
    "title_bool",
    "active_time_number",
    "retired_time_list",
    "question_text_bool",
    "option_label_bool",
    "option_label_integer",
    "required_integer",
    "response_type_invalid",
    "normalization_number",
    "formula_bool",
    "questions_tuple",
    "options_tuple",
    "options_reversed",
    "top_extra",
    "metadata_extra",
    "scoring_extra",
    "question_extra",
    "option_extra",
    "formula_drift",
    "normalization_drift",
    "active_time_invalid",
    "active_time_naive",
    "retired_time_invalid",
    "option_label_empty",
    "question_text_empty",
    "position_wrong",
]


def corrupt_snapshot(snapshot: dict, kind: str) -> None:
    """Synthetic structural changes shared by factory and public-history tests."""
    option = snapshot["questions"][0]["answers"][0]
    if kind.startswith("score_"):
        option["proposed_score"] = {
            "score_bool": True,
            "score_float": 1.0,
            "score_string": "1",
            "score_nonfinite": float("nan"),
        }[kind]
    elif kind.startswith("raw_"):
        field = "max" if kind == "raw_max_nonfinite" else "min"
        snapshot["scoring"]["dimension_raw_range"][field] = {
            "raw_min_bool": True,
            "raw_min_string": "5",
            "raw_max_nonfinite": float("inf"),
        }[kind]
    elif kind.startswith("weight_"):
        snapshot["scoring"]["combination"]["willingness_weight"] = {
            "weight_bool": True,
            "weight_string": "0.5",
            "weight_nonfinite": float("inf"),
        }[kind]
    elif kind.startswith("threshold_"):
        snapshot["scoring"]["category_boundaries"][0]["min"] = {
            "threshold_bool": False,
            "threshold_string": "0",
            "threshold_nonfinite": float("nan"),
        }[kind]
    elif kind.startswith("position_"):
        snapshot["questions"][0]["position"] = kind == "position_bool" or 1.0
    elif kind == "title_bool":
        snapshot["questionnaire"]["title"] = True
    elif kind == "active_time_number":
        snapshot["questionnaire"]["active_from"] = 1
    elif kind == "retired_time_list":
        snapshot["questionnaire"]["retired_at"] = []
    elif kind == "question_text_bool":
        snapshot["questions"][0]["text"] = True
    elif kind == "option_label_bool":
        option["label"] = True
    elif kind == "option_label_integer":
        option["label"] = 123
    elif kind == "required_integer":
        snapshot["questions"][0]["required"] = 1
    elif kind == "response_type_invalid":
        snapshot["questions"][0]["response_type"] = "synthetic-unapproved-type"
    elif kind == "normalization_number":
        snapshot["scoring"]["normalization"] = 1
    elif kind == "formula_bool":
        snapshot["scoring"]["combination"]["formula"] = True
    elif kind == "questions_tuple":
        snapshot["questions"] = tuple(snapshot["questions"])
    elif kind == "options_tuple":
        snapshot["questions"][0]["answers"] = tuple(snapshot["questions"][0]["answers"])
    elif kind == "options_reversed":
        snapshot["questions"][0]["answers"].reverse()
    elif kind == "top_extra":
        snapshot["unapproved"] = "synthetic"
    elif kind == "metadata_extra":
        snapshot["questionnaire"]["unapproved"] = "synthetic"
    elif kind == "scoring_extra":
        snapshot["scoring"]["unapproved"] = "synthetic"
    elif kind == "question_extra":
        snapshot["questions"][0]["unapproved"] = "synthetic"
    elif kind == "option_extra":
        option["unapproved"] = "synthetic"
    elif kind == "formula_drift":
        snapshot["scoring"]["combination"]["formula"] = "synthetic unapproved arithmetic"
    elif kind == "normalization_drift":
        snapshot["scoring"]["normalization"] = "synthetic unapproved normalization"
    elif kind == "active_time_invalid":
        snapshot["questionnaire"]["active_from"] = "synthetic invalid date"
    elif kind == "active_time_naive":
        snapshot["questionnaire"]["active_from"] = "2026-08-23T21:21:00"
    elif kind == "retired_time_invalid":
        snapshot["questionnaire"]["retired_at"] = "synthetic invalid date"
    elif kind == "option_label_empty":
        option["label"] = " "
    elif kind == "question_text_empty":
        snapshot["questions"][0]["text"] = ""
    elif kind == "position_wrong":
        snapshot["questions"][0]["position"] = 2
    else:
        raise AssertionError("Unknown synthetic corruption selector.")


def partial(answer_code: str = "W1_C") -> dict:
    return {
        "questionnaire_id": "risk_questionnaire_v1",
        "questionnaire_version": "v1",
        "answers": [{"question_id": "W1", "answer_code": answer_code}],
    }


def test_partial_validation_accepts_ordered_empty_or_partial_input_without_scoring() -> None:
    engine = RiskScoringEngine()
    accepted = partial()
    assert validate_risk_input(accepted, engine, require_complete=False) == accepted
    empty = {**accepted, "answers": []}
    assert validate_risk_input(empty, engine, require_complete=False) == empty
    with pytest.raises(RiskContractError) as complete:
        validate_risk_input(accepted, engine)
    assert complete.value.code == "MISSING_REQUIRED_QUESTION"


@pytest.mark.parametrize(
    "code,expected",
    [("W1_Z", "INVALID_ANSWER_CODE"), ("C1_C", "ANSWER_NOT_PERMITTED_FOR_QUESTION")],
)
def test_partial_validation_still_applies_all_answer_checks(code: str, expected: str) -> None:
    with pytest.raises(RiskContractError) as caught:
        validate_risk_input(partial(code), RiskScoringEngine(), require_complete=False)
    assert caught.value.code == expected
    with pytest.raises(RiskContractError) as pilot:
        evaluate_risk_contract(partial(code))
    assert pilot.value.code == "MISSING_REQUIRED_QUESTION"


def test_frozen_engine_is_independent_of_caller_mutation_and_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = deepcopy(RiskScoringEngine().config)
    frozen = RiskScoringEngine.from_config(source)
    original_text = source["questions"][0]["text"]
    source["questions"][0]["text"] = "synthetic caller mutation"
    source["scoring"]["combination"]["willingness_weight"] = 0.7
    assert frozen.config["questions"][0]["text"] == original_text
    assert frozen.w_weight == 0.5
    monkeypatch.setattr("ai.risk.scoring.DEFAULT_CONFIG_PATH", Path("missing-synthetic-config"))
    payload = {
        **partial(),
        "answers": [
            {"question_id": qid, "answer_code": f"{qid}_C"} for qid in frozen.questions_by_id
        ],
    }
    assert (
        evaluate_risk_contract(payload, calculated_at="2026-10-11T16:00:00Z", engine=frozen)[
            "composite_score"
        ]
        == 50.0
    )
    with pytest.raises(FileNotFoundError):
        evaluate_risk_contract(payload)


@pytest.mark.parametrize("mutation", ["weight", "membership", "nonfinite", "shape"])
def test_frozen_factory_rejects_changed_policy_and_non_json_config(mutation: str) -> None:
    snapshot = deepcopy(RiskScoringEngine().config)
    if mutation == "weight":
        snapshot["scoring"]["combination"]["willingness_weight"] = 0.7
    elif mutation == "membership":
        snapshot["questions"].pop()
    elif mutation == "nonfinite":
        snapshot["extra"] = float("nan")
    else:
        snapshot["extra"] = object()
    with pytest.raises((TypeError, ValueError)):
        RiskScoringEngine.from_config(snapshot)


@pytest.mark.parametrize("corruption", SNAPSHOT_CORRUPTIONS)
def test_snapshot_factory_rejects_nonapproved_json_types_and_structure(corruption: str) -> None:
    snapshot = deepcopy(RiskScoringEngine().config)
    corrupt_snapshot(snapshot, corruption)
    with pytest.raises((TypeError, ValueError)):
        RiskScoringEngine.from_config(snapshot)


def test_snapshot_factory_preserves_real_numeric_int_float_types_without_coercion() -> None:
    snapshot = deepcopy(RiskScoringEngine().config)
    snapshot["scoring"]["dimension_raw_range"]["min"] = 5.0
    snapshot["scoring"]["category_boundaries"][0]["min"] = 0.0
    frozen = RiskScoringEngine.from_config(snapshot)
    assert type(frozen.config["scoring"]["dimension_raw_range"]["min"]) is float
    assert type(frozen.config["scoring"]["category_boundaries"][0]["min"]) is float
    assert type(frozen.config["questions"][0]["answers"][0]["proposed_score"]) is int


@pytest.mark.parametrize("question_index", range(10))
@pytest.mark.parametrize("option_index", range(5))
def test_every_option_score_rejects_equal_valued_float_type(
    question_index: int, option_index: int
) -> None:
    snapshot = deepcopy(RiskScoringEngine().config)
    option = snapshot["questions"][question_index]["answers"][option_index]
    option["proposed_score"] = float(option["proposed_score"])
    with pytest.raises((TypeError, ValueError)):
        RiskScoringEngine.from_config(snapshot)


@pytest.mark.parametrize(
    "numeric_path",
    [
        ("dimension_raw_range", "min"),
        ("dimension_raw_range", "max"),
        ("combination", "willingness_weight"),
        ("combination", "capacity_weight"),
        *(("category_boundaries", index, field) for index in range(3) for field in ("min", "max")),
    ],
)
@pytest.mark.parametrize("bad_type", ["bool", "string", "nan", "infinity"])
def test_every_numeric_policy_field_rejects_non_numeric_or_nonfinite_types(
    numeric_path: tuple, bad_type: str
) -> None:
    snapshot = deepcopy(RiskScoringEngine().config)
    target = snapshot["scoring"]
    for key in numeric_path[:-1]:
        target = target[key]
    original = target[numeric_path[-1]]
    target[numeric_path[-1]] = {
        "bool": bool(original),
        "string": str(original),
        "nan": float("nan"),
        "infinity": float("inf"),
    }[bad_type]
    with pytest.raises((TypeError, ValueError)):
        RiskScoringEngine.from_config(snapshot)
