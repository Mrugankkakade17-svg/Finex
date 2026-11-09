"""Full S2 acceptance needs current native evidence on both typed consumers."""

import pytest

from tests.unit.test_s1_ci_contract import workflow


@pytest.mark.parametrize("name", ["s1-uat-evidence.yml", "r0-s2-release-evidence.yml"])
def test_native_s2_ci_explicitly_configures_repository_import_root(name: str) -> None:
    job_name = "owned-native" if name == "s1-uat-evidence.yml" else "evidence"
    job = workflow(name)["jobs"][job_name]
    assert job["defaults"]["run"]["working-directory"] == "backend"
    assert job.get("env", {}).get("PYTHONPATH") == "..", (
        "Direct native S2 commands import the repository's ai package; pytest's "
        "pythonpath configuration does not carry into a new Python CLI process."
    )
    for step in job["steps"]:
        if "verify_s2_" in step.get("run", ""):
            assert "PYTHONPATH" not in step.get("env", {})


@pytest.mark.parametrize("name", ["frontend-react-quality.yml", "frontend-flutter-quality.yml"])
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_s2_acceptance_evidence_triggers_both_complete_client_quality_gates(
    name: str, event: str
) -> None:
    paths = workflow(name)["on"][event]["paths"]
    assert "docs/evidence/s2-full-acceptance.md" in paths, (
        "An acceptance correction must run complete client quality checks at its "
        "new head; successful jobs from the previous head cannot accept it."
    )


def test_owned_native_ci_captures_all_three_slices_outside_the_checkout() -> None:
    job = workflow("s1-uat-evidence.yml")["jobs"]["owned-native"]
    steps = job["steps"]
    setup = [
        (index, step)
        for index, step in enumerate(steps)
        if step.get("name") == "Create owned evidence directory outside the source checkout"
    ]
    assert len(setup) == 1, "S1/S2 shared artifacts must not dirty the verified checkout."
    assert '"$RUNNER_TEMP/finex-owned-local-wire"' in setup[0][1]["run"]
    for driver, prefix in (
        ("verify_s1_application.py", "s1-owned"),
        ("verify_s2_saved_risk.py", "s2-saved-risk"),
        ("verify_s2_manual_portfolio.py", "s2-manual-portfolio"),
    ):
        native = [(i, s) for i, s in enumerate(steps) if driver in s.get("run", "")]
        assert len(native) == 1, f"Missing mandatory actual native driver: {driver}"
        index, step = native[0]
        assert setup[0][0] < index
        assert "if" not in step and "continue-on-error" not in step
        command = step["run"]
        assert f'--report "$FINEX_OWNED_EVIDENCE_DIR/{prefix}-proof.json"' in command
        assert f'--corpus "$FINEX_OWNED_EVIDENCE_DIR/{prefix}-corpus.json"' in command
        assert '--tested-sha "$GITHUB_SHA"' in command
        assert "--tested-tree \"$(git rev-parse 'HEAD^{tree}')\"" in command
        assert "set -euo pipefail" in command
    assert int(job["timeout-minutes"]) <= 8
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "test_owned_s2_acceptance_launcher.py" in commands
    assert "test_owned_s2_acceptance_ci.py" in commands


def test_ci_passively_validates_the_complete_pair_before_artifact_upload() -> None:
    steps = workflow("s1-uat-evidence.yml")["jobs"]["owned-native"]["steps"]
    guards = [
        (i, s) for i, s in enumerate(steps) if "verify_s2_evidence_pair.py" in s.get("run", "")
    ]
    assert len(guards) == 1, "Native producer exit zero is not a complete pair validation."
    index, guard = guards[0]
    assert "if" not in guard and "continue-on-error" not in guard
    for driver in (
        "verify_s1_application.py",
        "verify_s2_saved_risk.py",
        "verify_s2_manual_portfolio.py",
    ):
        assert next(i for i, s in enumerate(steps) if driver in s.get("run", "")) < index
    assert index < next(
        i for i, s in enumerate(steps) if "actions/upload-artifact@" in s.get("uses", "")
    )
    command = guard["run"]
    for option, filename in (
        ("risk-report", "s2-saved-risk-proof.json"),
        ("risk-corpus", "s2-saved-risk-corpus.json"),
        ("portfolio-report", "s2-manual-portfolio-proof.json"),
        ("portfolio-corpus", "s2-manual-portfolio-corpus.json"),
    ):
        assert f'--{option} "$FINEX_OWNED_EVIDENCE_DIR/{filename}"' in command
    assert '--tested-sha "$GITHUB_SHA"' in command
    assert "--tested-tree \"$(git rev-parse 'HEAD^{tree}')\"" in command
    assert "set -euo pipefail" in command


@pytest.mark.parametrize("name", ["react-journey", "flutter-journey"])
def test_both_clients_require_complete_current_s2_artifact_pairs(name: str) -> None:
    job = workflow("s1-uat-evidence.yml")["jobs"][name]
    assert "owned-native" in job["needs"]
    parity = [
        step
        for step in job["steps"]
        if step.get("env", {}).get("FINEX_REQUIRE_LOCAL_S2_CORPUS") == "1"
    ]
    assert len(parity) == 1, "A green S1 client gate is not full S2 wire parity."
    step = parity[0]
    assert "if" not in step and "continue-on-error" not in step
    assert step["env"]["FINEX_REQUIRE_LOCAL_S1_CORPUS"] == "1"
    for option, filename in (
        ("FINEX_LOCAL_S2_RISK_CORPUS", "s2-saved-risk-corpus.json"),
        ("FINEX_LOCAL_S2_RISK_REPORT", "s2-saved-risk-proof.json"),
        ("FINEX_LOCAL_S2_PORTFOLIO_CORPUS", "s2-manual-portfolio-corpus.json"),
        ("FINEX_LOCAL_S2_PORTFOLIO_REPORT", "s2-manual-portfolio-proof.json"),
    ):
        assert step["env"][option] == "${{ runner.temp }}/finex-owned-local-wire/" + filename
    command = step["run"]
    expected_tests = (
        ("localS1ContractParity.test.ts", "localS2NativeParity.test.ts")
        if name == "react-journey"
        else (
            "local_contract_parity_test.dart",
            "local_s2_risk_contract_parity_test.dart",
            "local_s2_portfolio_contract_parity_test.dart",
        )
    )
    assert all(test in command for test in expected_tests)


def test_s2_artifact_retention_is_exact_success_only_six_file_allowlist() -> None:
    steps = workflow("s1-uat-evidence.yml")["jobs"]["owned-native"]["steps"]
    uploads = [s for s in steps if "actions/upload-artifact@" in s.get("uses", "")]
    assert len(uploads) == 1
    upload = uploads[0]
    assert "if" not in upload and "continue-on-error" not in upload
    assert upload["with"]["if-no-files-found"] == "error"
    assert int(upload["with"]["retention-days"]) <= 7
    assert set(upload["with"]["path"].splitlines()) == {
        "${{ runner.temp }}/finex-owned-local-wire/" + filename
        for filename in (
            "s1-owned-proof.json",
            "s1-owned-corpus.json",
            "s2-saved-risk-proof.json",
            "s2-saved-risk-corpus.json",
            "s2-manual-portfolio-proof.json",
            "s2-manual-portfolio-corpus.json",
        )
    }


def test_s2_summary_distinguishes_native_decoder_parity_from_external_acceptance() -> None:
    job = workflow("s1-uat-evidence.yml")["jobs"]["summary"]
    assert {"owned-native", "react-journey", "flutter-journey"} <= set(job["needs"])
    command = "\n".join(s.get("run", "") for s in job["steps"])
    assert "saved risk" in command and "manual portfolio" in command
    assert "not human UAT" in command and "native-device" in command
    assert "GITHUB_SHA" in command and "CANDIDATE_HEAD" in command


def test_s2_launcher_and_handoff_changes_trigger_existing_quality_gates() -> None:
    for name in ("backend-quality.yml", "s1-uat-evidence.yml"):
        document = workflow(name)
        for event in ("push", "pull_request"):
            paths = document["on"][event]["paths"]
            assert "scripts/verify-owned-s2.ps1" in paths
            assert "docs/evidence/s2-full-acceptance.md" in paths
    typed = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    command = next(s["run"] for s in typed if s.get("name") == "Mypy type check")
    checks = [line for line in command.splitlines() if "python -m mypy" in line]
    assert len(checks) == 2
    assert all("local_s2_evidence.py" in line for line in checks)
    assert all("verify_s2_saved_risk.py" in line for line in checks)
    assert all("verify_s2_manual_portfolio.py" in line for line in checks)
    assert all("verify_s2_evidence_pair.py" in line for line in checks)


def test_release_evidence_requires_saved_risk_corpus_and_retains_exact_safe_file() -> None:
    steps = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]["steps"]
    native = [s for s in steps if "verify_s2_saved_risk.py" in s.get("run", "")]
    assert len(native) == 1
    assert '--corpus "$FINEX_EVIDENCE_DIR/s2-saved-risk-corpus.json"' in native[0]["run"]
    assert "if" not in native[0] and "continue-on-error" not in native[0]
    upload = next(s for s in steps if "actions/upload-artifact@" in s.get("uses", ""))
    assert "${{ runner.temp }}/finex-r0-s2-evidence/s2-saved-risk-corpus.json" in (
        upload["with"]["path"].splitlines()
    )


def test_approved_dev_checkpoint_keeps_native_release_evidence_mandatory() -> None:
    document = workflow("r0-s2-release-evidence.yml")
    assert set(document["on"]["push"]["branches"]) == {
        "feature/**",
        "release/**",
        "dev",
    }, "A completed dev checkpoint must run the same native/secret evidence workflow."
    assert "pull_request" in document["on"]
    assert document["permissions"] == {"contents": "read"}
    evidence = document["jobs"]["evidence"]
    assert "if" not in evidence and "continue-on-error" not in evidence
    for verifier in (
        "verify_s2_saved_risk.py",
        "verify_s2_manual_portfolio.py",
        "verify_secret_snapshot.py",
    ):
        steps = [s for s in evidence["steps"] if verifier in s.get("run", "")]
        assert len(steps) == 1
        assert "if" not in steps[0] and "continue-on-error" not in steps[0]
