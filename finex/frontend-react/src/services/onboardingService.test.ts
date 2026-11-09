import { onboardingService } from './onboardingService';

describe('onboardingService', () => {
  const validRequest = {
    preferredCurrency: 'USD',
    answers: {
      timeHorizon: 'LONG_TERM',
      lossReaction: 'HOLD',
      investmentGoal: 'GROWTH',
      riskComfort: 'HIGH',
      experience: 'INTERMEDIATE',
    },
  };

  test('returns successful onboarding response for valid data', async () => {
    const response = await onboardingService.submitOnboarding(validRequest);

    expect(response.saved).toBe(true);
    expect(response.preferredCurrency).toBe('USD');
    expect(response.riskProfile).toBe('MODERATE');
  });

  test('rejects onboarding when preferred currency is missing', async () => {
    const invalidRequest = {
      ...validRequest,
      preferredCurrency: '',
    };

    await expect(
      onboardingService.submitOnboarding(invalidRequest)
    ).rejects.toThrow('All onboarding fields are required.');
  });

  test('rejects onboarding when a questionnaire answer is missing', async () => {
    const invalidRequest = {
      ...validRequest,
      answers: {
        ...validRequest.answers,
        experience: '',
      },
    };

    await expect(
      onboardingService.submitOnboarding(invalidRequest)
    ).rejects.toThrow('All onboarding fields are required.');
  });
});