import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { LocalSessionProvider, useLocalSession } from './LocalSessionContext';
import {
  LOCAL_CONTRACT_VERSION, LOCAL_SCOPE, LocalApplicationClient, LocalApplicationError,
  LocalLogin, LocalLogout, LocalOnboardingState,
} from '../services/localApplicationClient';
import { clientMock, completedState, deferred, loginDto, stateDto } from '../testHelpers/localApplication';

function setup(client: LocalApplicationClient = clientMock()) {
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    <LocalSessionProvider client={client}>{children}</LocalSessionProvider>;
  return { client, ...renderHook(useLocalSession, { wrapper }) };
}
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });

test('cold session neither trusts legacy storage nor calls the API', () => {
  localStorage.setItem('finex_is_authenticated', 'true');
  const client = clientMock();
  const { result } = setup(client);
  expect(result.current.user).toBeNull();
  expect(result.current.onboarding).toBeNull();
  expect(client.login).not.toHaveBeenCalled();
});
test('approved login validates identity and restores only server onboarding', async () => {
  const client = clientMock();
  client.state.mockResolvedValue(completedState());
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.onboarding?.onboarding_completed).toBe(true);
  expect(client.me.mock.calls.length).toBe(1);
  expect(client.state.mock.calls.length).toBe(1);
});
test('session and credential stay out of browser storage and public context', async () => {
  const client = clientMock();
  const credential = loginDto();
  client.login.mockResolvedValue(credential);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  const leaked = JSON.stringify(result.current).includes(credential.access_token);
  expect(leaked).toBe(false);
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
  await act(async () => { await result.current.logout(); });
  expect(result.current.user).toBeNull();
  expect(result.current.onboarding).toBeNull();
});
test('login cannot silently return a different selected persona', async () => {
  const client = clientMock();
  client.login.mockResolvedValue(loginDto('learner-b'));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  expect(result.current.user).toBeNull();
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
  expect(client.me.mock.calls.length).toBe(0);
});
test('a mismatched me identity fails closed before fetching owner state', async () => {
  const client = clientMock();
  client.me.mockResolvedValue({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    user: { id: 'other-owner', alias: 'learner-a' } });
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  expect(result.current.user).toBeNull();
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
  expect(client.state.mock.calls.length).toBe(0);
});
test('invalid pilot state never becomes server completion', async () => {
  const client = clientMock();
  client.state.mockResolvedValue({ ...completedState(), scope: 'local_educational_pilot' } as unknown as LocalOnboardingState);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.onboarding).toBeNull();
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
});
test('late first-persona login cannot overwrite a later persona', async () => {
  const client = clientMock();
  const old = deferred<LocalLogin>();
  client.login.mockImplementationOnce(() => old.promise);
  const { result } = setup(client);
  let oldJob!: Promise<boolean>;
  act(() => { oldJob = result.current.login('learner-a'); });
  await act(async () => { await result.current.login('learner-b'); });
  await act(async () => { old.resolve(loginDto('learner-a')); await oldJob; });
  expect(result.current.user?.alias).toBe('learner-b');
  expect(result.current.error).toBeNull();
  const wasAborted = client.login.mock.calls[0]?.[1]?.signal?.aborted === true;
  expect(wasAborted).toBe(true);
});
test('late first-persona state 401 cannot clear the later valid session', async () => {
  const client = clientMock();
  const old = deferred<LocalOnboardingState>();
  client.state.mockImplementationOnce(() => old.promise);
  const { result } = setup(client);
  let oldJob!: Promise<boolean>;
  act(() => { oldJob = result.current.login('learner-a'); });
  await waitFor(() => expect(client.state.mock.calls.length).toBe(1));
  await act(async () => { await result.current.login('learner-b'); });
  await act(async () => { old.reject(new LocalApplicationError('SESSION_INVALID')); await oldJob; });
  expect(result.current.user?.alias).toBe('learner-b');
  expect(result.current.error).toBeNull();
});
test.each(['success', '401'])('stale mutation %s cannot affect the new owner', async (outcome) => {
  const client = clientMock();
  const old = deferred<LocalOnboardingState>();
  client.complete.mockImplementationOnce(() => old.promise);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  let oldJob!: Promise<boolean>;
  act(() => { oldJob = result.current.complete(); });
  await act(async () => { await result.current.login('learner-b'); });
  await act(async () => {
    if (outcome === '401') old.reject(new LocalApplicationError('SESSION_INVALID'));
    else old.resolve(completedState());
    await oldJob;
  });
  expect(result.current.user?.alias).toBe('learner-b');
  expect(result.current.onboarding?.onboarding_completed).toBe(false);
  expect(result.current.error).toBeNull();
});
test('failed logout retains the known session and completion for an explicit retry', async () => {
  const client = clientMock();
  client.state.mockResolvedValue(completedState());
  client.logout.mockRejectedValueOnce(new Error('untrusted network diagnostic'));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  const epoch = result.current.sessionEpoch;
  await act(async () => { await result.current.logout(); });
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.onboarding?.onboarding_completed).toBe(true);
  expect(result.current.sessionEpoch).toBe(epoch);
  expect(result.current.error?.code).toBe('API_UNAVAILABLE');
  await act(async () => { await result.current.logout(); });
  expect(result.current.user).toBeNull();
  expect(result.current.onboarding).toBeNull();
});
test('unconfirmed or malformed logout cannot claim server revocation', async () => {
  const client = clientMock();
  client.logout.mockResolvedValue({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    signed_out: false } as unknown as LocalLogout);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  await act(async () => { await result.current.logout(); });
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
});
test('late confirmed logout cannot clear a newer persona', async () => {
  const client = clientMock();
  const old = deferred<LocalLogout>();
  client.logout.mockImplementationOnce(() => old.promise);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  let oldJob!: Promise<boolean>;
  act(() => { oldJob = result.current.logout(); });
  await act(async () => { await result.current.login('learner-b'); });
  await act(async () => { old.resolve({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION, signed_out: true }); await oldJob; });
  expect(result.current.user?.alias).toBe('learner-b');
});
test('a current 401 clears every owned client state without trusting its body', async () => {
  const client = clientMock();
  client.state.mockResolvedValueOnce(completedState()).mockRejectedValueOnce(new LocalApplicationError('SESSION_INVALID'));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  await act(async () => { await result.current.refresh(); });
  expect(result.current.user).toBeNull();
  expect(result.current.onboarding).toBeNull();
  expect(result.current.error?.code).toBe('SESSION_INVALID');
});
test('unknown mutation diagnostics cannot be reflected into UI error state', async () => {
  const client = clientMock();
  const credential = loginDto();
  client.login.mockResolvedValue(credential);
  client.saveDraft.mockRejectedValue(new Error('trace.' + credential.access_token));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  await act(async () => { await result.current.saveDraft({ display_name: 'Unsaved input', experience_level: null }); });
  const reflected = String(result.current.error).includes(credential.access_token);
  expect(reflected).toBe(false);
  expect(result.current.user?.alias).toBe('learner-a');
  expect(result.current.error?.code).toBe('API_UNAVAILABLE');
});
test('duplicate completion cannot submit twice while the first call is unresolved', async () => {
  const client = clientMock();
  const pending = deferred<LocalOnboardingState>();
  client.complete.mockImplementationOnce(() => pending.promise);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  let first!: Promise<boolean>;
  act(() => { first = result.current.complete(); });
  await act(async () => { await result.current.complete(); });
  expect(client.complete.mock.calls.length).toBe(1);
  await act(async () => { pending.resolve(completedState()); await first; });
});
test('a later domain onboarding error removes the cached gate but preserves owned profile', async () => {
  const client = clientMock();
  client.state.mockResolvedValue(completedState());
  client.complete.mockRejectedValue(new LocalApplicationError('ONBOARDING_REQUIRED'));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  await act(async () => { await result.current.complete(); });
  expect(result.current.onboarding?.onboarding_completed).toBe(false);
  expect(result.current.onboarding?.completed_at).toBeNull();
  expect(result.current.onboarding?.draft.display_name).toBe('Synthetic learner');
});
test('refresh observes another client withdrawing consent instead of trusting completion cache', async () => {
  const client = clientMock();
  client.state.mockResolvedValueOnce(completedState()).mockResolvedValueOnce(stateDto({
    consent: { accepted: false, version: 'consent.v1', recorded_at: new Date().toISOString() } }));
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  await act(async () => { await result.current.refresh(); });
  expect(result.current.onboarding?.onboarding_completed).toBe(false);
  expect(result.current.onboarding?.consent?.accepted).toBe(false);
});
test('switching the injected API adapter cannot retain another adapter session or owner', async () => {
  const first = clientMock();
  const second = clientMock();
  let replace!: (adapter: LocalApplicationClient) => void;
  const Dynamic = ({ children }: { children: React.ReactNode }) => {
    const [adapter, setAdapter] = React.useState<LocalApplicationClient>(first);
    replace = setAdapter;
    return <LocalSessionProvider client={adapter}>{children}</LocalSessionProvider>;
  };
  const { result } = renderHook(useLocalSession, { wrapper: Dynamic });
  await act(async () => { await result.current.login('learner-a'); });
  act(() => { replace(second); });
  expect(result.current.user).toBeNull();
  expect(result.current.onboarding).toBeNull();
});
test('a completion endpoint returning incomplete state cannot be reported as completed', async () => {
  const client = clientMock();
  client.complete.mockResolvedValue(stateDto());
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  let confirmed = true;
  await act(async () => { confirmed = await result.current.complete(); });
  expect(confirmed).toBe(false);
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
});
test('session draft confirmation cannot be rebound by mutating the caller object', async () => {
  const client = clientMock();
  const pending = deferred<LocalOnboardingState>();
  client.saveDraft.mockImplementationOnce(() => pending.promise);
  const { result } = setup(client);
  await act(async () => { await result.current.login('learner-a'); });
  const draft: { display_name: string | null; experience_level: 'advanced' | null } = {
    display_name: 'Original label', experience_level: 'advanced' };
  let job!: Promise<boolean>;
  act(() => { job = result.current.saveDraft(draft); });
  draft.display_name = null; draft.experience_level = null;
  await act(async () => { pending.resolve(stateDto({ draft: { display_name: null, experience_level: null,
    updated_at: new Date().toISOString() } })); await job; });
  expect(result.current.error?.code).toBe('RESPONSE_INVALID');
});
test('StrictMode mount rehearsal does not mint credentials or reuse a previous mount session', async () => {
  const client = clientMock();
  const wrapper = ({ children }: { children: React.ReactNode }) => <React.StrictMode>
    <LocalSessionProvider client={client}>{children}</LocalSessionProvider>
  </React.StrictMode>;
  const first = renderHook(useLocalSession, { wrapper });
  expect(client.login.mock.calls.length).toBe(0);
  await act(async () => { await first.result.current.login('learner-a'); });
  expect(first.result.current.user?.alias).toBe('learner-a');
  first.unmount();
  const second = renderHook(useLocalSession, { wrapper });
  expect(second.result.current.user).toBeNull();
  expect(second.result.current.onboarding).toBeNull();
  expect(client.login.mock.calls.length).toBe(1);
});
test('the client expiry timer clears owned memory even before the next HTTP request', async () => {
  jest.useFakeTimers();
  try {
    const client = clientMock();
    const credential = loginDto();
    credential.expires_at = new Date(Date.now() + 1000).toISOString();
    client.login.mockResolvedValue(credential);
    const { result } = setup(client);
    await act(async () => { await result.current.login('learner-a'); });
    expect(result.current.user?.alias).toBe('learner-a');
    act(() => { jest.advanceTimersByTime(1001); });
    expect(result.current.user).toBeNull();
    expect(result.current.onboarding).toBeNull();
    expect(result.current.error?.code).toBe('SESSION_INVALID');
  } finally { jest.useRealTimers(); }
});
