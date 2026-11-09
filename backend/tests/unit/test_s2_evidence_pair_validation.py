"""Passive-loader unit guards, NOT TCP capture, native cleanup or release proof.

All revisions, source files, process IDs and reports here are handcrafted in an
owned temporary directory. The private revision seam is monkeypatched only for
these unit assertions; the public CLI has no fixture or provenance fallback.
"""

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import local_s2_evidence as shared
import verify_s2_evidence_pair as pair
import verify_s2_manual_portfolio as portfolio
import verify_s2_saved_risk as risk
from tests.unit.test_local_s2_portfolio_native_harness import (
    corpus_fixture as portfolio_fixture,
)
from tests.unit.test_s2_saved_risk_corpus import corpus_fixture as risk_fixture
from verify_s1_application import CONTRACT_VERSION, SCOPE, AcceptanceFailure

SHA, TREE = "a" * 40, "b" * 40
REPORT_FIELDS = (
    "schema_version",
    "scope",
    "contract_version",
    "success",
    "mode",
    "tested_commit",
    "tested_tree",
    "working_tree_dirty",
    "tracked_dirty",
    "source_hashes",
    "source_manifest_sha256",
    "checks",
    "required_checks",
    "failures",
    "responses_checked",
    "corpus_sha256",
    "corpus_case_ids",
    "native_process",
    "python_version",
    "limitations",
)
CORPUS_FIELDS = (
    "schema_version",
    "scope",
    "contract_version",
    "provenance",
    "source_hashes",
    "source_manifest_sha256",
    "cases",
)
NATIVE_FIELDS = (
    "starts",
    "application_restarts",
    "owned_pids",
    "child_reaped",
    "temporary_directory_removed",
    "session_ttl_minutes",
    "real_expiry_elapsed_seconds",
    "shutdown",
)
PROVENANCE_FIELDS = ("kind", "source", "command", "tested_commit", "tested_tree")
SHARED_SOURCES = (
    "backend/app/main.py",
    "backend/local_s2_evidence.py",
    "backend/verify_s2_evidence_pair.py",
    "backend/tests/unit/test_s2_evidence_pair_validation.py",
)


@dataclass
class UnitPair:
    root: Path
    paths: dict[str, Path]
    documents: dict[str, dict]
    revision_calls: list[int]

    def flush(self, *, bind_digest: bool = True) -> None:
        for domain in ("risk", "portfolio"):
            raw = shared.json_bytes(self.documents[domain + "_corpus"])
            self.paths[domain + "_corpus"].write_bytes(raw)
            if bind_digest:
                self.documents[domain + "_report"]["corpus_sha256"] = hashlib.sha256(
                    raw
                ).hexdigest()
            self.paths[domain + "_report"].write_bytes(
                shared.json_bytes(self.documents[domain + "_report"])
            )

    def validate(self, **overrides: object) -> None:
        options = {**self.paths, "tested_sha": SHA, "tested_tree": TREE, **overrides}
        pair.validate_pair(**options)

    def cli(self) -> list[str]:
        return [
            "--risk-report",
            str(self.paths["risk_report"]),
            "--risk-corpus",
            str(self.paths["risk_corpus"]),
            "--portfolio-report",
            str(self.paths["portfolio_report"]),
            "--portfolio-corpus",
            str(self.paths["portfolio_corpus"]),
            "--tested-sha",
            SHA,
            "--tested-tree",
            TREE,
        ]


@pytest.fixture
def unit_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UnitPair:
    root = tmp_path / "synthetic-checkout"
    root.mkdir()
    artifacts = tmp_path / "synthetic-artifacts"
    artifacts.mkdir()
    paths = {
        key: artifacts / (key + ".json")
        for key in ("risk_report", "risk_corpus", "portfolio_report", "portfolio_corpus")
    }
    documents: dict[str, dict] = {}
    for domain, driver, fixture, extra in (
        ("risk", risk, risk_fixture, "ai/risk/contract.py"),
        (
            "portfolio",
            portfolio,
            portfolio_fixture,
            "docs/features/local-application/S2-manual-portfolio-contract.md",
        ),
    ):
        corpus = fixture()
        names = (*SHARED_SOURCES, "backend/" + driver.__name__ + ".py", extra)
        source_rows = []
        for name in sorted(names):
            source = root / name
            source.parent.mkdir(parents=True, exist_ok=True)
            if not source.exists():
                source.write_bytes(("unit-only source " + name + "\n").encode("utf-8"))
            source_rows.append(
                {"path": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
            )
        corpus["source_hashes"] = source_rows
        corpus["source_manifest_sha256"] = shared.manifest_sha256(source_rows)
        report = {
            "schema_version": driver.REPORT_SCHEMA,
            "scope": SCOPE,
            "contract_version": CONTRACT_VERSION,
            "success": True,
            "mode": "owned_native_tcp",
            "tested_commit": SHA,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
            "source_hashes": copy.deepcopy(source_rows),
            "source_manifest_sha256": corpus["source_manifest_sha256"],
            "checks": [{"id": identifier, "passed": True} for identifier in driver.REQUIRED_CHECKS],
            "required_checks": list(driver.REQUIRED_CHECKS),
            "failures": [],
            "responses_checked": len(driver.CASE_IDS),
            "corpus_sha256": "c" * 64,
            "corpus_case_ids": list(driver.CASE_IDS),
            "native_process": {
                "starts": 4 if domain == "risk" else 5,
                "application_restarts": 2,
                "owned_pids": [100 + index for index in range(4 if domain == "risk" else 5)],
                "child_reaped": True,
                "temporary_directory_removed": True,
                "session_ttl_minutes": 1,
                "real_expiry_elapsed_seconds": None if domain == "risk" else 60.25,
                "shutdown": "owned_terminate_and_reap",
            },
            "python_version": "3.12.9",
            "limitations": ["Handcrafted passive-validator unit input; not native evidence."],
        }
        documents[domain + "_corpus"] = corpus
        documents[domain + "_report"] = report
    calls: list[int] = []

    def revision() -> dict:
        calls.append(len(calls) + 1)
        return {
            "tested_commit": SHA,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        }

    monkeypatch.setattr(pair, "ROOT", root)
    monkeypatch.setattr(pair, "_repository_snapshot", revision)
    fixture = UnitPair(root, paths, documents, calls)
    fixture.flush()
    return fixture


def test_complete_unit_pair_allows_different_domain_inventories_without_writes(
    unit_pair: UnitPair,
) -> None:
    before = {name: path.read_bytes() for name, path in unit_pair.paths.items()}
    risk.validate_corpus(unit_pair.documents["risk_corpus"])
    portfolio.validate_corpus(unit_pair.documents["portfolio_corpus"])
    unit_pair.validate()
    unchanged = all(path.read_bytes() == before[name] for name, path in unit_pair.paths.items())
    assert unchanged and len(unit_pair.revision_calls) >= 2
    assert (
        unit_pair.documents["risk_corpus"]["source_hashes"]
        != unit_pair.documents["portfolio_corpus"]["source_hashes"]
    )


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
def test_actual_hashed_empty_approved_source_is_valid_under_unit_revision_seam(
    unit_pair: UnitPair, domain: str
) -> None:
    # This is an actual empty file in the synthetic checkout, not a mocked
    # byte reader or a claim that the fixture is clean native evidence.
    name = "backend/app/__init__.py"
    source = unit_pair.root / name
    source.write_bytes(b"")
    rows = [
        *unit_pair.documents[domain + "_corpus"]["source_hashes"],
        {"path": name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
    ]
    rows.sort(key=lambda row: row["path"])
    manifest = shared.manifest_sha256(rows)
    for kind in ("report", "corpus"):
        document = unit_pair.documents[domain + "_" + kind]
        document["source_hashes"] = copy.deepcopy(rows)
        document["source_manifest_sha256"] = manifest
    unit_pair.flush()
    unit_pair.validate()
    assert source.read_bytes() == b"" and len(unit_pair.revision_calls) >= 2


@pytest.mark.parametrize(
    "name", ["risk_report", "risk_corpus", "portfolio_report", "portfolio_corpus"]
)
def test_empty_json_artifacts_remain_invalid_even_when_empty_sources_are_legal(
    unit_pair: UnitPair, name: str
) -> None:
    unit_pair.paths[name].write_bytes(b"")
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize("field", REPORT_FIELDS)
def test_each_required_report_field_is_mandatory(
    unit_pair: UnitPair, domain: str, field: str
) -> None:
    del unit_pair.documents[domain + "_report"][field]
    unit_pair.flush(bind_digest=field != "corpus_sha256")
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize("field", CORPUS_FIELDS)
def test_each_required_corpus_field_is_mandatory(
    unit_pair: UnitPair, domain: str, field: str
) -> None:
    del unit_pair.documents[domain + "_corpus"][field]
    unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize("field", NATIVE_FIELDS)
def test_each_required_native_cleanup_field_is_mandatory(
    unit_pair: UnitPair, domain: str, field: str
) -> None:
    del unit_pair.documents[domain + "_report"]["native_process"][field]
    unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize("field", PROVENANCE_FIELDS)
def test_each_required_provenance_field_is_mandatory(
    unit_pair: UnitPair, domain: str, field: str
) -> None:
    del unit_pair.documents[domain + "_corpus"]["provenance"][field]
    unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


REPORT_MUTATIONS = (
    "schema",
    "scope",
    "contract",
    "mode",
    "success_false",
    "success_integer",
    "commit",
    "tree",
    "dirty",
    "tracked_dirty",
    "dirty_integer",
    "tracked_integer",
    "manifest",
    "digest",
    "checks_missing",
    "checks_duplicate",
    "checks_order",
    "checks_pass_integer",
    "checks_extra",
    "required_checks",
    "failures",
    "responses_boolean",
    "responses_few",
    "responses_excess",
    "case_ids_order",
    "case_ids_missing",
    "python_empty",
    "python_private",
    "limitations_private",
    "extra",
)


def corrupt_report(report: dict, mutation: str) -> None:
    if mutation in {"schema", "scope", "contract", "mode", "commit", "tree"}:
        key = {
            "schema": "schema_version",
            "contract": "contract_version",
            "commit": "tested_commit",
            "tree": "tested_tree",
        }.get(mutation, mutation)
        report[key] = "unit-invalid"
    elif mutation.startswith("success_"):
        report["success"] = False if mutation == "success_false" else 1
    elif mutation in {"dirty", "tracked_dirty", "dirty_integer", "tracked_integer"}:
        key = "working_tree_dirty" if mutation.startswith("dirty") else "tracked_dirty"
        report[key] = 0 if mutation.endswith("integer") else True
    elif mutation in {"manifest", "digest"}:
        report["source_manifest_sha256" if mutation == "manifest" else "corpus_sha256"] = "f" * 64
    elif mutation.startswith("checks_"):
        checks = report["checks"]
        if mutation == "checks_missing":
            checks.pop()
        elif mutation == "checks_duplicate":
            checks[-1] = copy.deepcopy(checks[0])
        elif mutation == "checks_order":
            checks[0], checks[1] = checks[1], checks[0]
        elif mutation == "checks_pass_integer":
            checks[0]["passed"] = 1
        else:
            checks[0]["extra"] = True
    elif mutation == "required_checks":
        report["required_checks"][-1] = "unit-unapproved"
    elif mutation == "failures":
        report["failures"] = [{"code": "UNIT_ONLY_FAILURE"}]
    elif mutation.startswith("responses_"):
        report["responses_checked"] = (
            True
            if mutation == "responses_boolean"
            else 1
            if mutation == "responses_few"
            else 100001
        )
    elif mutation == "case_ids_order":
        report["corpus_case_ids"].reverse()
    elif mutation == "case_ids_missing":
        report["corpus_case_ids"].pop()
    elif mutation == "python_empty":
        report["python_version"] = ""
    elif mutation == "python_private":
        report["python_version"] = "Bearer synthetic-unit-value"
    elif mutation == "limitations_private":
        report["limitations"] = ["Bearer synthetic-unit-value"]
    else:
        report["extra"] = True


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize("mutation", REPORT_MUTATIONS)
def test_report_contradictions_fail_closed(unit_pair: UnitPair, domain: str, mutation: str) -> None:
    corrupt_report(unit_pair.documents[domain + "_report"], mutation)
    unit_pair.flush(bind_digest=mutation != "digest")
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize(
    "mutation",
    [
        "starts_boolean",
        "starts_wrong",
        "restarts_boolean",
        "restarts_wrong",
        "pids_duplicate",
        "pids_boolean",
        "pids_zero",
        "pids_count",
        "reaped_false",
        "reaped_integer",
        "removed_false",
        "removed_integer",
        "ttl_boolean",
        "ttl_wrong",
        "shutdown",
        "expiry",
        "extra",
    ],
)
def test_native_cleanup_and_bounds_are_strict(
    unit_pair: UnitPair, domain: str, mutation: str
) -> None:
    native = unit_pair.documents[domain + "_report"]["native_process"]
    if mutation.startswith("starts_"):
        native["starts"] = True if mutation.endswith("boolean") else 3
    elif mutation.startswith("restarts_"):
        native["application_restarts"] = True if mutation.endswith("boolean") else 1
    elif mutation == "pids_duplicate":
        native["owned_pids"][-1] = native["owned_pids"][0]
    elif mutation == "pids_boolean":
        native["owned_pids"][0] = True
    elif mutation == "pids_zero":
        native["owned_pids"][0] = 0
    elif mutation == "pids_count":
        native["owned_pids"].pop()
    elif mutation.startswith("reaped_"):
        native["child_reaped"] = 1 if mutation.endswith("integer") else False
    elif mutation.startswith("removed_"):
        native["temporary_directory_removed"] = 1 if mutation.endswith("integer") else False
    elif mutation.startswith("ttl_"):
        native["session_ttl_minutes"] = True if mutation.endswith("boolean") else 2
    elif mutation == "shutdown":
        native["shutdown"] = "unit-unreaped"
    elif mutation == "expiry":
        native["real_expiry_elapsed_seconds"] = 60 if domain == "risk" else 58.9
    else:
        native["extra"] = True
    unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("value", [None, True, "60", 58.999, 75.001, float("nan"), float("inf")])
def test_portfolio_real_expiry_cannot_be_absent_early_or_nonfinite(
    unit_pair: UnitPair, value: object
) -> None:
    unit_pair.documents["portfolio_report"]["native_process"]["real_expiry_elapsed_seconds"] = value
    if isinstance(value, float) and not (-float("inf") < value < float("inf")):
        unit_pair.paths["portfolio_report"].write_bytes(
            (json.dumps(unit_pair.documents["portfolio_report"], allow_nan=True) + "\n").encode(
                "utf-8"
            )
        )
    else:
        unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("domain", ["risk", "portfolio"])
@pytest.mark.parametrize(
    "mutation",
    [
        "schema",
        "scope",
        "version",
        "case_missing",
        "case_duplicate",
        "case_order",
        "case_operation",
        "body_duplicate",
        "body_private",
        "meta_version",
        "source_missing",
        "source_wrong",
        "source_parent",
        "source_absolute",
        "source_order",
        "source_duplicate",
        "pair_inventory",
        "pair_manifest",
        "wrong_revision",
        "foreign_command",
        "extra",
    ],
)
def test_domain_corpus_binding_and_semantics_cannot_be_relabelled(
    unit_pair: UnitPair, domain: str, mutation: str
) -> None:
    corpus = unit_pair.documents[domain + "_corpus"]
    if mutation in {"schema", "scope", "version"}:
        corpus[
            {"schema": "schema_version", "version": "contract_version"}.get(mutation, mutation)
        ] = "unit-invalid"
    elif mutation == "case_missing":
        corpus["cases"].pop()
    elif mutation == "case_duplicate":
        corpus["cases"][-1] = copy.deepcopy(corpus["cases"][0])
    elif mutation == "case_order":
        corpus["cases"][0], corpus["cases"][1] = corpus["cases"][1], corpus["cases"][0]
    elif mutation == "case_operation":
        corpus["cases"][0]["operation"] = "unit-wrong"
    elif mutation == "body_duplicate":
        corpus["cases"][0]["body_utf8"] = corpus["cases"][0]["body_utf8"].replace(
            '"success": true', '"success": false, "success": true'
        )
    elif mutation in {"body_private", "meta_version"}:
        body = json.loads(corpus["cases"][0]["body_utf8"])
        if mutation == "body_private":
            body["message"] = "Bearer synthetic-unit-value"
        else:
            body["meta"]["apiVersion"] = "v0"
        corpus["cases"][0]["body_utf8"] = json.dumps(body)
    elif mutation.startswith("source_"):
        rows = corpus["source_hashes"]
        if mutation == "source_missing":
            rows.clear()
        elif mutation == "source_wrong":
            rows[0]["sha256"] = "f" * 64
        elif mutation == "source_parent":
            rows[0]["path"] = "../unit-private"
        elif mutation == "source_absolute":
            rows[0]["path"] = "C:/unit-private"
        elif mutation == "source_order":
            rows.reverse()
        else:
            rows.append(copy.deepcopy(rows[0]))
    elif mutation == "pair_inventory":
        unit_pair.documents[domain + "_report"]["source_hashes"].pop()
    elif mutation == "pair_manifest":
        unit_pair.documents[domain + "_report"]["source_manifest_sha256"] = "d" * 64
    elif mutation == "wrong_revision":
        corpus["provenance"]["tested_commit"] = "d" * 40
    elif mutation == "foreign_command":
        corpus["provenance"]["command"] = "python unit-unapproved.py"
    else:
        corpus["extra"] = True
    unit_pair.flush()
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize("field", ["tested_sha", "tested_tree"])
@pytest.mark.parametrize("value", [None, "", "A" * 40, "a" * 39, "f" * 40])
def test_exact_requested_revision_is_required(
    unit_pair: UnitPair, field: str, value: object
) -> None:
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate(**{field: value})


@pytest.mark.parametrize(
    "mutation", ["dirty", "tracked", "changed_sha", "changed_tree", "source_drift"]
)
def test_current_provenance_and_actual_source_bytes_are_checked_twice(
    unit_pair: UnitPair, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    calls = 0

    def revision() -> dict:
        nonlocal calls
        calls += 1
        final = calls >= 2
        if final and mutation == "source_drift":
            (unit_pair.root / "backend/app/main.py").write_bytes(b"unit-only changed bytes\n")
        return {
            "tested_commit": "f" * 40 if final and mutation == "changed_sha" else SHA,
            "tested_tree": "f" * 40 if final and mutation == "changed_tree" else TREE,
            "working_tree_dirty": mutation == "dirty",
            "tracked_dirty": mutation == "tracked",
        }

    monkeypatch.setattr(pair, "_repository_snapshot", revision)
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


@pytest.mark.parametrize(
    "name", ["risk_report", "risk_corpus", "portfolio_report", "portfolio_corpus"]
)
@pytest.mark.parametrize(
    "mutation", ["missing", "directory", "oversized", "invalid_utf8", "duplicate_key"]
)
def test_inputs_are_bounded_unique_json_regular_files(
    unit_pair: UnitPair, name: str, mutation: str
) -> None:
    path = unit_pair.paths[name]
    if mutation in {"missing", "directory"}:
        path.unlink()
        if mutation == "directory":
            path.mkdir()
    elif mutation == "oversized":
        path.write_bytes(b" " * 2097153)
    elif mutation == "invalid_utf8":
        path.write_bytes(b"{\xff}")
    else:
        original = path.read_bytes()
        path.write_bytes(original.replace(b'"scope":', b'"scope":"unit-invalid", "scope":', 1))
        if name.endswith("corpus"):
            report = unit_pair.documents[name.replace("corpus", "report")]
            report["corpus_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            unit_pair.paths[name.replace("corpus", "report")].write_bytes(shared.json_bytes(report))
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


def test_byte_digest_is_of_the_exact_file_not_reserialized_json(unit_pair: UnitPair) -> None:
    path = unit_pair.paths["risk_corpus"]
    path.write_bytes(path.read_bytes() + b"\n ")
    with pytest.raises(AcceptanceFailure, match="PAIR_INVALID"):
        unit_pair.validate()


def test_cli_validates_without_writing_or_native_execution(
    unit_pair: UnitPair, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        risk, "evaluate_acceptance", lambda **_: pytest.fail("Unexpected native evaluator")
    )
    monkeypatch.setattr(
        portfolio, "evaluate_acceptance", lambda **_: pytest.fail("Unexpected native evaluator")
    )
    before = {name: path.read_bytes() for name, path in unit_pair.paths.items()}
    result = pair.main(unit_pair.cli())
    output = capsys.readouterr()
    assert result == 0 and output.out == "S2 evidence pair: PASS\n" and output.err == ""
    assert all(path.read_bytes() == before[name] for name, path in unit_pair.paths.items())


@pytest.mark.parametrize(
    "mutation", ["missing_argument", "unknown_argument", "malformed_json", "private_error"]
)
def test_cli_failure_prints_only_a_fixed_technical_status(
    unit_pair: UnitPair,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    arguments = unit_pair.cli()
    if mutation == "missing_argument":
        arguments = arguments[:-2]
    elif mutation == "unknown_argument":
        arguments += ["--unit-unapproved"]
    elif mutation == "malformed_json":
        unit_pair.paths["risk_report"].write_bytes(b'{"malformed":')
    else:

        def broken() -> dict:
            raise RuntimeError("synthetic-private-parser-diagnostic")

        monkeypatch.setattr(pair, "_repository_snapshot", broken)
    result = pair.main(arguments)
    output = capsys.readouterr()
    assert result == 1 and output.out == "S2 evidence pair: FAIL\n" and output.err == ""
