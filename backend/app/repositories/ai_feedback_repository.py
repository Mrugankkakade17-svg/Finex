"""Repository for persistent AI feedback storage (S1-MI01).

Supports both SQLite (local development and offline unit tests) and PostgreSQL
(production/Lakebase operational schema finex.ai_feedback).
Guarantees user scoping and isolation on all queries.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from app.config.settings import get_settings


class AIFeedbackRepository:
    """Persistent repository for AI chat feedback."""

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.settings = get_settings()
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            self.db_path = self.settings.local_db_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        self._ensure_sqlite_table(conn)
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_sqlite_table(self, conn: sqlite3.Connection) -> None:
        """Create ai_feedback table in SQLite if it does not exist."""
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_feedback (
                    user_id TEXT NOT NULL,
                    feedback_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    rating TEXT NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, feedback_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_ai_feedback_user_created
                ON ai_feedback(user_id, created_at)
                """
            )
            conn.commit()
        except Exception:
            pass

    def create_feedback(
        self,
        user_id: str,
        message_id: str,
        rating: str,
        comment: Optional[str] = None,
        feedback_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a feedback entry scoped to user_id."""
        if not user_id:
            raise ValueError("user_id is required to persist feedback")

        f_id = feedback_id or f"fb-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        created_at_iso = now.isoformat()

        # In PostgreSQL mode if enabled and database url is set
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql+psycopg://"
            ).replace("postgresql+asyncpg://", "postgresql://")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                stmt = text(
                    """
                    INSERT INTO finex.ai_feedback (
                        user_id, feedback_id, message_id, rating, comment, created_at
                    ) VALUES (
                        :user_id, :feedback_id, :message_id, :rating, :comment, :created_at
                    )
                    """
                )
                conn.execute(
                    stmt,
                    {
                        "user_id": user_id,
                        "feedback_id": f_id,
                        "message_id": message_id,
                        "rating": rating,
                        "comment": comment,
                        "created_at": now,
                    },
                )
                conn.commit()
            engine.dispose()
        else:
            # SQLite persistence
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO ai_feedback (
                        user_id, feedback_id, message_id, rating, comment, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, f_id, message_id, rating, comment, created_at_iso),
                )
                conn.commit()

        return {
            "feedback_id": f_id,
            "user_id": user_id,
            "message_id": message_id,
            "rating": rating,
            "comment": comment,
            "created_at": created_at_iso,
        }

    def get_feedback(self, user_id: str, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific feedback record scoped strictly to user_id."""
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql+psycopg://"
            ).replace("postgresql+asyncpg://", "postgresql://")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                stmt = text(
                    """
                    SELECT user_id, feedback_id, message_id, rating, comment, created_at
                    FROM finex.ai_feedback
                    WHERE user_id = :user_id AND feedback_id = :feedback_id
                    """
                )
                row = (
                    conn.execute(stmt, {"user_id": user_id, "feedback_id": feedback_id})
                    .mappings()
                    .first()
                )
                if row:
                    return {
                        "feedback_id": row["feedback_id"],
                        "user_id": row["user_id"],
                        "message_id": row["message_id"],
                        "rating": row["rating"],
                        "comment": row["comment"],
                        "created_at": row["created_at"].isoformat()
                        if hasattr(row["created_at"], "isoformat")
                        else str(row["created_at"]),
                    }
                return None
            engine.dispose()
        else:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT user_id, feedback_id, message_id, rating, comment, created_at
                    FROM ai_feedback
                    WHERE user_id = ? AND feedback_id = ?
                    """,
                    (user_id, feedback_id),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "feedback_id": row["feedback_id"],
                        "user_id": row["user_id"],
                        "message_id": row["message_id"],
                        "rating": row["rating"],
                        "comment": row["comment"],
                        "created_at": row["created_at"],
                    }
                return None

    def list_feedback_by_user(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List feedback records for a specific user ordered by created_at DESC."""
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql+psycopg://"
            ).replace("postgresql+asyncpg://", "postgresql://")
            engine = create_engine(sync_url)
            with engine.connect() as conn:
                stmt = text(
                    """
                    SELECT user_id, feedback_id, message_id, rating, comment, created_at
                    FROM finex.ai_feedback
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                )
                rows = conn.execute(stmt, {"user_id": user_id, "limit": limit}).mappings().all()
                return [
                    {
                        "feedback_id": r["feedback_id"],
                        "user_id": r["user_id"],
                        "message_id": r["message_id"],
                        "rating": r["rating"],
                        "comment": r["comment"],
                        "created_at": r["created_at"].isoformat()
                        if hasattr(r["created_at"], "isoformat")
                        else str(r["created_at"]),
                    }
                    for r in rows
                ]
            engine.dispose()
        else:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT user_id, feedback_id, message_id, rating, comment, created_at
                    FROM ai_feedback
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "feedback_id": r["feedback_id"],
                        "user_id": r["user_id"],
                        "message_id": r["message_id"],
                        "rating": r["rating"],
                        "comment": r["comment"],
                        "created_at": r["created_at"],
                    }
                    for r in rows
                ]

    def clear_for_test(self, user_id: Optional[str] = None) -> None:
        """Clear test records for test isolation."""
        try:
            with self._connection() as conn:
                if user_id:
                    conn.execute("DELETE FROM ai_feedback WHERE user_id = ?", (user_id,))
                else:
                    conn.execute("DELETE FROM ai_feedback")
                conn.commit()
        except Exception:
            pass


ai_feedback_repository = AIFeedbackRepository()
