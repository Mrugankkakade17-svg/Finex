/**
 * Client boundary for the Sprint 1 onboarding contract.
 *
 * The React UI calls only this module.  It can use deterministic local
 * fixtures for low-resource development or the versioned backend HTTP
 * contract, without exposing a datastore or cloud-provider dependency.
 */

export const CONSENT_VERSION = 'consent.v1';
export const PROFILE_SCHEMA_VERSION = 'profile.v1';
export const ONBOARDING_API_PATH = '/api/v1/onboarding-contract';

export type IntegrationMode = 'fixture' | 'api';
export type ExperienceLevel = 'beginner' | 'intermediate' | 'advanced';

export interface ConsentInput {
  correlationId: string;
  consentVersion: string;
  consentGiven: boolean;
}

export interface ProfileInput {
  correlationId: string;
  profileSchemaVersion: string;
  displayName: string;
  experienceLevel: ExperienceLevel;
}

export interface CompleteInput {
  correlationId: string;
  consentVersion: string;
  profileSchemaVersion: string;
}

export interface ConsentResult {
  consentVersion: string;
  consentStatus: 'accepted';
  recordedAt: string;
}

export interface ProfileResult {
  profileSchemaVersion: string;
  profileState: 'completed';
  displayName: string;
  experienceLevel: ExperienceLevel;
  recordedAt: string;
}

export interface CompleteResult {
  onboardingCompleted: true;
  consentVersion: string;
  profileSchemaVersion: string;
  fixtureMode: string | null;
  recordedAt: string;
}

export interface OnboardingContractClient {
  captureConsent(input: ConsentInput): Promise<ConsentResult>;
  submitProfile(input: ProfileInput): Promise<ProfileResult>;
  completeOnboarding(input: CompleteInput): Promise<CompleteResult>;
}

export class OnboardingContractError extends Error {
  public readonly code: string;

  constructor(message: string, code = 'ONBOARDING_REQUEST_FAILED') {
    super(message);
    this.name = 'OnboardingContractError';
    this.code = code;
  }
}

interface ApiEnvelope<T> {
  success: boolean;
  message: string;
  data?: T;
  error_code?: string;
}

interface JourneyConfig {
  mode: IntegrationMode;
  apiBaseUrl: string;
}

interface FixtureJourney {
  consentAccepted: boolean;
  profileSubmitted: boolean;
}

const fixtureJourneys = new Map<string, FixtureJourney>();
let testClient: OnboardingContractClient | undefined;

export function getJourneyConfig(): JourneyConfig {
  const configuredMode = process.env.REACT_APP_ONBOARDING_MODE?.trim().toLowerCase();
  const configuredBaseUrl = process.env.REACT_APP_FINEX_API_BASE_URL?.trim();

  return {
    mode: configuredMode === 'api' ? 'api' : 'fixture',
    apiBaseUrl: (configuredBaseUrl || 'http://127.0.0.1:8000').replace(/\/$/, ''),
  };
}

function recordedAt(): string {
  return new Date().toISOString();
}

function fixtureJourney(correlationId: string): FixtureJourney {
  const current = fixtureJourneys.get(correlationId);
  if (current) {
    return current;
  }

  const created: FixtureJourney = {
    consentAccepted: false,
    profileSubmitted: false,
  };
  fixtureJourneys.set(correlationId, created);
  return created;
}

function validateConsent(input: ConsentInput): void {
  if (input.consentVersion !== CONSENT_VERSION) {
    throw new OnboardingContractError(
      `Unsupported consent version '${input.consentVersion}'.`,
      'UNSUPPORTED_CONSENT_VERSION'
    );
  }
  if (!input.consentGiven) {
    throw new OnboardingContractError(
      'Consent must be accepted to continue.',
      'CONSENT_NOT_GIVEN'
    );
  }
}

function validateProfile(input: ProfileInput): void {
  if (input.profileSchemaVersion !== PROFILE_SCHEMA_VERSION) {
    throw new OnboardingContractError(
      `Unsupported profile version '${input.profileSchemaVersion}'.`,
      'UNSUPPORTED_PROFILE_VERSION'
    );
  }
  if (!input.displayName.trim()) {
    throw new OnboardingContractError(
      'Please enter a display name.',
      'DISPLAY_NAME_REQUIRED'
    );
  }
}

function invalidApiResponse(): never {
  throw new OnboardingContractError(
    'The local FinEx API returned an invalid onboarding response. Please retry.',
    'ONBOARDING_RESPONSE_INVALID'
  );
}

function responseRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return invalidApiResponse();
  }
  return value as Record<string, unknown>;
}

function responseString(record: Record<string, unknown>, field: string): string {
  const value = record[field];
  if (typeof value !== 'string' || !value) {
    return invalidApiResponse();
  }
  return value;
}

function decodeConsentResult(value: unknown): ConsentResult {
  const response = responseRecord(value);
  const consentStatus = responseString(response, 'consent_status');
  if (consentStatus !== 'accepted') {
    return invalidApiResponse();
  }
  return {
    consentVersion: responseString(response, 'consent_version'),
    consentStatus,
    recordedAt: responseString(response, 'recorded_at'),
  };
}

function decodeProfileResult(value: unknown): ProfileResult {
  const response = responseRecord(value);
  const profileState = responseString(response, 'profile_state');
  const experienceLevel = responseString(response, 'experience_level');
  if (
    profileState !== 'completed' ||
    !(['beginner', 'intermediate', 'advanced'] as string[]).includes(experienceLevel)
  ) {
    return invalidApiResponse();
  }
  return {
    profileSchemaVersion: responseString(response, 'profile_schema_version'),
    profileState,
    displayName: responseString(response, 'display_name'),
    experienceLevel: experienceLevel as ExperienceLevel,
    recordedAt: responseString(response, 'recorded_at'),
  };
}

function decodeCompletionResult(value: unknown): CompleteResult {
  const response = responseRecord(value);
  if (response.onboarding_completed !== true) {
    return invalidApiResponse();
  }
  const fixtureMode = response.fixture_mode;
  if (fixtureMode !== null && typeof fixtureMode !== 'string') {
    return invalidApiResponse();
  }
  return {
    onboardingCompleted: true,
    consentVersion: responseString(response, 'consent_version'),
    profileSchemaVersion: responseString(response, 'profile_schema_version'),
    fixtureMode,
    recordedAt: responseString(response, 'recorded_at'),
  };
}

const fixtureClient: OnboardingContractClient = {
  async captureConsent(input) {
    validateConsent(input);
    fixtureJourney(input.correlationId).consentAccepted = true;
    return {
      consentVersion: input.consentVersion,
      consentStatus: 'accepted',
      recordedAt: recordedAt(),
    };
  },

  async submitProfile(input) {
    validateProfile(input);
    const journey = fixtureJourney(input.correlationId);
    if (!journey.consentAccepted) {
      throw new OnboardingContractError(
        'Educational consent is required before a profile can be submitted.',
        'CONSENT_MISSING'
      );
    }
    journey.profileSubmitted = true;
    return {
      profileSchemaVersion: input.profileSchemaVersion,
      profileState: 'completed',
      displayName: input.displayName.trim(),
      experienceLevel: input.experienceLevel,
      recordedAt: recordedAt(),
    };
  },

  async completeOnboarding(input) {
    validateConsent({
      correlationId: input.correlationId,
      consentVersion: input.consentVersion,
      consentGiven: true,
    });
    if (input.profileSchemaVersion !== PROFILE_SCHEMA_VERSION) {
      throw new OnboardingContractError(
        `Unsupported profile version '${input.profileSchemaVersion}'.`,
        'UNSUPPORTED_PROFILE_VERSION'
      );
    }
    const journey = fixtureJourney(input.correlationId);
    if (!journey.consentAccepted) {
      throw new OnboardingContractError(
        'Educational consent is required before completion.',
        'CONSENT_MISSING'
      );
    }
    if (!journey.profileSubmitted) {
      throw new OnboardingContractError(
        'Please submit a profile before completing onboarding.',
        'PROFILE_MISSING'
      );
    }
    return {
      onboardingCompleted: true,
      consentVersion: input.consentVersion,
      profileSchemaVersion: input.profileSchemaVersion,
      fixtureMode: 's1_dat_01',
      recordedAt: recordedAt(),
    };
  },
};

function apiClient(config: JourneyConfig): OnboardingContractClient {
  async function request<T>(
    path: string,
    correlationId: string,
    payload: Record<string, unknown>,
    decode: (data: unknown) => T
  ): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${config.apiBaseUrl}${ONBOARDING_API_PATH}${path}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Correlation-ID': correlationId,
        },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new OnboardingContractError(
        'The local FinEx API is unavailable. Check that the backend is running, then retry.',
        'API_UNAVAILABLE'
      );
    }

    const envelope = (await response.json().catch(() => null)) as ApiEnvelope<unknown> | null;
    if (!response.ok || !envelope?.success || envelope.data === undefined) {
      throw new OnboardingContractError(
        envelope?.message || 'The onboarding request could not be completed. Please retry.',
        envelope?.error_code || 'ONBOARDING_REQUEST_FAILED'
      );
    }
    return decode(envelope.data);
  }

  return {
    captureConsent: (input) =>
      request<ConsentResult>('/consent', input.correlationId, {
        consent_version: input.consentVersion,
        consent_given: input.consentGiven,
      }, decodeConsentResult),
    submitProfile: (input) =>
      request<ProfileResult>('/profile', input.correlationId, {
        profile_schema_version: input.profileSchemaVersion,
        display_name: input.displayName,
        experience_level: input.experienceLevel,
      }, decodeProfileResult),
    completeOnboarding: (input) =>
      request<CompleteResult>('/complete', input.correlationId, {
        consent_version: input.consentVersion,
        profile_schema_version: input.profileSchemaVersion,
      }, decodeCompletionResult),
  };
}

function activeClient(): OnboardingContractClient {
  if (testClient) {
    return testClient;
  }
  const config = getJourneyConfig();
  return config.mode === 'fixture' ? fixtureClient : apiClient(config);
}

export const onboardingContract = {
  captureConsent: (input: ConsentInput) => activeClient().captureConsent(input),
  submitProfile: (input: ProfileInput) => activeClient().submitProfile(input),
  completeOnboarding: (input: CompleteInput) => activeClient().completeOnboarding(input),
};

/** Test-only hooks keep UI tests deterministic without exposing runtime toggles. */
export function setOnboardingClientForTests(client?: OnboardingContractClient): void {
  testClient = client;
}

export function resetFixtureJourneysForTests(): void {
  fixtureJourneys.clear();
}
