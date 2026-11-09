"""S1 application rules run against one typed, atomic unit of work."""

import secrets
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Iterator
from uuid import uuid4

from app.core.exceptions import FinExException
from app.domain.local_application import Clock, LocalSession, LocalUser
from app.ports.local_application_store import LocalApplicationStore, LocalApplicationTransaction
from app.schemas.consent_profile import (
    SUPPORTED_CONSENT_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
)
from app.schemas.local_application import (
    LocalConsentRequest,
    LocalDraftRequest,
    LocalLoginResponse,
    LocalOnboardingState,
    LocalUserResponse,
)
from app.services.local_authorization import (
    authorized_transaction,
    onboarding_state,
    utc_now,
)
from app.services.local_authorization import (
    digest_token as digest_token,
)
from app.services.local_authorization import (
    session_invalid as session_invalid,
)
from app.services.local_authorization import (
    utc_clock as utc_clock,
)

APPROVED_ALIASES = frozenset({"learner-a", "learner-b"})


def user_response(user: LocalUser) -> LocalUserResponse:
    return LocalUserResponse.model_validate({"id": user.id, "alias": user.alias})


class LocalApplicationService:
    def __init__(
        self, store: LocalApplicationStore, clock: Clock = utc_clock, session_ttl_minutes: int = 30
    ) -> None:
        if not 1 <= session_ttl_minutes <= 60:
            raise ValueError("Local session lifetime must be between 1 and 60 minutes.")
        self.store = store
        self.clock = clock
        self.session_ttl_minutes = session_ttl_minutes

    def _now(self) -> datetime:
        return utc_now(self.clock)

    @staticmethod
    def _version(value: str, supported: str, error_code: str) -> None:
        if value != supported:
            raise FinExException(
                message="The client contract version is not supported.",
                error_code=error_code,
                status_code=409,
            )

    def login(self, alias: str) -> LocalLoginResponse:
        if alias not in APPROVED_ALIASES:
            raise FinExException(
                message="Select an approved synthetic test persona.",
                error_code="UNKNOWN_LOCAL_ALIAS",
                status_code=422,
            )
        now = self._now()
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(minutes=self.session_ttl_minutes)
        with self.store.transaction(write=True) as transaction:
            user = transaction.get_user_by_alias(alias)
            if user is None:
                user = LocalUser(str(uuid4()), alias)
                transaction.create_user(user, SUPPORTED_PROFILE_SCHEMA_VERSION, now)
            transaction.insert_session(
                LocalSession(digest_token(token), user, expires_at, None), now
            )
        return LocalLoginResponse(
            access_token=token, expires_at=expires_at.isoformat(), user=user_response(user)
        )

    @contextmanager
    def authorized_transaction(
        self, token: str, *, write: bool = False, onboarding_required: bool = False
    ) -> Iterator[tuple[LocalSession, LocalApplicationTransaction]]:
        """Keep S1's public seam while sharing the same-transaction prerequisite policy."""
        with authorized_transaction(
            self.store,
            token,
            self.clock,
            write=write,
            onboarding_required=onboarding_required,
        ) as authorized:
            yield authorized

    def me(self, token: str) -> LocalUser:
        with self.authorized_transaction(token) as (session, _):
            return session.user

    def logout(self, token: str) -> None:
        with self.authorized_transaction(token, write=True) as (session, transaction):
            transaction.revoke_session(session.digest, session.user.id, self._now())

    def state(self, token: str) -> LocalOnboardingState:
        with self.authorized_transaction(token) as (session, transaction):
            return self._state(transaction, session.user.id)

    @staticmethod
    def _state(transaction: LocalApplicationTransaction, user_id: str) -> LocalOnboardingState:
        return onboarding_state(transaction, user_id)

    def draft(self, token: str, payload: LocalDraftRequest) -> LocalOnboardingState:
        with self.authorized_transaction(token, write=True) as (session, transaction):
            self._version(
                payload.profile_schema_version,
                SUPPORTED_PROFILE_SCHEMA_VERSION,
                "PROFILE_VERSION_MISMATCH",
            )
            old = transaction.get_onboarding(session.user.id)
            changed = old.display_name != payload.display_name or (
                old.experience_level != payload.experience_level
            )
            if changed or old.updated_at is None:
                transaction.save_onboarding(
                    replace(
                        old,
                        profile_schema_version=SUPPORTED_PROFILE_SCHEMA_VERSION,
                        display_name=payload.display_name,
                        experience_level=payload.experience_level,
                        updated_at=self._now(),
                        completed_at=None,
                    )
                )
            return self._state(transaction, session.user.id)

    def consent(self, token: str, payload: LocalConsentRequest) -> LocalOnboardingState:
        with self.authorized_transaction(token, write=True) as (session, transaction):
            self._version(
                payload.consent_version, SUPPORTED_CONSENT_VERSION, "CONSENT_VERSION_MISMATCH"
            )
            transaction.append_consent(
                session.user.id, payload.consent_version, payload.consent_given, self._now()
            )
            if not payload.consent_given:
                transaction.save_onboarding(
                    replace(transaction.get_onboarding(session.user.id), completed_at=None)
                )
            return self._state(transaction, session.user.id)

    def complete(
        self, token: str, consent_version: str, profile_schema_version: str
    ) -> LocalOnboardingState:
        with self.authorized_transaction(token, write=True) as (session, transaction):
            self._version(consent_version, SUPPORTED_CONSENT_VERSION, "CONSENT_VERSION_MISMATCH")
            self._version(
                profile_schema_version, SUPPORTED_PROFILE_SCHEMA_VERSION, "PROFILE_VERSION_MISMATCH"
            )
            consent = transaction.latest_consent(session.user.id)
            if consent is None or not consent.accepted or consent.version != consent_version:
                raise FinExException(
                    message="Accept the current educational consent notice.",
                    error_code="CONSENT_REQUIRED",
                    status_code=409,
                )
            profile = transaction.get_onboarding(session.user.id)
            if (
                not profile.display_name
                or profile.experience_level not in {"beginner", "intermediate", "advanced"}
                or profile.profile_schema_version != profile_schema_version
            ):
                raise FinExException(
                    message="Save the required display label and experience level.",
                    error_code="PROFILE_INCOMPLETE",
                    status_code=409,
                )
            if profile.completed_at is None:
                transaction.save_onboarding(replace(profile, completed_at=self._now()))
            return self._state(transaction, session.user.id)
