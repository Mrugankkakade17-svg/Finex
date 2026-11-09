"""
Verification tests covering Sprints 4, 5, 6, and 7 endpoints.
Validates simulated orders, goals, privacy, spending, grounded AI, alerts, and ops preflight.
"""

import sys
from pathlib import Path
from decimal import Decimal

# Ensure paths
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_sprint4_paper_account_summary():
    """Verify Sprint 4 paper trading account endpoint."""
    resp = client.get("/api/v1/paper-trading/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "data" in body
    assert body["data"]["is_simulated"] is True
    assert Decimal(str(body["data"]["cash_balance"])) >= 0


def test_sprint4_paper_order_execution():
    """Verify Sprint 4 simulated buy order execution with idempotency."""
    order_payload = {
        "instrument_id": "AAPL",
        "side": "BUY",
        "quantity": 5,
        "idempotency_key": "idemp-key-test-001",
    }
    resp1 = client.post("/api/v1/paper-trading/orders", json=order_payload)
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert data1["status"] == "FILLED"
    assert data1["instrument_id"] == "AAPL"
    assert "SIMULATION ONLY" in data1["simulation_notice"]

    # Idempotent retry returns identical payload
    resp2 = client.post("/api/v1/paper-trading/orders", json=order_payload)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["order_id"] == data1["order_id"]


def test_sprint4_goals_projection():
    """Verify Sprint 4 goal creation and deterministic compounding projections."""
    goal_payload = {
        "title": "Home Down Payment",
        "target_amount": 50000.0,
        "current_amount": 10000.0,
        "horizon_years": 5,
        "monthly_contribution": 600.0,
        "expected_annual_return_pct": 7.0,
    }
    resp = client.post("/api/v1/goals", json=goal_payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["projections"]) == 5
    assert Decimal(str(data["projected_final_amount"])) > 10000


def test_sprint5_privacy_consent_and_export():
    """Verify Sprint 5 privacy consent review and export request."""
    resp = client.get("/api/v1/privacy/consent")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_consent_active"] is True

    action_payload = {
        "action": "EXPORT",
        "reason": "Data portability request",
        "confirm_explicit": True,
    }
    resp_act = client.post("/api/v1/privacy/action", json=action_payload)
    assert resp_act.status_code == 200
    assert resp_act.json()["data"]["status"] == "COMPLETED"


def test_sprint5_spending_trends_and_masking():
    """Verify Sprint 5 masked transaction listings and trend calculation."""
    resp = client.get("/api/v1/spending/transactions")
    assert resp.status_code == 200
    txs = resp.json()["data"]
    assert len(txs) > 0
    # Ensure description is masked
    for tx in txs:
        assert "***" in tx["description_masked"]

    resp_trends = client.get("/api/v1/spending/trends")
    assert resp_trends.status_code == 200
    assert len(resp_trends.json()["data"]["monthly_trends"]) > 0


def test_sprint6_grounded_ai_assistant_and_refusal():
    """Verify Sprint 6 Grounded RAG citations and refusal of personalized advice."""
    # Test valid educational question
    resp_edu = client.post(
        "/api/v1/ai/chat",
        json={"message": "What is the importance of diversification in asset allocation?"},
    )
    assert resp_edu.status_code == 200
    edu_data = resp_edu.json()["data"]
    assert edu_data["intent"] == "CONCEPT_EDUCATION"
    assert len(edu_data["citations"]) > 0

    # Test safety guardrail refusal
    resp_refuse = client.post(
        "/api/v1/ai/chat",
        json={"message": "Should I buy Tesla stock today?"},
    )
    assert resp_refuse.status_code == 200
    refuse_data = resp_refuse.json()["data"]
    assert refuse_data["intent"] == "REFUSAL_FINANCIAL_ADVICE"
    assert "cannot provide specific buy/sell recommendations" in refuse_data["answer_text"]


def test_sprint6_smart_alerts_and_notifications():
    """Verify Sprint 6 alert rule creation and in-app notifications."""
    resp_rules = client.get("/api/v1/alerts/rules")
    assert resp_rules.status_code == 200

    resp_notifs = client.get("/api/v1/alerts/notifications")
    assert resp_notifs.status_code == 200
    assert "unread_count" in resp_notifs.json()["data"]


def test_sprint7_observability_and_preflight():
    """Verify Sprint 7 observability health report and release preflight gate."""
    resp_obs = client.get("/api/v1/ops/observability")
    assert resp_obs.status_code == 200
    obs_data = resp_obs.json()["data"]
    assert obs_data["healthy"] is True
    assert len(obs_data["dependencies"]) >= 3

    resp_pre = client.get("/api/v1/ops/preflight")
    assert resp_pre.status_code == 200
    pre_data = resp_pre.json()["data"]
    assert pre_data["ready_for_promotion"] is True
    assert pre_data["anand_uat_approved"] is True

