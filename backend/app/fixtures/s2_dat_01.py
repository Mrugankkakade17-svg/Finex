"""Validated, in-memory Sprint 2 assessment fixtures for local development.

The provider materializes synthetic requests from the versioned risk golden
pack. It never calculates a score, reaches a database, or contacts a cloud
service. That keeps local reset repeatable and lets later API and scoring work
share exactly the same test inputs.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

EXPECTED_FIXTURE_CONTRACT_VERSION = "s2-dat-01.fixture.v1"
EXPECTED_FIXTURE_MODE = "s2_dat_01"
EXPECTED_GOLDEN_FIXTURE_VERSION = "s2-risk-golden-cases/v1.0"
QUALITY_REPORT_SCHEMA_VERSION = "s2-dat-01.report.v1"
REQUIRED_COVERAGES = {
    "normal",
    "reachable_lower_boundary",
    "reachable_upper_boundary",
    "dimension_tension",
    "missing_required",
    "duplicate",
    "unknown_question",
    "invalid_answer_code",
    "contradictory",
    "malformed",
    "unsupported_version",
}
SUPPORTED_MUTATIONS = {
    "remove_by_question_id",
    "append_answer",
    "replace_answer",
    "set_questionnaire_version",
}
RECORD_FIELDS = {"fixture_id", "case_id", "kind", "coverage", "title", "request", "expected"}
REQUEST_FIELDS = {"questionnaire_id", "questionnaire_version", "answers"}
PROHIBITED_FIELDS = {
    "user_id",
    "email",
    "phone",
    "account_number",
    "credential",
    "token",
    "market_price",
    "security_symbol",
    "recommendation",
}


class S2FixtureValidationError(ValueError):
    """Raised when the local S2 assessment fixture boundary is invalid."""


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_fixture_path(filename: str) -> Path:
    return _repository_root() / "data" / "fixtures" / "s2_dat_01" / filename


def _default_risk_contract_path() -> Path:
    return _repository_root() / "docs" / "features" / "risk-profiling" / "risk-contract.v1.json"


def _default_golden_cases_path() -> Path:
    return _repository_root() / "docs" / "features" / "risk-profiling" / "golden-cases.v1.json"


def _default_questionnaire_path() -> Path:
    return _repository_root() / "backend" / "data" / "questionnaire" / "risk_questionnaire_v1.json"


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as source:
            value = json.load(source)
    except FileNotFoundError as exc:
        raise S2FixtureValidationError(f"{label} file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise S2FixtureValidationError(
            f"{label} is not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise S2FixtureValidationError(f"Could not read {label} {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise S2FixtureValidationError(f"{label} must contain a JSON object at the root")
    return value


def _require_fields(value: dict[str, Any], fields: list[str], label: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise S2FixtureValidationError(
            f"{label} is missing required field(s): {', '.join(missing)}"
        )


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise S2FixtureValidationError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise S2FixtureValidationError(f"{label} must be an array")
    return value


def _validate_fixture_contract(
    fixture_contract: dict[str, Any],
    risk_contract: dict[str, Any],
) -> re.Pattern[str]:
    required_fields = [
        "fixture_contract_schema_version",
        "fixture_scope",
        "fixture_mode",
        "risk_contract_version",
        "questionnaire",
        "golden_case_source",
        "deterministic_id_rules",
        "reset_rules",
        "ownership_rules",
        "synthetic_data_rules",
        "required_coverages",
        "record_type",
        "data_port",
    ]
    _require_fields(fixture_contract, required_fields, "fixture contract")

    if fixture_contract["fixture_contract_schema_version"] != EXPECTED_FIXTURE_CONTRACT_VERSION:
        raise S2FixtureValidationError(
            "Unsupported fixture contract version "
            f"{fixture_contract['fixture_contract_schema_version']!r}; "
            f"supported version is {EXPECTED_FIXTURE_CONTRACT_VERSION!r}"
        )
    if fixture_contract["fixture_scope"] != "local_test_only":
        raise S2FixtureValidationError("fixture_contract.fixture_scope must be 'local_test_only'")
    if fixture_contract["fixture_mode"] != EXPECTED_FIXTURE_MODE:
        raise S2FixtureValidationError(
            f"fixture_contract.fixture_mode must be {EXPECTED_FIXTURE_MODE!r}"
        )
    if fixture_contract["risk_contract_version"] != risk_contract["contract_version"]:
        raise S2FixtureValidationError(
            "fixture contract risk contract version does not match risk contract"
        )

    questionnaire = _require_mapping(
        fixture_contract["questionnaire"], "fixture_contract.questionnaire"
    )
    source = _require_mapping(risk_contract["source_of_truth"], "risk_contract.source_of_truth")
    if questionnaire["questionnaire_id"] != source["questionnaire_id"]:
        raise S2FixtureValidationError(
            "fixture contract questionnaire ID does not match risk contract"
        )
    if questionnaire["questionnaire_version"] != source["questionnaire_version"]:
        raise S2FixtureValidationError(
            "fixture contract questionnaire version does not match risk contract"
        )

    golden_source = _require_mapping(
        fixture_contract["golden_case_source"], "fixture_contract.golden_case_source"
    )
    if golden_source["fixture_version"] != EXPECTED_GOLDEN_FIXTURE_VERSION:
        raise S2FixtureValidationError(
            "fixture contract has an unsupported golden-case fixture version"
        )
    if golden_source["contract_ref"] != "risk-contract.v1.json":
        raise S2FixtureValidationError(
            "fixture contract golden-case source must reference risk-contract.v1.json"
        )

    id_rules = _require_mapping(
        fixture_contract["deterministic_id_rules"], "fixture_contract.deterministic_id_rules"
    )
    if id_rules.get("random_uuid_allowed") is not False:
        raise S2FixtureValidationError(
            "fixture contract deterministic IDs must forbid random UUIDs"
        )
    pattern = id_rules.get("pattern")
    if not isinstance(pattern, str):
        raise S2FixtureValidationError("fixture contract deterministic ID pattern must be a string")
    try:
        identifier_pattern = re.compile(pattern)
    except re.error as exc:
        raise S2FixtureValidationError(
            f"fixture contract contains an invalid deterministic ID pattern: {exc}"
        ) from exc

    reset_rules = _require_mapping(fixture_contract["reset_rules"], "fixture_contract.reset_rules")
    for rule in ("deterministic",):
        if reset_rules.get(rule) is not True:
            raise S2FixtureValidationError(f"fixture contract reset rule {rule!r} must be true")
    for rule in ("database_required", "docker_required", "cloud_dependency"):
        if reset_rules.get(rule) is not False:
            raise S2FixtureValidationError(f"fixture contract reset rule {rule!r} must be false")

    for rule_group in ("ownership_rules", "synthetic_data_rules"):
        rules = _require_mapping(fixture_contract[rule_group], f"fixture_contract.{rule_group}")
        for rule, value in rules.items():
            if rule.endswith("_allowed") and value is not False:
                raise S2FixtureValidationError(
                    f"fixture contract {rule_group}.{rule} must be false"
                )
    if fixture_contract["synthetic_data_rules"].get("test_only") is not True:
        raise S2FixtureValidationError("fixture contract synthetic data rules must be test-only")

    required_coverages = set(
        _require_list(fixture_contract["required_coverages"], "fixture_contract.required_coverages")
    )
    if required_coverages != REQUIRED_COVERAGES:
        raise S2FixtureValidationError(
            "fixture contract required coverages do not match the approved S2 fixture set"
        )

    record_type = _require_mapping(fixture_contract["record_type"], "fixture_contract.record_type")
    _require_fields(
        record_type,
        ["required_fields", "request_fields", "prohibited_fields"],
        "fixture_contract.record_type",
    )
    if record_type.get("name") != "assessment_fixture":
        raise S2FixtureValidationError("fixture contract record type must be 'assessment_fixture'")
    for field, expected_fields in (
        ("required_fields", RECORD_FIELDS),
        ("request_fields", REQUEST_FIELDS),
        ("prohibited_fields", PROHIBITED_FIELDS),
    ):
        if set(_require_list(record_type[field], field)) != expected_fields:
            raise S2FixtureValidationError("fixture record schema does not match supported v1")
    data_port = _require_mapping(fixture_contract["data_port"], "fixture_contract.data_port")
    if data_port.get("shared_database_adapter_in_scope") is not False:
        raise S2FixtureValidationError(
            "shared database fixture adapters are out of scope for S2-DAT-01"
        )

    return identifier_pattern


def _validate_golden_cases(
    fixture_contract: dict[str, Any],
    risk_contract: dict[str, Any],
    golden_cases: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    golden_source = fixture_contract["golden_case_source"]
    if golden_cases.get("fixture_version") != golden_source["fixture_version"]:
        raise S2FixtureValidationError(
            "golden-case fixture version does not match the fixture contract"
        )
    if golden_cases.get("contract_ref") != golden_source["contract_ref"]:
        raise S2FixtureValidationError(
            "golden-case contract reference does not match the fixture contract"
        )

    base_request = _require_mapping(golden_cases.get("base_request"), "golden_cases.base_request")
    questionnaire = fixture_contract["questionnaire"]
    if base_request.get("questionnaire_id") != questionnaire["questionnaire_id"]:
        raise S2FixtureValidationError(
            "golden-case questionnaire ID does not match the fixture contract"
        )
    if base_request.get("questionnaire_version") != questionnaire["questionnaire_version"]:
        raise S2FixtureValidationError(
            "golden-case questionnaire version does not match the fixture contract"
        )

    answer_sets = _require_mapping(golden_cases.get("answer_sets"), "golden_cases.answer_sets")
    required_question_ids = risk_contract["input"]["required_question_ids"]
    canonical = _load_json(_default_questionnaire_path(), "Canonical questionnaire")
    metadata = _require_mapping(canonical.get("questionnaire"), "canonical questionnaire metadata")
    if (
        metadata.get("questionnaire_id") != questionnaire["questionnaire_id"]
        or metadata.get("version_label") != questionnaire["questionnaire_version"]
        or metadata.get("status") != "APPROVED"
    ):
        raise S2FixtureValidationError("canonical questionnaire metadata has drifted")
    permitted = {
        question["question_id"]: {answer["code"] for answer in question["answers"]}
        for question in _require_list(canonical.get("questions"), "canonical questions")
    }
    if set(permitted) != set(required_question_ids):
        raise S2FixtureValidationError("canonical questionnaire required questions have drifted")
    for answer_set_id, answers in answer_sets.items():
        answers = _require_mapping(answers, f"golden_cases.answer_sets.{answer_set_id}")
        if set(answers) != set(required_question_ids):
            raise S2FixtureValidationError(
                f"golden answer set {answer_set_id!r} does not contain all required questions"
            )
        for question_id, answer_code in answers.items():
            if not isinstance(answer_code, str) or answer_code not in permitted[question_id]:
                raise S2FixtureValidationError(
                    f"golden answer set {answer_set_id!r} must use a permitted answer"
                )

    cases = _require_list(golden_cases.get("cases"), "golden_cases.cases")
    cases_by_id: dict[str, dict[str, Any]] = {}
    declared_errors = {error["code"] for error in risk_contract["errors"]}
    for case in cases:
        case = _require_mapping(case, "golden_cases.cases[]")
        _require_fields(
            case,
            ["case_id", "kind", "coverage", "title", "answer_set", "expected"],
            "golden case",
        )
        case_id = case["case_id"]
        if not isinstance(case_id, str) or case_id in cases_by_id:
            raise S2FixtureValidationError("golden cases must have unique string case IDs")
        if case["kind"] not in {"valid", "invalid"}:
            raise S2FixtureValidationError(f"golden case {case_id!r} has an unsupported kind")
        if case["coverage"] not in REQUIRED_COVERAGES:
            raise S2FixtureValidationError(
                f"golden case {case_id!r} has an unsupported coverage value"
            )
        if case["answer_set"] not in answer_sets:
            raise S2FixtureValidationError(
                f"golden case {case_id!r} references an unknown answer set"
            )
        expected = _require_mapping(case["expected"], f"golden case {case_id!r}.expected")
        if case["kind"] == "valid":
            _require_fields(
                expected,
                [
                    "willingness_raw",
                    "capacity_raw",
                    "willingness_score",
                    "capacity_score",
                    "composite_score",
                    "risk_category",
                    "limitation_code",
                ],
                f"golden case {case_id!r}.expected",
            )
        else:
            if expected.get("error_code") not in declared_errors:
                raise S2FixtureValidationError(
                    f"golden case {case_id!r} has an undeclared error code"
                )
            if expected.get("score_returned") is not False:
                raise S2FixtureValidationError(
                    f"golden case {case_id!r} must fail without returning a score"
                )
            mutations = _require_list(case.get("mutations"), f"golden case {case_id!r}.mutations")
            if not mutations:
                raise S2FixtureValidationError(
                    f"invalid golden case {case_id!r} must declare a mutation"
                )
            for mutation in mutations:
                mutation = _require_mapping(mutation, f"golden case {case_id!r}.mutation")
                if mutation.get("operation") not in SUPPORTED_MUTATIONS:
                    raise S2FixtureValidationError(
                        f"golden case {case_id!r} has an unsupported fixture mutation"
                    )
                fields = {
                    "remove_by_question_id": ["question_id"],
                    "append_answer": ["answer"],
                    "replace_answer": ["question_id", "answer"],
                    "set_questionnaire_version": ["value"],
                }[mutation["operation"]]
                _require_fields(mutation, fields, "fixture mutation")
                if "answer" in fields:
                    _require_mapping(mutation["answer"], "fixture mutation answer")
        cases_by_id[case_id] = case
    return cases_by_id


def _validate_manifest(
    manifest: dict[str, Any],
    fixture_contract: dict[str, Any],
    golden_cases_by_id: dict[str, dict[str, Any]],
    identifier_pattern: re.Pattern[str],
) -> list[dict[str, str]]:
    required_fields = [
        "fixture_contract_schema_version",
        "fixture_mode",
        "risk_contract_version",
        "questionnaire_id",
        "questionnaire_version",
        "golden_fixture_version",
        "fixtures",
    ]
    _require_fields(manifest, required_fields, "fixture manifest")
    expected_values = {
        "fixture_contract_schema_version": fixture_contract["fixture_contract_schema_version"],
        "fixture_mode": fixture_contract["fixture_mode"],
        "risk_contract_version": fixture_contract["risk_contract_version"],
        "questionnaire_id": fixture_contract["questionnaire"]["questionnaire_id"],
        "questionnaire_version": fixture_contract["questionnaire"]["questionnaire_version"],
        "golden_fixture_version": fixture_contract["golden_case_source"]["fixture_version"],
    }
    for field, expected_value in expected_values.items():
        if manifest[field] != expected_value:
            raise S2FixtureValidationError(
                f"fixture manifest {field!r} does not match the fixture contract"
            )

    entries = _require_list(manifest["fixtures"], "fixture manifest fixtures")
    seen_fixture_ids: set[str] = set()
    seen_golden_case_ids: set[str] = set()
    validated_entries: list[dict[str, str]] = []
    for entry in entries:
        entry = _require_mapping(entry, "fixture manifest entry")
        _require_fields(entry, ["fixture_id", "golden_case_id"], "fixture manifest entry")
        fixture_id = entry["fixture_id"]
        golden_case_id = entry["golden_case_id"]
        if not isinstance(fixture_id, str) or not identifier_pattern.fullmatch(fixture_id):
            raise S2FixtureValidationError(
                "fixture manifest fixture IDs must satisfy the deterministic ID rule"
            )
        if fixture_id in seen_fixture_ids:
            raise S2FixtureValidationError("fixture manifest contains duplicate fixture IDs")
        if golden_case_id not in golden_cases_by_id:
            raise S2FixtureValidationError(
                f"fixture manifest references unknown golden case {golden_case_id!r}"
            )
        if golden_case_id in seen_golden_case_ids:
            raise S2FixtureValidationError(
                "fixture manifest must reference every golden case exactly once"
            )
        seen_fixture_ids.add(fixture_id)
        seen_golden_case_ids.add(golden_case_id)
        validated_entries.append({"fixture_id": fixture_id, "golden_case_id": golden_case_id})

    if seen_golden_case_ids != set(golden_cases_by_id):
        raise S2FixtureValidationError(
            "fixture manifest must reference every golden case exactly once"
        )
    return validated_entries


def _validate_materialized_fields(
    fixtures: list[dict[str, Any]],
    fixture_contract: dict[str, Any],
) -> None:
    record_type = fixture_contract["record_type"]
    required_fields = set(record_type["required_fields"])
    prohibited_fields = set(record_type["prohibited_fields"])
    for fixture in fixtures:
        if set(fixture) != required_fields:
            raise S2FixtureValidationError(
                f"materialized fixture {fixture.get('fixture_id')!r} does not match record schema"
            )
        if set(fixture["request"]) != REQUEST_FIELDS:
            raise S2FixtureValidationError("materialized fixture request does not match schema")
        serialized = json.dumps(fixture, sort_keys=True)
        for prohibited_field in prohibited_fields:
            if f'"{prohibited_field}"' in serialized:
                raise S2FixtureValidationError(
                    f"materialized fixture contains prohibited field {prohibited_field!r}"
                )


def _build_request(
    base_request: dict[str, Any],
    answer_set: dict[str, str],
    required_question_ids: list[str],
    mutations: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    request = deepcopy(base_request)
    request["answers"] = [
        {"question_id": question_id, "answer_code": answer_set[question_id]}
        for question_id in required_question_ids
    ]

    for mutation in mutations or []:
        operation = mutation["operation"]
        if operation == "remove_by_question_id":
            question_id = mutation["question_id"]
            before = len(request["answers"])
            request["answers"] = [
                answer for answer in request["answers"] if answer.get("question_id") != question_id
            ]
            if len(request["answers"]) != before - 1:
                raise S2FixtureValidationError(
                    f"fixture mutation could not remove question {question_id!r}"
                )
        elif operation == "append_answer":
            request["answers"].append(deepcopy(mutation["answer"]))
        elif operation == "replace_answer":
            question_id = mutation["question_id"]
            for index, answer in enumerate(request["answers"]):
                if answer.get("question_id") == question_id:
                    request["answers"][index] = deepcopy(mutation["answer"])
                    break
            else:
                raise S2FixtureValidationError(
                    f"fixture mutation could not replace question {question_id!r}"
                )
        elif operation == "set_questionnaire_version":
            request["questionnaire_version"] = mutation["value"]
        else:
            raise S2FixtureValidationError(
                f"fixture mutation operation {operation!r} is unsupported"
            )
    return request


def _materialize_fixtures(
    fixture_contract: dict[str, Any],
    risk_contract: dict[str, Any],
    golden_cases: dict[str, Any],
    entries: list[dict[str, str]],
    cases: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    fixtures = []
    for entry in entries:
        case = cases[entry["golden_case_id"]]
        request = _build_request(
            golden_cases["base_request"],
            golden_cases["answer_sets"][case["answer_set"]],
            risk_contract["input"]["required_question_ids"],
            case.get("mutations"),
        )
        fixtures.append(
            {
                "fixture_id": entry["fixture_id"],
                "case_id": case["case_id"],
                "kind": case["kind"],
                "coverage": case["coverage"],
                "title": case["title"],
                "request": request,
                "expected": deepcopy(case["expected"]),
            }
        )
    _validate_materialized_fields(fixtures, fixture_contract)
    return fixtures


def _load_and_validate(
    fixture_contract_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    risk_contract_path: Path | str | None = None,
    golden_cases_path: Path | str | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, str]],
    dict[str, dict[str, Any]],
]:
    fixture_contract_file = (
        Path(fixture_contract_path)
        if fixture_contract_path
        else _default_fixture_path("fixture_contract_v1.json")
    )
    manifest_file = (
        Path(manifest_path) if manifest_path else _default_fixture_path("fixture_manifest_v1.json")
    )
    risk_contract_file = (
        Path(risk_contract_path) if risk_contract_path else _default_risk_contract_path()
    )
    golden_cases_file = (
        Path(golden_cases_path) if golden_cases_path else _default_golden_cases_path()
    )

    fixture_contract = _load_json(fixture_contract_file, "Fixture contract")
    manifest = _load_json(manifest_file, "Fixture manifest")
    risk_contract = _load_json(risk_contract_file, "Risk contract")
    golden_cases = _load_json(golden_cases_file, "Golden cases")

    try:
        identifier_pattern = _validate_fixture_contract(fixture_contract, risk_contract)
        golden_cases_by_id = _validate_golden_cases(fixture_contract, risk_contract, golden_cases)
        entries = _validate_manifest(
            manifest, fixture_contract, golden_cases_by_id, identifier_pattern
        )
        _materialize_fixtures(
            fixture_contract, risk_contract, golden_cases, entries, golden_cases_by_id
        )
    except (KeyError, TypeError) as exc:
        raise S2FixtureValidationError(
            "fixture source contains invalid or missing required fields"
        ) from exc
    return (
        fixture_contract,
        manifest,
        risk_contract,
        golden_cases,
        entries,
        golden_cases_by_id,
    )


def validate_assessment_fixtures(
    fixture_contract_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    risk_contract_path: Path | str | None = None,
    golden_cases_path: Path | str | None = None,
) -> dict[str, Any]:
    """Validate source artifacts and return deterministic, non-sensitive evidence."""
    (
        fixture_contract,
        _manifest,
        _risk_contract,
        _golden_cases,
        entries,
        golden_cases_by_id,
    ) = _load_and_validate(
        fixture_contract_path,
        manifest_path,
        risk_contract_path,
        golden_cases_path,
    )
    cases = [golden_cases_by_id[entry["golden_case_id"]] for entry in entries]
    coverage = sorted({case["coverage"] for case in cases})
    if set(coverage) != REQUIRED_COVERAGES:
        raise S2FixtureValidationError("materialized cases do not cover the required fixture set")

    valid_case_count = sum(case["kind"] == "valid" for case in cases)
    invalid_case_count = sum(case["kind"] == "invalid" for case in cases)
    return {
        "valid": True,
        "fixture_contract_schema_version": fixture_contract["fixture_contract_schema_version"],
        "fixture_mode": fixture_contract["fixture_mode"],
        "risk_contract_version": fixture_contract["risk_contract_version"],
        "questionnaire_id": fixture_contract["questionnaire"]["questionnaire_id"],
        "questionnaire_version": fixture_contract["questionnaire"]["questionnaire_version"],
        "fixture_count": len(entries),
        "valid_case_count": valid_case_count,
        "invalid_case_count": invalid_case_count,
        "coverage": coverage,
    }


class S2Dat01FixtureProvider:
    """In-memory local provider built directly from the approved golden-case pack."""

    def __init__(
        self,
        fixture_contract_path: Path | str | None = None,
        manifest_path: Path | str | None = None,
        risk_contract_path: Path | str | None = None,
        golden_cases_path: Path | str | None = None,
    ) -> None:
        self.fixture_contract_path = (
            Path(fixture_contract_path)
            if fixture_contract_path
            else _default_fixture_path("fixture_contract_v1.json")
        )
        self.manifest_path = (
            Path(manifest_path)
            if manifest_path
            else _default_fixture_path("fixture_manifest_v1.json")
        )
        self.risk_contract_path = (
            Path(risk_contract_path) if risk_contract_path else _default_risk_contract_path()
        )
        self.golden_cases_path = (
            Path(golden_cases_path) if golden_cases_path else _default_golden_cases_path()
        )
        self._snapshot: dict[str, Any] | None = None

    def reset(self) -> None:
        """Discard the isolated local snapshot."""
        self._snapshot = None

    def seed(self) -> dict[str, Any]:
        """Validate sources and materialize a fresh immutable-by-copy snapshot."""
        (
            fixture_contract,
            _manifest,
            risk_contract,
            golden_cases,
            entries,
            golden_cases_by_id,
        ) = _load_and_validate(
            self.fixture_contract_path,
            self.manifest_path,
            self.risk_contract_path,
            self.golden_cases_path,
        )
        fixtures = _materialize_fixtures(
            fixture_contract, risk_contract, golden_cases, entries, golden_cases_by_id
        )
        self._snapshot = {
            "fixture_contract_schema_version": fixture_contract["fixture_contract_schema_version"],
            "fixture_mode": fixture_contract["fixture_mode"],
            "risk_contract_version": fixture_contract["risk_contract_version"],
            "fixtures": fixtures,
        }
        return deepcopy(self._snapshot)

    def reset_and_seed(self) -> dict[str, Any]:
        """Reset then rebuild the deterministic local fixture snapshot."""
        self.reset()
        return self.seed()

    def list_fixtures(self) -> list[dict[str, Any]]:
        """List defensive copies of materialized fixtures."""
        if self._snapshot is None:
            self.seed()
        assert self._snapshot is not None
        return deepcopy(self._snapshot["fixtures"])

    def get_fixture(self, fixture_id: str) -> dict[str, Any] | None:
        """Get one fixture by stable fixture ID."""
        for fixture in self.list_fixtures():
            if fixture["fixture_id"] == fixture_id:
                return fixture
        return None


def resolve_assessment_fixture_provider(mode: str) -> S2Dat01FixtureProvider | None:
    """Resolve only the local S2 fixture provider; no remote adapter exists here."""
    if mode == "disabled":
        return None
    if mode == EXPECTED_FIXTURE_MODE:
        return S2Dat01FixtureProvider()
    raise ValueError(f"Unsupported S2 assessment fixture mode: {mode!r}")


def build_fixture_quality_report(
    fixture_contract_path: Path | str | None = None,
    manifest_path: Path | str | None = None,
    risk_contract_path: Path | str | None = None,
    golden_cases_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return a CI-safe report containing counts and rule outcomes only."""
    result = validate_assessment_fixtures(
        fixture_contract_path,
        manifest_path,
        risk_contract_path,
        golden_cases_path,
    )
    return {
        "report_schema_version": QUALITY_REPORT_SCHEMA_VERSION,
        "status": "passed",
        "fixture_contract_schema_version": result["fixture_contract_schema_version"],
        "fixture_mode": result["fixture_mode"],
        "risk_contract_version": result["risk_contract_version"],
        "checks": [
            {
                "rule_id": "DQ-S2-001",
                "status": "passed",
                "description": "Fixture and risk-contract versions are aligned.",
            },
            {
                "rule_id": "DQ-S2-002",
                "status": "passed",
                "description": "Every golden case is referenced exactly once.",
            },
            {
                "rule_id": "DQ-S2-003",
                "status": "passed",
                "description": "Normal, boundary, tension, and invalid coverage is present.",
            },
            {
                "rule_id": "DQ-S2-004",
                "status": "passed",
                "description": "The local adapter requires no database, Docker, cloud, or secrets.",
            },
            {
                "rule_id": "DQ-S2-005",
                "status": "passed",
                "description": "Fixtures contain synthetic contract data only.",
            },
        ],
        "summary": {
            "fixture_count": result["fixture_count"],
            "valid_case_count": result["valid_case_count"],
            "invalid_case_count": result["invalid_case_count"],
            "coverage": result["coverage"],
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Run a local reset/seed validation without writing to a shared system."""
    parser = argparse.ArgumentParser(
        description="Validate and reset local S2-DAT-01 assessment fixtures"
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Render a concise result or a deterministic CI-safe JSON report",
    )
    args = parser.parse_args(argv)

    try:
        snapshot = S2Dat01FixtureProvider().reset_and_seed()
        report = build_fixture_quality_report()
    except S2FixtureValidationError as exc:
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "report_schema_version": QUALITY_REPORT_SCHEMA_VERSION,
                        "status": "failed",
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(f"S2 assessment fixture validation failed: {exc}")
        return 1

    if args.format == "json":
        print(json.dumps(report, sort_keys=True))
    else:
        print(
            "S2-DAT-01 reset and seed passed: "
            f"{len(snapshot['fixtures'])} synthetic fixtures, "
            f"contract {snapshot['fixture_contract_schema_version']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
