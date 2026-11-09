"""Offline writer/hash controls, not native capture or release acceptance."""

import ast
import hashlib
import inspect
import json
import textwrap
from pathlib import Path

import pytest

import local_s2_evidence as shared
import verify_s2_manual_portfolio as portfolio
import verify_s2_saved_risk as risk
from tests.unit.test_local_s2_portfolio_native_harness import (
    corpus_fixture as portfolio_corpus_fixture,
)
from tests.unit.test_local_s2_portfolio_native_harness import (
    fake_complete,
    installed_response,
    wire_body,
)
from verify_s1_application import AcceptanceFailure, _write_new_json


def exact_bytes(document: object) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
        "utf-8"
    )


@pytest.mark.parametrize("text", ["ASCII control", "Synthetic — choice", "π / 1–3 years"])
def test_shared_writer_hashes_the_exact_unicode_file_bytes(tmp_path: Path, text: str) -> None:
    document = {"body_utf8": json.dumps({"message": text}, ensure_ascii=False)}
    destination = tmp_path / "synthetic-evidence.json"
    shared.write_new_json(destination, document)
    expected = exact_bytes(document)
    bytes_match = destination.read_bytes() == expected
    digest_matches = (
        hashlib.sha256(destination.read_bytes()).digest() == hashlib.sha256(expected).digest()
    )
    assert bytes_match and digest_matches


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_shared_writer_rejects_nonfinite_before_creating_output(
    tmp_path: Path, value: float
) -> None:
    destination = tmp_path / "invalid-evidence.json"
    with pytest.raises(AcceptanceFailure):
        shared.write_new_json(destination, {"value": value})
    assert not destination.exists()


def test_shared_writer_never_overwrites_an_existing_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "existing.json"
    original = b"synthetic existing evidence\n"
    destination.write_bytes(original)
    with pytest.raises((AcceptanceFailure, OSError)):
        shared.write_new_json(destination, {"replacement": True})
    assert destination.read_bytes() == original


def test_s1_compatibility_writer_is_not_changed_by_s2_work(tmp_path: Path) -> None:
    destination = tmp_path / "s1-compatibility.json"
    _write_new_json(destination, {"message": "Synthetic — control"})
    expected = (json.dumps({"message": "Synthetic — control"}, indent=2) + "\n").encode()
    assert destination.read_bytes() == expected


def test_source_hash_manifest_uses_actual_bytes_not_newline_normalization(tmp_path: Path) -> None:
    first = tmp_path / "lf.py"
    second = tmp_path / "crlf.py"
    first.write_bytes(b"synthetic\n")
    second.write_bytes(b"synthetic\r\n")
    items = [
        {"path": "backend/crlf.py", "sha256": hashlib.sha256(second.read_bytes()).hexdigest()},
        {"path": "backend/lf.py", "sha256": hashlib.sha256(first.read_bytes()).hexdigest()},
    ]
    raw = "".join(
        f"{item['path']} {item['sha256'].upper()}\n"
        for item in sorted(items, key=lambda item: item["path"])
    ).encode("utf-8")
    assert items[0]["sha256"] != items[1]["sha256"]
    assert portfolio.manifest_sha256(items) == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("driver", [risk, portfolio], ids=["saved-risk", "portfolio"])
def test_runtime_source_manifest_binds_the_shared_writer_module(driver: object) -> None:
    paths = {entry["path"] for entry in driver.runtime_hashes()}
    assert "backend/local_s2_evidence.py" in paths


def test_portfolio_report_digest_matches_exclusively_written_unicode_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # CLI writer unit proof only: this intentionally mocks the native evaluator.
    corpus = {"body_utf8": '{"message":"Synthetic — π"}'}
    expected_digest = hashlib.sha256(portfolio._json_bytes(corpus)).hexdigest()
    report = {"success": True, "corpus_sha256": expected_digest}
    monkeypatch.setattr(portfolio, "evaluate_acceptance", lambda **_: (report, corpus))
    corpus_path, report_path = tmp_path / "corpus.json", tmp_path / "report.json"
    result = portfolio.main(
        [
            "--tested-sha",
            "a" * 40,
            "--tested-tree",
            "b" * 40,
            "--corpus",
            str(corpus_path),
            "--report",
            str(report_path),
        ]
    )
    capsys.readouterr()
    assert result == 0
    written_digest = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    recorded_digest = json.loads(report_path.read_bytes())["corpus_sha256"]
    assert written_digest == recorded_digest


@pytest.mark.parametrize("size", [262143, 262144, 262145])
def test_portfolio_wire_acceptance_uses_the_frozen_client_byte_boundary(size: int) -> None:
    raw = json.dumps(wire_body()).encode("utf-8")
    raw += b" " * (size - len(raw))
    if size <= 262144:
        decoded = portfolio._wire_body(raw, "portfolio_detail", 200, None)
        assert decoded["portfolio_id"] == wire_body()["data"]["portfolio_id"]
    else:
        with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
            portfolio._wire_body(raw, "portfolio_detail", 200, None)


@pytest.mark.parametrize("size", [262143, 262144, 262145])
def test_portfolio_capture_rejects_plus_one_without_trimming_original_bytes(
    tmp_path: Path, size: int
) -> None:
    import httpx

    proof = portfolio.PortfolioProof(tmp_path / "unused-unit-database.sqlite3")
    raw = json.dumps(wire_body()).encode("utf-8")
    raw += b" " * (size - len(raw))
    installed_response(
        proof,
        httpx.Response(200, content=raw, headers={"Content-Type": "application/json"}),
    )
    if size <= 262144:
        proof.request(
            "portfolio_detail",
            None,
            portfolio_id=wire_body()["data"]["portfolio_id"],
            case_id="portfolio_detail",
        )
        unchanged = proof.cases["portfolio_detail"]["body_utf8"].encode("utf-8") == raw
        assert unchanged
    else:
        with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
            proof.request(
                "portfolio_detail",
                None,
                portfolio_id=wire_body()["data"]["portfolio_id"],
                case_id="portfolio_detail",
            )
        assert proof.cases == {} and proof.responses_checked == 0


@pytest.mark.parametrize("size", [262143, 262144, 262145])
def test_portfolio_corpus_uses_the_same_untrimmed_byte_boundary(size: int) -> None:
    corpus = portfolio_corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == "portfolio_detail")
    original = case["body_utf8"].encode("utf-8")
    case["body_utf8"] = (original + b" " * (size - len(original))).decode("utf-8")
    if size <= 262144:
        portfolio.validate_corpus(corpus)
    else:
        with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
            portfolio.validate_corpus(corpus)


def install_chronological_portfolio_unit_proof(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, fault: str | None = None
) -> list[int]:
    """Use real source check-ID chronology with a fully fake native lifecycle.

    No observed response bodies, private IDs or actual process records are
    copied. Only static approved technical check IDs come from the real run
    method; the existing unit harness replaces all child/API/clock effects.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(portfolio.PortfolioProof.run)))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr == "mark"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    ids = [node.args[0].value for node in sorted(calls, key=lambda node: node.lineno)]
    assert len(ids) == len(portfolio.REQUIRED_CHECKS) - 1
    assert set(ids) == set(portfolio.REQUIRED_CHECKS) - {"owned_cleanup"}
    stopped = fake_complete(monkeypatch, tmp_path)
    constructor = portfolio.PortfolioProof

    def make_proof(database: Path) -> object:
        proof = constructor(database)
        records = {item["id"]: item for item in proof.checks}
        proof.checks = [records[identifier] for identifier in ids]
        if fault == "duplicate":
            proof.checks[-1] = proof.checks[0].copy()
        elif fault == "missing":
            proof.checks.pop()
        elif fault == "false":
            proof.checks[0]["passed"] = False
        elif fault in {"cleanup", "provenance"}:
            server = proof.native.servers[-1]
            stop = server.stop

            def stop_with_fault() -> None:
                stop()
                if fault == "cleanup":
                    raise AcceptanceFailure("CHILD_CLEANUP_FAILED")
                monkeypatch.setattr(portfolio, "runtime_hashes", lambda: [])

            server.stop = stop_with_fault
        return proof

    monkeypatch.setattr(portfolio, "PortfolioProof", make_proof)
    return stopped


def test_completed_chronological_portfolio_proof_has_canonical_report_summary_after_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Source-derived chronology is not a TCP proof. This guards the producer's
    # successful report serialization without relaxing consumer check order.
    stopped = install_chronological_portfolio_unit_proof(monkeypatch, tmp_path)
    report, corpus = portfolio.evaluate_acceptance(tested_sha="a" * 40, tested_tree="b" * 40)
    assert report["success"] is True and corpus is not None
    canonical = report["checks"] == [
        {"id": identifier, "passed": True} for identifier in portfolio.REQUIRED_CHECKS
    ]
    assert canonical
    assert stopped == [1, 2, 3, 4, 5] and list(tmp_path.iterdir()) == []
    assert report["native_process"]["child_reaped"] is True
    assert report["native_process"]["temporary_directory_removed"] is True


@pytest.mark.parametrize("fault", ["duplicate", "missing", "false", "cleanup", "provenance"])
def test_invalid_or_unconfirmed_chronological_proof_never_becomes_completed_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    stopped = install_chronological_portfolio_unit_proof(monkeypatch, tmp_path, fault=fault)
    report, corpus = portfolio.evaluate_acceptance(tested_sha="a" * 40, tested_tree="b" * 40)
    code = {
        "cleanup": "CHILD_CLEANUP_FAILED",
        "provenance": "SOURCE_CHANGED",
    }.get(fault, "PROBE_FAILED")
    assert report["success"] is False and corpus is None
    assert report["failures"] == [{"code": code}]
    has_fabricated_summary = report["checks"] == [
        {"id": identifier, "passed": True} for identifier in portfolio.REQUIRED_CHECKS
    ]
    assert not has_fabricated_summary
    assert stopped == [1, 2, 3, 4, 5] and list(tmp_path.iterdir()) == []
