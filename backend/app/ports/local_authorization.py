"""Narrow authorization reads and a typed, shared unit-of-work boundary."""

from contextlib import AbstractContextManager
from typing import Protocol, TypeVar

from app.domain.local_application import ConsentRecord, LocalSession, OnboardingRecord


class AuthorizationTransaction(Protocol):
    def get_session(self, digest: str) -> LocalSession | None: ...

    def get_onboarding(self, user_id: str) -> OnboardingRecord: ...

    def latest_consent(self, user_id: str) -> ConsentRecord | None: ...


Transaction_co = TypeVar("Transaction_co", bound=AuthorizationTransaction, covariant=True)


class TransactionStore(Protocol[Transaction_co]):
    def transaction(self, *, write: bool = False) -> AbstractContextManager[Transaction_co]: ...
