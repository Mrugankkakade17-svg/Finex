"""PostgreSQL contract test for S3-LI02 goal_contributions and goals.target_date."""

import os
import uuid
from datetime import date
from decimal import Decimal

import psycopg
import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import app.repositories.goal_repo as goal_repo_module
from app.config.settings import Settings
from app.ports.adapters.postgres_local_store import postgres_dsn
from app.repositories.goal_repo import GoalRepository
from app.schemas.sprint4_paper_goals import (
    GoalContributionCreateRequest,
    GoalCreateRequest,
    GoalUpdateRequest,
)
from app.services.goal_service import GoalService

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_s3_li02_goal_contributions_constraints_and_cascade(postgres_db) -> None:
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            user_a = str(uuid.uuid4())
            user_b = str(uuid.uuid4())
            for user_id in (user_a, user_b):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.users (user_id, email, password_hash, name)
                        VALUES (:user_id, :email, 'test-hash', 's3-li02 test')
                        """
                    ),
                    {"user_id": user_id, "email": f"{user_id}@example.test"},
                )

            await connection.execute(
                text(
                    """
                    INSERT INTO finex.goals (
                        user_id, goal_id, title, target_amount, current_amount,
                        horizon_years, monthly_contribution, expected_annual_return_pct,
                        projected_final_amount, shortfall_or_surplus, is_on_track,
                        assumptions_statement, target_date
                    ) VALUES (
                        :user_id, 'goal-a', 'Emergency', 5000, 1000, 2, 100, 0,
                        3400, -1600, false, 'Deterministic test', '2028-02-29'
                    )
                    """
                ),
                {"user_id": user_a},
            )

            await connection.execute(
                text(
                    """
                    INSERT INTO finex.goal_contributions (
                        user_id, goal_id, contribution_id, amount, contribution_date, note
                    ) VALUES (
                        :user_id, 'goal-a', 'contrib-1', 250.50, '2026-11-28', 'Deposit'
                    )
                    """
                ),
                {"user_id": user_a},
            )

            # Reject cross-user contribution referencing another user's goal
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.goal_contributions (
                                user_id, goal_id, contribution_id, amount, contribution_date
                            ) VALUES (
                                :user_id, 'goal-a', 'contrib-cross', 100.00, '2026-11-28'
                            )
                            """
                        ),
                        {"user_id": user_b},
                    )

            # Reject non-positive contribution amount
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.goal_contributions (
                                user_id, goal_id, contribution_id, amount, contribution_date
                            ) VALUES (
                                :user_id, 'goal-a', 'contrib-zero', 0, '2026-11-28'
                            )
                            """
                        ),
                        {"user_id": user_a},
                    )

            await connection.execute(
                text("DELETE FROM finex.goals WHERE user_id = :user_id AND goal_id = 'goal-a'"),
                {"user_id": user_a},
            )
            remaining = await connection.execute(
                text("SELECT count(*) FROM finex.goal_contributions WHERE user_id = :user_id"),
                {"user_id": user_a},
            )
            assert remaining.scalar_one() == 0
        finally:
            await transaction.rollback()


def test_s3_li02_goal_service_roundtrip_on_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    load_dotenv()
    database_url = os.getenv("APP_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("APP_DATABASE_URL or DATABASE_URL is required for PostgreSQL coverage")

    settings = Settings(app_persistence="postgresql", app_database_url=database_url)
    monkeypatch.setattr(goal_repo_module, "get_settings", lambda: settings)
    repository = GoalRepository()
    service = GoalService(repository)
    user_id = str(uuid.uuid4())
    with psycopg.connect(postgres_dsn(database_url)) as connection:
        connection.execute(
            """
            INSERT INTO finex.users (user_id, email, password_hash, name)
            VALUES (%s, %s, 'test-hash', 's3-li02 service postgres test')
            """,
            (user_id, f"{user_id}@example.test"),
        )

    try:
        created = service.create_goal(
            user_id,
            GoalCreateRequest(
                title="Postgres Goal",
                target_amount=Decimal("2400.00"),
                current_amount=Decimal("0.00"),
                horizon_years=1,
                monthly_contribution=Decimal("100.00"),
                expected_annual_return_pct=Decimal("0.0"),
                target_date=date(2027, 11, 28),
            ),
        )
        recorded = service.record_contribution(
            user_id,
            created.goal_id,
            GoalContributionCreateRequest(
                amount=Decimal("1200.00"),
                contribution_date=date(2026, 11, 28),
                note="Halfway deposit",
            ),
            as_of_date=date(2026, 11, 28),
        )
        assert recorded is not None
        assert recorded.progress.required_monthly_contribution == Decimal("100.00")
        assert len(service.list_contributions(user_id, created.goal_id) or []) == 1

        updated = service.update_goal(
            user_id,
            created.goal_id,
            GoalUpdateRequest(title="Updated Postgres Goal"),
        )
        assert updated is not None
        assert updated.title == "Updated Postgres Goal"
        assert service.delete_goal(user_id, created.goal_id) is True
        assert service.get_goal(user_id, created.goal_id) is None
    finally:
        with psycopg.connect(postgres_dsn(database_url)) as connection:
            connection.execute("DELETE FROM finex.users WHERE user_id=%s", (user_id,))
