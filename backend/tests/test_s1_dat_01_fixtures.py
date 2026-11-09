import copy
import json
from pathlib import Path

import pytest
from scripts.seed_s1_dat_01 import S1Dat01FixtureStore

from app.config.settings import Settings
from app.fixtures.s1_dat_01 import (
    FixtureValidationError,
    build_data_quality_report,
    resolve_fixture_provider,
    validate_fixtures,
)
from app.fixtures.s1_dat_01 import main as fixture_validation_main

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "s1_dat_01"
CONTRACT_PATH = FIXTURE_DIR / "fixture_contract_v1.json"
RECORDS_PATH = FIXTURE_DIR / "records_v1.json"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_s1_dat_01_fixtures_validate():
    result = validate_fixtures(CONTRACT_PATH, RECORDS_PATH)

    assert result["valid"] is True
    assert result["synthetic_user_count"] == 5
    assert result["scenario_count"] == 5
    assert set(result["scenario_states"]) == {
        "new",
        "partial-draft",
        "completed",
        "validation-failure",
        "revoked/changed-consent",
    }


def test_data_quality_report_is_deterministic_and_contains_core_check_evidence():
    first = build_data_quality_report(CONTRACT_PATH, RECORDS_PATH)
    second = build_data_quality_report(CONTRACT_PATH, RECORDS_PATH)

    assert first == second
    assert first["report_schema_version"] == "s1-dat-03.report.v1"
    assert first["status"] == "passed"
    assert "checked_at" not in first
    assert first["summary"] == {
        "scenario_count": 5,
        "synthetic_user_count": 5,
        "scenario_states": [
            "completed",
            "new",
            "partial-draft",
            "revoked/changed-consent",
            "validation-failure",
        ],
    }
    assert [check["rule_id"] for check in first["checks"]] == [
        "DQ-S1-001",
        "DQ-S1-002",
        "DQ-S1-003",
        "DQ-S1-004",
        "DQ-S1-005",
        "DQ-S1-006",
    ]
    assert all(check["status"] == "passed" for check in first["checks"])


def test_data_quality_report_contains_no_fixture_payload_or_personal_fields():
    report = build_data_quality_report(CONTRACT_PATH, RECORDS_PATH)
    serialized_report = json.dumps(report, sort_keys=True)

    assert "profile_label" not in serialized_report
    assert "user_id" not in serialized_report
    assert "consent_id" not in serialized_report


def test_data_quality_cli_writes_the_safe_machine_readable_report(capsys):
    assert fixture_validation_main(["--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "passed"
    assert report["summary"]["scenario_count"] == 5


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "fixture_contract_schema_version",
            "s1-dat-01.fixture.v99",
            "Unsupported fixture contract version",
        ),
        (
            "supported_consent_version",
            "consent.v99",
            "Unsupported contract consent version",
        ),
        (
            "supported_profile_schema_version",
            "profile.v99",
            "Unsupported contract profile schema version",
        ),
    ],
)
def test_unsupported_contract_versions_fail_safely(tmp_path, field, value, message):
    contract = load_json(CONTRACT_PATH)
    contract[field] = value
    contract_path = tmp_path / "fixture_contract.json"
    write_json(contract_path, contract)

    with pytest.raises(FixtureValidationError, match=message):
        validate_fixtures(contract_path, RECORDS_PATH)


def test_missing_required_field_fails_safely(tmp_path):
    records = load_json(RECORDS_PATH)
    del records["records"]["scenarios"][0]["profile"]["profile_label"]
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="missing required field"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_invalid_ownership_fails_safely(tmp_path):
    records = load_json(RECORDS_PATH)
    records["records"]["scenarios"][0]["profile"]["user_id"] = "s1_dat_01_user_002"
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="does not match owning scenario user"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_profile_label_must_remain_a_safe_synthetic_label(tmp_path):
    records = load_json(RECORDS_PATH)
    records["records"]["scenarios"][0]["profile"]["profile_label"] = "alice@example.com"
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="safe synthetic label"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_changed_consent_scenario_requires_matching_audit_event_and_status(tmp_path):
    records = load_json(RECORDS_PATH)
    changed_consent = records["records"]["scenarios"][-1]
    changed_consent["consent"]["consent_status"] = "accepted"
    changed_consent["audit"]["event_type"] = "fixture_loaded"
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="changed-consent scenario requires"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_unsupported_scenario_state_fails_safely(tmp_path):
    records = load_json(RECORDS_PATH)
    records["records"]["scenarios"][0]["scenario_state"] = "unsupported-state"
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="is not an allowed fixture state"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_missing_required_scenario_fails_safely(tmp_path):
    records = load_json(RECORDS_PATH)
    records["records"]["scenarios"] = records["records"]["scenarios"][1:]
    records_path = tmp_path / "records.json"
    write_json(records_path, records)

    with pytest.raises(FixtureValidationError, match="Missing required scenario state"):
        validate_fixtures(CONTRACT_PATH, records_path)


def test_reset_and_seed_is_repeatable_and_isolated():
    store = S1Dat01FixtureStore()
    first = store.reset_and_seed()
    second = store.reset_and_seed()

    assert first == second
    assert first is not second

    mutated = copy.deepcopy(first)
    mutated["records"]["scenarios"].clear()
    assert len(second["records"]["scenarios"]) == 5


def test_fixture_mode_defaults_disabled():
    settings = Settings(_env_file=None)

    assert settings.fixture_mode == "disabled"
    assert resolve_fixture_provider(settings.fixture_mode) is None


def test_fixture_mode_resolves_provider_without_database_credentials(monkeypatch):
    monkeypatch.setenv("FIXTURE_MODE", "s1_dat_01")
    settings = Settings(app_env="test", _env_file=None)
    provider = resolve_fixture_provider(settings.fixture_mode)

    assert provider is not None
    records = provider.reset_and_seed()
    assert len(records["records"]["scenarios"]) == 5


def test_fixture_mode_is_rejected_in_production():
    with pytest.raises(ValueError, match="disabled in UAT and production"):
        Settings(app_env="production", fixture_mode="s1_dat_01", _env_file=None)


def test_fixture_mode_is_rejected_in_uat():
    with pytest.raises(ValueError, match="disabled in UAT and production"):
        Settings(app_env="uat", fixture_mode="s1_dat_01", _env_file=None)
