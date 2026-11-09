"""Shared-policy regressions for typed, same-unit S1/S2 authorization."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Iterator

import pytest

from app.core.exceptions import FinExException
from app.domain.local_application import ConsentRecord, LocalSession, LocalUser, OnboardingRecord
from app.schemas.consent_profile import (
    SUPPORTED_CONSENT_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
)
from app.services.local_authorization import authorized_transaction, digest_token, utc_now

NOW = datetime(2026, 10, 11, 16, 0, tzinfo=timezone.utc)
TOKEN = "a" * 43


class NarrowTransaction:
    def __init__(self) -> None:
        self.active = False
        self.session: LocalSession | None = LocalSession(
            digest_token(TOKEN),
            LocalUser("synthetic-owner", "learner-a"),
            NOW + timedelta(minutes=30),
            None,
        )
        self.profile = OnboardingRecord(
            "synthetic-owner",
            SUPPORTED_PROFILE_SCHEMA_VERSION,
            "Synthetic learner",
            "beginner",
            NOW,
            NOW,
        )
        self.consent: ConsentRecord | None = ConsentRecord(
            1, "synthetic-owner", SUPPORTED_CONSENT_VERSION, True, NOW
        )
        self.owned_writes = 0

    def get_session(self, digest: str) -> LocalSession | None:
        assert self.active
        return self.session if self.session is not None and digest == self.session.digest else None

    def get_onboarding(self, user_id: str) -> OnboardingRecord:
        assert self.active and user_id == self.profile.user_id
        return self.profile

    def latest_consent(self, user_id: str) -> ConsentRecord | None:
        assert self.active and user_id == self.profile.user_id
        return self.consent

    def owned_write(self) -> None:
        # This domain capability is not part of S1's mutation port.
        assert self.active
        self.owned_writes += 1


class NarrowStore:
    def __init__(self) -> None:
        self.unit = NarrowTransaction()
        self.calls: list[bool] = []
        self.committed = False

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[NarrowTransaction]:
        self.calls.append(write)
        self.unit.active = True
        try:
            yield self.unit
            self.committed = True
        finally:
            self.unit.active = False


def test_authorization_yields_original_concrete_capability_inside_one_write_unit() -> None:
    store = NarrowStore()

    def clock() -> datetime:
        assert store.unit.active
        return NOW

    with authorized_transaction(store, TOKEN, clock, write=True, onboarding_required=True) as (
        session,
        transaction,
    ):
        assert session is store.unit.session
        assert transaction is store.unit
        transaction.owned_write()
        assert not store.committed
    assert store.calls == [True]
    assert store.committed and not store.unit.active
    assert store.unit.owned_writes == 1


@pytest.mark.parametrize("token", ["", "a" * 42, "a" * 44, "!" * 43, "a" * 42 + " "])
def test_malformed_token_never_opens_store_or_calls_clock(token: str) -> None:
    store = NarrowStore()

    def clock() -> datetime:
        pytest.fail("Malformed credentials must not reach the clock or store.")

    with pytest.raises(FinExException) as caught:
        with authorized_transaction(store, token, clock):
            pytest.fail("An unauthorized unit must not be yielded.")
    assert caught.value.status_code == 401 and caught.value.error_code == "SESSION_INVALID"
    assert store.calls == []


@pytest.mark.parametrize("state", ["missing", "revoked", "expired", "past"])
def test_session_failures_roll_back_without_yielding_a_domain_unit(state: str) -> None:
    store = NarrowStore()
    assert store.unit.session is not None
    if state == "missing":
        store.unit.session = None
    elif state == "revoked":
        store.unit.session = replace(store.unit.session, revoked_at=NOW)
    else:
        expiry = NOW if state == "expired" else NOW - timedelta(microseconds=1)
        store.unit.session = replace(store.unit.session, expires_at=expiry)
    with pytest.raises(FinExException) as caught:
        with authorized_transaction(store, TOKEN, lambda: NOW, write=True):
            pytest.fail("An unauthorized unit must not be yielded.")
    assert caught.value.status_code == 401 and caught.value.error_code == "SESSION_INVALID"
    assert store.calls == [True] and not store.committed and not store.unit.active


@pytest.mark.parametrize(
    "prerequisite",
    [
        "incomplete",
        "old-profile",
        "no-label",
        "no-experience",
        "no-consent",
        "withdrawn",
        "old-consent",
    ],
)
def test_current_onboarding_is_rechecked_in_the_owned_unit(prerequisite: str) -> None:
    store = NarrowStore()
    if prerequisite == "incomplete":
        store.unit.profile = replace(store.unit.profile, completed_at=None)
    elif prerequisite == "old-profile":
        store.unit.profile = replace(store.unit.profile, profile_schema_version="v0")
    elif prerequisite == "no-label":
        store.unit.profile = replace(store.unit.profile, display_name=None)
    elif prerequisite == "no-experience":
        store.unit.profile = replace(store.unit.profile, experience_level=None)
    elif prerequisite == "no-consent":
        store.unit.consent = None
    else:
        assert store.unit.consent is not None
        store.unit.consent = replace(
            store.unit.consent,
            accepted=prerequisite != "withdrawn",
            version="v0" if prerequisite == "old-consent" else SUPPORTED_CONSENT_VERSION,
        )
    with pytest.raises(FinExException) as caught:
        with authorized_transaction(store, TOKEN, lambda: NOW, onboarding_required=True):
            pytest.fail("An incomplete unit must not be yielded.")
    assert caught.value.status_code == 409 and caught.value.error_code == "ONBOARDING_REQUIRED"
    assert not store.committed and not store.unit.active


def test_s1_operations_may_authorize_before_onboarding_is_completed() -> None:
    store = NarrowStore()
    store.unit.profile = replace(store.unit.profile, completed_at=None)
    with authorized_transaction(store, TOKEN, lambda: NOW) as (_, transaction):
        assert transaction is store.unit
    assert store.calls == [False] and store.committed


@pytest.mark.parametrize(
    "now",
    [NOW.replace(tzinfo=None), NOW.astimezone(timezone(timedelta(hours=1)))],
)
def test_utc_clock_requires_an_aware_zero_offset(now: datetime) -> None:
    with pytest.raises(ValueError, match="UTC-aware"):
        utc_now(lambda: now)


def test_valid_utc_clock_is_not_replaced_with_a_new_wall_clock_time() -> None:
    assert utc_now(lambda: NOW) is NOW
