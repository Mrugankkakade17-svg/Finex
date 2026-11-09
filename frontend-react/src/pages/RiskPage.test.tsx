import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RiskPage } from './RiskPage';
import { createRiskClient, RiskContractClient, RiskClientError } from '../services/riskContract';
import { saveOnboardingJourney } from '../services/onboardingJourneyStorage';

function renderRisk(client?: RiskContractClient): void {
  render(
    <MemoryRouter>
      <RiskPage client={client} />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  saveOnboardingJourney({
    contractVersion: 1,
    correlationId: 'web-s2-proof',
    integrationMode: 'fixture',
    consentRecorded: true,
    completed: true,
  });
});

test('requires local onboarding completion first', () => {
  localStorage.clear();
  renderRisk();
  expect(screen.getByText('Complete onboarding first')).toBeInTheDocument();
  expect(screen.queryByRole('radio')).not.toBeInTheDocument();
});

test('required selection is announced and back navigation preserves choices', async () => {
  renderRisk();
  await screen.findByText(/Question 1 of 10/);
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
  expect(screen.getByRole('alert')).toHaveTextContent(/select an option/i);
  fireEvent.click(screen.getAllByRole('radio')[2]);
  fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
  fireEvent.click(screen.getByRole('button', { name: 'Previous question' }));
  expect(screen.getAllByRole('radio')[2]).toBeChecked();
});

async function finishPreset(): Promise<void> {
  await screen.findByLabelText('Approved synthetic profile');
  fireEvent.change(screen.getByLabelText('Approved synthetic profile'), {
    target: { value: 'RISK-GOLD-004' },
  });
  for (let i = 0; i < 9; i += 1)
    fireEvent.click(screen.getByRole('button', { name: 'Next question' }));
  fireEvent.click(screen.getByRole('button', { name: 'Calculate educational profile' }));
}

test('completes, discloses method/version/time, focuses result and clears only transient answers', async () => {
  renderRisk();
  await finishPreset();
  const heading = await screen.findByRole('heading', { name: 'Your educational risk profile' });
  expect(heading).toHaveFocus();
  expect(screen.getByTestId('risk-category')).toHaveTextContent('Moderate');
  expect(screen.getByTestId('risk-composite')).toHaveTextContent('50/100');
  expect(screen.getByText(/not individualized financial/i)).toBeInTheDocument();
  expect(screen.getByText(/deterministic_v1.0.0/)).toBeInTheDocument();
  expect(localStorage.length).toBe(1);
  fireEvent.click(screen.getByRole('button', { name: 'Start a new assessment' }));
  expect(screen.getByText(/Question 1 of 10/)).toBeInTheDocument();
  expect(screen.getAllByRole('radio').every((radio) => !(radio as HTMLInputElement).checked)).toBe(
    true,
  );
});

test('failed submission retains answers and offers retry without duplicate clicks', async () => {
  const base = createRiskClient({ mode: 'fixture', apiBaseUrl: '' });
  const submit = jest
    .fn()
    .mockRejectedValueOnce(new RiskClientError('RISK_ASSESSMENT_UNAVAILABLE'))
    .mockImplementation(base.submit);
  renderRisk({ ...base, submit });
  await finishPreset();
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Retry assessment' }));
  await screen.findByRole('heading', { name: 'Your educational risk profile' });
  expect(submit).toHaveBeenCalledTimes(2);
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
});

test('loading disables submission controls until a deferred calculation finishes', async () => {
  const base = createRiskClient({ mode: 'fixture', apiBaseUrl: '' });
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  const submit = jest.fn(async (...args: Parameters<RiskContractClient['submit']>) => {
    await pending;
    return base.submit(...args);
  });
  renderRisk({ ...base, submit });
  await finishPreset();
  expect(screen.getByRole('status')).toHaveTextContent(/calculating/i);
  expect(screen.getByRole('button', { name: 'Calculate educational profile' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Previous question' })).toBeDisabled();
  release();
  await screen.findByRole('heading', { name: 'Your educational risk profile' });
  expect(submit).toHaveBeenCalledTimes(1);
});

test('questionnaire load failure offers an accessible retry', async () => {
  const base = createRiskClient({ mode: 'fixture', apiBaseUrl: '' });
  const loadQuestionnaire = jest
    .fn()
    .mockRejectedValueOnce(new RiskClientError('RISK_ASSESSMENT_UNAVAILABLE'))
    .mockImplementation(base.loadQuestionnaire);
  renderRisk({ ...base, loadQuestionnaire });
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Retry questionnaire' }));
  await screen.findByText(/Question 1 of 10/);
  expect(loadQuestionnaire).toHaveBeenCalledTimes(2);
});
