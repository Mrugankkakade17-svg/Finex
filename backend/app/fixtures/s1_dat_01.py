"""Validator for the local S1-DAT-01 fixture contract and records."""

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

EXPECTED_CONTRACT_VERSION = "s1-dat-01.fixture.v1"
EXPECTED_CONSENT_VERSION = "consent.v1"
EXPECTED_PROFILE_SCHEMA_VERSION = "profile.v1"
REQUIRED_SCENARIOS = {
    "new",
    "partial-draft",
    "completed",
    "validation-failure",
    "revoked/changed-consent",
}
RECORD_TYPES = ("consent", "profile", "onboarding", "audit")
SUPPORTED_FIXTURE_MODE = "s1_dat_01"
DATA_QUALITY_REPORT_SCHEMA_VERSION = "s1-dat-03.report.v1"
SAFE_SYNTHETIC_PROFILE_LABEL_PATTERN = re.compile(r"^synthetic_profile_[a-z0-9]+(?:_[a-z0-9]+)*$")
DATA_QUALITY_CHECKS = (
    (
        "DQ-S1-001",
        "Contract, record versions, required fields, and field types are valid.",
    ),
    (
        "DQ-S1-002",
        "Fixture identifiers and timestamps satisfy the deterministic contract rules.",
    ),
    (
        "DQ-S1-003",
        "Every record belongs to its declared synthetic user and has no cross-user reference.",
    ),
    (
        "DQ-S1-004",
        "All required onboarding and consent scenarios are present and state-consistent.",
    ),
    (
        "DQ-S1-005",
        (
            "Fixtures are local-only synthetic data and exclude production, credential, "
            "and financial data."
        ),
    ),
    (
        "DQ-S1-006",
        "Audit records use approved event states and the local fixture source.",
    ),
)


class FixtureValidationError(ValueError):
    """Raised when an S1-DAT-01 fixture assumption is violated."""


class S1Dat01FixtureProvider:
    """Validated, in-memory provider for local S1-DAT-01 consumers."""

    def __init__(
        self,
        contract_path: Path | str | None = None,
        records_path: Path | str | None = None,
    ) -> None:
        self.contract_path = (
            Path(contract_path) if contract_path else _default_path("fixture_contract_v1.json")
        )
        self.records_path = Path(records_path) if records_path else _default_path("records_v1.json")
        self._records: dict[str, Any] | None = None

    def reset(self) -> None:
        """Clear this provider's ephemeral local snapshot."""
        self._records = None

    def seed(self) -> dict[str, Any]:
        """Validate and load a fresh fixture snapshot."""
        validate_fixtures(self.contract_path, self.records_path)
        self._records = _load_json(self.records_path, "Fixture records")
        return deepcopy(self._records)

    def reset_and_seed(self) -> dict[str, Any]:
        """Reset and reload the validated fixture snapshot."""
        self.reset()
        return self.seed()


def resolve_fixture_provider(mode: str) -> S1Dat01FixtureProvider | None:
    """Resolve the local fixture provider without database access."""
    if mode == "disabled":
        return None
    if mode == SUPPORTED_FIXTURE_MODE:
        return S1Dat01FixtureProvider()
    raise ValueError(f"Unsupported fixture mode: {mode!r}")


def _default_path(filename: str) -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "fixtures" / "s1_dat_01" / filename


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as fixture_file:
            value = json.load(fixture_file)
    except FileNotFoundError as exc:
        raise FixtureValidationError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FixtureValidationError(
            f"{label} is not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise FixtureValidationError(f"Could not read {label} {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise FixtureValidationError(f"{label} must contain a JSON object at the root")
    return value


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FixtureValidationError(f"{path} must be an object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise FixtureValidationError(f"{path} must be an array")
    return value


def _require_fields(value: dict[str, Any], fields: list[str], path: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise FixtureValidationError(f"{path} is missing required field(s): {', '.join(missing)}")


def _validate_contract(contract: dict[str, Any]) -> tuple[re.Pattern[str], re.Pattern[str]]:
    required = [
        "fixture_contract_schema_version",
        "fixture_scope",
        "supported_consent_version",
        "supported_profile_schema_version",
        "timestamp_rules",
        "deterministic_id_rules",
        "ownership_rules",
        "allowed_fixture_states",
        "synthetic_data_rules",
        "record_types",
    ]
    _require_fields(contract, required, "contract")

    if contract["fixture_contract_schema_version"] != EXPECTED_CONTRACT_VERSION:
        raise FixtureValidationError(
            "Unsupported fixture contract version "
            f"{contract['fixture_contract_schema_version']!r}; "
            f"supported version is {EXPECTED_CONTRACT_VERSION!r}"
        )
    if contract["fixture_scope"] != "local_test_only":
        raise FixtureValidationError("contract.fixture_scope must be 'local_test_only'")
    if contract["supported_consent_version"] != EXPECTED_CONSENT_VERSION:
        raise FixtureValidationError(
            "Unsupported contract consent version "
            f"{contract['supported_consent_version']!r}; "
            f"supported version is {EXPECTED_CONSENT_VERSION!r}"
        )
    if contract["supported_profile_schema_version"] != EXPECTED_PROFILE_SCHEMA_VERSION:
        raise FixtureValidationError(
            "Unsupported contract profile schema version "
            f"{contract['supported_profile_schema_version']!r}; "
            f"supported version is {EXPECTED_PROFILE_SCHEMA_VERSION!r}"
        )

    timestamp_rules = _require_mapping(contract["timestamp_rules"], "contract.timestamp_rules")
    timestamp_pattern = timestamp_rules.get("pattern")
    if not isinstance(timestamp_pattern, str):
        raise FixtureValidationError(
            "contract.timestamp_rules.pattern must be a regular-expression string"
        )

    id_rules = _require_mapping(
        contract["deterministic_id_rules"], "contract.deterministic_id_rules"
    )
    id_pattern = id_rules.get("pattern")
    if not isinstance(id_pattern, str):
        raise FixtureValidationError(
            "contract.deterministic_id_rules.pattern must be a regular-expression string"
        )

    try:
        timestamp_regex = re.compile(timestamp_pattern)
        id_regex = re.compile(id_pattern)
    except re.error as exc:
        raise FixtureValidationError(
            f"Contract contains an invalid regular expression: {exc}"
        ) from exc

    states = set(
        _require_list(contract["allowed_fixture_states"], "contract.allowed_fixture_states")
    )
    missing_states = REQUIRED_SCENARIOS - states
    if missing_states:
        raise FixtureValidationError(
            "Contract does not allow required scenario state(s): "
            + ", ".join(sorted(missing_states))
        )

    synthetic_rules = _require_mapping(
        contract["synthetic_data_rules"], "contract.synthetic_data_rules"
    )
    if synthetic_rules.get("test_only") is not True:
        raise FixtureValidationError("contract.synthetic_data_rules.test_only must be true")
    for rule in (
        "real_personal_data_allowed",
        "real_financial_data_allowed",
        "credentials_allowed",
        "oauth_tokens_allowed",
        "production_data_allowed",
        "cloud_endpoints_allowed",
    ):
        if synthetic_rules.get(rule) is not False:
            raise FixtureValidationError(f"contract.synthetic_data_rules.{rule} must be false")

    record_types = _require_mapping(contract["record_types"], "contract.record_types")
    _require_fields(record_types, ["synthetic_users", *RECORD_TYPES], "contract.record_types")
    for record_type, definition in record_types.items():
        definition = _require_mapping(definition, f"contract.record_types.{record_type}")
        _require_fields(
            definition,
            ["required_fields", "fields"],
            f"contract.record_types.{record_type}",
        )
        fields = _require_mapping(
            definition["fields"], f"contract.record_types.{record_type}.fields"
        )
        for field in definition["required_fields"]:
            if field not in fields:
                raise FixtureValidationError(
                    f"contract.record_types.{record_type} does not define required field {field!r}"
                )

    return timestamp_regex, id_regex


def _validate_field(
    value: Any,
    field_rules: dict[str, Any],
    path: str,
    timestamp_regex: re.Pattern[str],
    id_regex: re.Pattern[str],
) -> None:
    field_type = field_rules.get("type")
    type_matches = {
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
    }
    if field_type not in type_matches:
        raise FixtureValidationError(f"{path} uses unsupported contract field type {field_type!r}")
    if not type_matches[field_type]:
        raise FixtureValidationError(f"{path} must be a {field_type}")

    if "const" in field_rules and value != field_rules["const"]:
        raise FixtureValidationError(
            f"{path} must equal the contract constant {field_rules['const']!r}"
        )
    if "supported_values" in field_rules and value not in field_rules["supported_values"]:
        raise FixtureValidationError(
            f"{path} has unsupported value {value!r}; "
            f"supported values are {field_rules['supported_values']}"
        )
    if "allowed_values" in field_rules and value not in field_rules["allowed_values"]:
        raise FixtureValidationError(
            f"{path} has invalid value {value!r}; "
            f"allowed values are {field_rules['allowed_values']}"
        )
    if field_rules.get("format") == "timestamp_rules" and not timestamp_regex.fullmatch(value):
        raise FixtureValidationError(
            f"{path} must match the contract UTC timestamp format "
            "(for example, 2026-09-11T00:00:00Z)"
        )
    if field_rules.get("id_rule") == "deterministic_id_rules" and not id_regex.fullmatch(value):
        raise FixtureValidationError(
            f"{path} must be a deterministic lowercase ASCII identifier matching the contract rule"
        )


def _validate_record(
    record: Any,
    record_type: str,
    definition: dict[str, Any],
    path: str,
    timestamp_regex: re.Pattern[str],
    id_regex: re.Pattern[str],
    known_user_ids: set[str] | None = None,
    expected_user_id: str | None = None,
    seen_ids: set[str] | None = None,
) -> None:
    record = _require_mapping(record, path)
    required_fields = definition["required_fields"]
    _require_fields(record, required_fields, path)
    fields = definition["fields"]

    unknown_fields = set(record) - set(fields)
    if unknown_fields:
        raise FixtureValidationError(
            f"{path} contains unsupported field(s): {', '.join(sorted(unknown_fields))}"
        )

    for field, field_rules in fields.items():
        if field in record:
            _validate_field(
                record[field],
                _require_mapping(field_rules, f"{path}.{field} contract rule"),
                f"{path}.{field}",
                timestamp_regex,
                id_regex,
            )

    user_id = record.get("user_id")
    if known_user_ids is not None:
        if user_id not in known_user_ids:
            raise FixtureValidationError(
                f"{path}.user_id {user_id!r} does not reference a synthetic user fixture"
            )
    if expected_user_id is not None and user_id != expected_user_id:
        raise FixtureValidationError(
            f"{path}.user_id {user_id!r} does not match owning scenario user {expected_user_id!r}"
        )

    if seen_ids is not None:
        for field, field_rules in fields.items():
            if field in record and field_rules.get("id_rule") == "deterministic_id_rules":
                record_id = record[field]
                if record_id in seen_ids:
                    raise FixtureValidationError(
                        f"{path}.{field} duplicates identifier {record_id!r}"
                    )
                seen_ids.add(record_id)


def validate_fixtures(
    contract_path: Path | str | None = None,
    records_path: Path | str | None = None,
) -> dict[str, Any]:
    """Validate S1-DAT-01 contract and records and return a success summary."""
    contract_file = (
        Path(contract_path) if contract_path else _default_path("fixture_contract_v1.json")
    )
    records_file = Path(records_path) if records_path else _default_path("records_v1.json")
    contract = _load_json(contract_file, "Fixture contract")
    records_document = _load_json(records_file, "Fixture records")
    timestamp_regex, id_regex = _validate_contract(contract)

    for field in (
        "fixture_contract_schema_version",
        "supported_consent_version",
        "supported_profile_schema_version",
    ):
        if records_document.get(field) != contract[field]:
            raise FixtureValidationError(
                f"records.{field} {records_document.get(field)!r} does not match "
                f"contract.{field} {contract[field]!r}"
            )
    if records_document.get("fixture_mode") != "local":
        raise FixtureValidationError("records.fixture_mode must be 'local'")

    records = _require_mapping(records_document.get("records"), "records.records")
    record_types = contract["record_types"]
    users = _require_list(records.get("synthetic_users"), "records.records.synthetic_users")
    known_user_ids: set[str] = set()
    seen_ids: set[str] = set()
    for index, user in enumerate(users):
        path = f"records.records.synthetic_users[{index}]"
        _validate_record(
            user,
            "synthetic_users",
            record_types["synthetic_users"],
            path,
            timestamp_regex,
            id_regex,
            seen_ids=seen_ids,
        )
        user_id = user["user_id"]
        if user_id in known_user_ids:
            raise FixtureValidationError(f"{path}.user_id duplicates synthetic user {user_id!r}")
        known_user_ids.add(user_id)

    scenarios = _require_list(records.get("scenarios"), "records.records.scenarios")
    seen_scenario_ids: set[str] = set()
    scenario_states: set[str] = set()
    for index, scenario_value in enumerate(scenarios):
        path = f"records.records.scenarios[{index}]"
        scenario = _require_mapping(scenario_value, path)
        _require_fields(scenario, ["scenario_id", "scenario_state", "user_id", *RECORD_TYPES], path)
        unknown_fields = set(scenario) - {"scenario_id", "scenario_state", "user_id", *RECORD_TYPES}
        if unknown_fields:
            raise FixtureValidationError(
                f"{path} contains unsupported field(s): {', '.join(sorted(unknown_fields))}"
            )
        scenario_id = scenario["scenario_id"]
        scenario_state = scenario["scenario_state"]
        scenario_user_id = scenario["user_id"]
        if not isinstance(scenario_id, str) or not id_regex.fullmatch(scenario_id):
            raise FixtureValidationError(
                f"{path}.scenario_id is not a deterministic contract identifier"
            )
        if scenario_id in seen_scenario_ids or scenario_id in seen_ids:
            raise FixtureValidationError(
                f"{path}.scenario_id duplicates identifier {scenario_id!r}"
            )
        seen_scenario_ids.add(scenario_id)
        seen_ids.add(scenario_id)
        if scenario_state not in contract["allowed_fixture_states"]:
            raise FixtureValidationError(
                f"{path}.scenario_state {scenario_state!r} is not an allowed fixture state"
            )
        scenario_states.add(scenario_state)
        if scenario_user_id not in known_user_ids:
            raise FixtureValidationError(
                f"{path}.user_id {scenario_user_id!r} does not reference a synthetic user fixture"
            )

        for record_type in RECORD_TYPES:
            record_path = f"{path}.{record_type}"
            _validate_record(
                scenario[record_type],
                record_type,
                record_types[record_type],
                record_path,
                timestamp_regex,
                id_regex,
                known_user_ids=known_user_ids,
                expected_user_id=scenario_user_id,
                seen_ids=seen_ids,
            )

        profile_state = scenario["profile"]["profile_state"]
        profile_label = scenario["profile"]["profile_label"]
        onboarding_state = scenario["onboarding"]["onboarding_state"]
        consent_status = scenario["consent"]["consent_status"]
        audit_state = scenario["audit"]["event_state"]
        audit_event_type = scenario["audit"]["event_type"]
        if not SAFE_SYNTHETIC_PROFILE_LABEL_PATTERN.fullmatch(profile_label):
            raise FixtureValidationError(
                f"{path}.profile.profile_label must be a safe synthetic label"
            )
        if scenario_state == "revoked/changed-consent":
            if profile_state != "completed" or onboarding_state != "completed":
                raise FixtureValidationError(
                    f"{path} changed-consent scenario requires completed profile "
                    "and onboarding state"
                )
            if (
                audit_state != scenario_state
                or audit_event_type != "consent_changed"
                or consent_status not in {"revoked", "changed"}
            ):
                raise FixtureValidationError(
                    f"{path} changed-consent scenario requires a changed/revoked consent "
                    "record and consent_changed audit event"
                )
        elif {profile_state, onboarding_state, audit_state} != {scenario_state}:
            raise FixtureValidationError(
                f"{path} nested states must all match scenario_state {scenario_state!r}"
            )
        elif consent_status != "accepted":
            raise FixtureValidationError(
                f"{path}.consent.consent_status must be 'accepted' outside changed-consent"
            )

        expected_audit_event = (
            "validation_failed" if scenario_state == "validation-failure" else "fixture_loaded"
        )
        if scenario_state != "revoked/changed-consent" and audit_event_type != expected_audit_event:
            raise FixtureValidationError(
                f"{path}.audit.event_type must be {expected_audit_event!r} "
                f"for scenario state {scenario_state!r}"
            )
        completed = scenario["onboarding"]["completed"]
        expected_completed = scenario_state in {"completed", "revoked/changed-consent"}
        if completed != expected_completed:
            raise FixtureValidationError(
                f"{path}.onboarding.completed is inconsistent with scenario_state "
                f"{scenario_state!r}"
            )

    missing_scenarios = REQUIRED_SCENARIOS - scenario_states
    if missing_scenarios:
        raise FixtureValidationError(
            "Missing required scenario state(s): " + ", ".join(sorted(missing_scenarios))
        )
    if len(seen_scenario_ids) != len(scenarios):
        raise FixtureValidationError("Scenario identifiers must be unique")

    return {
        "valid": True,
        "fixture_contract_schema_version": contract["fixture_contract_schema_version"],
        "supported_consent_version": contract["supported_consent_version"],
        "supported_profile_schema_version": contract["supported_profile_schema_version"],
        "synthetic_user_count": len(users),
        "scenario_count": len(scenarios),
        "scenario_states": sorted(scenario_states),
    }


def build_data_quality_report(
    contract_path: Path | str | None = None,
    records_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return deterministic, non-sensitive evidence for the S1 data-quality gate.

    The report intentionally contains counts and rule results only. It never emits fixture
    records, user identifiers, or profile labels, so it is safe to publish in CI logs.
    """
    result = validate_fixtures(contract_path, records_path)
    return {
        "report_schema_version": DATA_QUALITY_REPORT_SCHEMA_VERSION,
        "status": "passed",
        "fixture_contract_schema_version": result["fixture_contract_schema_version"],
        "supported_consent_version": result["supported_consent_version"],
        "supported_profile_schema_version": result["supported_profile_schema_version"],
        "checks": [
            {
                "rule_id": rule_id,
                "status": "passed",
                "description": description,
            }
            for rule_id, description in DATA_QUALITY_CHECKS
        ],
        "summary": {
            "synthetic_user_count": result["synthetic_user_count"],
            "scenario_count": result["scenario_count"],
            "scenario_states": result["scenario_states"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate local S1-DAT-01 fixtures")
    parser.add_argument(
        "--contract", type=Path, default=None, help="Path to the fixture contract JSON"
    )
    parser.add_argument(
        "--records", type=Path, default=None, help="Path to the fixture records JSON"
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Render a human-readable result or a stable CI-safe JSON quality report",
    )
    args = parser.parse_args(argv)

    try:
        report = build_data_quality_report(args.contract, args.records)
    except FixtureValidationError as exc:
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "report_schema_version": DATA_QUALITY_REPORT_SCHEMA_VERSION,
                        "status": "failed",
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
            )
            return 1
        print(f"Fixture validation failed: {exc}")
        return 1

    if args.format == "json":
        print(json.dumps(report, sort_keys=True))
        return 0

    summary = report["summary"]
    print(
        "Fixture validation passed: "
        f"{summary['scenario_count']} scenarios, "
        f"{summary['synthetic_user_count']} synthetic users, "
        f"contract {report['fixture_contract_schema_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
