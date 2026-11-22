"""Persistent, user-scoped goal repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config.settings import get_settings
from app.schemas.sprint4_paper_goals import GoalProjection, GoalResponse


class GoalRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.settings = get_settings()
        self.db_path = Path(db_path) if db_path is not None else self.settings.local_db_path

    @contextmanager
    def _sqlite_connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        self._ensure_sqlite_tables(connection)
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _ensure_sqlite_tables(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                title TEXT NOT NULL,
                target_amount TEXT NOT NULL,
                current_amount TEXT NOT NULL,
                horizon_years INTEGER NOT NULL,
                monthly_contribution TEXT NOT NULL,
                expected_annual_return_pct TEXT NOT NULL,
                projected_final_amount TEXT NOT NULL,
                shortfall_or_surplus TEXT NOT NULL,
                is_on_track INTEGER NOT NULL,
                assumptions_statement TEXT NOT NULL,
                PRIMARY KEY (user_id, goal_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_projections (
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                projected_balance TEXT NOT NULL,
                contributions_total TEXT NOT NULL,
                growth_total TEXT NOT NULL,
                PRIMARY KEY (user_id, goal_id, year),
                FOREIGN KEY (user_id, goal_id)
                    REFERENCES goals (user_id, goal_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_goals_user_id ON goals(user_id)"
        )
        connection.commit()

    @staticmethod
    def _goal_from_row(row: sqlite3.Row, projections: list[GoalProjection]) -> GoalResponse:
        return GoalResponse(
            goal_id=row["goal_id"],
            title=row["title"],
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            horizon_years=row["horizon_years"],
            monthly_contribution=row["monthly_contribution"],
            expected_annual_return_pct=row["expected_annual_return_pct"],
            projected_final_amount=row["projected_final_amount"],
            shortfall_or_surplus=row["shortfall_or_surplus"],
            is_on_track=bool(row["is_on_track"]),
            assumptions_statement=row["assumptions_statement"],
            projections=projections,
        )

    def create_goal(self, user_id: str, goal: GoalResponse) -> GoalResponse:
        if not user_id:
            raise ValueError("user_id is required")

        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
            engine = create_engine(sync_url)
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.goals (
                                user_id, goal_id, title, target_amount, current_amount,
                                horizon_years, monthly_contribution,
                                expected_annual_return_pct, projected_final_amount,
                                shortfall_or_surplus, is_on_track, assumptions_statement
                            ) VALUES (
                                :user_id, :goal_id, :title, :target_amount, :current_amount,
                                :horizon_years, :monthly_contribution,
                                :expected_annual_return_pct, :projected_final_amount,
                                :shortfall_or_surplus, :is_on_track, :assumptions_statement
                            )
                            """
                        ),
                        {
                            "user_id": user_id,
                            "goal_id": goal.goal_id,
                            "title": goal.title,
                            "target_amount": goal.target_amount,
                            "current_amount": goal.current_amount,
                            "horizon_years": goal.horizon_years,
                            "monthly_contribution": goal.monthly_contribution,
                            "expected_annual_return_pct": goal.expected_annual_return_pct,
                            "projected_final_amount": goal.projected_final_amount,
                            "shortfall_or_surplus": goal.shortfall_or_surplus,
                            "is_on_track": goal.is_on_track,
                            "assumptions_statement": goal.assumptions_statement,
                        },
                    )
                    for projection in goal.projections:
                        connection.execute(
                            text(
                                """
                                INSERT INTO finex.goal_projections (
                                    user_id, goal_id, year, projected_balance,
                                    contributions_total, growth_total
                                ) VALUES (
                                    :user_id, :goal_id, :year, :projected_balance,
                                    :contributions_total, :growth_total
                                )
                                """
                            ),
                            {
                                "user_id": user_id,
                                "goal_id": goal.goal_id,
                                "year": projection.year,
                                "projected_balance": projection.projected_balance,
                                "contributions_total": projection.contributions_total,
                                "growth_total": projection.growth_total,
                            },
                        )
            finally:
                engine.dispose()
            return goal

        with self._sqlite_connection() as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO goals (
                        user_id, goal_id, title, target_amount, current_amount,
                        horizon_years, monthly_contribution, expected_annual_return_pct,
                        projected_final_amount, shortfall_or_surplus, is_on_track,
                        assumptions_statement
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        goal.goal_id,
                        goal.title,
                        str(goal.target_amount),
                        str(goal.current_amount),
                        goal.horizon_years,
                        str(goal.monthly_contribution),
                        str(goal.expected_annual_return_pct),
                        str(goal.projected_final_amount),
                        str(goal.shortfall_or_surplus),
                        int(goal.is_on_track),
                        goal.assumptions_statement,
                    ),
                )
                for projection in goal.projections:
                    connection.execute(
                        """
                        INSERT INTO goal_projections (
                            user_id, goal_id, year, projected_balance,
                            contributions_total, growth_total
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            goal.goal_id,
                            projection.year,
                            str(projection.projected_balance),
                            str(projection.contributions_total),
                            str(projection.growth_total),
                        ),
                    )
        return goal

    def list_goals(self, user_id: str) -> list[GoalResponse]:
        if not user_id:
            return []

        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
            engine = create_engine(sync_url)
            try:
                with engine.connect() as connection:
                    rows = connection.execute(
                        text(
                            """
                            SELECT * FROM finex.goals
                            WHERE user_id = :user_id
                            """
                        ),
                        {"user_id": user_id},
                    ).mappings().all()
                    goals: list[GoalResponse] = []
                    for row in rows:
                        projection_rows = connection.execute(
                            text(
                                """
                                SELECT * FROM finex.goal_projections
                                WHERE user_id = :user_id AND goal_id = :goal_id
                                ORDER BY year
                                """
                            ),
                            {"user_id": user_id, "goal_id": row["goal_id"]},
                        ).mappings().all()
                        goals.append(
                            GoalResponse(
                                goal_id=row["goal_id"],
                                title=row["title"],
                                target_amount=row["target_amount"],
                                current_amount=row["current_amount"],
                                horizon_years=row["horizon_years"],
                                monthly_contribution=row["monthly_contribution"],
                                expected_annual_return_pct=row["expected_annual_return_pct"],
                                projected_final_amount=row["projected_final_amount"],
                                shortfall_or_surplus=row["shortfall_or_surplus"],
                                is_on_track=row["is_on_track"],
                                assumptions_statement=row["assumptions_statement"],
                                projections=[
                                    GoalProjection(
                                        year=p["year"],
                                        projected_balance=p["projected_balance"],
                                        contributions_total=p["contributions_total"],
                                        growth_total=p["growth_total"],
                                    )
                                    for p in projection_rows
                                ],
                            )
                        )
                    return goals
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM goals WHERE user_id=? ORDER BY goal_id",
                (user_id,),
            ).fetchall()
            goals = []
            for row in rows:
                projection_rows = connection.execute(
                    """
                    SELECT * FROM goal_projections
                    WHERE user_id=? AND goal_id=? ORDER BY year
                    """,
                    (user_id, row["goal_id"]),
                ).fetchall()
                projections = [
                    GoalProjection(
                        year=projection["year"],
                        projected_balance=projection["projected_balance"],
                        contributions_total=projection["contributions_total"],
                        growth_total=projection["growth_total"],
                    )
                    for projection in projection_rows
                ]
                goals.append(self._goal_from_row(row, projections))
            return goals

    def get_goal(self, user_id: str, goal_id: str) -> GoalResponse | None:
        if not user_id or not goal_id:
            return None

        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            return next(
                (
                    goal
                    for goal in self.list_goals(user_id)
                    if goal.goal_id == goal_id
                ),
                None,
            )

        with self._sqlite_connection() as connection:
            row = connection.execute(
                "SELECT * FROM goals WHERE user_id=? AND goal_id=?",
                (user_id, goal_id),
            ).fetchone()
            if row is None:
                return None
            projection_rows = connection.execute(
                """
                SELECT * FROM goal_projections
                WHERE user_id=? AND goal_id=? ORDER BY year
                """,
                (user_id, goal_id),
            ).fetchall()
            projections = [
                GoalProjection(
                    year=projection["year"],
                    projected_balance=projection["projected_balance"],
                    contributions_total=projection["contributions_total"],
                    growth_total=projection["growth_total"],
                )
                for projection in projection_rows
            ]
            return self._goal_from_row(row, projections)


goal_repository = GoalRepository()
