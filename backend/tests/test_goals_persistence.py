import os
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

import app.repositories.goal_repo as goal_repo_module
from app.auth.principal import Principal, get_current_principal
from app.config.settings import Settings
from app.main import create_app
from app.ports.adapters.postgres_local_store import postgres_dsn
from app.repositories.goal_repo import GoalRepository
from app.schemas.sprint4_paper_goals import GoalCreateRequest
from app.services.goal_service import GoalService


def test_goal_repository_selects_installed_psycopg_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        app_persistence="postgresql",
        app_database_url="postgresql+asyncpg://localhost/finex_test",
    )
    monkeypatch.setattr(goal_repo_module, "get_settings", lambda: settings)
    engine = GoalRepository()._postgres_engine()
    try:
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


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


@pytest.mark.postgres
def test_goal_repository_persists_through_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    load_dotenv()
    database_url = os.getenv("APP_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("APP_DATABASE_URL or DATABASE_URL is required for PostgreSQL coverage")

    monkeypatch.setenv("APP_PERSISTENCE", "postgresql")
    settings = Settings(app_persistence="postgresql", app_database_url=database_url)
    monkeypatch.setattr(goal_repo_module, "get_settings", lambda: settings)
    repository = GoalRepository()
    service = GoalService(repository)
    user_id = str(uuid4())
    with psycopg.connect(postgres_dsn(database_url)) as connection:
        connection.execute(
            """
            INSERT INTO finex.users (user_id, email, password_hash, name)
            VALUES (%s, %s, 'test-hash', 'Goal persistence test')
            """,
            (user_id, f"{user_id}@example.test"),
        )

    try:
        request = GoalCreateRequest(
            title="PostgreSQL Emergency Fund",
            target_amount=Decimal("5000"),
            current_amount=Decimal("1000"),
            horizon_years=5,
            monthly_contribution=Decimal("100"),
            expected_annual_return_pct=Decimal("6"),
        )
        created = service.create_goal(user_id, request)
        assert repository.get_goal(user_id, created.goal_id) == created
        assert repository.list_goals(user_id) == [created]
    finally:
        with psycopg.connect(postgres_dsn(database_url)) as connection:
            connection.execute("DELETE FROM finex.users WHERE user_id=%s", (user_id,))
