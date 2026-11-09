"""Owned S1 evidence must not silently fall back to stateless pilot proof."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def workflow(name: str) -> dict[str, Any]:
    source = ROOT / ".github" / "workflows" / name
    result = yaml.load(source.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(result, dict)
    return result


def test_s1_ci_executes_owned_native_proof_and_keeps_pilot_separate() -> None:
    jobs = workflow("s1-uat-evidence.yml")["jobs"]
    assert "owned-native" in jobs, "S1 CI currently proves only the compatibility pilot"
    steps = jobs["owned-native"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "verify_s1_application.py" in commands
    assert "--report" in commands and "--corpus" in commands
    assert "verify_r0_thin_slice.py" not in commands
    pilot_commands = "\n".join(step.get("run", "") for step in jobs["backend-contract"]["steps"])
    assert "verify_r0_thin_slice.py" in pilot_commands


@pytest.mark.parametrize("name", ["react-journey", "flutter-journey"])
def test_both_clients_require_successful_native_corpus_without_fixture_fallback(name: str) -> None:
    job = workflow("s1-uat-evidence.yml")["jobs"][name]
    needs = job.get("needs", [])
    assert "owned-native" in needs
    steps = job["steps"]
    assert any("actions/download-artifact@" in step.get("uses", "") for step in steps)
    parity = [step for step in steps if step.get("env", {}).get("FINEX_LOCAL_S1_CORPUS")]
    assert len(parity) == 1
    assert parity[0]["env"].get("FINEX_REQUIRE_LOCAL_S1_CORPUS") == "1"
    assert "continue-on-error" not in parity[0]
    assert "if" not in parity[0], "A selected S1 parity gate must not be conditional"


def test_s1_summary_distinguishes_tested_checkout_candidate_and_nonhuman_acceptance() -> None:
    summary = workflow("s1-uat-evidence.yml")["jobs"]["summary"]
    assert "owned-native" in summary["needs"]
    commands = "\n".join(step.get("run", "") for step in summary["steps"])
    assert "GITHUB_SHA" in commands and "CANDIDATE_HEAD" in commands
    assert "not human UAT" in commands
    assert "native TCP" in commands


def test_backend_types_the_native_verifier_and_changes_trigger_the_gates() -> None:
    backend = workflow("backend-quality.yml")
    commands = "\n".join(step.get("run", "") for step in backend["jobs"]["quality"]["steps"])
    assert "mypy app verify_s1_application.py" in commands
    for trigger in ("push", "pull_request"):
        paths = workflow("s1-uat-evidence.yml")["on"][trigger]["paths"]
        assert "data/fixtures/local_s1/**" in paths
        assert "scripts/verify-s1.ps1" in paths


def test_backend_checks_both_developer_and_hosted_ci_type_platforms() -> None:
    steps = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Mypy type check")
    checks = [line for line in command.splitlines() if "python -m mypy" in line]
    assert len(checks) == 2, "Windows-only local typing must not hide a Linux CI defect"
    assert all("verify_s1_application.py" in line for line in checks)
    assert all("--python-version 3.13" in line for line in checks)
    assert {line.split("--platform ")[1].split()[0] for line in checks} == {
        "linux",
        "win32",
    }


def test_s1_artifact_is_an_explicit_safe_report_allowlist_not_database_or_raw_logs() -> None:
    jobs = workflow("s1-uat-evidence.yml")["jobs"]
    assert "owned-native" in jobs
    uploads = [
        step
        for step in jobs["owned-native"]["steps"]
        if "actions/upload-artifact@" in step.get("uses", "")
    ]
    assert len(uploads) == 1
    artifact = uploads[0]["with"]
    assert artifact["if-no-files-found"] == "error"
    assert int(artifact["retention-days"]) <= 7
    assert set(artifact["path"].splitlines()) == {
        "${{ runner.temp }}/finex-owned-local-wire/s1-owned-proof.json",
        "${{ runner.temp }}/finex-owned-local-wire/s1-owned-corpus.json",
        "${{ runner.temp }}/finex-owned-local-wire/s2-saved-risk-proof.json",
        "${{ runner.temp }}/finex-owned-local-wire/s2-saved-risk-corpus.json",
        "${{ runner.temp }}/finex-owned-local-wire/s2-manual-portfolio-proof.json",
        "${{ runner.temp }}/finex-owned-local-wire/s2-manual-portfolio-corpus.json",
    }


def test_fixed_browser_probe_server_is_linted_tested_and_triggers_ci() -> None:
    for name in ("backend-quality.yml", "s1-uat-evidence.yml"):
        source = workflow(name)
        for trigger in ("push", "pull_request"):
            assert "scripts/serve-s1-web-probe.py" in source["on"][trigger]["paths"]
    quality = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    lint = next(step["run"] for step in quality if step.get("name") == "Ruff lint")
    formatting = next(step["run"] for step in quality if step.get("name") == "Ruff format check")
    assert "../scripts/serve-s1-web-probe.py" in lint
    assert "../scripts/serve-s1-web-probe.py" in formatting
    native = workflow("s1-uat-evidence.yml")["jobs"]["owned-native"]["steps"]
    assert any("test_s1_web_probe_server.py" in step.get("run", "") for step in native)
