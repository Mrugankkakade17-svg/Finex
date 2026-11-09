import { randomBytes } from 'crypto';
import {
  createLocalApplicationClient, LOCAL_CONSENT_VERSION, LOCAL_CONTRACT_VERSION,
  LOCAL_PROFILE_VERSION, LOCAL_SCOPE, LocalOnboardingState, validateLocalBaseOrigin,
  hasCompletedOnboarding, validateLocalState,
} from './localApplicationClient';

function token(): string { return randomBytes(32).toString('base64url'); }
function state(): LocalOnboardingState {
  return { scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    profile_schema_version: LOCAL_PROFILE_VERSION, consent_version: LOCAL_CONSENT_VERSION,
    consent: null, draft: { display_name: null, experience_level: null, updated_at: null },
    onboarding_completed: false, completed_at: null };
}
function response(data: unknown, overrides: Record<string, unknown> = {}): Response {
  return { ok: true, status: 200, json: async () => ({ success: true, message: 'Confirmed',
    data, meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null,
      correlationId: 's1-client-test' }, ...overrides }) } as Response;
}

test.each([
  { display_name: 'Saved label', experience_level: null },
  { display_name: null, experience_level: 'beginner' },
  { display_name: 'Saved label', experience_level: 'advanced' },
  { display_name: '', experience_level: null },
])('a non-null saved draft field requires a UTC save timestamp: %j', async (draft) => {
  const fetchMock = jest.fn().mockResolvedValue(response({ ...state(), draft: { ...draft, updated_at: null } }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.state(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});

function untimestampedCompletion(): LocalOnboardingState {
  const now = new Date().toISOString();
  return { ...state(), consent: { accepted: true, version: LOCAL_CONSENT_VERSION, recorded_at: now },
    draft: { display_name: 'Saved label', experience_level: 'beginner', updated_at: null },
    onboarding_completed: true, completed_at: now };
}
test('the completion gate cannot accept a profile with no saved timestamp', () => {
  expect(hasCompletedOnboarding(untimestampedCompletion())).toBe(false);
});
test('state validation rejects a purported completion with no saved profile timestamp', () => {
  expect(() => validateLocalState(untimestampedCompletion())).toThrow();
});
test('a completion response cannot confirm an untimestamped saved profile', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(untimestampedCompletion()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.complete(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});

test.each([
  { name: 'wrong API version', change: { apiVersion: 'v2' } },
  { name: 'absent API version', change: { apiVersion: undefined } },
  { name: 'non-null source time', change: { dataAsOf: '2026-10-11T12:00:00Z' } },
  { name: 'absent source time', change: { dataAsOf: undefined } },
  { name: 'absent correlation', change: { correlationId: undefined } },
  { name: 'empty correlation', change: { correlationId: '' } },
  { name: 'blank correlation', change: { correlationId: ' ' } },
  { name: 'unsafe correlation', change: { correlationId: 'trace/<bad>' } },
  { name: 'final newline correlation', change: { correlationId: 'trace\n' } },
  { name: 'final CRLF correlation', change: { correlationId: 'trace\r\n' } },
  { name: 'oversized correlation', change: { correlationId: 'a'.repeat(129) } },
  { name: 'non-text correlation', change: { correlationId: 42 } },
])('strict existing success metadata rejects $name', async ({ change }) => {
  const fetchMock = jest.fn().mockResolvedValue(response(state(), { meta: {
    apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: null, correlationId: 's1-client-test', ...change } }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.state(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('CACHED alone is not the existing v1 success metadata contract', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(state(), { meta: { dataStatus: 'CACHED' } }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.state(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('a timestamped partial draft and a maximum-length safe correlation remain valid', async () => {
  const timestamp = new Date().toISOString();
  const valid = { ...state(), draft: { display_name: 'Partial label', experience_level: null, updated_at: timestamp } };
  const fetchMock = jest.fn().mockResolvedValue(response(valid, { meta: { apiVersion: 'v1',
    dataStatus: 'CACHED', dataAsOf: null, correlationId: 'a'.repeat(128) } }));
  const loaded = await createLocalApplicationClient({ fetchImpl: fetchMock }).state(token());
  expect(loaded.draft.display_name).toBe('Partial label');
  expect(loaded.draft.experience_level).toBeNull();
  expect(loaded.draft.updated_at).toBe(timestamp);
  expect(loaded.onboarding_completed).toBe(false);
});

test.each(['http://localhost:8000', 'http://127.0.0.1:8000/', 'https://[::1]:8443'])(
  'accepts a canonical loopback origin %s', (value) => {
    expect(validateLocalBaseOrigin(value)).toBe(value.replace(/\/$/, ''));
  },
);
test.each(['https://remote.example', 'http://localhost.evil:8000', 'http://user@localhost:8000',
  'http://localhost:8000/api', 'http://localhost:8000?secret=x', 'http://localhost:8000#x',
  'http://localhost:0', 'file://localhost', 'http://127.1:8000', 'http://localhost:65536'])(
  'rejects an unsafe origin before any request %s', (value) => {
    const fetchMock = jest.fn();
    expect(() => createLocalApplicationClient({ baseOrigin: value, fetchImpl: fetchMock })).toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

test.each(['http://127.0.0.1:8000', 'http://127.0.0.1:8082'])(
  'explicit origin %s uses the local login namespace and strict scoped DTO, not the legacy mock', async (baseOrigin) => {
  const bearer = token();
  const fetchMock = jest.fn().mockResolvedValue(response({ scope: LOCAL_SCOPE,
    contract_version: LOCAL_CONTRACT_VERSION, access_token: bearer, token_type: 'Bearer',
    expires_at: new Date(Date.now() + 1800000).toISOString(), user: { id: 'owner-a', alias: 'learner-a' } }));
  const client = createLocalApplicationClient({ baseOrigin, fetchImpl: fetchMock });
  const login = await client.login('learner-a');
  const correctSecret = login.access_token === bearer;
  expect(correctSecret).toBe(true);
  const call = fetchMock.mock.calls[0];
  expect(call[0] === baseOrigin + '/api/v1/local-auth/mock-login').toBe(true);
  expect(call[1].method).toBe('POST');
  expect(JSON.parse(call[1].body)).toEqual({ alias: 'learner-a' });
  expect(call[1].redirect).toBe('error');
  expect(call[1].credentials).toBe('omit');
  },
);

test('nullable initial state is decoded and all protected requests use a bearer header only', async () => {
  const bearer = token();
  const fetchMock = jest.fn().mockResolvedValue(response(state()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  const loaded = await client.state(bearer);
  expect(loaded.draft.display_name).toBeNull();
  const [url, options] = fetchMock.mock.calls[0];
  const headerCorrect = options.headers.Authorization === 'Bearer ' + bearer;
  const secretInUrl = url.includes(bearer);
  expect(headerCorrect).toBe(true);
  expect(secretInUrl).toBe(false);
});

test('draft save is an exact nullable full replacement with the frozen profile version', async () => {
  const saved = { ...state(), draft: { display_name: null, experience_level: null, updated_at: new Date().toISOString() } };
  const fetchMock = jest.fn().mockResolvedValue(response(saved));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await client.saveDraft(token(), { display_name: null, experience_level: null });
  const options = fetchMock.mock.calls[0][1];
  expect(options.method).toBe('PUT');
  expect(JSON.parse(options.body)).toEqual({ profile_schema_version: LOCAL_PROFILE_VERSION,
    display_name: null, experience_level: null });
});
test('blank labels confirm the accepted API trim-to-empty behavior without manufacturing completion', async () => {
  const saved = { ...state(), draft: { display_name: '', experience_level: null, updated_at: new Date().toISOString() } };
  const fetchMock = jest.fn().mockResolvedValue(response(saved));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  const loaded = await client.saveDraft(token(), { display_name: '   ', experience_level: null });
  expect(JSON.parse(fetchMock.mock.calls[0][1].body).display_name).toBe('   ');
  expect(loaded.draft.display_name).toBe('');
  expect(loaded.onboarding_completed).toBe(false);
});

test.each([
  { scope: 'educational_local_pilot' }, { contract_version: 'local.v2' },
  { onboarding_completed: 'true' }, { completed_at: undefined },
  { draft: { display_name: null, experience_level: null } },
  { consent: { accepted: 'true', version: LOCAL_CONSENT_VERSION, recorded_at: new Date().toISOString() } },
  { consent: { accepted: true, version: 'consent.v0', recorded_at: new Date().toISOString() } },
  { consent: { accepted: false, version: 'consent.v0', recorded_at: new Date().toISOString() } },
])('rejects malformed or pilot state rather than opening completed routes', async (changes) => {
  const fetchMock = jest.fn().mockResolvedValue(response({ ...state(), ...changes }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.state(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});

test.each([{ success: 'true' }, { meta: { dataStatus: 'LIVE' } }, { data: null }])(
  'rejects malformed success envelopes', async (changes) => {
    const fetchMock = jest.fn().mockResolvedValue(response(state(), changes));
    const client = createLocalApplicationClient({ fetchImpl: fetchMock });
    await expect(client.state(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
  },
);

test('401 clears by status even when the error body is unreadable', async () => {
  const fetchMock = jest.fn().mockResolvedValue({ ok: false, status: 401, json: async () => { throw new Error('bad body'); } });
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.state(token())).rejects.toMatchObject({ code: 'SESSION_INVALID' });
});

test('raw error messages never escape the transport', async () => {
  const bearer = token();
  const fetchMock = jest.fn().mockResolvedValue({ ok: false, status: 503,
    json: async () => ({ success: false, message: bearer, error_code: 'LOCAL_STORE_UNAVAILABLE' }) });
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  let reflected = false;
  try { await client.state(bearer); } catch (error) { reflected = String(error).includes(bearer); }
  expect(reflected).toBe(false);
});

test('timeout bounds response body parsing as well as fetch', async () => {
  jest.useFakeTimers();
  try {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 200, json: () => new Promise(() => undefined) });
    const client = createLocalApplicationClient({ fetchImpl: fetchMock, timeoutMs: 100 });
    const pending = client.state(token());
    const expectation = expect(pending).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' });
    await Promise.resolve();
    jest.advanceTimersByTime(101);
    await expectation;
  } finally { jest.useRealTimers(); }
});
test('completion cannot succeed with a valid but incomplete state DTO', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(state()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.complete(token())).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('transport binds a login response to the selected approved alias', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response({ scope: LOCAL_SCOPE,
    contract_version: LOCAL_CONTRACT_VERSION, access_token: token(), token_type: 'Bearer',
    expires_at: new Date(Date.now() + 1800000).toISOString(), user: { id: 'owner-b', alias: 'learner-b' } }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  let code = '';
  try { await client.login('learner-a'); } catch (failure) { code = (failure as { code?: string }).code || ''; }
  expect(code).toBe('RESPONSE_INVALID');
});
test('a draft success cannot silently return different replacement fields', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(state()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.saveDraft(token(), { display_name: 'My label', experience_level: 'beginner' }))
    .rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test.each([true, false])('consent %s requires confirmation of that exact current decision', async (accepted) => {
  const fetchMock = jest.fn().mockResolvedValue(response(state()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.setConsent(token(), accepted)).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('saved draft requires a UTC save timestamp even when both replacement fields are null', async () => {
  const fetchMock = jest.fn().mockResolvedValue(response(state()));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  await expect(client.saveDraft(token(), { display_name: null, experience_level: null }))
    .rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
test('draft postconditions use the immutable fields sent on the wire, not later caller mutation', async () => {
  let resolve!: (value: Response) => void;
  const fetchMock = jest.fn(() => new Promise<Response>((yes) => { resolve = yes; }));
  const client = createLocalApplicationClient({ fetchImpl: fetchMock });
  const draft: { display_name: string | null; experience_level: 'advanced' | null } = {
    display_name: 'Original label', experience_level: 'advanced' };
  const pending = client.saveDraft(token(), draft);
  draft.display_name = null; draft.experience_level = null;
  resolve(response({ ...state(), draft: { display_name: null, experience_level: null,
    updated_at: new Date().toISOString() } }));
  await expect(pending).rejects.toMatchObject({ code: 'RESPONSE_INVALID' });
});
