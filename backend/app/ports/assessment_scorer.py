"""Vendor-neutral deterministic scoring boundary; no persistence semantics."""

from typing import Any, Protocol


class AssessmentScorer(Protocol):
    def score(self, payload: object) -> dict[str, Any]:
        """Score accepted versioned input or raise a stable domain error."""
        ...
