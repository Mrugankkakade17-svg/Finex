"""Run the local R0 thin vertical-slice proof without a server or cloud dependency."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

# Running this file from ``backend`` must also expose repository-level packages
# such as ``ai`` that the application composition root imports.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

EVIDENCE_SCHEMA_VERSION = "r0-int-01.local-proof.v1"
CORRELATION_ID = "r0-int-local-0001"
HEALTH_URL = "/api/v1/health"
CONSENT_URL = "/api/v1/onboarding-contract/consent"
PROFILE_URL = "/api/v1/onboarding-contract/profile"
COMPLETE_URL = "/api/v1/onboarding-contract/complete"


class ThinSliceVerificationError(RuntimeError):
    """Raised when the local R0 integration proof does not meet its contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ThinSliceVerificationError(message)


def _response_body(response: Any, expected_status: int) -> dict[str, Any]:
    _require(
        response.status_code == expected_status,
        f"Expected HTTP {expected_status}, received {response.status_code}",
    )
    body = response.json()
    _require(isinstance(body, dict), "API response must be a JSON object")
    _require(
        response.headers.get("x-correlation-id") == CORRELATION_ID,
        "API response did not preserve the correlation ID header",
    )
    return body


def _success_body(response: Any, expected_status: int) -> dict[str, Any]:
    body = _response_body(response, expected_status)
    _require(body.get("success") is True, "Expected a successful FinEx response envelope")
    _require(
        body.get("meta", {}).get("correlationId") == CORRELATION_ID,
        "Successful response did not preserve the correlation ID in its envelope",
    )
    return body


def _error_body(response: Any, expected_status: int) -> dict[str, Any]:
    body = _response_body(response, expected_status)
    _require(body.get("success") is False, "Expected a failed FinEx response envelope")
    _require(
        body.get("error", {}).get("correlationId") == CORRELATION_ID,
        "Error response did not preserve the correlation ID in its envelope",
    )
    return body


def _fixture_summary(provider_type: Any) -> dict[str, int]:
    provider = provider_type()
    first = provider.reset_and_seed()
    second = provider.reset_and_seed()
    _require(first == second, "Local fixture reset is not deterministic")
    records = first["records"]
    return {
        "synthetic_user_count": len(records["synthetic_users"]),
        "scenario_count": len(records["scenarios"]),
    }


def run_verification() -> dict[str, Any]:
    """Exercise the approved local consent/profile vertical slice and return safe evidence."""
    from app.fixtures.s1_dat_01 import S1Dat01FixtureProvider
    from app.main import app
    from app.schemas.consent_profile import (
        SUPPORTED_CONSENT_VERSION,
        SUPPORTED_PROFILE_SCHEMA_VERSION,
    )
    from app.services import consent_profile_service

    fixture_summary = _fixture_summary(S1Dat01FixtureProvider)
    headers = {"X-Correlation-ID": CORRELATION_ID}
    consent_profile_service._reset_stores()

    try:
        with TestClient(app) as client:
            health = _success_body(client.get(HEALTH_URL, headers=headers), 200)
            consent = _success_body(
                client.post(
                    CONSENT_URL,
                    headers=headers,
                    json={
                        "consent_version": SUPPORTED_CONSENT_VERSION,
                        "consent_given": True,
                    },
                ),
                201,
            )
            profile = _success_body(
                client.post(
                    PROFILE_URL,
                    headers=headers,
                    json={
                        "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
                        "display_name": "Local Test",
                        "experience_level": "beginner",
                    },
                ),
                201,
            )
            completed = _success_body(
                client.post(
                    COMPLETE_URL,
                    headers=headers,
                    json={
                        "consent_version": SUPPORTED_CONSENT_VERSION,
                        "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
                    },
                ),
                200,
            )
            safe_error = _error_body(
                client.post(
                    CONSENT_URL,
                    headers=headers,
                    json={"consent_version": "consent.v999", "consent_given": True},
                ),
                400,
            )
    finally:
        consent_profile_service._reset_stores()

    _require(health.get("data", {}).get("status") == "healthy", "Health check was not healthy")
    _require(
        consent.get("data", {}).get("consent_status") == "accepted",
        "Consent flow did not return accepted status",
    )
    _require(
        profile.get("data", {}).get("profile_state") == "completed",
        "Profile flow did not return completed state",
    )
    _require(
        completed.get("data", {}).get("onboarding_completed") is True,
        "Onboarding completion was not confirmed",
    )
    _require(
        safe_error.get("error_code") == "UNSUPPORTED_CONSENT_VERSION",
        "Invalid contract version did not return the safe expected error",
    )

    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "status": "passed",
        "correlation_id": CORRELATION_ID,
        "fixture_summary": fixture_summary,
        "success": {
            "health_status": "healthy",
            "consent_status": "accepted",
            "profile_state": "completed",
            "onboarding_completed": True,
        },
        "safe_error": {
            "status_code": 400,
            "error_code": "UNSUPPORTED_CONSENT_VERSION",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the local R0 thin vertical slice")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Render a human-readable result or a deterministic JSON evidence record",
    )
    args = parser.parse_args(argv)

    try:
        evidence = run_verification()
    except ThinSliceVerificationError as exc:
        if args.format == "json":
            print(
                json.dumps(
                    {
                        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                        "status": "failed",
                        "error": str(exc),
                    },
                    sort_keys=True,
                )
            )
            return 1
        print(f"R0 thin-slice verification failed: {exc}")
        return 1

    if args.format == "json":
        print(json.dumps(evidence, sort_keys=True))
        return 0

    print(
        "R0 thin-slice verification passed: "
        f"{evidence['fixture_summary']['synthetic_user_count']} synthetic users, "
        f"{evidence['fixture_summary']['scenario_count']} scenarios, "
        f"correlation {evidence['correlation_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
