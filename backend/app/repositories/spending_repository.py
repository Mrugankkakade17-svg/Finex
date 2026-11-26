"""Persistent, principal-scoped spending transaction repository."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from app.config.settings import get_settings
from app.schemas.sprint5_privacy_spending import SpendingTransaction


class SpendingRepository:
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
            CREATE TABLE IF NOT EXISTS spending_transactions (
                user_id TEXT NOT NULL,
                transaction_id TEXT NOT NULL,
                date TEXT NOT NULL,
                description_masked TEXT NOT NULL,
                amount TEXT NOT NULL,
                category TEXT NOT NULL,
                is_user_corrected INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, transaction_id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS ix_spending_transactions_user_date "
            "ON spending_transactions(user_id, date)"
        )
        connection.commit()

    def _seed_if_empty(self, user_id: str) -> None:
        if not user_id:
            return
        with self._sqlite_connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM spending_transactions WHERE user_id=? LIMIT 1",
                (user_id,),
            ).fetchone()
            if row is not None:
                return
            seeds = (
                ("tx-001", "2026-10-05", "GROCERY STORE #***12", "84.50", "Groceries"),
                ("tx-002", "2026-10-12", "ELECTRIC UTILITY CO #***99", "115.00", "Utilities"),
                ("tx-003", "2026-10-18", "STREAMING SUBSCRIPTION #***44", "14.99", "Entertainment"),
                ("tx-004", "2026-10-22", "METRO TRANSIT PASS #***01", "45.00", "Transportation"),
            )
            with connection:
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO spending_transactions (
                        user_id, transaction_id, date, description_masked,
                        amount, category, is_user_corrected
                    ) VALUES (?, ?, ?, ?, ?, ?, 0)
                    """,
                    [(user_id, *seed) for seed in seeds],
                )

    def _postgres_seed_if_empty(self, user_id: str) -> None:
        from sqlalchemy import create_engine, text

        engine = create_engine(
            self.settings.app_database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        try:
            with engine.begin() as connection:
                exists = connection.execute(
                    text(
                        "SELECT 1 FROM finex.spending_transactions WHERE user_id=:user_id LIMIT 1"
                    ),
                    {"user_id": user_id},
                ).first()
                if exists is not None:
                    return
                seeds = (
                    ("tx-001", "2026-10-05", "GROCERY STORE #***12", "84.50", "Groceries"),
                    ("tx-002", "2026-10-12", "ELECTRIC UTILITY CO #***99", "115.00", "Utilities"),
                    (
                        "tx-003",
                        "2026-10-18",
                        "STREAMING SUBSCRIPTION #***44",
                        "14.99",
                        "Entertainment",
                    ),
                    (
                        "tx-004",
                        "2026-10-22",
                        "METRO TRANSIT PASS #***01",
                        "45.00",
                        "Transportation",
                    ),
                )
                for transaction_id, date, description, amount, category in seeds:
                    connection.execute(
                        text(
                            """
                            INSERT INTO finex.spending_transactions (
                                user_id, transaction_id, date, description_masked,
                                amount, category, is_user_corrected
                            ) VALUES (
                                :user_id, :transaction_id, :date, :description,
                                :amount, :category, false
                            )
                            """
                        ),
                        {
                            "user_id": user_id,
                            "transaction_id": transaction_id,
                            "date": date,
                            "description": description,
                            "amount": amount,
                            "category": category,
                        },
                    )
        finally:
            engine.dispose()

    def list_transactions(self, user_id: str) -> list[SpendingTransaction]:
        if not user_id:
            return []
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            self._postgres_seed_if_empty(user_id)
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
            engine = create_engine(sync_url)
            try:
                with engine.connect() as connection:
                    rows = (
                        connection.execute(
                            text(
                                """
                                SELECT transaction_id, date, description_masked,
                                       amount, category, is_user_corrected
                                FROM finex.spending_transactions
                                WHERE user_id=:user_id
                                ORDER BY date, transaction_id
                                """
                            ),
                            {"user_id": user_id},
                        )
                        .mappings()
                        .all()
                    )
                    return [
                        SpendingTransaction(
                            transaction_id=row["transaction_id"],
                            date=str(row["date"]),
                            description_masked=row["description_masked"],
                            amount=Decimal(str(row["amount"])),
                            category=row["category"],
                            is_user_corrected=bool(row["is_user_corrected"]),
                        )
                        for row in rows
                    ]
            finally:
                engine.dispose()

        self._seed_if_empty(user_id)
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                """
                SELECT transaction_id, date, description_masked, amount,
                       category, is_user_corrected
                FROM spending_transactions
                WHERE user_id=? ORDER BY date, transaction_id
                """,
                (user_id,),
            ).fetchall()
            return [
                SpendingTransaction(
                    transaction_id=row["transaction_id"],
                    date=row["date"],
                    description_masked=row["description_masked"],
                    amount=Decimal(row["amount"]),
                    category=row["category"],
                    is_user_corrected=bool(row["is_user_corrected"]),
                )
                for row in rows
            ]

    def correct_category(
        self, user_id: str, transaction_id: str, corrected_category: str
    ) -> SpendingTransaction | None:
        if not user_id or not transaction_id:
            return None
        if self.settings.app_persistence == "postgresql" and self.settings.app_database_url:
            from sqlalchemy import create_engine, text

            sync_url = self.settings.app_database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
            engine = create_engine(sync_url)
            try:
                with engine.begin() as connection:
                    row = (
                        connection.execute(
                            text(
                                """
                                UPDATE finex.spending_transactions
                                SET category=:category, is_user_corrected=true
                                WHERE user_id=:user_id AND transaction_id=:transaction_id
                                RETURNING transaction_id, date, description_masked,
                                          amount, category, is_user_corrected
                                """
                            ),
                            {
                                "user_id": user_id,
                                "transaction_id": transaction_id,
                                "category": corrected_category,
                            },
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        return None
                    return SpendingTransaction(
                        transaction_id=row["transaction_id"],
                        date=str(row["date"]),
                        description_masked=row["description_masked"],
                        amount=Decimal(str(row["amount"])),
                        category=row["category"],
                        is_user_corrected=bool(row["is_user_corrected"]),
                    )
            finally:
                engine.dispose()

        with self._sqlite_connection() as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE spending_transactions
                    SET category=?, is_user_corrected=1
                    WHERE user_id=? AND transaction_id=?
                    """,
                    (corrected_category, user_id, transaction_id),
                )
                if cursor.rowcount == 0:
                    return None
            row = connection.execute(
                """
                SELECT transaction_id, date, description_masked, amount,
                       category, is_user_corrected
                FROM spending_transactions
                WHERE user_id=? AND transaction_id=?
                """,
                (user_id, transaction_id),
            ).fetchone()
            return SpendingTransaction(
                transaction_id=row["transaction_id"],
                date=row["date"],
                description_masked=row["description_masked"],
                amount=Decimal(row["amount"]),
                category=row["category"],
                is_user_corrected=bool(row["is_user_corrected"]),
            )


spending_repository = SpendingRepository()
