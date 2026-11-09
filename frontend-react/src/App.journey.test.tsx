import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';
import { LocalApplicationError, LocalOnboardingState } from './services/localApplicationClient';
import { completedState, deferred, journeyClientMock, stateDto } from './testHelpers/localApplication';

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); window.history.replaceState({}, '', '/login');
});
async function enterOnboarding(client: ReturnType<typeof journeyClientMock>['client']) {
  render(<App client={client} />);
  fireEvent.click(screen.getByRole('button', { name: 'Sign in as learner-a' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
}
async function acceptNotice() {
  fireEvent.click(screen.getByRole('checkbox', { name: /I accept the educational notice/i }));
  fireEvent.click(screen.getByRole('button', { name: 'Save consent choice' }));
  await screen.findByText(/Current notice accepted/i);
}
function fillProfile(label = 'Synthetic tester') {
  fireEvent.change(screen.getByRole('textbox', { name: 'Display label' }), { target: { value: label } });
  fireEvent.click(screen.getByRole('radio', { name: /Beginner/i }));
}
test('onboarding explicitly records consent, saves a profile and confirms server completion', async () => {
  const { client } = journeyClientMock();
  await enterOnboarding(client);
  expect(screen.getByRole('checkbox', { name: /I accept the educational notice/i })).not.toBeChecked();
  await acceptNotice();
  fillProfile();
  fireEvent.click(screen.getByRole('button', { name: 'Complete onboarding' }));
  await screen.findByRole('heading', { name: 'Your learning space' });
  expect(screen.getByText('Synthetic tester')).toBeInTheDocument();
  expect(client.saveDraft.mock.calls.length).toBe(1);
  expect(client.complete.mock.calls.length).toBe(1);
});
test('a nullable partial draft can be saved without manufacturing completion', async () => {
  const { client } = journeyClientMock();
  await enterOnboarding(client);
  fireEvent.change(screen.getByRole('textbox', { name: 'Display label' }), { target: { value: 'Partial learner' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByText(/Draft saved on the local backend/i);
  const payload = client.saveDraft.mock.calls[0]?.[1];
  expect(payload).toEqual({ display_name: 'Partial learner', experience_level: null });
  expect(client.complete.mock.calls.length).toBe(0);
  expect(screen.getByRole('heading', { name: 'Your local onboarding' })).toBeInTheDocument();
});
test('failed save retains profile input and never submits completion', async () => {
  const { client } = journeyClientMock();
  client.saveDraft.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
  await enterOnboarding(client);
  await acceptNotice();
  fillProfile('Keep this label');
  fireEvent.click(screen.getByRole('button', { name: 'Complete onboarding' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveValue('Keep this label');
  expect(screen.getByRole('radio', { name: /Beginner/i })).toBeChecked();
  expect(client.complete.mock.calls.length).toBe(0);
  expect(screen.queryByRole('heading', { name: 'Your learning space' })).not.toBeInTheDocument();
});
test.each(['consent', 'save', 'complete'] as const)(
  'an async %s failure focuses visible feedback and preserves retryable inputs', async (operation) => {
    const { client } = journeyClientMock();
    const scroll = jest.fn();
    const previousScroll = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'scrollIntoView');
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scroll });
    try {
      await enterOnboarding(client);
      fillProfile('Retain my unsaved label');
      if (operation === 'consent') {
        client.setConsent.mockRejectedValueOnce(new LocalApplicationError('API_UNAVAILABLE'));
        fireEvent.click(screen.getByRole('checkbox', { name: /I accept the educational notice/i }));
        fireEvent.click(screen.getByRole('button', { name: 'Save consent choice' }));
      } else {
        await acceptNotice();
        if (operation === 'save') client.saveDraft.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
        else client.complete.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
        fireEvent.click(screen.getByRole('button', { name: operation === 'save' ? 'Save draft' : 'Complete onboarding' }));
      }
      const alert = await screen.findByRole('alert');
      await waitFor(() => expect(alert).toHaveFocus());
      expect(scroll).toHaveBeenCalledWith(expect.objectContaining({ block: 'center', behavior: 'auto' }));
      expect(scroll.mock.instances.some((instance) => instance === alert)).toBe(true);
      expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveValue('Retain my unsaved label');
      expect(screen.getByRole('radio', { name: /Beginner/i })).toBeChecked();
      expect(screen.queryByRole('heading', { name: 'Your learning space' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: operation === 'consent' ? 'Save consent choice' :
        operation === 'save' ? 'Save draft' : 'Complete onboarding' })).toBeEnabled();
      const field = screen.getByRole('textbox', { name: 'Display label' });
      const initialScrolls = scroll.mock.calls.length;
      field.focus();
      fireEvent.change(field, { target: { value: 'Continue editing after failure' } });
      expect(field).toHaveFocus();
      expect(field).toHaveValue('Continue editing after failure');
      expect(scroll.mock.calls.length).toBe(initialScrolls);
    } finally {
      if (previousScroll) Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', previousScroll);
      else delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView;
    }
  },
);
test('failed logout preserves dirty inputs with an explicit retry instead of claiming sign-out', async () => {
  const { client } = journeyClientMock();
  client.logout.mockRejectedValueOnce(new LocalApplicationError('API_UNAVAILABLE'));
  await enterOnboarding(client);
  fillProfile('Not yet saved');
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  await screen.findByRole('button', { name: 'Retry sign out' });
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveValue('Not yet saved');
  expect(screen.getByText(/learner-a/i, { selector: '[data-testid="local-persona"]' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry sign out' }));
  await screen.findByRole('heading', { name: 'Choose a local persona' });
});
test('saved server draft resumes after a cold client remount and explicit persona selection', async () => {
  const { client } = journeyClientMock(stateDto({ draft: { display_name: 'Saved label', experience_level: 'advanced', updated_at: new Date().toISOString() } }));
  const first = render(<App client={client} />);
  expect(screen.getByRole('heading', { name: 'Choose a local persona' })).toBeInTheDocument();
  first.unmount();
  await enterOnboarding(client);
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveValue('Saved label');
  expect(screen.getByRole('radio', { name: /Advanced/i })).toBeChecked();
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});
test('a protected route rechecks server state and gates a cross-client withdrawal', async () => {
  const server = journeyClientMock(completedState());
  await enterOnboarding(server.client);
  fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));
  await screen.findByRole('heading', { name: 'Your learning space' });
  server.setState(stateDto({ consent: { accepted: false, version: 'consent.v1', recorded_at: new Date().toISOString() },
    draft: completedState().draft }));
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  await screen.findByRole('heading', { name: 'Your local onboarding' });
  expect(screen.queryByRole('heading', { name: 'Your manual portfolios' })).not.toBeInTheDocument();
  expect(screen.getByText(/Current notice not accepted/i)).toBeInTheDocument();
});
test('failed protected refresh never opens the feature from cached completion', async () => {
  const { client } = journeyClientMock(completedState());
  await enterOnboarding(client);
  client.state.mockRejectedValueOnce(new LocalApplicationError('LOCAL_STORE_UNAVAILABLE'));
  fireEvent.click(screen.getByRole('link', { name: 'Portfolio' }));
  await screen.findByRole('button', { name: 'Retry server check' });
  expect(screen.queryByRole('heading', { name: 'Your manual portfolios' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Retry server check' }));
  await screen.findByRole('heading', { name: 'Your manual portfolios' });
  expect(await screen.findByRole('alert')).toHaveTextContent('The S2 capability is unavailable on this API adapter.');
});
test('a current 401 clears the form and owner rather than retaining cached completion', async () => {
  const { client } = journeyClientMock(completedState());
  await enterOnboarding(client);
  client.me.mockRejectedValueOnce(new LocalApplicationError('SESSION_INVALID'));
  fireEvent.click(screen.getByRole('link', { name: 'Dashboard' }));
  await screen.findByRole('heading', { name: 'Choose a local persona' });
  expect(screen.queryByRole('textbox', { name: 'Display label' })).not.toBeInTheDocument();
  expect(screen.queryByTestId('local-persona')).not.toBeInTheDocument();
});
test('withdrawal and reacceptance retain draft but require explicit recompletion', async () => {
  const { client } = journeyClientMock(completedState());
  await enterOnboarding(client);
  fireEvent.click(screen.getByRole('button', { name: 'Withdraw consent' }));
  await screen.findByText(/Current notice not accepted/i);
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveValue('Synthetic learner');
  await acceptNotice();
  expect(screen.queryByRole('heading', { name: 'Your learning space' })).not.toBeInTheDocument();
  expect(client.complete.mock.calls.length).toBe(0);
  fireEvent.click(screen.getByRole('button', { name: 'Complete onboarding' }));
  await screen.findByRole('heading', { name: 'Your learning space' });
});
test('a double completion click cannot duplicate writes or navigation', async () => {
  const { client } = journeyClientMock();
  const pending = deferred<LocalOnboardingState>();
  client.saveDraft.mockImplementationOnce(() => pending.promise);
  await enterOnboarding(client);
  await acceptNotice();
  fillProfile();
  const button = screen.getByRole('button', { name: 'Complete onboarding' });
  fireEvent.click(button); fireEvent.click(button);
  expect(client.saveDraft.mock.calls.length).toBe(1);
  await act(async () => { pending.resolve(stateDto({
    draft: { display_name: 'Synthetic tester', experience_level: 'beginner', updated_at: new Date().toISOString() },
    consent: { accepted: true, version: 'consent.v1', recorded_at: new Date().toISOString() } })); });
  await waitFor(() => expect(client.complete.mock.calls.length).toBe(1));
});
test('oversized labels are rejected accessibly before calling the API', async () => {
  const { client } = journeyClientMock();
  await enterOnboarding(client);
  fillProfile('x'.repeat(81));
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await screen.findByRole('alert');
  expect(client.saveDraft.mock.calls.length).toBe(0);
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByRole('textbox', { name: 'Display label' })).toHaveFocus();
});
