"""Portfolio acceptance must execute, not merely mention a manual checklist."""

from tests.unit.test_s1_ci_contract import workflow


def test_portfolio_native_proof_is_mandatory_and_bound_to_actual_checkout() -> None:
    job = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]
    native = [
        step for step in job["steps"] if "verify_s2_manual_portfolio.py" in step.get("run", "")
    ]
    assert len(native) == 1, "The release gate has no actual owned portfolio TCP/restart proof"
    step = native[0]
    assert "if" not in step and "continue-on-error" not in step
    command = step["run"]
    assert "python verify_s2_manual_portfolio.py" in command
    assert '--report "$FINEX_EVIDENCE_DIR/s2-manual-portfolio-proof.json"' in command
    assert '--corpus "$FINEX_EVIDENCE_DIR/s2-manual-portfolio-corpus.json"' in command
    assert '--tested-sha "$GITHUB_SHA"' in command
    assert "--tested-tree \"$(git rev-parse 'HEAD^{tree}')\"" in command
    assert "set -euo pipefail" in command
    assert int(job["timeout-minutes"]) <= 20


def test_owned_portfolio_contract_and_fail_closed_harness_run_before_native_proof() -> None:
    steps = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]["steps"]
    controlled = [
        (index, step)
        for index, step in enumerate(steps)
        if "test_local_s2_portfolio_api.py" in step.get("run", "")
    ]
    assert len(controlled) == 1
    index, step = controlled[0]
    command = step["run"]
    assert "python -m pytest" in command
    assert "tests/contract/test_local_s2_portfolio_transport.py" in command
    assert "tests/unit/test_local_s2_portfolio_native_harness.py" in command
    assert "tests/unit/test_local_s2_portfolio_ci.py" in command
    assert "if" not in step and "continue-on-error" not in step
    native_index = next(
        index
        for index, step in enumerate(steps)
        if "verify_s2_manual_portfolio.py" in step.get("run", "")
    )
    assert index < native_index


def test_portfolio_native_is_typed_for_linux_and_windows_without_removing_existing_gates() -> None:
    steps = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Mypy type check")
    checks = [line for line in command.splitlines() if "python -m mypy" in line]
    assert len(checks) == 2
    assert all("verify_s2_manual_portfolio.py" in line for line in checks)
    assert all(
        "verify_s1_application.py" in line and "verify_s2_saved_risk.py" in line for line in checks
    )
    assert all("--python-version 3.13" in line for line in checks)
    assert {line.split("--platform ")[1].split()[0] for line in checks} == {"linux", "win32"}


def test_portfolio_report_retention_is_only_the_owned_sanitized_output() -> None:
    steps = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]["steps"]
    upload = next(step for step in steps if "actions/upload-artifact@" in step.get("uses", ""))
    paths = {line.strip() for line in upload["with"]["path"].splitlines() if line.strip()}
    assert "${{ runner.temp }}/finex-r0-s2-evidence/s2-manual-portfolio-proof.json" in paths
    assert "${{ runner.temp }}/finex-r0-s2-evidence/s2-manual-portfolio-corpus.json" in paths
    assert all("sqlite" not in path and "*.json" not in path and "**" not in path for path in paths)
    assert int(upload["with"]["retention-days"]) <= 14
    summary = next(step for step in steps if step.get("name") == "Provenance summary")
    assert "s2-manual-portfolio-proof.json" in summary["run"]
