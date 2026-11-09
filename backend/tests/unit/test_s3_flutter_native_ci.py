"""Flutter S3 consumes successful original same-run native evidence."""

from tests.unit.test_s1_ci_contract import ROOT, workflow


def flutter_job():
    return workflow("s1-uat-evidence.yml")["jobs"]["flutter-journey"]


def test_flutter_waits_for_both_successful_native_producers() -> None:
    assert set(flutter_job()["needs"]) == {"owned-native", "owned-s3-native"}


def test_flutter_downloads_s3_original_wire_separately_from_s1_s2() -> None:
    downloads = [
        step
        for step in flutter_job()["steps"]
        if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert len(downloads) == 2
    assert {step["with"]["name"] for step in downloads} == {
        "owned-s1-s2-wire-${{ github.run_id }}",
        "owned-s3-wire-${{ github.run_id }}",
    }
    step = next(step for step in downloads if step["with"]["name"].startswith("owned-s3-"))
    assert step["with"]["path"] == "${{ runner.temp }}/finex-owned-s3-wire"
    assert "if" not in step and "continue-on-error" not in step


def test_flutter_requires_current_original_s3_pair_without_optional_skip() -> None:
    steps = flutter_job()["steps"]
    matches = [
        (index, step)
        for index, step in enumerate(steps)
        if "test/local_s3_contract_parity_test.dart" in step.get("run", "")
    ]
    assert len(matches) == 1
    index, step = matches[0]
    assert "test/local_s3_corpus_loader_test.dart" in step["run"]
    assert "--no-pub" in step["run"] and "--concurrency=1" in step["run"]
    assert step["env"]["FINEX_REQUIRE_LOCAL_S3_CORPUS"] == "1"
    assert step["env"]["FINEX_LOCAL_S3_CORPUS"] == (
        "${{ runner.temp }}/finex-owned-s3-wire/s3-foundation-corpus.json"
    )
    assert step["env"]["FINEX_LOCAL_S3_REPORT"] == (
        "${{ runner.temp }}/finex-owned-s3-wire/s3-foundation-proof.json"
    )
    assert "if" not in step and "continue-on-error" not in step
    assert any(
        previous.get("with", {}).get("name") == "owned-s3-wire-${{ github.run_id }}"
        for previous in steps[:index]
    )


def test_s3_native_job_requires_the_flutter_wiring_guard() -> None:
    steps = workflow("s1-uat-evidence.yml")["jobs"]["owned-s3-native"]["steps"]
    assert "tests/unit/test_s3_flutter_native_ci.py" in "\n".join(
        step.get("run", "") for step in steps
    )


def test_summary_identifies_flutter_replay_without_claiming_full_s3() -> None:
    steps = workflow("s1-uat-evidence.yml")["jobs"]["summary"]["steps"]
    text = "\n".join(step.get("run", "") for step in steps)
    assert "Flutter S3 typed parity with original native response bytes: passed" in text
    assert "Full S3 acceptance and controlled provider-fault journeys remain separate" in text
    assert "not human UAT" in text and "native-device GUI" in text


def test_native_consumer_and_loader_exist_before_publication() -> None:
    for name in ("local_s3_contract_parity_test.dart", "local_s3_corpus_loader_test.dart"):
        assert (ROOT / "frontend_flutter/test" / name).is_file()


def test_s1_s2_required_flutter_parity_is_preserved() -> None:
    step = next(
        step
        for step in flutter_job()["steps"]
        if "test/local_s2_portfolio_contract_parity_test.dart" in step.get("run", "")
    )
    assert "test/local_contract_parity_test.dart" in step["run"]
    assert step["env"]["FINEX_REQUIRE_LOCAL_S1_CORPUS"] == "1"
    assert step["env"]["FINEX_REQUIRE_LOCAL_S2_CORPUS"] == "1"


def test_react_cannot_require_a_missing_s3_consumer() -> None:
    consumer = "src/services/localS3ContractParity.test.ts"
    job = workflow("s1-uat-evidence.yml")["jobs"]["react-journey"]
    if not (ROOT / "frontend-react" / consumer).is_file():
        assert "owned-s3-native" not in job["needs"]
        assert consumer not in "\n".join(step.get("run", "") for step in job["steps"])
        assert not any(
            key.startswith("FINEX_LOCAL_S3_") or key == "FINEX_REQUIRE_LOCAL_S3_CORPUS"
            for step in job["steps"]
            for key in step.get("env", {})
        )
    else:
        steps = [step for step in job["steps"] if consumer in step.get("run", "")]
        assert len(steps) == 1 and "owned-s3-native" in job["needs"]
        assert steps[0]["env"]["FINEX_REQUIRE_LOCAL_S3_CORPUS"] == "1"


def test_no_optional_or_paid_external_service_bypass_is_added() -> None:
    job = flutter_job()
    assert "if" not in job and "continue-on-error" not in job
    assert "services" not in job and "container" not in job
    for step in job["steps"]:
        assert "if" not in step and "continue-on-error" not in step
        assert "secrets." not in str(step)
