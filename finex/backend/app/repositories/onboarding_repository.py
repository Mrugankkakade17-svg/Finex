from typing import Any


class OnboardingRepository:
    """
    Repository for onboarding and consent state.

    Current implementation is in-memory and can later be backed
    by the OperationalStore/Lakebase adapter.
    """

    def __init__(self):
        self._onboarding: dict[int, dict[str, Any]] = {}

    def complete_onboarding(
        self,
        user_id: int,
        consent_given: bool,
    ) -> dict[str, Any]:

        record = {
            "user_id": user_id,
            "onboarding_completed": True,
            "consent_given": consent_given,
        }

        self._onboarding[user_id] = record

        return record

    def get_onboarding(self, user_id: int) -> dict[str, Any] | None:
        return self._onboarding.get(user_id)


onboarding_repository = OnboardingRepository()
