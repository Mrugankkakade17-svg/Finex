"""
analytics_store.py

WHAT THIS FILE IS FOR
----------------------
Analytics/history data (risk trend views, goal-progress views, alert event
views, etc.) lives in Databricks Delta -- not in the same place as the
transactional data. This interface is how the FastAPI backend reads
Delta-backed views without any service file needing to know Databricks
SQL connection details, warehouse IDs, or query syntax.

STATUS: interface only, same as operational_store.py.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AnalyticsStore(Protocol):
    """Abstract contract for read-only analytical queries against Delta."""

    async def query_view(
        self,
        view_name: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query a named, pre-approved Delta view (e.g. "risk_trends_v1",
        "goal_progress_v1"). Callers never write raw SQL here -- that
        keeps the query surface reviewable and stable.
        """
        ...

    async def latest_snapshot(self, view_name: str, owner_id: str) -> dict[str, Any] | None:
        """Return the most recent row for a given owner (e.g. user_id) from
        a snapshot-style view. Returns None if nothing has been computed
        yet for this owner."""
        ...

    async def data_as_of(self, view_name: str) -> str | None:
        """
        Return an ISO-8601 timestamp describing how fresh `view_name` is.
        Every API response's `meta.dataAsOf` / `meta.dataStatus` fields
        should ultimately trace back to a call like this one.
        """
        ...
