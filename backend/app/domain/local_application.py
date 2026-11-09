"""Immutable S1 records. No transport or database dependency belongs here."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def __call__(self) -> datetime: ...


@dataclass(frozen=True)
class LocalUser:
    id: str
    alias: str


@dataclass(frozen=True)
class LocalSession:
    digest: str
    user: LocalUser
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class OnboardingRecord:
    user_id: str
    profile_schema_version: str
    display_name: str | None
    experience_level: str | None
    updated_at: datetime | None
    completed_at: datetime | None


@dataclass(frozen=True)
class ConsentRecord:
    event_id: int
    user_id: str
    version: str
    accepted: bool
    recorded_at: datetime


class LocalStoreUnavailable(Exception):
    """Opaque adapter failure; public messages must not include its cause."""
