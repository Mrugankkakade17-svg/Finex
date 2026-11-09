import {
  CONSENT_VERSION,
  onboardingContract,
  OnboardingContractError,
  PROFILE_SCHEMA_VERSION,
  setOnboardingClientForTests,
} from './onboardingContract';

const correlationId = 'r0-int-react-api-0001';
const initialMode = process.env.REACT_APP_ONBOARDING_MODE;
const initialBaseUrl = process.env.REACT_APP_FINEX_API_BASE_URL;
const initialFetch = global.fetch;

function restoreEnvironment(name: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[name];
    return;
  }
  process.env[name] = value;
}

beforeEach(() => {
  process.env.REACT_APP_ONBOARDING_MODE = 'api';
  process.env.REACT_APP_FINEX_API_BASE_URL = 'http://127.0.0.1:8000';
  setOnboardingClientForTests();
});

afterEach(() => {
  restoreEnvironment('REACT_APP_ONBOARDING_MODE', initialMode);
  restoreEnvironment('REACT_APP_FINEX_API_BASE_URL', initialBaseUrl);
  global.fetch = initialFetch;
  setOnboardingClientForTests();
});

describe('onboardingContract API adapter', () => {
  test('maps the FastAPI consent envelope into the typed client result', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        message: 'Consent recorded',
        data: {
          consent_version: CONSENT_VERSION,
          consent_status: 'accepted',
          recorded_at: '2026-10-10T00:00:00Z',
        },
      }),
    });
    global.fetch = fetchMock as typeof global.fetch;

    await expect(
      onboardingContract.captureConsent({
        correlationId,
        consentVersion: CONSENT_VERSION,
        consentGiven: true,
      })
    ).resolves.toEqual({
      consentVersion: CONSENT_VERSION,
      consentStatus: 'accepted',
      recordedAt: '2026-10-10T00:00:00Z',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/onboarding-contract/consent',
      expect.objectContaining({
        headers: expect.objectContaining({ 'X-Correlation-ID': correlationId }),
      })
    );
  });

  test('keeps the server error code visible to the UI retry state', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        success: false,
        message: 'Consent version is not supported.',
        error_code: 'UNSUPPORTED_CONSENT_VERSION',
      }),
    });
    global.fetch = fetchMock as typeof global.fetch;

    await expect(
      onboardingContract.captureConsent({
        correlationId,
        consentVersion: 'consent.v999',
        consentGiven: true,
      })
    ).rejects.toMatchObject<Partial<OnboardingContractError>>({
      code: 'UNSUPPORTED_CONSENT_VERSION',
      message: 'Consent version is not supported.',
    });
  });

  test('maps profile and completion envelopes before exposing them to the UI', async () => {
    const fetchMock = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Profile recorded',
          data: {
            profile_schema_version: PROFILE_SCHEMA_VERSION,
            profile_state: 'completed',
            display_name: 'Local Test',
            experience_level: 'beginner',
            recorded_at: '2026-10-10T00:00:01Z',
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          success: true,
          message: 'Onboarding completed',
          data: {
            onboarding_completed: true,
            consent_version: CONSENT_VERSION,
            profile_schema_version: PROFILE_SCHEMA_VERSION,
            fixture_mode: null,
            recorded_at: '2026-10-10T00:00:02Z',
          },
        }),
      });
    global.fetch = fetchMock as typeof global.fetch;

    await expect(
      onboardingContract.submitProfile({
        correlationId,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
        displayName: 'Local Test',
        experienceLevel: 'beginner',
      })
    ).resolves.toEqual({
      profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      profileState: 'completed',
      displayName: 'Local Test',
      experienceLevel: 'beginner',
      recordedAt: '2026-10-10T00:00:01Z',
    });

    await expect(
      onboardingContract.completeOnboarding({
        correlationId,
        consentVersion: CONSENT_VERSION,
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      })
    ).resolves.toEqual({
      onboardingCompleted: true,
      consentVersion: CONSENT_VERSION,
      profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      fixtureMode: null,
      recordedAt: '2026-10-10T00:00:02Z',
    });
  });
});
