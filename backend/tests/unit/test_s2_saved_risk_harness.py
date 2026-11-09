"""Saved-risk evidence must fail closed and never accept a dirty or wrong checkout."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import verify_s2_saved_risk as verifier
from verify_s1_application import AcceptanceFailure

SHA = "a" * 40
TREE = "b" * 40


def test_dirty_candidate_stops_before_any_owned_process_or_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        verifier,
        "repository_provenance",
        lambda *_: {"working_tree_dirty": True, "tested_commit": SHA, "tested_tree": TREE},
    )
    monkeypatch.setattr(
        verifier, "SavedRiskProof", lambda *_: pytest.fail("Must not start a child")
    )
    report = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False
    assert report["failures"] == [{"code": "PROVENANCE_MISMATCH"}]
    assert report["native_process"]["starts"] == 0


def test_wrong_requested_sha_is_not_silently_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    def provenance(*_: object) -> dict:
        raise AcceptanceFailure("PROVENANCE_MISMATCH")

    monkeypatch.setattr(verifier, "repository_provenance", provenance)
    monkeypatch.setattr(
        verifier, "SavedRiskProof", lambda *_: pytest.fail("Must not start a child")
    )
    report = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False
    assert report["failures"] == [{"code": "PROVENANCE_MISMATCH"}]


@pytest.mark.parametrize("failure", ["WIRE_INVALID", "CHILD_CLEANUP_FAILED"])
def test_application_or_owned_cleanup_failure_is_not_a_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    monkeypatch.setattr(verifier, "_temp_base", lambda: tmp_path.resolve())
    monkeypatch.setattr(
        verifier,
        "repository_provenance",
        lambda *_: {"working_tree_dirty": False, "tested_commit": SHA, "tested_tree": TREE},
    )
    monkeypatch.setattr(verifier, "runtime_hashes", lambda: [])

    def git(arguments: list[str]) -> str:
        if arguments == ["rev-parse", "HEAD"]:
            return SHA
        if arguments == ["rev-parse", "HEAD^{tree}"]:
            return TREE
        return ""

    monkeypatch.setattr(verifier, "_git", git)
    stopped: list[bool] = []

    class Server:
        reaped = False

        def stop(self) -> None:
            stopped.append(True)
            self.reaped = True
            if failure == "CHILD_CLEANUP_FAILED":
                raise AcceptanceFailure(failure)

    class Proof:
        def __init__(self, database: Path) -> None:
            self.native = SimpleNamespace(servers=[Server()])
            self.checks: list[dict] = []
            self.responses_checked = 0
            self.database = database

        def run(self) -> None:
            if failure == "WIRE_INVALID":
                raise AcceptanceFailure(failure)

    monkeypatch.setattr(verifier, "SavedRiskProof", Proof)
    report = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False
    assert report["failures"] == [{"code": failure}]
    assert stopped == [True]
    assert report["native_process"]["temporary_directory_removed"] is True
    assert list(tmp_path.iterdir()) == []


def test_cli_does_not_overwrite_existing_report(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    path = tmp_path / "existing.json"
    path.write_text("preserve synthetic report\n", encoding="utf-8")
    result = verifier.main(["--tested-sha", SHA, "--tested-tree", TREE, "--report", str(path)])
    assert result == 1
    assert path.read_text(encoding="utf-8") == "preserve synthetic report\n"
    assert json.loads(capsys.readouterr().out)["failures"] == [{"code": "OUTPUT_EXISTS"}]


def test_cli_never_relays_unexpected_exception_or_sensitive_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    def fail(**_: object) -> dict:
        raise RuntimeError("synthetic-private-diagnostic-that-must-not-be-printed")

    monkeypatch.setattr(verifier, "evaluate_acceptance", fail)
    assert verifier.main(["--tested-sha", SHA, "--tested-tree", TREE]) == 1
    output = capsys.readouterr().out
    assert "private-diagnostic" not in output
    assert json.loads(output)["failures"] == [{"code": "INTERNAL_FAILURE"}]
