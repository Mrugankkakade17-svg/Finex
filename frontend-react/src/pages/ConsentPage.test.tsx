import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { ConsentPage } from './ConsentPage';
import {
  CONSENT_VERSION,
  ConsentResult,
  OnboardingContractClient,
  resetFixtureJourneysForTests,
  setOnboardingClientForTests,
} from '../services/onboardingContract';
import { clearOnboardingJourney } from '../services/onboardingJourneyStorage';

function renderConsentPage(): void {
  render(
    <MemoryRouter initialEntries={['/consent']}>
      <Routes>
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/onboarding" element={<p>Profile route reached</p>} />
      </Routes>
    </MemoryRouter>
  );
}

function client(overrides: Partial<OnboardingContractClient> = {}): OnboardingContractClient {
  return {
    captureConsent: async () => ({
      consentVersion: CONSENT_VERSION,
      consentStatus: 'accepted',
      recordedAt: '2026-10-10T00:00:00Z',
    }),
    submitProfile: async () => {
      throw new Error('not used');
    },
    completeOnboarding: async () => {
      throw new Error('not used');
    },
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

describe('ConsentPage', () => {
  test('requires an explicit consent choice before profile can be reached', () => {
    renderConsentPage();

    expect(screen.getByRole('button', { name: /continue to profile/i })).toBeDisabled();
    expect(screen.getByTestId('onboarding-integration-mode')).toHaveTextContent('Fixture mode');
  });

  test('records consent with the v1 contract and advances to the profile route', async () => {
    const captureConsent = jest.fn(client().captureConsent);
    setOnboardingClientForTests(client({ captureConsent }));
    renderConsentPage();

    fireEvent.click(screen.getByLabelText(/i understand and agree/i));
    fireEvent.click(screen.getByRole('button', { name: /continue to profile/i }));

    await waitFor(() => expect(screen.getByText('Profile route reached')).toBeInTheDocument());
    expect(captureConsent).toHaveBeenCalledWith(
      expect.objectContaining({ consentVersion: CONSENT_VERSION, consentGiven: true })
    );
  });

  test('shows a retry state when the contract call fails', async () => {
    setOnboardingClientForTests(
      client({ captureConsent: async () => Promise.reject(new Error('Local API is unavailable')) })
    );
    renderConsentPage();

    fireEvent.click(screen.getByLabelText(/i understand and agree/i));
    fireEvent.click(screen.getByRole('button', { name: /continue to profile/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Local API is unavailable');
    expect(screen.getByRole('button', { name: /retry consent/i })).toBeEnabled();
  });

  test('exposes a disabled, busy state while consent is being recorded', async () => {
    let resolveConsent: (result: ConsentResult) => void = () => undefined;
    const pendingConsent = new Promise<ConsentResult>((resolve) => {
      resolveConsent = resolve;
    });
    setOnboardingClientForTests(client({ captureConsent: async () => pendingConsent }));
    renderConsentPage();

    fireEvent.click(screen.getByLabelText(/i understand and agree/i));
    fireEvent.click(screen.getByRole('button', { name: /continue to profile/i }));

    const action = screen.getByRole('button', { name: /recording consent/i });
    expect(action).toBeDisabled();
    expect(action).toHaveAttribute('aria-busy', 'true');

    resolveConsent({
      consentVersion: CONSENT_VERSION,
      consentStatus: 'accepted',
      recordedAt: '2026-10-10T00:00:00Z',
    });
    await waitFor(() => expect(screen.getByText('Profile route reached')).toBeInTheDocument());
  });
});
