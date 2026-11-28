"""Integration and contract tests for S3-LI02 goals CRUD, contributions, and progress."""

from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.config.settings import Settings
from app.main import create_app
from app.repositories.goal_repo import GoalRepository
from app.routers import goals as goals_router
from app.services.goal_service import GoalService


def _auth_headers(user_id: str) -> dict[str, str]:
    token = create_access_token({"sub": user_id, "user_id": user_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def goal_api_client(tmp_path: Path) -> Generator[tuple[TestClient, Path], None, None]:
    db_path = tmp_path / "s3-li02-goals.sqlite3"
    repository = GoalRepository(db_path)
    repository.settings = Settings(app_persistence="sqlite", local_db_path=db_path)

    original_service = goals_router.goal_service
    goals_router.goal_service = GoalService(repository)
    application = create_app(Settings(app_persistence="sqlite", local_db_path=db_path))
    try:
        with TestClient(application) as client:
            yield client, db_path
    finally:
        goals_router.goal_service = original_service


def test_new_goal_endpoints_require_authentication(
    goal_api_client: tuple[TestClient, Path],
) -> None:
    client, _ = goal_api_client
    for method, path, kwargs in (
        ("PUT", "/api/v1/goals/goal-1", {"json": {"title": "Updated"}}),
        ("DELETE", "/api/v1/goals/goal-1", {}),
        ("POST", "/api/v1/goals/goal-1/contributions", {"json": {"amount": 100}}),
        ("GET", "/api/v1/goals/goal-1/contributions", {}),
        ("GET", "/api/v1/goals/goal-1/progress", {}),
    ):
        response = client.request(method, path, **kwargs)
        assert response.status_code == 401


def test_goals_contributions_progress_crud_and_user_isolation(
    goal_api_client: tuple[TestClient, Path],
) -> None:
    client, db_path = goal_api_client
    user_a = _auth_headers("s3-li02-user-a")
    user_b = _auth_headers("s3-li02-user-b")

    # 1. Create a zero-return goal with explicit target_date
    created = client.post(
        "/api/v1/goals",
        headers=user_a,
        json={
            "title": "Laptop Fund",
            "target_amount": 1200,
            "current_amount": 0,
            "horizon_years": 1,
            "monthly_contribution": 50,
            "expected_annual_return_pct": 0,
            "target_date": "2027-11-28",
        },
    )
    assert created.status_code == 200
    created_data = created.json()["data"]
    goal_id = created_data["goal_id"]
    assert created_data["target_date"] == "2027-11-28"
    assert Decimal(created_data["projected_final_amount"]) == Decimal("600.00")

    # 2. Empty contributions state and initial progress check with as_of_date
    empty_contribs = client.get(f"/api/v1/goals/{goal_id}/contributions", headers=user_a)
    assert empty_contribs.status_code == 200
    assert empty_contribs.json()["data"] == []

    initial_progress = client.get(
        f"/api/v1/goals/{goal_id}/progress",
        params={"as_of_date": "2026-11-28"},
        headers=user_a,
    )
    assert initial_progress.status_code == 200
    progress_data = initial_progress.json()["data"]
    assert progress_data["months_remaining"] == 12
    assert Decimal(progress_data["required_monthly_contribution"]) == Decimal("100.00")
    assert Decimal(progress_data["monthly_contribution_gap"]) == Decimal("50.00")
    assert progress_data["is_on_track"] is False

    # 3. Record contribution and verify updated balance, projections, and progress
    contrib = client.post(
        f"/api/v1/goals/{goal_id}/contributions",
        headers=user_a,
        json={
            "amount": "600.00",
            "contribution_date": "2026-11-28",
            "note": "Initial bonus deposit",
        },
    )
    assert contrib.status_code == 200
    contrib_data = contrib.json()["data"]
    assert Decimal(contrib_data["goal"]["current_amount"]) == Decimal("600.00")
    assert Decimal(contrib_data["goal"]["projected_final_amount"]) == Decimal("1200.00")
    assert contrib_data["goal"]["is_on_track"] is True
    assert Decimal(contrib_data["progress"]["progress_pct"]) == Decimal("50.00")
    assert Decimal(contrib_data["progress"]["total_contributed"]) == Decimal("600.00")
    assert Decimal(contrib_data["progress"]["required_monthly_contribution"]) == Decimal("50.00")
    assert contrib_data["progress"]["is_on_track"] is True

    # 4. Cross-user isolation: user B gets 404 on every endpoint for user A's goal
    assert client.get(f"/api/v1/goals/{goal_id}/contributions", headers=user_b).status_code == 404
    assert client.get(f"/api/v1/goals/{goal_id}/progress", headers=user_b).status_code == 404
    assert (
        client.post(
            f"/api/v1/goals/{goal_id}/contributions",
            headers=user_b,
            json={"amount": 100, "contribution_date": "2026-11-28"},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/goals/{goal_id}",
            headers=user_b,
            json={"title": "Hijacked"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/goals/{goal_id}", headers=user_b).status_code == 404

    # 5. Update goal (PUT) and verify persistence across repository reload
    updated = client.put(
        f"/api/v1/goals/{goal_id}",
        headers=user_a,
        json={"title": "Updated Laptop Fund", "target_date": None},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "Updated Laptop Fund"
    assert updated.json()["data"]["target_date"] is None

    reloaded_repo = GoalRepository(db_path)
    reloaded_repo.settings = Settings(app_persistence="sqlite", local_db_path=db_path)
    reloaded_service = GoalService(reloaded_repo)
    assert reloaded_service.get_goal("s3-li02-user-a", goal_id) is not None
    assert len(reloaded_service.list_contributions("s3-li02-user-a", goal_id) or []) == 1

    # 6. Edge-date validation & query behavior (same-day, overdue, invalid leap date)
    same_day = client.get(
        f"/api/v1/goals/{goal_id}/progress",
        params={"as_of_date": "2027-11-28"},
        headers=user_a,
    )
    assert same_day.status_code == 200
    assert same_day.json()["data"]["months_remaining"] == 12  # target_date was cleared to None

    # Create a leap-day target goal to test edge-date progress over HTTP
    leap_goal = client.post(
        "/api/v1/goals",
        headers=user_a,
        json={
            "title": "Leap Reserve",
            "target_amount": 4800,
            "current_amount": 0,
            "horizon_years": 4,
            "monthly_contribution": 100,
            "expected_annual_return_pct": 0,
            "target_date": "2028-02-29",
        },
    )
    assert leap_goal.status_code == 200
    leap_id = leap_goal.json()["data"]["goal_id"]
    assert all(
        Decimal(p["growth_total"]) == Decimal("0.00")
        for p in leap_goal.json()["data"]["projections"]
    )
    leap_progress = client.get(
        f"/api/v1/goals/{leap_id}/progress",
        params={"as_of_date": "2024-02-29"},
        headers=user_a,
    )
    assert leap_progress.status_code == 200
    assert leap_progress.json()["data"]["months_remaining"] == 48
    assert Decimal(leap_progress.json()["data"]["required_monthly_contribution"]) == Decimal(
        "100.00"
    )

    overdue_progress = client.get(
        f"/api/v1/goals/{leap_id}/progress",
        params={"as_of_date": "2028-03-01"},
        headers=user_a,
    )
    assert overdue_progress.status_code == 200
    assert overdue_progress.json()["data"]["months_remaining"] == 0
    assert overdue_progress.json()["data"]["is_overdue"] is True
    assert overdue_progress.json()["data"]["required_monthly_contribution"] is None

    invalid_as_of = client.get(
        f"/api/v1/goals/{leap_id}/progress",
        params={"as_of_date": "2026-02-29"},
        headers=user_a,
    )
    assert invalid_as_of.status_code == 422

    bad_contrib = client.post(
        f"/api/v1/goals/{goal_id}/contributions",
        headers=user_a,
        json={"amount": -10, "contribution_date": "2026-11-28"},
    )
    assert bad_contrib.status_code == 422

    empty_put = client.put(f"/api/v1/goals/{goal_id}", headers=user_a, json={})
    assert empty_put.status_code == 422

    # 7. Delete goal and confirm 404 afterwards
    deleted = client.delete(f"/api/v1/goals/{goal_id}", headers=user_a)
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"goal_id": goal_id, "deleted": True}
    assert client.get(f"/api/v1/goals/{goal_id}", headers=user_a).status_code == 404
    assert client.get(f"/api/v1/goals/{goal_id}/progress", headers=user_a).status_code == 404
