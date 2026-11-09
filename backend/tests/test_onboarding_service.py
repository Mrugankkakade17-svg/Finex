import pytest

from app.core.exceptions import BadRequestException
from app.repositories.onboarding_repository import OnboardingRepository
from app.services import onboarding_service


def test_complete_onboarding_with_consent(monkeypatch):
    repository = OnboardingRepository()

    monkeypatch.setattr(
        onboarding_service,
        "onboarding_repository",
        repository,
    )

    result = onboarding_service.complete_onboarding(
        user_id=1,
        consent_given=True,
    )

    assert result["user_id"] == 1
    assert result["onboarding_completed"] is True
    assert result["consent_given"] is True


def test_complete_onboarding_without_consent(monkeypatch):
    repository = OnboardingRepository()

    monkeypatch.setattr(
        onboarding_service,
        "onboarding_repository",
        repository,
    )

    with pytest.raises(BadRequestException) as exc:
        onboarding_service.complete_onboarding(
            user_id=1,
            consent_given=False,
        )

    assert exc.value.error_code == "CONSENT_REQUIRED"
