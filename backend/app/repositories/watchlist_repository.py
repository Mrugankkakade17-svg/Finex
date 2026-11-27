"""Persistent, user-scoped repository for production watchlists and items."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from sqlalchemy.engine import Engine

from app.config.settings import get_settings


class WatchlistRepository:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.settings = get_settings()
        self.db_path = Path(db_path) if db_path is not None else self.settings.local_db_path

    def _postgres_engine(self) -> Engine:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url

        url = make_url(self.settings.app_database_url)
        if url.get_backend_name() not in {"postgres", "postgresql"}:
            raise ValueError("Watchlist persistence requires a PostgreSQL database URL")
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
            CREATE TABLE IF NOT EXISTS watchlists (
                user_id TEXT NOT NULL,
                watchlist_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, watchlist_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_items (
                user_id TEXT NOT NULL,
                watchlist_id TEXT NOT NULL,
                instrument_id TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (watchlist_id, instrument_id),
                FOREIGN KEY (user_id, watchlist_id)
                    REFERENCES watchlists (user_id, watchlist_id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS ix_watchlists_user ON watchlists(user_id)")
        connection.commit()

    @property
    def is_postgres(self) -> bool:
        return bool(
            self.settings.app_persistence == "postgresql" and self.settings.app_database_url
        )

    def create_watchlist(self, user_id: str, name: str) -> dict:
        if not user_id:
            raise ValueError("user_id is required")
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("name cannot be empty")

        watchlist_id = str(uuid4())
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        INSERT INTO finex.watchlists (
                            user_id, watchlist_id, name, created_at, updated_at
                        )
                        VALUES (:user_id, :watchlist_id, :name, :created_at, :updated_at)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "watchlist_id": watchlist_id,
                        "name": clean_name,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        else:
            with self._sqlite_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO watchlists (user_id, watchlist_id, name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, watchlist_id, clean_name, now_iso, now_iso),
                )
                connection.commit()

        return {
            "watchlist_id": watchlist_id,
            "name": clean_name,
            "created_at": now_iso,
            "updated_at": now_iso,
            "item_count": 0,
            "items": [],
        }

    def list_watchlists(self, user_id: str) -> list[dict]:
        if not user_id:
            raise ValueError("user_id is required")

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.connect() as connection:
                rows = (
                    connection.execute(
                        text(
                            """
                        SELECT w.watchlist_id, w.name, w.created_at, w.updated_at,
                               COUNT(i.instrument_id) AS item_count
                        FROM finex.watchlists w
                        LEFT JOIN finex.watchlist_items i
                          ON i.watchlist_id = w.watchlist_id AND i.user_id = w.user_id
                        WHERE w.user_id = :user_id
                        GROUP BY w.watchlist_id, w.name, w.created_at, w.updated_at
                        ORDER BY w.created_at ASC, w.watchlist_id ASC
                        """
                        ),
                        {"user_id": user_id},
                    )
                    .mappings()
                    .all()
                )

                return [
                    {
                        "watchlist_id": str(r["watchlist_id"]),
                        "name": str(r["name"]),
                        "created_at": r["created_at"].isoformat()
                        if hasattr(r["created_at"], "isoformat")
                        else str(r["created_at"]),
                        "updated_at": r["updated_at"].isoformat()
                        if hasattr(r["updated_at"], "isoformat")
                        else str(r["updated_at"]),
                        "item_count": int(r["item_count"]),
                    }
                    for r in rows
                ]
        else:
            with self._sqlite_connection() as connection:
                rows = connection.execute(
                    """
                    SELECT w.watchlist_id, w.name, w.created_at, w.updated_at,
                           COUNT(i.instrument_id) AS item_count
                    FROM watchlists w
                    LEFT JOIN watchlist_items i
                      ON i.watchlist_id = w.watchlist_id AND i.user_id = w.user_id
                    WHERE w.user_id = ?
                    GROUP BY w.watchlist_id, w.name, w.created_at, w.updated_at
                    ORDER BY w.created_at ASC, w.watchlist_id ASC
                    """,
                    (user_id,),
                ).fetchall()

                return [
                    {
                        "watchlist_id": r["watchlist_id"],
                        "name": r["name"],
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                        "item_count": r["item_count"],
                    }
                    for r in rows
                ]

    def get_watchlist(self, user_id: str, watchlist_id: str) -> dict | None:
        if not user_id or not watchlist_id:
            return None

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.connect() as connection:
                w_row = (
                    connection.execute(
                        text(
                            """
                        SELECT watchlist_id, name, created_at, updated_at
                        FROM finex.watchlists
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                        """
                        ),
                        {"user_id": user_id, "watchlist_id": watchlist_id},
                    )
                    .mappings()
                    .first()
                )

                if not w_row:
                    return None

                i_rows = (
                    connection.execute(
                        text(
                            """
                        SELECT instrument_id, added_at
                        FROM finex.watchlist_items
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                        ORDER BY added_at ASC, instrument_id ASC
                        """
                        ),
                        {"user_id": user_id, "watchlist_id": watchlist_id},
                    )
                    .mappings()
                    .all()
                )

                items = [
                    {
                        "instrument_id": str(i["instrument_id"]),
                        "added_at": i["added_at"].isoformat()
                        if hasattr(i["added_at"], "isoformat")
                        else str(i["added_at"]),
                    }
                    for i in i_rows
                ]

                return {
                    "watchlist_id": str(w_row["watchlist_id"]),
                    "name": str(w_row["name"]),
                    "created_at": w_row["created_at"].isoformat()
                    if hasattr(w_row["created_at"], "isoformat")
                    else str(w_row["created_at"]),
                    "updated_at": w_row["updated_at"].isoformat()
                    if hasattr(w_row["updated_at"], "isoformat")
                    else str(w_row["updated_at"]),
                    "item_count": len(items),
                    "items": items,
                }
        else:
            with self._sqlite_connection() as connection:
                w_row = connection.execute(
                    """
                    SELECT watchlist_id, name, created_at, updated_at
                    FROM watchlists
                    WHERE user_id = ? AND watchlist_id = ?
                    """,
                    (user_id, watchlist_id),
                ).fetchone()

                if not w_row:
                    return None

                i_rows = connection.execute(
                    """
                    SELECT instrument_id, added_at
                    FROM watchlist_items
                    WHERE user_id = ? AND watchlist_id = ?
                    ORDER BY added_at ASC, instrument_id ASC
                    """,
                    (user_id, watchlist_id),
                ).fetchall()

                items = [
                    {
                        "instrument_id": i["instrument_id"],
                        "added_at": i["added_at"],
                    }
                    for i in i_rows
                ]

                return {
                    "watchlist_id": w_row["watchlist_id"],
                    "name": w_row["name"],
                    "created_at": w_row["created_at"],
                    "updated_at": w_row["updated_at"],
                    "item_count": len(items),
                    "items": items,
                }

    def update_watchlist(self, user_id: str, watchlist_id: str, name: str) -> dict | None:
        if not user_id or not watchlist_id:
            return None
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("name cannot be empty")

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.begin() as connection:
                res = connection.execute(
                    text(
                        """
                        UPDATE finex.watchlists
                        SET name = :name, updated_at = :updated_at
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                        """
                    ),
                    {
                        "user_id": user_id,
                        "watchlist_id": watchlist_id,
                        "name": clean_name,
                        "updated_at": now,
                    },
                )
                if res.rowcount == 0:
                    return None
        else:
            with self._sqlite_connection() as connection:
                cur = connection.execute(
                    """
                    UPDATE watchlists
                    SET name = ?, updated_at = ?
                    WHERE user_id = ? AND watchlist_id = ?
                    """,
                    (clean_name, now_iso, user_id, watchlist_id),
                )
                connection.commit()
                if cur.rowcount == 0:
                    return None

        return self.get_watchlist(user_id, watchlist_id)

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> bool:
        if not user_id or not watchlist_id:
            return False

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.begin() as connection:
                res = connection.execute(
                    text(
                        """
                        DELETE FROM finex.watchlists
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                        """
                    ),
                    {"user_id": user_id, "watchlist_id": watchlist_id},
                )
                return res.rowcount > 0
        else:
            with self._sqlite_connection() as connection:
                cur = connection.execute(
                    """
                    DELETE FROM watchlists
                    WHERE user_id = ? AND watchlist_id = ?
                    """,
                    (user_id, watchlist_id),
                )
                connection.commit()
                return cur.rowcount > 0

    def add_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> dict | None:
        if not user_id or not watchlist_id or not instrument_id:
            return None
        clean_instrument = instrument_id.strip().upper()
        if not clean_instrument:
            raise ValueError("instrument_id cannot be empty")

        # Verify watchlist exists and belongs to user
        watchlist = self.get_watchlist(user_id, watchlist_id)
        if watchlist is None:
            return None

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.begin() as connection:
                # Upsert / insert if not exists
                connection.execute(
                    text(
                        """
                        INSERT INTO finex.watchlist_items (
                            user_id, watchlist_id, instrument_id, added_at
                        )
                        VALUES (:user_id, :watchlist_id, :instrument_id, :added_at)
                        ON CONFLICT (watchlist_id, instrument_id) DO NOTHING
                        """
                    ),
                    {
                        "user_id": user_id,
                        "watchlist_id": watchlist_id,
                        "instrument_id": clean_instrument,
                        "added_at": now,
                    },
                )
                connection.execute(
                    text(
                        """
                        UPDATE finex.watchlists
                        SET updated_at = :updated_at
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                        """
                    ),
                    {"user_id": user_id, "watchlist_id": watchlist_id, "updated_at": now},
                )
        else:
            with self._sqlite_connection() as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO watchlist_items (
                        user_id, watchlist_id, instrument_id, added_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, watchlist_id, clean_instrument, now_iso),
                )
                connection.execute(
                    """
                    UPDATE watchlists
                    SET updated_at = ?
                    WHERE user_id = ? AND watchlist_id = ?
                    """,
                    (now_iso, user_id, watchlist_id),
                )
                connection.commit()

        # Retrieve actual added_at
        items = self.list_items(user_id, watchlist_id)
        for it in items or []:
            if it["instrument_id"] == clean_instrument:
                return it

        return {"instrument_id": clean_instrument, "added_at": now_iso}

    def list_items(self, user_id: str, watchlist_id: str) -> list[dict] | None:
        watchlist = self.get_watchlist(user_id, watchlist_id)
        if watchlist is None:
            return None
        return watchlist.get("items", [])

    def remove_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> bool:
        if not user_id or not watchlist_id or not instrument_id:
            return False
        clean_instrument = instrument_id.strip().upper()

        # Verify watchlist exists and belongs to user
        watchlist = self.get_watchlist(user_id, watchlist_id)
        if watchlist is None:
            return False

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if self.is_postgres:
            from sqlalchemy import text

            engine = self._postgres_engine()
            with engine.begin() as connection:
                res = connection.execute(
                    text(
                        """
                        DELETE FROM finex.watchlist_items
                        WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                          AND upper(instrument_id) = :instrument_id
                        """
                    ),
                    {
                        "user_id": user_id,
                        "watchlist_id": watchlist_id,
                        "instrument_id": clean_instrument,
                    },
                )
                if res.rowcount > 0:
                    connection.execute(
                        text(
                            """
                            UPDATE finex.watchlists
                            SET updated_at = :updated_at
                            WHERE user_id = :user_id AND watchlist_id = :watchlist_id
                            """
                        ),
                        {"user_id": user_id, "watchlist_id": watchlist_id, "updated_at": now},
                    )
                return res.rowcount > 0
        else:
            with self._sqlite_connection() as connection:
                cur = connection.execute(
                    """
                    DELETE FROM watchlist_items
                    WHERE user_id = ? AND watchlist_id = ? AND upper(instrument_id) = ?
                    """,
                    (user_id, watchlist_id, clean_instrument),
                )
                if cur.rowcount > 0:
                    connection.execute(
                        """
                        UPDATE watchlists
                        SET updated_at = ?
                        WHERE user_id = ? AND watchlist_id = ?
                        """,
                        (now_iso, user_id, watchlist_id),
                    )
                connection.commit()
                return cur.rowcount > 0
