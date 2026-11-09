import pytest

from app.repositories.onboarding_repository import onboarding_repository
from app.repositories.risk_repository import risk_repository
from app.repositories.user_repository import user_repository


@pytest.fixture(autouse=True)
def reset_in_memory_repositories():
    """Reset in-memory repositories before every test."""

    # Reset users
    if hasattr(user_repository, "_users"):
        user_repository._users.clear()

    if hasattr(user_repository, "_next_id"):
        user_repository._next_id = 1

    # Reset onboarding
    if hasattr(onboarding_repository, "_onboarding"):
        onboarding_repository._onboarding.clear()

    # Reset risk assessments
    if hasattr(risk_repository, "_assessments"):
        risk_repository._assessments.clear()

    if hasattr(risk_repository, "_next_assessment_id"):
        risk_repository._next_assessment_id = 1

    yield
