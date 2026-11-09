from app.core.exceptions import BadRequestException
from app.repositories.onboarding_repository import onboarding_repository


def complete_onboarding(
    user_id: int,
    consent_given: bool,
) -> dict:
    """Complete onboarding only when required consent is explicitly given."""

    if consent_given is not True:
        raise BadRequestException(
            message="Required consent must be accepted before completing onboarding.",
            error_code="CONSENT_REQUIRED",
        )

    return onboarding_repository.complete_onboarding(
        user_id=user_id,
        consent_given=consent_given,
    )


def get_onboarding(user_id: int) -> dict | None:
    """Return onboarding state for the authenticated user."""
    return onboarding_repository.get_onboarding(user_id)
