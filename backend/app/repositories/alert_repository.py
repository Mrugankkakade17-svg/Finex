"""Persistent, principal-scoped smart alert and notification repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.config.settings import get_settings
from app.schemas.sprint6_ai_alerts import AlertRule, NotificationItem


class AlertRepository:
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
            CREATE TABLE IF NOT EXISTS alert_rules (
                user_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                target_symbol_or_goal TEXT NOT NULL,
                comparison_operator TEXT NOT NULL,
                threshold_value REAL NOT NULL,
                cooldown_minutes INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, rule_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                user_id TEXT NOT NULL,
                notification_id TEXT NOT NULL,
                rule_id TEXT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                severity TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, notification_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_alerts_user_created_at ON alerts(user_id, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_alerts_user_is_read ON alerts(user_id, is_read)"
        )
        connection.commit()

    def _seed_if_empty(self, user_id: str) -> None:
        if not user_id:
            return
        with self._sqlite_connection() as connection:
            rule = connection.execute(
                "SELECT 1 FROM alert_rules WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone()
            notification = connection.execute(
                "SELECT 1 FROM alerts WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone()
            with connection:
                if rule is None:
                    connection.execute(
                        """
                        INSERT INTO alert_rules (
                            user_id, rule_id, rule_name, condition_type,
                            target_symbol_or_goal, comparison_operator,
                            threshold_value, cooldown_minutes, is_active, created_at
                        ) VALUES (?, 'rule-001', 'AAPL Price Above 200',
                                  'PRICE_THRESHOLD', 'AAPL', 'GT', 200.0, 60, 1,
                                  '2026-10-01T12:00:00Z')
                        """,
                        (user_id,),
                    )
                if notification is None:
                    now = datetime.now(timezone.utc).isoformat()
                    connection.executemany(
                        """
                        INSERT INTO alerts (
                            user_id, notification_id, rule_id, title, body,
                            severity, created_at, is_read
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            (
                                user_id,
                                "notif-001",
                                "rule-001",
                                "Simulated Price Alert",
                                "AAPL crossed threshold of $195.00 (Current: $195.50).",
                                "INFO",
                                now,
                                0,
                            ),
                            (
                                user_id,
                                "notif-002",
                                None,
                                "Welcome to FinEx Simulation",
                                "Your virtual paper portfolio has been initialized with $50,000.",
                                "INFO",
                                now,
                                1,
                            ),
                        ),
                    )

    def _postgres_seed_if_empty(self, user_id: str) -> None:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        try:
            with engine.begin() as connection:
                rule_exists = connection.execute(
                    text("SELECT 1 FROM finex.alert_rules WHERE user_id=:user_id LIMIT 1"),
                    {"user_id": user_id},
                ).first()
                if rule_exists is None:
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.alert_rules (
                                user_id, rule_id, rule_name, condition_type,
                                target_symbol_or_goal, comparison_operator,
                                threshold_value, cooldown_minutes, is_active, created_at
                            ) VALUES (
                                :user_id, 'rule-001', 'AAPL Price Above 200',
                                'PRICE_THRESHOLD', 'AAPL', 'GT', 200.0, 60, true,
                                '2026-10-01T12:00:00Z'
                            )
                            """
                        ),
                        {"user_id": user_id},
                    )

                notification_exists = connection.execute(
                    text("SELECT 1 FROM finex.alerts WHERE user_id=:user_id LIMIT 1"),
                    {"user_id": user_id},
                ).first()
                if notification_exists is None:
                    now = datetime.now(timezone.utc).isoformat()
                    for notification_id, rule_id, title, body, is_read in (
                        (
                            "notif-001",
                            "rule-001",
                            "Simulated Price Alert",
                            "AAPL crossed threshold of $195.00 (Current: $195.50).",
                            False,
                        ),
                        (
                            "notif-002",
                            None,
                            "Welcome to FinEx Simulation",
                            "Your virtual paper portfolio has been initialized with $50,000.",
                            True,
                        ),
                    ):
                        connection.execute(
                            text(
                                """
                                INSERT INTO finex.alerts (
                                    user_id, notification_id, rule_id, title, body,
                                    severity, created_at, is_read
                                ) VALUES (
                                    :user_id, :notification_id, :rule_id, :title, :body,
                                    'INFO', :created_at, :is_read
                                )
                                """
                            ),
                            {
                                "user_id": user_id,
                                "notification_id": notification_id,
                                "rule_id": rule_id,
                                "title": title,
                                "body": body,
                                "created_at": now,
                                "is_read": is_read,
                            },
                        )
        finally:
            engine.dispose()

    @staticmethod
    def _rule_from_row(row: sqlite3.Row) -> AlertRule:
        return AlertRule(
            rule_id=row["rule_id"],
            rule_name=row["rule_name"],
            condition_type=row["condition_type"],
            target_symbol_or_goal=row["target_symbol_or_goal"],
            comparison_operator=row["comparison_operator"],
            threshold_value=row["threshold_value"],
            cooldown_minutes=row["cooldown_minutes"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    def list_rules(self, user_id: str) -> list[AlertRule]:
        if not user_id:
            return []
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            self._postgres_seed_if_empty(user_id)
            return self._postgres_list_rules(user_id)
        self._seed_if_empty(user_id)
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM alert_rules WHERE user_id=? ORDER BY rule_id",
                (user_id,),
            ).fetchall()
            return [self._rule_from_row(row) for row in rows]

    def _postgres_list_rules(self, user_id: str) -> list[AlertRule]:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        try:
            with engine.connect() as connection:
                rows = (
                    connection.execute(
                        text(
                            """
                            SELECT * FROM finex.alert_rules
                            WHERE user_id=:user_id ORDER BY rule_id
                            """
                        ),
                        {"user_id": user_id},
                    )
                    .mappings()
                    .all()
                )
                return [
                    AlertRule(
                        rule_id=row["rule_id"],
                        rule_name=row["rule_name"],
                        condition_type=row["condition_type"],
                        target_symbol_or_goal=row["target_symbol_or_goal"],
                        comparison_operator=row["comparison_operator"],
                        threshold_value=row["threshold_value"],
                        cooldown_minutes=row["cooldown_minutes"],
                        is_active=bool(row["is_active"]),
                        created_at=row["created_at"].isoformat(),
                    )
                    for row in rows
                ]
        finally:
            engine.dispose()

    def create_rule(self, user_id: str, rule: AlertRule) -> AlertRule:
        if not user_id:
            raise ValueError("user_id is required")
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            engine = create_engine(
                self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
            )
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.alert_rules (
                                user_id, rule_id, rule_name, condition_type,
                                target_symbol_or_goal, comparison_operator,
                                threshold_value, cooldown_minutes, is_active, created_at
                            ) VALUES (
                                :user_id, :rule_id, :rule_name, :condition_type,
                                :target_symbol_or_goal, :comparison_operator,
                                :threshold_value, :cooldown_minutes, :is_active, :created_at
                            )
                            """
                        ),
                        {
                            "user_id": user_id,
                            "rule_id": rule.rule_id,
                            "rule_name": rule.rule_name,
                            "condition_type": rule.condition_type,
                            "target_symbol_or_goal": rule.target_symbol_or_goal,
                            "comparison_operator": rule.comparison_operator,
                            "threshold_value": rule.threshold_value,
                            "cooldown_minutes": rule.cooldown_minutes,
                            "is_active": rule.is_active,
                            "created_at": rule.created_at,
                        },
                    )
            finally:
                engine.dispose()
            return rule

        with self._sqlite_connection() as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO alert_rules (
                        user_id, rule_id, rule_name, condition_type,
                        target_symbol_or_goal, comparison_operator,
                        threshold_value, cooldown_minutes, is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        rule.rule_id,
                        rule.rule_name,
                        rule.condition_type,
                        rule.target_symbol_or_goal,
                        rule.comparison_operator,
                        rule.threshold_value,
                        rule.cooldown_minutes,
                        int(rule.is_active),
                        rule.created_at,
                    ),
                )
        return rule

    def delete_rule(self, user_id: str, rule_id: str) -> bool:
        if not user_id or not rule_id:
            return False
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            engine = create_engine(
                self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
            )
            try:
                with engine.begin() as connection:
                    result = connection.execute(
                        text(
                            """
                            DELETE FROM finex.alert_rules
                            WHERE user_id=:user_id AND rule_id=:rule_id
                            """
                        ),
                        {"user_id": user_id, "rule_id": rule_id},
                    )
                    return result.rowcount > 0
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM alert_rules WHERE user_id=? AND rule_id=?",
                    (user_id, rule_id),
                )
                if cursor.rowcount > 0:
                    connection.execute(
                        "DELETE FROM alerts WHERE user_id=? AND rule_id=?",
                        (user_id, rule_id),
                    )
                    return True
        return False

    def list_notifications(self, user_id: str) -> list[NotificationItem]:
        if not user_id:
            return []
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            self._postgres_seed_if_empty(user_id)
            return self._postgres_list_notifications(user_id)
        self._seed_if_empty(user_id)
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM alerts WHERE user_id=? ORDER BY created_at, notification_id",
                (user_id,),
            ).fetchall()
            return [
                NotificationItem(
                    notification_id=row["notification_id"],
                    rule_id=row["rule_id"],
                    title=row["title"],
                    body=row["body"],
                    severity=row["severity"],
                    created_at=row["created_at"],
                    is_read=bool(row["is_read"]),
                )
                for row in rows
            ]

    def _postgres_list_notifications(self, user_id: str) -> list[NotificationItem]:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        try:
            with engine.connect() as connection:
                rows = (
                    connection.execute(
                        text(
                            """
                            SELECT * FROM finex.alerts
                            WHERE user_id=:user_id ORDER BY created_at, notification_id
                            """
                        ),
                        {"user_id": user_id},
                    )
                    .mappings()
                    .all()
                )
                return [
                    NotificationItem(
                        notification_id=row["notification_id"],
                        rule_id=row["rule_id"],
                        title=row["title"],
                        body=row["body"],
                        severity=row["severity"],
                        created_at=row["created_at"].isoformat(),
                        is_read=bool(row["is_read"]),
                    )
                    for row in rows
                ]
        finally:
            engine.dispose()

    def mark_read(self, user_id: str, notification_id: str) -> NotificationItem | None:
        if not user_id or not notification_id:
            return None
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            engine = create_engine(
                self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
            )
            try:
                with engine.begin() as connection:
                    row = (
                        connection.execute(
                            text(
                                """
                                UPDATE finex.alerts
                                SET is_read=true
                                WHERE user_id=:user_id AND notification_id=:notification_id
                                RETURNING *
                                """
                            ),
                            {"user_id": user_id, "notification_id": notification_id},
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        return None
                    return NotificationItem(
                        notification_id=row["notification_id"],
                        rule_id=row["rule_id"],
                        title=row["title"],
                        body=row["body"],
                        severity=row["severity"],
                        created_at=row["created_at"].isoformat(),
                        is_read=bool(row["is_read"]),
                    )
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            with connection:
                cursor = connection.execute(
                    "UPDATE alerts SET is_read=1 WHERE user_id=? AND notification_id=?",
                    (user_id, notification_id),
                )
                if cursor.rowcount == 0:
                    return None
            row = connection.execute(
                "SELECT * FROM alerts WHERE user_id=? AND notification_id=?",
                (user_id, notification_id),
            ).fetchone()
            return NotificationItem(
                notification_id=row["notification_id"],
                rule_id=row["rule_id"],
                title=row["title"],
                body=row["body"],
                severity=row["severity"],
                created_at=row["created_at"],
                is_read=bool(row["is_read"]),
            )


alert_repository = AlertRepository()
