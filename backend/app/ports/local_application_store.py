"""Typed transactional port shared by S1 and later owned domain services."""

from datetime import datetime
from typing import Protocol

from app.domain.local_application import (
    LocalSession,
    LocalUser,
    OnboardingRecord,
)
from app.ports.local_authorization import AuthorizationTransaction, TransactionStore


class LocalApplicationTransaction(AuthorizationTransaction, Protocol):
    def get_user_by_alias(self, alias: str) -> LocalUser | None: ...

    def create_user(self, user: LocalUser, profile_version: str, now: datetime) -> None: ...

    def insert_session(self, session: LocalSession, now: datetime) -> None: ...

    def revoke_session(self, digest: str, user_id: str, now: datetime) -> None: ...

    def save_onboarding(self, record: OnboardingRecord) -> None: ...

    def append_consent(self, user_id: str, version: str, accepted: bool, now: datetime) -> None: ...


class LocalApplicationStore(TransactionStore[LocalApplicationTransaction], Protocol):
    pass
