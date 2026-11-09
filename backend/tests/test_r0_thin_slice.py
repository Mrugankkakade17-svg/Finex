import json

from verify_r0_thin_slice import main, run_verification


def test_r0_thin_slice_proves_a_repeatable_success_and_error_path():
    first = run_verification()
    second = run_verification()

    assert first == second
    assert first["evidence_schema_version"] == "r0-int-01.local-proof.v1"
    assert first["status"] == "passed"
    assert first["correlation_id"] == "r0-int-local-0001"
    assert first["fixture_summary"] == {
        "scenario_count": 5,
        "synthetic_user_count": 5,
    }
    assert first["success"] == {
        "consent_status": "accepted",
        "health_status": "healthy",
        "onboarding_completed": True,
        "profile_state": "completed",
    }
    assert first["safe_error"] == {
        "error_code": "UNSUPPORTED_CONSENT_VERSION",
        "status_code": 400,
    }


def test_r0_thin_slice_json_output_contains_no_profile_or_fixture_record_values(capsys):
    assert main(["--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    rendered = json.dumps(report, sort_keys=True)
    assert report["status"] == "passed"
    assert "display_name" not in rendered
    assert "profile_label" not in rendered
    assert "user_id" not in rendered
