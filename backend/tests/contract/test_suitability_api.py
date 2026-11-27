"""Contract and user-isolation tests for FinEx Suitability Engine API (S3-LI01)."""

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.main import create_app
from app.schemas.portfolio import PortfolioCreate, PortfolioType
from app.services.portfolio_service import portfolio_service


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_suitability_endpoints_appear_in_openapi_schema(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})
    assert "/api/v1/suitability/allocation" in paths
    assert "/api/v1/suitability/allocation/{risk_category}" in paths
    assert "/api/v1/suitability/rebalance" in paths


def test_get_target_allocation_by_category(client: TestClient) -> None:
    response = client.get("/api/v1/suitability/allocation/MODERATE")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Target allocation retrieved successfully"
    data = body["data"]
    assert data["risk_category"] == "MODERATE"
    assert data["model_code"] == "MODERATE_V1"
    assert data["invariants_satisfied"] is True
    assert len(data["allocations"]) == 3


def test_post_target_allocation_with_questionnaire(client: TestClient) -> None:
    answers = [{"question_id": f"W{i}", "answer_code": f"W{i}_E"} for i in range(1, 6)] + [
        {"question_id": f"C{i}", "answer_code": f"C{i}_E"} for i in range(1, 6)
    ]
    response = client.post(
        "/api/v1/suitability/allocation",
        json={"questionnaire_answers": answers},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["risk_category"] == "AGGRESSIVE"
    assert data["model_code"] == "AGGRESSIVE_V1"


def test_target_allocation_invalid_category_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suitability/allocation",
        json={"risk_category": "UNKNOWN_CATEGORY"},
    )
    assert response.status_code == 400


def test_rebalance_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/suitability/rebalance",
        json={"risk_category": "MODERATE", "current_allocation": []},
    )
    assert response.status_code in (401, 403)


def test_rebalance_endpoint_authenticated_with_custom_allocation(client: TestClient) -> None:
    token = create_access_token({"sub": "suit-user", "user_id": "suit-user"})
    response = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "risk_category": "CONSERVATIVE",
            "current_allocation": [
                {"asset_class": "EQUITY", "weight": 0.50},
                {"asset_class": "FIXED_INCOME", "weight": 0.30},
                {"asset_class": "CASH", "weight": 0.20},
            ],
            "portfolio_value": 100000.0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Suitability rebalance plan generated successfully"
    data = body["data"]
    assert data["risk_category"] == "CONSERVATIVE"
    assert data["rebalance_required"] is True
    assert len(data["rebalance_plan"]) == 3


@pytest.mark.asyncio
async def test_rebalance_user_isolation_between_distinct_users(client: TestClient) -> None:
    """Verify strict user isolation: User B cannot access or rebalance User A's portfolio."""
    token_user_a = create_access_token({"sub": "user-a", "user_id": "user-a"})
    token_user_b = create_access_token({"sub": "user-b", "user_id": "user-b"})

    # 1. Create portfolio for User A
    portfolio_a = await portfolio_service.create_portfolio(
        "user-a",
        PortfolioCreate(
            name="User A Retirement",
            description="User A individual retirement portfolio",
            portfolio_type=PortfolioType.INDIVIDUAL,
            currency="USD",
        ),
    )
    portfolio_id_a = portfolio_a.portfolio_id

    # 2. User A evaluates rebalance for User A's portfolio -> 200 OK
    resp_a = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token_user_a}"},
        json={"portfolio_id": portfolio_id_a, "risk_category": "MODERATE"},
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["portfolio_id"] == portfolio_id_a
    assert resp_a.json()["data"]["is_empty_portfolio"] is True

    # 3. User B attempts to access User A's portfolio -> 404 PORTFOLIO_NOT_FOUND
    resp_b = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token_user_b}"},
        json={"portfolio_id": portfolio_id_a, "risk_category": "MODERATE"},
    )
    assert resp_b.status_code == 404
    assert resp_b.json()["error_code"] == "PORTFOLIO_NOT_FOUND"


def test_rebalance_endpoint_duplicate_asset_class_returns_400(client: TestClient) -> None:
    token = create_access_token({"sub": "user-test", "user_id": "user-test"})
    response = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "risk_category": "MODERATE",
            "current_allocation": [
                {"asset_class": "EQUITY", "weight": 0.50},
                {"asset_class": "EQUITY", "weight": 0.50},
            ],
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "DUPLICATE_ASSET_CLASS"
    assert "Duplicate asset class 'EQUITY'" in body["message"]


def test_rebalance_endpoint_incomplete_allocation_total_returns_400(client: TestClient) -> None:
    token = create_access_token({"sub": "user-test", "user_id": "user-test"})
    # Custom allocation totaling 80% (0.80) must be rejected
    response = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "risk_category": "MODERATE",
            "current_allocation": [
                {"asset_class": "EQUITY", "weight": 0.50},
                {"asset_class": "FIXED_INCOME", "weight": 0.30},
            ],
            "portfolio_value": 100000.0,
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_ALLOCATION_TOTAL"
    assert "must sum to 1.0" in body["message"]


def test_rebalance_endpoint_excess_allocation_total_returns_400(client: TestClient) -> None:
    token = create_access_token({"sub": "user-test", "user_id": "user-test"})
    # Custom allocation totaling 120% must be rejected
    response = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "risk_category": "MODERATE",
            "current_allocation": [
                {"asset_class": "EQUITY", "weight": 60.0},
                {"asset_class": "FIXED_INCOME", "weight": 40.0},
                {"asset_class": "CASH", "weight": 20.0},
            ],
            "portfolio_value": 100000.0,
        },
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_ALLOCATION_TOTAL"
    assert "must equal 100%" in body["message"]


def test_rebalance_endpoint_boundary_allocations_normalized_and_conserved(
    client: TestClient,
) -> None:
    token = create_access_token({"sub": "user-test", "user_id": "user-test"})
    # Lower boundary 99.9% allocation (50% + 30% + 19.9%)
    response = client.post(
        "/api/v1/suitability/rebalance",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "risk_category": "MODERATE",
            "current_allocation": [
                {"asset_class": "EQUITY", "weight": 50.0},
                {"asset_class": "FIXED_INCOME", "weight": 30.0},
                {"asset_class": "CASH", "weight": 19.9},
            ],
            "portfolio_value": 150000.55,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    # Check normalized current weights sum to exactly 1.000000
    w_sum = sum(float(item["current_weight"]) for item in data["drift_summary"])
    assert round(w_sum, 6) == 1.000000
    # Check drift sum equals exactly zero
    drift_sum = sum(float(item["drift"]) for item in data["drift_summary"])
    assert round(drift_sum, 6) == 0.000000
    # Check adjustment weight sum equals exactly zero
    adj_sum = sum(float(item["adjustment_weight"]) for item in data["rebalance_plan"])
    assert round(adj_sum, 6) == 0.000000
    # Check monetary adjustments conserve portfolio value (sum == 0.00)
    amt_sum = sum(
        float(item["indicative_amount"])
        for item in data["rebalance_plan"]
        if item["indicative_amount"] is not None
    )
    assert round(amt_sum, 2) == 0.00
