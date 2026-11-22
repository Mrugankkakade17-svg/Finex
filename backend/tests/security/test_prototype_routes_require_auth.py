"""Security test probe for prototype routes and demo endpoints.

AUTHORITATIVE REQUIREMENT:
Task ID: S0-LI02 (Issue #15)
Acceptance criterion: "One xfail per route now, pass after S1."

These tests verify that unauthenticated requests to the seven prototype routers
and demo router are rejected with HTTP 401 Unauthorized or HTTP 403 Forbidden.
In Sprint 0, authentication is not yet wired to these routers, producing expected
xfails. In Sprint 1, once authentication dependencies are attached, these tests
transition cleanly to pass.
"""

from decimal import Decimal
from typing import Any, Generator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.routers import alerts, goals

client = TestClient(app)

SEED_GOAL_ID = "seed-goal-001"
SEED_RULE_ID = "rule-del-001"

PROTOTYPE_ROUTES: list[tuple[str, str, str, dict[str, Any]]] = [
    # Router 1: Goals (app.routers.goals) - 3 endpoints
    (
        "goals",
        "POST",
        "/api/v1/goals",
        {
            "json": {
                "title": "Emergency Fund",
                "target_amount": 5000.0,
                "current_amount": 1000.0,
                "horizon_years": 5,
                "monthly_contribution": 100.0,
                "expected_annual_return_pct": 6.0,
            }
        },
    ),
    ("goals", "GET", "/api/v1/goals", {}),
    ("goals", "GET", f"/api/v1/goals/{SEED_GOAL_ID}", {}),
    # Router 2: Spending (app.routers.spending) - 3 endpoints
    ("spending", "GET", "/api/v1/spending/transactions", {}),
    (
        "spending",
        "POST",
        "/api/v1/spending/correct-category",
        {"json": {"transaction_id": "tx-001", "corrected_category": "Dining"}},
    ),
    ("spending", "GET", "/api/v1/spending/trends", {}),
    # Router 3: Alerts (app.routers.alerts) - 5 endpoints
    ("alerts", "GET", "/api/v1/alerts/rules", {}),
    (
        "alerts",
        "POST",
        "/api/v1/alerts/rules",
        {
            "json": {
                "rule_name": "High Spend Alert",
                "condition_type": "PRICE_THRESHOLD",
                "target_symbol_or_goal": "AAPL",
                "comparison_operator": "GT",
                "threshold_value": 250.0,
                "cooldown_minutes": 60,
            }
        },
    ),
    ("alerts", "DELETE", f"/api/v1/alerts/rules/{SEED_RULE_ID}", {}),
    ("alerts", "GET", "/api/v1/alerts/notifications", {}),
    ("alerts", "POST", "/api/v1/alerts/notifications/notif-001/read", {}),
    # Router 4: Ops Hardening (app.routers.ops_hardening) - 4 endpoints
    ("ops_hardening", "GET", "/api/v1/ops/observability", {}),
    ("ops_hardening", "GET", "/api/v1/ops/flags", {}),
    (
        "ops_hardening",
        "POST",
        "/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle",
        {"params": {"enabled": "true"}},
    ),
    ("ops_hardening", "GET", "/api/v1/ops/preflight", {}),
    # Router 5: Release Handover (app.routers.release_handover) - 5 endpoints
    ("release_handover", "GET", "/api/v1/release/manifest", {}),
    ("release_handover", "GET", "/api/v1/release/uat-signoffs", {}),
    (
        "release_handover",
        "POST",
        "/api/v1/release/uat-signoffs",
        {
            "json": {
                "stakeholder_name": "Test Signer",
                "role": "QA Lead",
                "decision": "APPROVED",
                "comments": "Sprint signoff verified",
                "checklist_verified": True,
            }
        },
    ),
    ("release_handover", "GET", "/api/v1/release/dr-drill", {}),
    ("release_handover", "GET", "/api/v1/release/handover", {}),
    # Router 6: Privacy (app.routers.privacy) - 2 endpoints
    ("privacy", "GET", "/api/v1/privacy/consent", {}),
    (
        "privacy",
        "POST",
        "/api/v1/privacy/action",
        {"json": {"action": "EXPORT", "confirm_explicit": True}},
    ),
    # Router 7: AI Assistant (app.routers.ai_assistant) - 2 endpoints
    ("ai_assistant", "POST", "/api/v1/ai/chat", {"json": {"message": "What is asset allocation?"}}),
    (
        "ai_assistant",
        "POST",
        "/api/v1/ai/feedback",
        {"json": {"message_id": "msg-001", "rating": "THUMBS_UP"}},
    ),
    # Demo Router (app.routers.demo) - 2 endpoints
    ("demo", "GET", "/api/v1/demo/error", {}),
    ("demo", "GET", "/api/v1/demo/error500", {}),
]


@pytest.fixture(autouse=True)
def setup_probe_resources() -> Generator[None, None, None]:
    """Seed prerequisite test resources so requests reach intended route handlers."""
    # Seed a goal for GET /api/v1/goals/{goal_id}
    goals._goals_db[SEED_GOAL_ID] = goals.GoalResponse(
        goal_id=SEED_GOAL_ID,
        title="Seed Goal",
        target_amount=Decimal("10000.00"),
        current_amount=Decimal("1000.00"),
        horizon_years=5,
        monthly_contribution=Decimal("150.00"),
        expected_annual_return_pct=Decimal("6.0"),
        projected_final_amount=Decimal("12000.00"),
        shortfall_or_surplus=Decimal("2000.00"),
        is_on_track=True,
        assumptions_statement="Deterministic test seed.",
        projections=[],
    )

    # Seed an alert rule in persistent storage for DELETE /api/v1/alerts/rules/{rule_id}.
    alerts.alert_repository.delete_rule("auth-probe-user", SEED_RULE_ID)
    alerts.alert_repository.create_rule(
        "auth-probe-user",
        alerts.AlertRule(
            rule_id=SEED_RULE_ID,
            rule_name="Rule to delete",
            condition_type="PRICE_THRESHOLD",
            target_symbol_or_goal="AAPL",
            comparison_operator="GT",
            threshold_value=200.0,
            cooldown_minutes=60,
            is_active=True,
            created_at="2026-10-01T12:00:00Z",
        ),
    )

    yield

    # Clean up seeded resources
    goals._goals_db.pop(SEED_GOAL_ID, None)
    alerts.alert_repository.delete_rule("auth-probe-user", SEED_RULE_ID)


# SPRINT 0 AUTH PROBE & SPRINT 1 TRANSITION:
# Routes secured under Sprint 1 (e.g. S1-MR05: Ops, Release, Privacy) now strictly enforce
# authentication and pass cleanly. Routes not yet migrated retain xfail(strict=False).
SECURED_ROUTERS_S1 = {
    "spending",
    "alerts",
    "ops_hardening",
    "release_handover",
    "privacy",
}


def _build_test_params() -> list[Any]:
    params = []
    for router, method, path, kwargs in PROTOTYPE_ROUTES:
        param_id = f"{router}_{method}_{path}"
        if router in SECURED_ROUTERS_S1:
            params.append(pytest.param(router, method, path, kwargs, id=param_id))
        else:
            params.append(
                pytest.param(
                    router,
                    method,
                    path,
                    kwargs,
                    id=param_id,
                    marks=pytest.mark.xfail(
                        strict=False,
                        reason="Route not yet enforced; will pass in subsequent Sprint 1 tasks",
                    ),
                )
            )
    return params


@pytest.mark.parametrize(
    ("router_name", "method", "path", "request_kwargs"),
    _build_test_params(),
)
def test_prototype_routes_require_auth(
    router_name: str,
    method: str,
    path: str,
    request_kwargs: dict[str, Any],
) -> None:
    """Verify that unauthenticated requests to prototype endpoints are rejected with 401 or 403.

    Sprint 0 Note:
        Endpoints currently allow unauthenticated access and return 200/201/400/500,
        causing this assertion to fail as an expected failure (XFAIL).

    Sprint 1 Transition Note:
        When authentication protection is implemented in Sprint 1, each endpoint will
        reject unauthenticated calls with HTTP 401/403. Because `strict=False` is set,
        pytest may report XPASS until the xfail marker is removed. As part of Sprint 1
        authentication delivery, the xfail marker must be removed so all tests report
        standard PASSED results, while maintaining the strict 401/403 assertion.
    """
    response = client.request(method=method, url=path, **request_kwargs)
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ), (
        f"Expected HTTP 401 or 403 for unauthenticated access to {path}, "
        f"got HTTP {response.status_code}"
    )
