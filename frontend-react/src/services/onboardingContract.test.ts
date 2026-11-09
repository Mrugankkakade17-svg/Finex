import {
  CONSENT_VERSION,
  onboardingContract,
  OnboardingContractError,
  PROFILE_SCHEMA_VERSION,
  resetFixtureJourneysForTests,
  setOnboardingClientForTests,
} from './onboardingContract';

const correlationId = 'react-contract-test-1';

afterEach(() => {
  resetFixtureJourneysForTests();
  setOnboardingClientForTests();
});

describe('onboardingContract fixture adapter', () => {
  test('requires consent, then completes the typed local journey', async () => {
    await expect(
      onboardingContract.submitProfile({
        correlationId,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
        displayName: 'Test Investor',
        experienceLevel: 'beginner',
      })
    ).rejects.toMatchObject({ code: 'CONSENT_MISSING' });

    await expect(
      onboardingContract.captureConsent({
        correlationId,
        consentVersion: CONSENT_VERSION,
        consentGiven: true,
      })
    ).resolves.toMatchObject({ consentStatus: 'accepted' });

    await expect(
      onboardingContract.submitProfile({
        correlationId,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
        displayName: '  Test Investor  ',
        experienceLevel: 'intermediate',
      })
    ).resolves.toMatchObject({
      displayName: 'Test Investor',
      experienceLevel: 'intermediate',
    });

    await expect(
      onboardingContract.completeOnboarding({
        correlationId,
        consentVersion: CONSENT_VERSION,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      })
    ).resolves.toMatchObject({
      onboardingCompleted: true,
      fixtureMode: 's1_dat_01',
    });
  });

  test('keeps stable contract errors for invalid input', async () => {
    await expect(
      onboardingContract.captureConsent({
        correlationId,
        consentVersion: 'consent.v999',
        consentGiven: true,
      })
    ).rejects.toMatchObject<Partial<OnboardingContractError>>({
      code: 'UNSUPPORTED_CONSENT_VERSION',
    });
  });
});
