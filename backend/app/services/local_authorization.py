"""One current S1 prerequisite check inside the caller's own transaction."""

import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator, TypeVar

from app.core.exceptions import FinExException
from app.domain.local_application import Clock, LocalSession
from app.ports.local_authorization import AuthorizationTransaction, TransactionStore
from app.schemas.consent_profile import (
    SUPPORTED_CONSENT_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
    ExperienceLevel,
)
from app.schemas.local_application import LocalConsentState, LocalDraftState, LocalOnboardingState

Transaction = TypeVar("Transaction", bound=AuthorizationTransaction)


def utc_clock() -> datetime:
    return datetime.now(timezone.utc)


def utc_now(clock: Clock) -> datetime:
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("The local application clock must return UTC-aware time.")
    return now


def session_invalid() -> FinExException:
    return FinExException(
        message="A valid local session is required.", error_code="SESSION_INVALID", status_code=401
    )


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_token(token: str) -> None:
    if len(token) != 43 or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in token
    ):
        raise session_invalid()


def onboarding_state(transaction: AuthorizationTransaction, user_id: str) -> LocalOnboardingState:
    profile = transaction.get_onboarding(user_id)
    consent = transaction.latest_consent(user_id)
    completed = bool(
        profile.completed_at
        and profile.profile_schema_version == SUPPORTED_PROFILE_SCHEMA_VERSION
        and profile.display_name
        and profile.experience_level in {"beginner", "intermediate", "advanced"}
        and consent
        and consent.accepted
        and consent.version == SUPPORTED_CONSENT_VERSION
    )
    return LocalOnboardingState(
        profile_schema_version=SUPPORTED_PROFILE_SCHEMA_VERSION,
        consent_version=SUPPORTED_CONSENT_VERSION,
        consent=LocalConsentState(
            accepted=consent.accepted,
            version=consent.version,
            recorded_at=consent.recorded_at.isoformat(),
        )
        if consent
        else None,
        draft=LocalDraftState(
            display_name=profile.display_name,
            experience_level=ExperienceLevel(profile.experience_level)
            if profile.experience_level
            else None,
            updated_at=profile.updated_at.isoformat() if profile.updated_at else None,
        ),
        onboarding_completed=completed,
        completed_at=profile.completed_at.isoformat()
        if completed and profile.completed_at
        else None,
    )


@contextmanager
def authorized_transaction(
    store: TransactionStore[Transaction],
    token: str,
    clock: Clock,
    *,
    write: bool = False,
    onboarding_required: bool = False,
) -> Iterator[tuple[LocalSession, Transaction]]:
    # Reject malformed credentials before creating even a database connection.
    validate_token(token)
    with store.transaction(write=write) as transaction:
        session = transaction.get_session(digest_token(token))
        now = utc_now(clock)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise session_invalid()
        if (
            onboarding_required
            and not onboarding_state(transaction, session.user.id).onboarding_completed
        ):
            raise FinExException(
                message="Complete current consent and onboarding before using the feature.",
                error_code="ONBOARDING_REQUIRED",
                status_code=409,
            )
        yield session, transaction
