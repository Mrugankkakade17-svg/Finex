"""
operational_store.py

WHAT THIS FILE IS FOR
----------------------
FinEx's day-to-day transactional data (users, sessions, risk assessments,
goals, paper-trading orders, etc.) lives in Postgres. Today that Postgres
is "Databricks Lakebase Free Edition." Later, the team may move to a paid
Lakebase or a plain Azure Database for PostgreSQL.

The rest of the team's code (services, repositories) must NEVER import
`psycopg2`, `sqlalchemy`, or any Lakebase-specific client directly.
Instead, everyone codes against THIS interface. When the vendor changes,
only the class that implements this interface changes -- nobody else's
code has to be touched.

This is called the "ports and adapters" (a.k.a. hexagonal architecture)
pattern. Think of this file as a USB port on a laptop: it defines the
*shape* of the connection. Any device (Lakebase today, paid Postgres
tomorrow) that fits the shape can plug in without the laptop's own
circuitry changing.

STATUS: interface only. No real database connection code goes here yet --
that belongs in a concrete adapter class (e.g. `lakebase_operational_store.py`)
that `implements` this Protocol. Sprint 1+ owners will write that adapter.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OperationalStore(Protocol):
    """
    Abstract contract for reading and writing transactional (row-level)
    data. Every method here should feel like a small, boring, predictable
    database operation -- no business logic belongs in an implementation
    of this interface. Business rules live in `app/services/*`.
    """

    async def fetch_one(self, table: str, filters: dict[str, Any]) -> dict[str, Any] | None:
        """
        Return a single row matching `filters`, or None if no row matches.

        Example: fetch_one("identity.users", {"user_id": "..."})
        """
        ...

    async def fetch_many(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return zero or more rows matching `filters`, paginated."""
        ...

    async def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        """Insert one row and return the row as stored (including generated
        columns such as user_id, created_at)."""
        ...

    async def update(
        self, table: str, filters: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Update the row(s) matching `filters` with `values`. Returns the
        updated row, or None if nothing matched."""
        ...

    async def soft_delete(self, table: str, filters: dict[str, Any]) -> bool:
        """Mark a row deleted (status/deleted_at) rather than physically
        removing it -- required for ledgers and assessment history."""
        ...

    async def run_in_transaction(self, operations: list[Any]) -> Any:
        """
        Run multiple writes atomically. Required whenever a single request
        needs to write to more than one table (per the handbook's DB
        transaction/idempotency rule).
        """
        ...
