"""Append-only audit event emission to the application audit log."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

_EVENT_NAME = re.compile(r"[a-z][a-z0-9_.-]{1,127}\Z", re.ASCII)
_audit_logger = logging.getLogger("finex.audit")


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Allowlisted metadata for one immutable audit record."""

    event_type: str
    outcome: Literal["success", "failure", "denied"]
    correlation_id: str
    occurred_at: datetime
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        values = asdict(self)
        values["occurred_at"] = self.occurred_at.isoformat()
        return values


def _validate_optional_identifier(name: str, value: str | None) -> None:
    if value is not None and (
        not value.strip()
        or len(value) > 256
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError(f"{name} must be a non-empty single-line value of at most 256 characters")


def write_audit_event(
    *,
    event_type: str,
    correlation_id: str,
    outcome: Literal["success", "failure", "denied"] = "success",
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    occurred_at: datetime | None = None,
    logger: logging.Logger | None = None,
) -> AuditEvent:
    """Emit one redacted, append-only JSON log record and return its value.

    Only identifiers and operation outcome are accepted. Callers cannot attach
    request bodies, credentials, or arbitrary metadata to audit records.
    """
    if not _EVENT_NAME.fullmatch(event_type):
        raise ValueError("event_type must be a lowercase event name")
    if (
        not correlation_id.strip()
        or len(correlation_id) > 128
        or any(ord(character) < 32 or ord(character) == 127 for character in correlation_id)
    ):
        raise ValueError(
            "correlation_id must be a non-empty single-line value of at most 128 characters"
        )
    if outcome not in {"success", "failure", "denied"}:
        raise ValueError("outcome must be success, failure, or denied")
    _validate_optional_identifier("actor_id", actor_id)
    _validate_optional_identifier("resource_type", resource_type)
    _validate_optional_identifier("resource_id", resource_id)

    timestamp = occurred_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")

    event = AuditEvent(
        event_type=event_type,
        outcome=outcome,
        correlation_id=correlation_id,
        occurred_at=timestamp.astimezone(timezone.utc),
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    (logger or _audit_logger).info("audit_event=%s", json.dumps(event.to_dict(), sort_keys=True))
    return event
