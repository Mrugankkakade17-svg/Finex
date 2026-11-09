"""Structural validation for the proposed R1 golden-case fixture."""

import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).with_name("golden_examples_r1.json")
REPOSITORY_ROOT = FIXTURE_PATH.parents[2]
STABLE_ERROR_CODE_TYPES = (str, type(None))


def load_fixture() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_r1_fixture_structure_and_references():
    fixture = load_fixture()

    assert fixture["matrix_version"] == "v1.0.0-proposed"
    assert fixture["contract_version"] == "risk_contract_v1.0.0-proposed"
    assert fixture["questionnaire_id"] == "risk_questionnaire_v1"
    assert fixture["questionnaire_version"] == "v1"
    assert fixture["proposed_scoring_version"] == "risk_scoring_v1"

    cases = fixture["cases"]
    case_ids = [case["id"] for case in cases]
    assert len(case_ids) == len(set(case_ids))

    for case in cases:
        source = case["source"]
        source_path = source["file"] if isinstance(source, dict) else source
        assert (REPOSITORY_ROOT / source_path).is_file(), source_path

        if case["id"] == "GC-24":
            assert "expected" not in case
            assert case["observed_current"]["result"] == "scored"
            assert case["observed_current"]["error_code"] is None
            assert case["proposed_target"]["result"] == "rejected"
            assert case["proposed_target"]["error_code"] is None
            assert case["proposed_target"]["requires_approval"] is True
            continue

        expected = case["expected"]
        assert isinstance(expected["result"], str)
        assert isinstance(expected["error_code"], STABLE_ERROR_CODE_TYPES)
        if expected["error_code"] is None and expected["result"] == "rejected":
            assert expected.get("requires_approval") is True
            assert expected.get("approval_note")
        elif expected["error_code"] is not None:
            assert expected["error_code"].replace("_", "").isalnum()
            assert "approval" not in expected["error_code"].lower()
