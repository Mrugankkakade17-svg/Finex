"""Reproducible, non-networked release gate for #144 and R0 contract coverage.

Golden expectations are independent of the scorer. HTTP uses an in-process
local API, and both clients' published assets must equal the canonical replay.
Reports include outcomes and provenance, never submitted answers or credentials.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from ai.risk.contract import (
    CONTRACT_VERSION,
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    RiskContractError,
    educational_explanation,
    evaluate_risk_contract,
)
from fastapi.testclient import TestClient

from app.config.settings import AppEnv, Settings
from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider
from app.main import create_app

ROOT = Path(__file__).resolve().parent.parent
STAMP = "2026-10-10T00:00:00Z"
CLIENT_PATHS = {
    "react": ROOT / "frontend-react/src/data/s2RiskFixtures.v1.json",
    "flutter": ROOT / "frontend_flutter/assets/s2_risk_fixtures.v1.json",
}
SCORE_FIELDS = ("willingness_score", "capacity_score", "composite_score", "risk_category")
UNSAFE_EXPLANATION = re.compile(
    r"\b(you should|buy|sell|allocate|guaranteed(?: returns?)?)\b", re.IGNORECASE
)


def _client() -> TestClient:
    # Pydantic's runtime settings options are not constructor fields in its stub.
    options: dict[str, Any] = {"app_env": AppEnv.LOCAL, "_env_file": None}
    return TestClient(create_app(Settings(**options)))


def build_client_pack() -> dict[str, Any]:
    """Build replay data; do not silently overwrite either client asset."""
    with _client() as client:
        questionnaire = client.get("/api/v1/risk-contract/questionnaire").json()["data"]
    cases = []
    for fixture in S2Dat01FixtureProvider().list_fixtures():
        row = {key: deepcopy(fixture[key]) for key in ("case_id", "title", "request")}
        try:
            result = evaluate_risk_contract(fixture["request"], calculated_at=STAMP)
            row["response"] = {
                "assessment": result,
                "explanation": educational_explanation(result),
                "scope": "local_educational_pilot",
                "persisted": False,
            }
        except RiskContractError as error:
            row["error_code"] = error.code
        cases.append(row)
    return {
        "schema_version": "s2-client-fixtures/v1",
        "synthetic": True,
        "contract_version": CONTRACT_VERSION,
        "questionnaire": questionnaire,
        "cases": cases,
    }


def _numeric_match(result: dict[str, Any], expected: dict[str, Any]) -> bool:
    if any(result.get(field) != expected[field] for field in SCORE_FIELDS):
        return False
    if result.get("limitation", {}).get("code") != expected["limitation_code"]:
        return False
    tension = expected.get("informational_tension_code")
    return tension is None or result.get("informational_tension", {}).get("code") == tension


def _safe(result: dict[str, Any], explanation: dict[str, Any]) -> bool:
    if (
        result.get("contract_version") != CONTRACT_VERSION
        or result.get("questionnaire_id") != "risk_questionnaire_v1"
        or result.get("questionnaire_version") != "v1"
        or result.get("scoring_version") != "deterministic_v1.0.0"
        or result.get("limitation") != {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE}
        or explanation.get("limitation") != LIMITATION_MESSAGE
    ):
        return False
    if any(
        explanation.get(field) != result.get(field)
        for field in ("questionnaire_version", "scoring_version", "calculated_at")
    ):
        return False
    for field in ("summary", "dimensions", "method"):
        text = explanation.get(field)
        if not isinstance(text, str) or not text or UNSAFE_EXPLANATION.search(text):
            return False
    return True


def evaluate_release(
    *,
    tested_sha: str | None = None,
    fixtures: list[dict[str, Any]] | None = None,
    client_packs: dict[str, dict[str, Any]] | None = None,
    client_paths: dict[str, Path] | None = None,
    explainer: Callable[[dict[str, Any]], dict[str, Any]] = educational_explanation,
) -> dict[str, Any]:
    if tested_sha is not None and not re.fullmatch(r"[0-9a-f]{40}", tested_sha):
        raise ValueError("Use an exact lowercase 40-character commit SHA")
    fixtures = S2Dat01FixtureProvider().list_fixtures() if fixtures is None else fixtures
    outcomes = []
    with _client() as client:
        for fixture in fixtures:
            row = {
                "case_id": fixture["case_id"],
                "coverage": fixture["coverage"],
                "kind": fixture["kind"],
                "domain": False,
                "api": False,
                "safety": False,
                "determinism": False,
            }
            try:
                result = evaluate_risk_contract(fixture["request"], calculated_at=STAMP)
                row["domain"] = fixture["kind"] == "valid" and _numeric_match(
                    result, fixture["expected"]
                )
                row["safety"] = _safe(result, explainer(result))
                reordered = deepcopy(fixture["request"])
                reordered["answers"].reverse()
                row["determinism"] = result == evaluate_risk_contract(
                    reordered, calculated_at=STAMP
                )
            except RiskContractError as error:
                row["domain"] = (
                    fixture["kind"] == "invalid" and error.code == fixture["expected"]["error_code"]
                )
                row["safety"] = row["domain"]
                row["determinism"] = row["domain"]
            response = client.post(
                "/api/v1/risk-contract/assessments",
                json=fixture["request"],
                headers={"X-Correlation-ID": "s2-release-evidence"},
            )
            body = response.json()
            if fixture["kind"] == "invalid":
                row["api"] = (
                    response.status_code in (400, 422)
                    and body.get("error", {}).get("code") == fixture["expected"]["error_code"]
                    and "answer_code" not in response.text
                    and "data" not in body
                )
            elif response.status_code == 200:
                data, meta = body["data"], body["meta"]
                assessment = data["assessment"]
                row["api"] = (
                    _numeric_match(assessment, fixture["expected"])
                    and _safe(assessment, data["explanation"])
                    and data["scope"] == "local_educational_pilot"
                    and data["persisted"] is False
                    and meta["apiVersion"] == "v1"
                    and meta["dataAsOf"] == assessment["calculated_at"]
                    and meta["correlationId"] == "s2-release-evidence"
                )
            outcomes.append(row)
    canonical = build_client_pack()
    client_results = {}
    for name, path in {**CLIENT_PATHS, **(client_paths or {})}.items():
        try:
            pack = (client_packs or {}).get(name)
            if pack is None:
                pack = json.loads(path.read_text(encoding="utf-8"))
            client_results[name] = pack == canonical
        except (OSError, ValueError):
            client_results[name] = False
    passed = (
        len(outcomes) == 16
        and all(
            all(row[key] for key in ("domain", "api", "safety", "determinism")) for row in outcomes
        )
        and all(client_results.values())
    )
    return {
        "schema_version": "s2-risk-evaluation/v1",
        "status": "PASS" if passed else "FAIL",
        "tested_commit_sha": tested_sha,
        "contract_version": CONTRACT_VERSION,
        "questionnaire_version": "v1",
        "scoring_version": "deterministic_v1.0.0",
        "execution_mode": "native_in_process_local_api_no_network",
        "counts": {
            "valid": sum(row["kind"] == "valid" for row in outcomes),
            "invalid": sum(row["kind"] == "invalid" for row in outcomes),
            "total": len(outcomes),
        },
        "client_assets": client_results,
        "cases": outcomes,
        "promotion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tested-sha")
    parser.add_argument("--probe-invalid-client", action="store_true")
    args = parser.parse_args()
    if args.probe_invalid_client:
        probe = build_client_pack()
        probe["cases"][0]["response"]["assessment"]["scoring_version"] = "invalid-red-probe"
        report = evaluate_release(tested_sha=args.tested_sha, client_packs={"react": probe})
    else:
        report = evaluate_release(tested_sha=args.tested_sha)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
