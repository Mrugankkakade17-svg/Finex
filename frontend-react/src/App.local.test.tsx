import React from 'react';
import { render, screen } from '@testing-library/react';

import App from './App';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState({}, '', '/');
});

test('cold root starts signed out with the two approved synthetic personas', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Choose a local persona' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign in as learner-a' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign in as learner-b' })).toBeInTheDocument();
});

test('cold full application does not write legacy authentication or owner claims', () => {
  render(<App />);
  expect(localStorage.getItem('finex_is_authenticated')).toBeNull();
  expect(localStorage.getItem('finex_auth_user')).toBeNull();
});

test.each(['/dashboard', '/onboarding', '/consent', '/risk'])(
  'stored legacy authentication and completion cannot unlock %s',
  (path) => {
    localStorage.setItem('finex_is_authenticated', 'true');
    localStorage.setItem('finex_auth_user', JSON.stringify({
      userId: 'spoofed-owner', displayName: 'Spoofed', onboardingStatus: 'COMPLETED',
    }));
    localStorage.setItem('finex_s1_onboarding_journey_v1', JSON.stringify({
      contractVersion: 1, correlationId: 'legacy-test', integrationMode: 'fixture',
      consentRecorded: true, completed: true,
    }));
    window.history.replaceState({}, '', path);
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Choose a local persona' })).toBeInTheDocument();
    expect(screen.queryByText('Spoofed')).not.toBeInTheDocument();
  },
);

test('compatibility consent stays publicly reachable and visibly separated', () => {
  window.history.replaceState({}, '', '/pilot/consent');
  render(<App />);
  expect(screen.getByRole('heading', { name: 'Educational consent' })).toBeInTheDocument();
  expect(screen.getByText('Compatibility pilot — not saved to a persona')).toBeInTheDocument();
});

test('compatibility onboarding links back to pilot consent, not the owned application', () => {
  window.history.replaceState({}, '', '/pilot/onboarding');
  render(<App />);
  expect(screen.getByRole('link', { name: /review consent/i })).toHaveAttribute(
    'href', '/pilot/consent',
  );
});
test('invalid full-app origin is a safe configuration error, never a fixture fallback', () => {
  const previous = process.env.REACT_APP_FINEX_API_BASE_URL;
  process.env.REACT_APP_FINEX_API_BASE_URL = 'https://remote.example';
  try {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Choose a local persona' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(/loopback API origin/i);
    expect(screen.queryByText(/Fixture mode/i)).not.toBeInTheDocument();
  } finally {
    if (previous === undefined) delete process.env.REACT_APP_FINEX_API_BASE_URL;
    else process.env.REACT_APP_FINEX_API_BASE_URL = previous;
  }
});
