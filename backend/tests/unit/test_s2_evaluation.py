"""Tests-first release evaluation must fail closed, without reporting raw answers."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from verify_s2_risk import build_client_pack, evaluate_release


def test_all_golden_cases_and_both_client_assets_pass() -> None:
    report = evaluate_release(tested_sha="a" * 40)
    assert report["status"] == "PASS"
    assert report["tested_commit_sha"] == "a" * 40
    assert report["counts"] == {"valid": 9, "invalid": 7, "total": 16}
    assert len(report["cases"]) == 16
    assert all(row["domain"] and row["api"] for row in report["cases"])
    assert set(report["client_assets"]) == {"react", "flutter"}
    assert '"answers"' not in json.dumps(report)
    assert '"answer_code"' not in json.dumps(report)


@pytest.mark.parametrize("client", ["react", "flutter"])
def test_client_score_version_and_disclosure_drift_fails(client: str) -> None:
    for field, value in [("composite_score", 99), ("scoring_version", "v999")]:
        pack = build_client_pack()
        pack["cases"][0]["response"]["assessment"][field] = value
        report = evaluate_release(client_packs={client: pack})
        assert report["status"] == "FAIL"
        assert report["client_assets"][client] is False
    pack = build_client_pack()
    pack["cases"][0]["response"]["explanation"]["limitation"] = "Advice omitted"
    assert evaluate_release(client_packs={client: pack})["status"] == "FAIL"


def test_expected_value_is_independent_from_scorer() -> None:
    from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider

    fixtures = deepcopy(S2Dat01FixtureProvider().list_fixtures())
    fixtures[0]["expected"]["composite_score"] = 99
    report = evaluate_release(fixtures=fixtures)
    assert report["status"] == "FAIL"
    assert report["cases"][0]["domain"] is False
    assert report["cases"][0]["api"] is False


def test_unsafe_generated_explanation_fails_without_echoing_it() -> None:
    def unsafe(result: dict) -> dict:
        from ai.risk.contract import educational_explanation

        value = educational_explanation(result)
        value["summary"] = "You should buy a specific security."
        return value

    report = evaluate_release(explainer=unsafe)
    assert report["status"] == "FAIL"
    assert any(row["safety"] is False for row in report["cases"])
    assert "specific security" not in json.dumps(report)


def test_missing_client_asset_is_a_failure_not_an_implicit_pass(tmp_path: Path) -> None:
    report = evaluate_release(client_paths={"react": tmp_path / "missing.json"})
    assert report["status"] == "FAIL"
    assert report["client_assets"]["react"] is False


def test_report_rejects_untrusted_commit_label() -> None:
    with pytest.raises(ValueError, match="commit SHA"):
        evaluate_release(tested_sha="private input")


def test_cli_probe_really_exits_nonzero(monkeypatch, capsys) -> None:
    from verify_s2_risk import main

    monkeypatch.setattr("sys.argv", ["verify_s2_risk.py", "--probe-invalid-client"])
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"
