import { randomBytes } from 'crypto';
import {
  LOCAL_CONSENT_VERSION, LOCAL_CONTRACT_VERSION, LOCAL_PROFILE_VERSION, LOCAL_SCOPE,
  LocalAlias, LocalApplicationClient, LocalLogin, LocalOnboardingState,
} from '../services/localApplicationClient';

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (failure: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  // A rejected RED-phase deferred mock may not yet have an application consumer.
  void promise.catch(() => undefined);
  return { promise, resolve, reject };
}
export function loginDto(alias: LocalAlias = 'learner-a'): LocalLogin {
  return { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    user: { id: alias === 'learner-a' ? 'owner-a' : 'owner-b', alias },
    token_type: 'Bearer', access_token: randomBytes(32).toString('base64url'),
    expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString() };
}
export function stateDto(overrides: Partial<LocalOnboardingState> = {}): LocalOnboardingState {
  return { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    consent_version: LOCAL_CONSENT_VERSION, profile_schema_version: LOCAL_PROFILE_VERSION,
    consent: null, draft: { display_name: null, experience_level: null, updated_at: null },
    onboarding_completed: false, completed_at: null, ...overrides };
}
export function completedState(): LocalOnboardingState {
  const now = new Date().toISOString();
  return stateDto({ consent: { accepted: true, version: LOCAL_CONSENT_VERSION, recorded_at: now },
    draft: { display_name: 'Synthetic learner', experience_level: 'beginner', updated_at: now },
    onboarding_completed: true, completed_at: now });
}
export function clientMock(): jest.Mocked<LocalApplicationClient> {
  const first = loginDto('learner-a');
  const second = loginDto('learner-b');
  return { login: jest.fn<ReturnType<LocalApplicationClient['login']>, Parameters<LocalApplicationClient['login']>>(
    async (alias) => alias === 'learner-a' ? first : second),
    me: jest.fn<ReturnType<LocalApplicationClient['me']>, Parameters<LocalApplicationClient['me']>>(
      async (token) => ({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
      user: token === second.access_token ? second.user : first.user })),
    logout: jest.fn<ReturnType<LocalApplicationClient['logout']>, Parameters<LocalApplicationClient['logout']>>(
      async () => ({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION, signed_out: true as const })),
    state: jest.fn<ReturnType<LocalApplicationClient['state']>, Parameters<LocalApplicationClient['state']>>(async () => stateDto()),
    saveDraft: jest.fn<ReturnType<LocalApplicationClient['saveDraft']>, Parameters<LocalApplicationClient['saveDraft']>>(
      async (_token, draft) => stateDto({ draft: { ...draft, updated_at: new Date().toISOString() } })),
    setConsent: jest.fn<ReturnType<LocalApplicationClient['setConsent']>, Parameters<LocalApplicationClient['setConsent']>>(
      async (_token, accepted) => stateDto({
      consent: { accepted, version: LOCAL_CONSENT_VERSION, recorded_at: new Date().toISOString() } })),
    complete: jest.fn<ReturnType<LocalApplicationClient['complete']>, Parameters<LocalApplicationClient['complete']>>(async () => completedState()) };
}
/** Test-only server simulation; production always uses the typed HTTP adapter. */
export function journeyClientMock(initial: LocalOnboardingState = stateDto()) {
  const client = clientMock();
  const states: Record<LocalAlias, LocalOnboardingState> = { 'learner-a': initial, 'learner-b': stateDto() };
  const loginA = loginDto('learner-a');
  const loginB = loginDto('learner-b');
  const owner = (credential: string): LocalAlias => credential === loginB.access_token ? 'learner-b' : 'learner-a';
  client.login.mockImplementation(async (alias) => alias === 'learner-a' ? loginA : loginB);
  client.me.mockImplementation(async (credential) => ({ scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    user: owner(credential) === 'learner-a' ? loginA.user : loginB.user }));
  client.state.mockImplementation(async (credential) => states[owner(credential)]);
  client.saveDraft.mockImplementation(async (credential, input) => {
    const alias = owner(credential);
    const old = states[alias];
    const changed = old.draft.display_name !== input.display_name || old.draft.experience_level !== input.experience_level;
    states[alias] = { ...old, draft: { ...input, updated_at: new Date().toISOString() },
      onboarding_completed: changed ? false : old.onboarding_completed,
      completed_at: changed ? null : old.completed_at };
    return states[alias];
  });
  client.setConsent.mockImplementation(async (credential, accepted) => {
    const alias = owner(credential);
    const old = states[alias];
    states[alias] = { ...old, consent: { accepted, version: LOCAL_CONSENT_VERSION, recorded_at: new Date().toISOString() },
      onboarding_completed: accepted ? old.onboarding_completed : false,
      completed_at: accepted ? old.completed_at : null };
    return states[alias];
  });
  client.complete.mockImplementation(async (credential) => {
    const alias = owner(credential);
    states[alias] = { ...states[alias], onboarding_completed: true,
      completed_at: states[alias].completed_at || new Date().toISOString() };
    return states[alias];
  });
  return { client, setState: (value: LocalOnboardingState, alias: LocalAlias = 'learner-a') => { states[alias] = value; } };
}
