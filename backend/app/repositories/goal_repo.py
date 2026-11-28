"""Persistent, user-scoped goal repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping

from sqlalchemy.engine import Engine, RowMapping

from app.config.settings import get_settings
from app.schemas.sprint4_paper_goals import (
    GoalContributionResponse,
    GoalProjection,
    GoalResponse,
)


def _coerce_optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        return date.fromisoformat(cleaned) if cleaned else None
    raise ValueError(f"Unsupported date value: {value!r}")


def _coerce_date(value: Any) -> date:
    parsed = _coerce_optional_date(value)
    if parsed is None:
        raise ValueError("Date value cannot be None")
    return parsed


def _coerce_iso_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class GoalRepository:
    """Repository for user-owned goals, projections, and recorded contributions."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.settings = get_settings()
        self.db_path = Path(db_path) if db_path is not None else self.settings.local_db_path

    def _use_postgres(self) -> bool:
        return self.settings.app_persistence == "postgresql" and bool(
            self.settings.app_database_url
        )

    def _postgres_engine(self) -> Engine:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url

        url = make_url(self.settings.app_database_url)
        if url.get_backend_name() not in {"postgres", "postgresql"}:
            raise ValueError("Goal persistence requires a PostgreSQL database URL")
        return create_engine(url.set(drivername="postgresql+psycopg"))

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
                target_date TEXT,
                PRIMARY KEY (user_id, goal_id)
            )
            """
        )
        goal_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(goals)").fetchall()
        }
        if "target_date" not in goal_columns:
            connection.execute("ALTER TABLE goals ADD COLUMN target_date TEXT")

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
            """
            CREATE TABLE IF NOT EXISTS goal_contributions (
                user_id TEXT NOT NULL,
                goal_id TEXT NOT NULL,
                contribution_id TEXT NOT NULL,
                amount TEXT NOT NULL,
                contribution_date TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, goal_id, contribution_id),
                FOREIGN KEY (user_id, goal_id)
                    REFERENCES goals (user_id, goal_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS ix_goals_user_id ON goals(user_id)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_goal_contributions_user_goal_date "
            "ON goal_contributions(user_id, goal_id, contribution_date)"
        )
        connection.commit()

    @staticmethod
    def _goal_from_row(row: sqlite3.Row, projections: list[GoalProjection]) -> GoalResponse:
        target_date_raw = row["target_date"] if "target_date" in row.keys() else None
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
            target_date=_coerce_optional_date(target_date_raw),
        )

    @staticmethod
    def _goal_from_mapping(
        row: Mapping[str, Any] | RowMapping, projections: list[GoalProjection]
    ) -> GoalResponse:
        return GoalResponse(
            goal_id=str(row["goal_id"]),
            title=str(row["title"]),
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            horizon_years=int(row["horizon_years"]),
            monthly_contribution=row["monthly_contribution"],
            expected_annual_return_pct=row["expected_annual_return_pct"],
            projected_final_amount=row["projected_final_amount"],
            shortfall_or_surplus=row["shortfall_or_surplus"],
            is_on_track=bool(row["is_on_track"]),
            assumptions_statement=str(row["assumptions_statement"]),
            projections=projections,
            target_date=_coerce_optional_date(row.get("target_date")),
        )

    @staticmethod
    def _contribution_from_row(
        row: sqlite3.Row | Mapping[str, Any] | RowMapping,
    ) -> GoalContributionResponse:
        return GoalContributionResponse(
            contribution_id=str(row["contribution_id"]),
            goal_id=str(row["goal_id"]),
            amount=Decimal(str(row["amount"])),
            contribution_date=_coerce_date(row["contribution_date"]),
            note=row["note"],
            created_at=_coerce_iso_timestamp(row["created_at"]),
        )

    def create_goal(self, user_id: str, goal: GoalResponse) -> GoalResponse:
        if not user_id:
            raise ValueError("user_id is required")

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.goals (
                                user_id, goal_id, title, target_amount, current_amount,
                                horizon_years, monthly_contribution,
                                expected_annual_return_pct, projected_final_amount,
                                shortfall_or_surplus, is_on_track, assumptions_statement,
                                target_date
                            ) VALUES (
                                :user_id, :goal_id, :title, :target_amount, :current_amount,
                                :horizon_years, :monthly_contribution,
                                :expected_annual_return_pct, :projected_final_amount,
                                :shortfall_or_surplus, :is_on_track, :assumptions_statement,
                                :target_date
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
                            "target_date": goal.target_date,
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
                        assumptions_statement, target_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        goal.target_date.isoformat() if goal.target_date else None,
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

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.connect() as connection:
                    rows = (
                        connection.execute(
                            text(
                                """
                                SELECT * FROM finex.goals
                                WHERE user_id = :user_id
                                ORDER BY goal_id
                                """
                            ),
                            {"user_id": user_id},
                        )
                        .mappings()
                        .all()
                    )
                    goals: list[GoalResponse] = []
                    for row in rows:
                        projection_rows = (
                            connection.execute(
                                text(
                                    """
                                    SELECT * FROM finex.goal_projections
                                    WHERE user_id = :user_id AND goal_id = :goal_id
                                    ORDER BY year
                                    """
                                ),
                                {"user_id": user_id, "goal_id": row["goal_id"]},
                            )
                            .mappings()
                            .all()
                        )
                        projections = [
                            GoalProjection(
                                year=p["year"],
                                projected_balance=p["projected_balance"],
                                contributions_total=p["contributions_total"],
                                growth_total=p["growth_total"],
                            )
                            for p in projection_rows
                        ]
                        goals.append(self._goal_from_mapping(row, projections))
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

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.connect() as connection:
                    row = (
                        connection.execute(
                            text(
                                """
                                SELECT * FROM finex.goals
                                WHERE user_id = :user_id AND goal_id = :goal_id
                                """
                            ),
                            {"user_id": user_id, "goal_id": goal_id},
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        return None
                    projection_rows = (
                        connection.execute(
                            text(
                                """
                                SELECT * FROM finex.goal_projections
                                WHERE user_id = :user_id AND goal_id = :goal_id
                                ORDER BY year
                                """
                            ),
                            {"user_id": user_id, "goal_id": goal_id},
                        )
                        .mappings()
                        .all()
                    )
                    projections = [
                        GoalProjection(
                            year=p["year"],
                            projected_balance=p["projected_balance"],
                            contributions_total=p["contributions_total"],
                            growth_total=p["growth_total"],
                        )
                        for p in projection_rows
                    ]
                    return self._goal_from_mapping(row, projections)
            finally:
                engine.dispose()

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

    def update_goal(self, user_id: str, goal: GoalResponse) -> GoalResponse | None:
        if not user_id or not goal.goal_id:
            return None

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.begin() as connection:
                    result = connection.execute(
                        text(
                            """
                            UPDATE finex.goals
                            SET title = :title,
                                target_amount = :target_amount,
                                current_amount = :current_amount,
                                horizon_years = :horizon_years,
                                monthly_contribution = :monthly_contribution,
                                expected_annual_return_pct = :expected_annual_return_pct,
                                projected_final_amount = :projected_final_amount,
                                shortfall_or_surplus = :shortfall_or_surplus,
                                is_on_track = :is_on_track,
                                assumptions_statement = :assumptions_statement,
                                target_date = :target_date
                            WHERE user_id = :user_id AND goal_id = :goal_id
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
                            "target_date": goal.target_date,
                        },
                    )
                    if result.rowcount == 0:
                        return None
                    connection.execute(
                        text(
                            """
                            DELETE FROM finex.goal_projections
                            WHERE user_id = :user_id AND goal_id = :goal_id
                            """
                        ),
                        {"user_id": user_id, "goal_id": goal.goal_id},
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
                cursor = connection.execute(
                    """
                    UPDATE goals
                    SET title=?,
                        target_amount=?,
                        current_amount=?,
                        horizon_years=?,
                        monthly_contribution=?,
                        expected_annual_return_pct=?,
                        projected_final_amount=?,
                        shortfall_or_surplus=?,
                        is_on_track=?,
                        assumptions_statement=?,
                        target_date=?
                    WHERE user_id=? AND goal_id=?
                    """,
                    (
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
                        goal.target_date.isoformat() if goal.target_date else None,
                        user_id,
                        goal.goal_id,
                    ),
                )
                if cursor.rowcount == 0:
                    return None
                connection.execute(
                    "DELETE FROM goal_projections WHERE user_id=? AND goal_id=?",
                    (user_id, goal.goal_id),
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

    def delete_goal(self, user_id: str, goal_id: str) -> bool:
        if not user_id or not goal_id:
            return False

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.begin() as connection:
                    result = connection.execute(
                        text(
                            """
                            DELETE FROM finex.goals
                            WHERE user_id = :user_id AND goal_id = :goal_id
                            """
                        ),
                        {"user_id": user_id, "goal_id": goal_id},
                    )
                    return bool(result.rowcount and result.rowcount > 0)
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM goals WHERE user_id=? AND goal_id=?",
                    (user_id, goal_id),
                )
                return cursor.rowcount > 0

    def add_contribution(
        self,
        user_id: str,
        goal_id: str,
        contribution: GoalContributionResponse,
        updated_goal: GoalResponse,
    ) -> GoalContributionResponse | None:
        """Persist a contribution and update goal balances/projections atomically."""
        if not user_id or not goal_id:
            return None

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.begin() as connection:
                    result = connection.execute(
                        text(
                            """
                            UPDATE finex.goals
                            SET current_amount = :current_amount,
                                projected_final_amount = :projected_final_amount,
                                shortfall_or_surplus = :shortfall_or_surplus,
                                is_on_track = :is_on_track
                            WHERE user_id = :user_id AND goal_id = :goal_id
                            """
                        ),
                        {
                            "user_id": user_id,
                            "goal_id": goal_id,
                            "current_amount": updated_goal.current_amount,
                            "projected_final_amount": updated_goal.projected_final_amount,
                            "shortfall_or_surplus": updated_goal.shortfall_or_surplus,
                            "is_on_track": updated_goal.is_on_track,
                        },
                    )
                    if result.rowcount == 0:
                        return None
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.goal_contributions (
                                user_id, goal_id, contribution_id, amount,
                                contribution_date, note, created_at
                            ) VALUES (
                                :user_id, :goal_id, :contribution_id, :amount,
                                :contribution_date, :note, :created_at
                            )
                            """
                        ),
                        {
                            "user_id": user_id,
                            "goal_id": goal_id,
                            "contribution_id": contribution.contribution_id,
                            "amount": contribution.amount,
                            "contribution_date": contribution.contribution_date,
                            "note": contribution.note,
                            "created_at": contribution.created_at,
                        },
                    )
                    connection.execute(
                        text(
                            """
                            DELETE FROM finex.goal_projections
                            WHERE user_id = :user_id AND goal_id = :goal_id
                            """
                        ),
                        {"user_id": user_id, "goal_id": goal_id},
                    )
                    for projection in updated_goal.projections:
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
                                "goal_id": goal_id,
                                "year": projection.year,
                                "projected_balance": projection.projected_balance,
                                "contributions_total": projection.contributions_total,
                                "growth_total": projection.growth_total,
                            },
                        )
            finally:
                engine.dispose()
            return contribution

        with self._sqlite_connection() as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE goals
                    SET current_amount=?,
                        projected_final_amount=?,
                        shortfall_or_surplus=?,
                        is_on_track=?
                    WHERE user_id=? AND goal_id=?
                    """,
                    (
                        str(updated_goal.current_amount),
                        str(updated_goal.projected_final_amount),
                        str(updated_goal.shortfall_or_surplus),
                        int(updated_goal.is_on_track),
                        user_id,
                        goal_id,
                    ),
                )
                if cursor.rowcount == 0:
                    return None
                connection.execute(
                    """
                    INSERT INTO goal_contributions (
                        user_id, goal_id, contribution_id, amount,
                        contribution_date, note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        goal_id,
                        contribution.contribution_id,
                        str(contribution.amount),
                        contribution.contribution_date.isoformat(),
                        contribution.note,
                        contribution.created_at,
                    ),
                )
                connection.execute(
                    "DELETE FROM goal_projections WHERE user_id=? AND goal_id=?",
                    (user_id, goal_id),
                )
                for projection in updated_goal.projections:
                    connection.execute(
                        """
                        INSERT INTO goal_projections (
                            user_id, goal_id, year, projected_balance,
                            contributions_total, growth_total
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            goal_id,
                            projection.year,
                            str(projection.projected_balance),
                            str(projection.contributions_total),
                            str(projection.growth_total),
                        ),
                    )
        return contribution

    def list_contributions(self, user_id: str, goal_id: str) -> list[GoalContributionResponse]:
        if not user_id or not goal_id:
            return []

        if self._use_postgres():
            from sqlalchemy import text

            engine = self._postgres_engine()
            try:
                with engine.connect() as connection:
                    rows = (
                        connection.execute(
                            text(
                                """
                                SELECT contribution_id, goal_id, amount,
                                       contribution_date, note, created_at
                                FROM finex.goal_contributions
                                WHERE user_id = :user_id AND goal_id = :goal_id
                                ORDER BY contribution_date DESC, created_at DESC,
                                         contribution_id DESC
                                """
                            ),
                            {"user_id": user_id, "goal_id": goal_id},
                        )
                        .mappings()
                        .all()
                    )
                    return [self._contribution_from_row(row) for row in rows]
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            rows = connection.execute(
                """
                SELECT contribution_id, goal_id, amount,
                       contribution_date, note, created_at
                FROM goal_contributions
                WHERE user_id=? AND goal_id=?
                ORDER BY contribution_date DESC, created_at DESC, contribution_id DESC
                """,
                (user_id, goal_id),
            ).fetchall()
            return [self._contribution_from_row(row) for row in rows]


goal_repository = GoalRepository()
