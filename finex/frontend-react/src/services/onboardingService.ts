export type RiskProfile =
  | 'CONSERVATIVE'
  | 'MODERATE'
  | 'AGGRESSIVE';

export interface RiskQuestionnaire {
  timeHorizon: string;
  lossReaction: string;
  investmentGoal: string;
  riskComfort: string;
  experience: string;
}

export interface OnboardingRequest {
  preferredCurrency: string;
  answers: RiskQuestionnaire;
}

export interface OnboardingResponse {
  saved: boolean;
  preferredCurrency: string;
  riskProfile: RiskProfile;
}

export const onboardingService = {
  submitOnboarding: async (
    request: OnboardingRequest
  ): Promise<OnboardingResponse> => {
    // Mock service while backend API is pending.
    await new Promise((resolve) =>
      setTimeout(resolve, 500)
    );

    // Required field validation
    if (
      !request.preferredCurrency ||
      !request.answers.timeHorizon ||
      !request.answers.lossReaction ||
      !request.answers.investmentGoal ||
      !request.answers.riskComfort ||
      !request.answers.experience
    ) {
      throw new Error(
        'All onboarding fields are required.'
      );
    }

    // Mock backend result.
    // This will be replaced by the generated API client
    // when the backend contract is available.
    const riskProfile: RiskProfile = 'MODERATE';

    return {
      saved: true,
      preferredCurrency: request.preferredCurrency,
      riskProfile,
    };
  },
};