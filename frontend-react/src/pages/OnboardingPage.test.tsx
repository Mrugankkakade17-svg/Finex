import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import { OnboardingPage } from './OnboardingPage';
import {
  CONSENT_VERSION,
  OnboardingContractClient,
  PROFILE_SCHEMA_VERSION,
  resetFixtureJourneysForTests,
  setOnboardingClientForTests,
} from '../services/onboardingContract';
import {
  clearOnboardingJourney,
  onboardingStorageKeyForTests,
  saveOnboardingJourney,
} from '../services/onboardingJourneyStorage';

const consentedJourney = {
  contractVersion: 1 as const,
  correlationId: 'profile-page-test-1',
  integrationMode: 'fixture' as const,
  consentRecorded: true,
  completed: false,
};

function renderOnboarding(): void {
  render(
    <MemoryRouter initialEntries={['/onboarding']}>
      <OnboardingPage />
    </MemoryRouter>,
  );
}

function client(overrides: Partial<OnboardingContractClient> = {}): OnboardingContractClient {
  return {
    captureConsent: async () => {
      throw new Error('not used');
    },
    submitProfile: async (input) => ({
      profileSchemaVersion: input.profileSchemaVersion,
      profileState: 'completed',
      displayName: input.displayName,
      experienceLevel: input.experienceLevel,
      recordedAt: '2026-10-10T00:00:00Z',
    }),
    completeOnboarding: async () => ({
      onboardingCompleted: true,
      consentVersion: CONSENT_VERSION,
      profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      fixtureMode: 's1_dat_01',
      recordedAt: '2026-10-10T00:00:01Z',
    }),
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  clearOnboardingJourney();
  resetFixtureJourneysForTests();
});

afterEach(() => {
  setOnboardingClientForTests();
});

describe('OnboardingPage', () => {
  test('does not expose the profile form until consent is recorded', () => {
    renderOnboarding();

    expect(screen.getByText('Consent is required first')).toBeInTheDocument();
    expect(screen.queryByLabelText('Display label')).not.toBeInTheDocument();
  });

  test('explains a missing display label and focuses it instead of silently ignoring a click', () => {
    saveOnboardingJourney(consentedJourney);
    const submitProfile = jest.fn(client().submitProfile);
    const completeOnboarding = jest.fn(client().completeOnboarding);
    setOnboardingClientForTests(client({ submitProfile, completeOnboarding }));
    renderOnboarding();

    fireEvent.click(screen.getByLabelText(/beginner/i));
    const action = screen.getByRole('button', { name: /complete onboarding/i });
    expect(action).toBeEnabled();
    fireEvent.click(action);

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Enter a display label before completing onboarding.',
    );
    expect(screen.getByLabelText('Display label')).toHaveFocus();
    expect(screen.getByLabelText('Display label')).toHaveAttribute('aria-invalid', 'true');
    expect(action).toHaveAccessibleDescription(/both fields are required/i);
    expect(submitProfile).not.toHaveBeenCalled();
    expect(completeOnboarding).not.toHaveBeenCalled();
  });

  test('explains a missing experience level and focuses its first choice', () => {
    saveOnboardingJourney(consentedJourney);
    const submitProfile = jest.fn(client().submitProfile);
    setOnboardingClientForTests(client({ submitProfile }));
    renderOnboarding();
    fireEvent.change(screen.getByLabelText('Display label'), {
      target: { value: 'Local Tester' },
    });
    fireEvent.click(screen.getByRole('button', { name: /complete onboarding/i }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Select an experience level before completing onboarding.',
    );
    expect(screen.getByLabelText(/beginner/i)).toHaveFocus();
    expect(screen.getByRole('group', { name: /experience level/i })).toHaveAttribute(
      'aria-invalid',
      'true',
    );
    expect(submitProfile).not.toHaveBeenCalled();
  });

  test('rejects a whitespace-only label without sending a profile request', () => {
    saveOnboardingJourney(consentedJourney);
    const submitProfile = jest.fn(client().submitProfile);
    setOnboardingClientForTests(client({ submitProfile }));
    renderOnboarding();
    fireEvent.change(screen.getByLabelText('Display label'), {
      target: { value: '   ' },
    });
    fireEvent.click(screen.getByLabelText(/beginner/i));
    fireEvent.click(screen.getByRole('button', { name: /complete onboarding/i }));

    expect(screen.getByRole('alert')).toHaveTextContent('Enter a display label');
    expect(screen.getByLabelText('Display label')).toHaveFocus();
    expect(submitProfile).not.toHaveBeenCalled();
  });

  test('disables the action only while saving and prevents duplicate submissions', async () => {
    saveOnboardingJourney(consentedJourney);
    let finishProfile:
      | ((value: Awaited<ReturnType<OnboardingContractClient['submitProfile']>>) => void)
      | undefined;
    const submitProfile = jest.fn(
      () =>
        new Promise<Awaited<ReturnType<OnboardingContractClient['submitProfile']>>>((resolve) => {
          finishProfile = resolve;
        }),
    );
    setOnboardingClientForTests(client({ submitProfile }));
    renderOnboarding();
    fireEvent.change(screen.getByLabelText('Display label'), {
      target: { value: 'Local Tester' },
    });
    fireEvent.click(screen.getByLabelText(/beginner/i));
    fireEvent.click(screen.getByRole('button', { name: /complete onboarding/i }));

    const savingAction = screen.getByRole('button', { name: /saving profile/i });
    expect(savingAction).toBeDisabled();
    expect(savingAction).toHaveAttribute('aria-busy', 'true');
    fireEvent.click(savingAction);
    expect(submitProfile).toHaveBeenCalledTimes(1);
    finishProfile?.({
      profileSchemaVersion: PROFILE_SCHEMA_VERSION,
      profileState: 'completed',
      displayName: 'Local Tester',
      experienceLevel: 'beginner',
      recordedAt: '2026-10-10T00:00:00Z',
    });
    await screen.findByText('Your local completion state is saved');
  });

  test('completes a typed profile journey and persists the local completion state', async () => {
    saveOnboardingJourney(consentedJourney);
    const submitProfile = jest.fn(client().submitProfile);
    const completeOnboarding = jest.fn(client().completeOnboarding);
    setOnboardingClientForTests(client({ submitProfile, completeOnboarding }));
    renderOnboarding();

    fireEvent.change(screen.getByLabelText('Display label'), {
      target: { value: 'Local Tester' },
    });
    fireEvent.click(screen.getByLabelText(/intermediate/i));
    fireEvent.click(screen.getByRole('button', { name: /complete onboarding/i }));

    await waitFor(() => {
      expect(screen.getByText('Your local completion state is saved')).toBeInTheDocument();
    });
    expect(submitProfile).toHaveBeenCalledWith(
      expect.objectContaining({
        profileSchemaVersion: PROFILE_SCHEMA_VERSION,
        experienceLevel: 'intermediate',
      }),
    );
    expect(completeOnboarding).toHaveBeenCalledWith(
      expect.objectContaining({ consentVersion: CONSENT_VERSION }),
    );
    expect(localStorage.getItem(onboardingStorageKeyForTests())).toContain('"completed":true');
  });

  test('keeps input visible and offers retry after an API failure', async () => {
    saveOnboardingJourney(consentedJourney);
    setOnboardingClientForTests(
      client({ submitProfile: async () => Promise.reject(new Error('API service unavailable')) }),
    );
    renderOnboarding();

    fireEvent.change(screen.getByLabelText('Display label'), {
      target: { value: 'Local Tester' },
    });
    fireEvent.click(screen.getByLabelText(/beginner/i));
    fireEvent.click(screen.getByRole('button', { name: /complete onboarding/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('API service unavailable');
    expect(screen.getByRole('button', { name: /retry submission/i })).toBeEnabled();
    expect(screen.getByLabelText('Display label')).toBeInTheDocument();
  });
});
