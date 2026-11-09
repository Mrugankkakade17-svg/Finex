"""Local-only data port for deterministic Sprint 2 assessment fixtures."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AssessmentFixtureStore(Protocol):
    """Safe local fixture boundary for the Sprint 2 assessment API.

    This port intentionally has no database, cloud, or user-account semantics.
    A future shared-environment implementation must be introduced through a
    separately approved operational-store adapter, not by changing this local
    fixture provider.
    """

    def reset(self) -> None:
        """Discard the ephemeral in-memory snapshot."""
        ...

    def seed(self) -> dict[str, Any]:
        """Validate sources and return a fresh deterministic snapshot."""
        ...

    def reset_and_seed(self) -> dict[str, Any]:
        """Discard then rebuild the deterministic snapshot."""
        ...

    def list_fixtures(self) -> list[dict[str, Any]]:
        """Return defensive copies of all materialized synthetic fixtures."""
        ...

    def get_fixture(self, fixture_id: str) -> dict[str, Any] | None:
        """Return a defensive copy of one fixture, if present."""
        ...
