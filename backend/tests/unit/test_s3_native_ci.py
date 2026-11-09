"""S3 API evidence is mandatory and separate from S1/S2 client acceptance."""

import pytest

from tests.unit.test_s1_ci_contract import workflow


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_both_complete_type_targets_include_the_s3_producer_and_passive_guard(platform) -> None:
    steps = workflow("backend-quality.yml")["jobs"]["quality"]["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Mypy type check")
    lines = [line for line in command.splitlines() if f"--platform {platform}" in line]
    assert len(lines) == 1
    assert "verify_s3_foundation.py" in lines[0]
    assert "verify_s3_evidence.py" in lines[0]
    assert "--python-version 3.13" in lines[0]


def native_steps():
    jobs = workflow("s1-uat-evidence.yml")["jobs"]
    assert "owned-s3-native" in jobs, "S3 API acceptance needs actual S3 native TCP proof."
    return jobs["owned-s3-native"]["steps"]


def test_s3_native_job_preserves_earlier_gates_and_runs_without_paid_or_external_services() -> None:
    source = workflow("s1-uat-evidence.yml")
    assert source["permissions"] == {"contents": "read"}
    assert "owned-s3-native" in source["jobs"]
    job = source["jobs"]["owned-s3-native"]
    assert job["needs"] == ["owned-native"]
    assert job["runs-on"] == "ubuntu-latest"
    assert int(job["timeout-minutes"]) <= 8
    assert job["env"] == {"PYTHONPATH": ".."}
    assert job["defaults"]["run"]["working-directory"] == "backend"
    assert "if" not in job and "continue-on-error" not in job
    assert "services" not in job and "container" not in job
    for step in job["steps"]:
        assert "if" not in step and "continue-on-error" not in step
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] == "false"
        assert "secrets." not in str(step)


def test_s3_native_producer_and_passive_guard_bind_the_same_actual_checkout_in_order() -> None:
    steps = native_steps()
    setup = next(
        i for i, step in enumerate(steps) if "FINEX_S3_EVIDENCE_DIR=" in step.get("run", "")
    )
    assert '"$RUNNER_TEMP/finex-owned-s3-wire"' in steps[setup]["run"]
    guards = "\n".join(step.get("run", "") for step in steps)
    assert "test_verify_s3_foundation.py" in guards and "test_s3_native_ci.py" in guards
    selected = []
    for driver in ("verify_s3_foundation.py", "verify_s3_evidence.py"):
        matches = [
            (i, step)
            for i, step in enumerate(steps)
            if any(
                line.strip().startswith("python " + driver + " ")
                for line in step.get("run", "").splitlines()
            )
        ]
        assert len(matches) == 1
        index, step = matches[0]
        selected.append(index)
        assert setup < index
        assert "if" not in step and "continue-on-error" not in step
        assert "set -euo pipefail" in step["run"]
        assert '--report "$FINEX_S3_EVIDENCE_DIR/s3-foundation-proof.json"' in step["run"]
        assert '--corpus "$FINEX_S3_EVIDENCE_DIR/s3-foundation-corpus.json"' in step["run"]
        assert '--tested-sha "$GITHUB_SHA"' in step["run"]
        assert "--tested-tree \"$(git rev-parse 'HEAD^{tree}')\"" in step["run"]
    assert selected[0] < selected[1]
    assert selected[1] < next(
        i for i, step in enumerate(steps) if "actions/upload-artifact@" in step.get("uses", "")
    )


def test_s3_retains_only_the_successfully_validated_report_and_original_safe_wire_bytes() -> None:
    uploads = [
        step for step in native_steps() if "actions/upload-artifact@" in step.get("uses", "")
    ]
    assert len(uploads) == 1
    upload = uploads[0]
    assert "if" not in upload and "continue-on-error" not in upload
    assert upload["with"]["name"] == "owned-s3-wire-${{ github.run_id }}"
    assert upload["with"]["if-no-files-found"] == "error"
    assert int(upload["with"]["retention-days"]) <= 7
    assert set(upload["with"]["path"].splitlines()) == {
        "${{ runner.temp }}/finex-owned-s3-wire/s3-foundation-proof.json",
        "${{ runner.temp }}/finex-owned-s3-wire/s3-foundation-corpus.json",
    }


def test_summary_requires_s3_native_api_without_inventing_s3_client_or_human_acceptance() -> None:
    summary = workflow("s1-uat-evidence.yml")["jobs"]["summary"]
    assert {"owned-native", "owned-s3-native", "react-journey", "flutter-journey"} <= set(
        summary["needs"]
    )
    text = "\n".join(step.get("run", "") for step in summary["steps"])
    assert "S3 default synthetic API" in text
    assert "Full S3 acceptance and controlled provider-fault journeys remain separate" in text
    assert "not human UAT" in text and "native-device" in text


@pytest.mark.parametrize(
    "name",
    [
        "backend-quality.yml",
        "frontend-react-quality.yml",
        "frontend-flutter-quality.yml",
        "s1-uat-evidence.yml",
    ],
)
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_s3_api_evidence_changes_run_all_current_quality_gates(name: str, event: str) -> None:
    paths = workflow(name)["on"][event]["paths"]
    assert "docs/evidence/s3-api-validation.md" in paths
    assert "docs/evidence/s3-owned-flutter-validation.md" in paths
