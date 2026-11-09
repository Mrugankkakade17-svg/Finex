"""TDD contract tests for the Sprint 2 local assessment fixture adapter."""

import copy
import json
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.fixtures.s2_dat_01 import (
    S2Dat01FixtureProvider,
    S2FixtureValidationError,
    build_fixture_quality_report,
    resolve_assessment_fixture_provider,
    validate_assessment_fixtures,
)
from app.ports.assessment_fixture_store import AssessmentFixtureStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPOSITORY_ROOT / "data" / "fixtures" / "s2_dat_01"
FIXTURE_CONTRACT_PATH = FIXTURE_DIR / "fixture_contract_v1.json"
FIXTURE_MANIFEST_PATH = FIXTURE_DIR / "fixture_manifest_v1.json"
RISK_CONTRACT_PATH = (
    REPOSITORY_ROOT / "docs" / "features" / "risk-profiling" / "risk-contract.v1.json"
)
GOLDEN_CASES_PATH = (
    REPOSITORY_ROOT / "docs" / "features" / "risk-profiling" / "golden-cases.v1.json"
)


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_s2_assessment_fixtures_validate_against_risk_contract_and_golden_pack() -> None:
    result = validate_assessment_fixtures(
        FIXTURE_CONTRACT_PATH,
        FIXTURE_MANIFEST_PATH,
        RISK_CONTRACT_PATH,
        GOLDEN_CASES_PATH,
    )

    assert result == {
        "valid": True,
        "fixture_contract_schema_version": "s2-dat-01.fixture.v1",
        "fixture_mode": "s2_dat_01",
        "risk_contract_version": "s2-risk-contract/v1.0",
        "questionnaire_id": "risk_questionnaire_v1",
        "questionnaire_version": "v1",
        "fixture_count": 16,
        "valid_case_count": 9,
        "invalid_case_count": 7,
        "coverage": [
            "contradictory",
            "dimension_tension",
            "duplicate",
            "invalid_answer_code",
            "malformed",
            "missing_required",
            "normal",
            "reachable_lower_boundary",
            "reachable_upper_boundary",
            "unknown_question",
            "unsupported_version",
        ],
    }


def test_reset_and_seed_are_repeatable_and_satisfy_the_fixture_port() -> None:
    provider = S2Dat01FixtureProvider()

    assert isinstance(provider, AssessmentFixtureStore)
    first = provider.reset_and_seed()
    second = provider.reset_and_seed()

    assert first == second
    assert first is not second
    assert len(first["fixtures"]) == 16

    changed = copy.deepcopy(first)
    changed["fixtures"].clear()
    assert len(second["fixtures"]) == 16


def test_fixture_provider_materializes_valid_and_invalid_contract_cases() -> None:
    snapshot = S2Dat01FixtureProvider().reset_and_seed()
    fixtures = {fixture["case_id"]: fixture for fixture in snapshot["fixtures"]}

    assert fixtures["RISK-GOLD-004"]["request"]["questionnaire_version"] == "v1"
    assert len(fixtures["RISK-GOLD-004"]["request"]["answers"]) == 10
    assert fixtures["RISK-GOLD-004"]["expected"]["composite_score"] == 50.0

    assert len(fixtures["RISK-GOLD-010"]["request"]["answers"]) == 9
    assert fixtures["RISK-GOLD-010"]["expected"]["error_code"] == "MISSING_REQUIRED_QUESTION"

    duplicate_answers = fixtures["RISK-GOLD-011"]["request"]["answers"]
    assert len(duplicate_answers) == 11
    assert sum(answer["question_id"] == "W1" for answer in duplicate_answers) == 2

    contradictory_answers = fixtures["RISK-GOLD-014"]["request"]["answers"]
    contradictory_w1 = next(
        answer for answer in contradictory_answers if answer["question_id"] == "W1"
    )
    assert contradictory_w1["answer_code"] == "C1_C"
    assert fixtures["RISK-GOLD-014"]["expected"]["error_code"] == (
        "ANSWER_NOT_PERMITTED_FOR_QUESTION"
    )

    unsupported = fixtures["RISK-GOLD-016"]["request"]
    assert unsupported["questionnaire_version"] == "v2"
    assert fixtures["RISK-GOLD-016"]["expected"]["error_code"] == (
        "UNSUPPORTED_QUESTIONNAIRE_VERSION"
    )


def test_fixture_quality_report_is_deterministic_and_does_not_expose_answers() -> None:
    first = build_fixture_quality_report()
    second = build_fixture_quality_report()
    serialized = json.dumps(first, sort_keys=True)

    assert first == second
    assert first["status"] == "passed"
    assert first["summary"]["fixture_count"] == 16
    assert first["summary"]["invalid_case_count"] == 7
    assert '"answer_code"' not in serialized
    assert '"question_id"' not in serialized


def test_contract_version_drift_fails_safely(tmp_path: Path) -> None:
    contract = _load_json(FIXTURE_CONTRACT_PATH)
    contract["risk_contract_version"] = "s2-risk-contract/v99"
    changed_contract_path = tmp_path / "fixture_contract.json"
    _write_json(changed_contract_path, contract)

    with pytest.raises(S2FixtureValidationError, match="risk contract version"):
        validate_assessment_fixtures(
            changed_contract_path,
            FIXTURE_MANIFEST_PATH,
            RISK_CONTRACT_PATH,
            GOLDEN_CASES_PATH,
        )


def test_golden_fixture_version_drift_fails_safely(tmp_path: Path) -> None:
    golden_cases = _load_json(GOLDEN_CASES_PATH)
    golden_cases["fixture_version"] = "s2-risk-golden-cases/v99"
    changed_golden_path = tmp_path / "golden-cases.json"
    _write_json(changed_golden_path, golden_cases)

    with pytest.raises(S2FixtureValidationError, match="golden-case fixture version"):
        validate_assessment_fixtures(
            FIXTURE_CONTRACT_PATH,
            FIXTURE_MANIFEST_PATH,
            RISK_CONTRACT_PATH,
            changed_golden_path,
        )


def test_manifest_requires_every_golden_case_exactly_once(tmp_path: Path) -> None:
    manifest = _load_json(FIXTURE_MANIFEST_PATH)
    manifest["fixtures"] = manifest["fixtures"][:-1]
    changed_manifest_path = tmp_path / "fixture_manifest.json"
    _write_json(changed_manifest_path, manifest)

    with pytest.raises(S2FixtureValidationError, match="must reference every golden case"):
        validate_assessment_fixtures(
            FIXTURE_CONTRACT_PATH,
            changed_manifest_path,
            RISK_CONTRACT_PATH,
            GOLDEN_CASES_PATH,
        )


def test_s2_fixture_mode_is_local_only_and_rejected_in_uat_and_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIXTURE_MODE", "s2_dat_01")
    local_settings = Settings(app_env="local", _env_file=None)

    provider = resolve_assessment_fixture_provider(local_settings.fixture_mode)
    assert provider is not None
    assert provider.reset_and_seed()["fixture_mode"] == "s2_dat_01"

    with pytest.raises(ValueError, match="disabled in UAT and production"):
        Settings(app_env="uat", fixture_mode="s2_dat_01", _env_file=None)
    with pytest.raises(ValueError, match="disabled in UAT and production"):
        Settings(app_env="production", fixture_mode="s2_dat_01", _env_file=None)


@pytest.mark.parametrize("invalid_code", ["W1_Z", "C1_C", 3])
def test_invalid_baseline_options_are_not_accepted_as_valid_fixtures(
    tmp_path: Path, invalid_code: object
) -> None:
    golden = _load_json(GOLDEN_CASES_PATH)
    golden["answer_sets"]["all_mid"]["W1"] = invalid_code
    path = tmp_path / "golden.json"
    _write_json(path, golden)
    with pytest.raises(S2FixtureValidationError, match="permitted answer"):
        validate_assessment_fixtures(golden_cases_path=path)


def test_missing_baseline_answer_is_rejected(tmp_path: Path) -> None:
    golden = _load_json(GOLDEN_CASES_PATH)
    del golden["answer_sets"]["all_mid"]["C5"]
    path = tmp_path / "golden.json"
    _write_json(path, golden)
    with pytest.raises(S2FixtureValidationError, match="required questions"):
        validate_assessment_fixtures(golden_cases_path=path)


def test_object_key_order_does_not_change_fixture_requests(tmp_path: Path) -> None:
    golden = _load_json(GOLDEN_CASES_PATH)
    for name, answers in golden["answer_sets"].items():
        golden["answer_sets"][name] = dict(reversed(list(answers.items())))
    path = tmp_path / "golden.json"
    _write_json(path, golden)
    assert S2Dat01FixtureProvider(golden_cases_path=path).seed() == S2Dat01FixtureProvider().seed()


def test_quality_report_rejects_prohibited_materialized_fields(tmp_path: Path) -> None:
    golden = _load_json(GOLDEN_CASES_PATH)
    golden["cases"][0]["expected"]["email"] = "synthetic@example.invalid"
    path = tmp_path / "golden.json"
    _write_json(path, golden)
    with pytest.raises(S2FixtureValidationError, match="prohibited field"):
        build_fixture_quality_report(golden_cases_path=path)


def test_incomplete_mutation_fails_with_a_controlled_validation_error(tmp_path: Path) -> None:
    golden = _load_json(GOLDEN_CASES_PATH)
    golden["cases"][9]["mutations"] = [{"operation": "remove_by_question_id"}]
    path = tmp_path / "golden.json"
    _write_json(path, golden)
    with pytest.raises(S2FixtureValidationError, match="required field"):
        validate_assessment_fixtures(golden_cases_path=path)


def test_provider_returns_defensive_copies_and_none_for_unknown_id() -> None:
    provider = S2Dat01FixtureProvider()
    fixture = provider.get_fixture("s2_dat_01_risk_gold_004")
    assert fixture is not None
    fixture["request"]["answers"].clear()
    unchanged = provider.get_fixture("s2_dat_01_risk_gold_004")
    assert unchanged is not None and len(unchanged["request"]["answers"]) == 10
    assert provider.get_fixture("unknown") is None
