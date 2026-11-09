import { IntegrationMode } from './onboardingContract';

const STORAGE_KEY = 'finex_s1_onboarding_journey_v1';

export interface StoredOnboardingJourney {
  contractVersion: 1;
  correlationId: string;
  integrationMode: IntegrationMode;
  consentRecorded: boolean;
  completed: boolean;
  completedAt?: string;
}

function createCorrelationId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `web-${crypto.randomUUID()}`;
  }
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function loadOnboardingJourney(): StoredOnboardingJourney | null {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) {
    return null;
  }
  try {
    const journey = JSON.parse(saved) as StoredOnboardingJourney;
    if (journey.contractVersion !== 1 || !journey.correlationId) {
      throw new Error('Invalid journey shape');
    }
    return journey;
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function ensureOnboardingJourney(
  integrationMode: IntegrationMode
): StoredOnboardingJourney {
  const existing = loadOnboardingJourney();
  if (existing && !existing.completed && existing.integrationMode === integrationMode) {
    return existing;
  }
  const journey: StoredOnboardingJourney = {
    contractVersion: 1,
    correlationId: createCorrelationId(),
    integrationMode,
    consentRecorded: false,
    completed: false,
  };
  saveOnboardingJourney(journey);
  return journey;
}

export function saveOnboardingJourney(journey: StoredOnboardingJourney): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(journey));
}

export function clearOnboardingJourney(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function onboardingStorageKeyForTests(): string {
  return STORAGE_KEY;
}
