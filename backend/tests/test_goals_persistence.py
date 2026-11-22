from decimal import Decimal

from fastapi.testclient import TestClient

from app.auth.principal import Principal, get_current_principal
from app.main import create_app
from app.repositories.goal_repo import GoalRepository
from app.schemas.sprint4_paper_goals import GoalCreateRequest
from app.services.goal_service import GoalService


def test_goal_repository_isolates_users_and_persists(tmp_path) -> None:
    repository = GoalRepository(tmp_path / "goals.sqlite3")
    service = GoalService(repository)
    request = GoalCreateRequest(
        title="Emergency Fund",
        target_amount=Decimal("5000"),
        current_amount=Decimal("1000"),
        horizon_years=5,
        monthly_contribution=Decimal("100"),
        expected_annual_return_pct=Decimal("6"),
    )

    goal_a = service.create_goal("user-a", request)
    service.create_goal("user-b", request.model_copy(update={"title": "User B Goal"}))

    restarted = GoalService(GoalRepository(tmp_path / "goals.sqlite3"))
    assert restarted.get_goal("user-a", goal_a.goal_id) is not None
    assert restarted.get_goal("user-b", goal_a.goal_id) is None
    assert [goal.title for goal in restarted.list_goals("user-a")] == ["Emergency Fund"]
    assert [goal.title for goal in restarted.list_goals("user-b")] == ["User B Goal"]


def test_goals_api_is_scoped_to_authenticated_principal(tmp_path) -> None:
    app = create_app()
    repository = GoalRepository(tmp_path / "api-goals.sqlite3")

    from app.routers import goals

    original_service = goals.goal_service
    goals.goal_service = GoalService(repository)
    try:
        client = TestClient(app)
        app.dependency_overrides[get_current_principal] = lambda: Principal(
            user_id="user-a",
            is_synthetic=True,
        )
        created = client.post(
            "/api/v1/goals",
            json={
                "title": "Emergency Fund",
                "target_amount": 5000,
                "current_amount": 1000,
                "horizon_years": 5,
                "monthly_contribution": 100,
                "expected_annual_return_pct": 6,
            },
        )
        assert created.status_code == 200
        goal_id = created.json()["data"]["goal_id"]

        app.dependency_overrides[get_current_principal] = lambda: Principal(
            user_id="user-b",
            is_synthetic=True,
        )
        assert client.get("/api/v1/goals").json()["data"] == []
        assert client.get(f"/api/v1/goals/{goal_id}").status_code == 404
    finally:
        goals.goal_service = original_service
        app.dependency_overrides.clear()
