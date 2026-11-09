"""CI must exercise the saved application API, not substitute pilot proof."""

from tests.unit.test_s1_ci_contract import workflow


def test_release_evidence_requires_native_saved_risk_and_owned_contract_tests() -> None:
    steps = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]["steps"]
    native = [step for step in steps if "verify_s2_saved_risk.py" in step.get("run", "")]
    assert len(native) == 1, "Release evidence currently omits the saved-risk native API"
    assert "--tested-sha" in native[0]["run"] and "--tested-tree" in native[0]["run"]
    assert '--report "$FINEX_EVIDENCE_DIR/s2-saved-risk-proof.json"' in native[0]["run"]
    assert "continue-on-error" not in native[0] and "if" not in native[0]
    commands = "\n".join(step.get("run", "") for step in steps)
    for filename in (
        "test_local_s2_risk_api.py",
        "test_local_s2_risk_transport.py",
        "test_s2_saved_risk_harness.py",
    ):
        assert filename in commands
    uploads = [step for step in steps if "actions/upload-artifact@" in step.get("uses", "")]
    assert len(uploads) == 1
    assert (
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-saved-risk-proof.json"
        in uploads[0]["with"]["path"].splitlines()
    )
    assert "state.sqlite3" not in uploads[0]["with"]["path"]


def test_release_outputs_do_not_dirty_the_verified_source_checkout() -> None:
    job = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]
    assert "FINEX_EVIDENCE_DIR" not in job.get("env", {})
    steps = job["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert 'mkdir -p "$evidence_directory"' in commands
    for filename in (
        "s2-data-quality.json",
        "s2-risk-evaluation.json",
        "s2-saved-risk-proof.json",
        "r0-secret-snapshot.json",
        "s2-evaluation-tests.xml",
    ):
        assert f'"$FINEX_EVIDENCE_DIR/{filename}"' in commands
    assert "--junitxml=s2-evaluation-tests.xml" not in commands
    assert "--report s2-saved-risk-proof.json" not in commands


def test_release_summary_and_upload_use_only_the_owned_safe_report_directory() -> None:
    steps = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]["steps"]
    summary = next(step["run"] for step in steps if step.get("name") == "Provenance summary")
    assert '"$FINEX_EVIDENCE_DIR/$report"' in summary
    upload = next(step for step in steps if "actions/upload-artifact@" in step.get("uses", ""))
    assert upload["with"]["path"].splitlines() == [
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-data-quality.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-risk-evaluation.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-saved-risk-proof.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-saved-risk-corpus.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-manual-portfolio-proof.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-manual-portfolio-corpus.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/r0-secret-snapshot.json",
        "${{ runner.temp }}/finex-r0-s2-evidence/s2-evaluation-tests.xml",
    ]
    assert upload.get("if") == "always()"


def test_runner_directory_is_bound_only_after_the_job_has_started() -> None:
    job = workflow("r0-s2-release-evidence.yml")["jobs"]["evidence"]
    assert all("runner." not in str(value) for value in job.get("env", {}).values())
    steps = job["steps"]
    setup_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Create owned evidence directory outside the source checkout"
    )
    setup = steps[setup_index]["run"]
    assert 'evidence_directory="$RUNNER_TEMP/finex-r0-s2-evidence"' in setup
    assert 'mkdir -p "$evidence_directory"' in setup
    assert 'echo "FINEX_EVIDENCE_DIR=$evidence_directory" >> "$GITHUB_ENV"' in setup
    assert "if" not in steps[setup_index] and "continue-on-error" not in steps[setup_index]
    first_writer = next(
        index for index, step in enumerate(steps) if "$FINEX_EVIDENCE_DIR/" in step.get("run", "")
    )
    assert setup_index < first_writer


def test_saved_risk_native_driver_is_typed_on_both_ci_platforms() -> None:
    steps = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Mypy type check")
    checks = [line for line in command.splitlines() if "python -m mypy" in line]
    assert len(checks) == 2
    assert all("verify_s2_saved_risk.py" in line for line in checks)
    assert {line.split("--platform ")[1].split()[0] for line in checks} == {"linux", "win32"}
