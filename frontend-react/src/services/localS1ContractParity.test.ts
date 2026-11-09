import { randomBytes } from 'crypto';
import {
  createLocalApplicationClient, LocalApplicationClient, LocalApplicationError, LocalDraftInput,
  LOCAL_CONSENT_VERSION, LOCAL_PROFILE_VERSION,
} from './localApplicationClient';
import {
  configuredLocalS1Corpora, LocalS1Corpus, LocalS1WireCase, parseLocalS1Corpus,
  readLocalS1Corpus, REQUIRED_LOCAL_S1_CASES, wireEnvelope,
} from '../testHelpers/localS1Corpus';

// All coverage of existing decoders is GREEN-only unless a real regression is observed.
// Native proof requires a separately generated, matching-revision TCP corpus; no live API here.
const corpora = configuredLocalS1Corpora({
  corpusPath: process.env.FINEX_LOCAL_S1_CORPUS,
  requireNative: process.env.FINEX_REQUIRE_LOCAL_S1_CORPUS,
});
const fixture = corpora[0].corpus;
type JsonRecord = Record<string, unknown>;
function object(value: unknown): JsonRecord {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid local S1 test case.');
  }
  return value as JsonRecord;
}
function caseById(corpus: LocalS1Corpus, id: string): LocalS1WireCase {
  const found = corpus.cases.find((entry) => entry.id === id);
  if (!found) throw new Error('Required local S1 test case is absent.');
  return found;
}
function dataOf(entry: LocalS1WireCase): JsonRecord { return object(wireEnvelope(entry).data); }
function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function equivalent(left: unknown, right: unknown): boolean {
  const canonical = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value !== null && typeof value === 'object') {
      const fields = object(value);
      return Object.fromEntries(Object.keys(fields).sort().map((key) => [key, canonical(fields[key])]));
    }
    return value;
  };
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}
function utcInstant(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const match = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!match || !Number.isFinite(Date.parse(value))) return null;
  // Preserve native microseconds; Date.getTime alone would discard precision.
  return match[1] + '.' + (match[2] || '').padEnd(6, '0') + 'Z';
}

const routes = {
  state: ['/api/v1/local-onboarding/state', 'GET'],
  draft: ['/api/v1/local-onboarding/draft', 'PUT'],
  consent: ['/api/v1/local-onboarding/consent', 'POST'],
  complete: ['/api/v1/local-onboarding/complete', 'POST'],
  me: ['/api/v1/local-auth/me', 'GET'],
  logout: ['/api/v1/local-auth/logout', 'POST'],
} as const;

function issuedRequest(entry: LocalS1WireCase): JsonRecord | null {
  if (entry.expected.outcome === 'success') return entry.request;
  // Illegal captured server inputs cannot be emitted by the typed client. These
  // error cases replay only the response through a canonical corresponding call.
  if (entry.operation === 'draft') return caseById(fixture, 'saved_profile').request;
  if (entry.operation === 'consent') return caseById(fixture, 'consent_accepted').request;
  if (entry.operation === 'complete') return caseById(fixture, 'completed').request;
  return null;
}
function dispatch(client: LocalApplicationClient, entry: LocalS1WireCase, bearer: string): Promise<unknown> {
  const request = issuedRequest(entry);
  switch (entry.operation) {
    case 'state': return client.state(bearer);
    case 'me': return client.me(bearer);
    case 'logout': return client.logout(bearer);
    case 'draft': {
      const input = object(request);
      return client.saveDraft(bearer, {
        display_name: input.display_name,
        experience_level: input.experience_level,
      } as LocalDraftInput);
    }
    case 'consent': return client.setConsent(bearer, object(request).consent_given as boolean);
    case 'complete': return client.complete(bearer);
  }
}
interface ReplayResult {
  failed: boolean;
  errorCode: string;
  reflectedCredential: boolean;
  requestMatches: boolean;
  value?: unknown;
}
async function replay(entry: LocalS1WireCase, alteredBody?: string | ((bearer: string) => string)): Promise<ReplayResult> {
  const bearer = randomBytes(32).toString('base64url');
  const rawBody = typeof alteredBody === 'function' ? alteredBody(bearer) : alteredBody ?? entry.body_utf8;
  const rawBytes = Buffer.from(rawBody, 'utf8');
  let calls = 0;
  let requestMatches = true;
  const fetchImpl = (async (url: RequestInfo | URL, options?: RequestInit) => {
    calls++;
    const headers = object(options?.headers);
    const payload = issuedRequest(entry);
    const body = typeof options?.body === 'string' ? options.body : undefined;
    const transmitted = body === undefined ? null : JSON.parse(body) as unknown;
    requestMatches = requestMatches &&
      String(url) === 'http://127.0.0.1:8000' + routes[entry.operation][0] &&
      options?.method === routes[entry.operation][1] &&
      headers.Authorization === 'Bearer ' + bearer && headers.Accept === 'application/json' &&
      options?.credentials === 'omit' && options.cache === 'no-store' && options.redirect === 'error' &&
      !String(url).includes(bearer) && !(body || '').includes(bearer) &&
      equivalent(transmitted, payload) &&
      (payload === null ? headers['Content-Type'] === undefined : headers['Content-Type'] === 'application/json');
    return { status: entry.status, ok: entry.status >= 200 && entry.status < 300,
      redirected: false, headers: { get: () => entry.content_type },
      json: async () => JSON.parse(rawBytes.toString('utf8')) as unknown } as unknown as Response;
  }) as typeof fetch;
  const client = createLocalApplicationClient({ baseOrigin: 'http://127.0.0.1:8000', fetchImpl });
  try {
    const value = await dispatch(client, entry, bearer);
    return { failed: false, errorCode: '', reflectedCredential: JSON.stringify(value).includes(bearer),
      requestMatches: requestMatches && calls === 1, value };
  } catch (failure) {
    // No error/body/header snapshots: even a regression must not print a bearer.
    const safeCode = failure instanceof LocalApplicationError ? failure.code : 'UNCLASSIFIED_FAILURE';
    return { failed: true, errorCode: safeCode, reflectedCredential: String(failure).includes(bearer),
      requestMatches: requestMatches && calls === 1 };
  }
}

interface Mutation { name: string; caseId: string; path: string[]; remove?: true; value?: unknown; }
function mutate(entry: LocalS1WireCase, mutation: Mutation): string {
  const envelope = clone(wireEnvelope(entry));
  let parent = envelope;
  for (const field of mutation.path.slice(0, -1)) parent = object(parent[field]);
  const leaf = mutation.path[mutation.path.length - 1];
  if (mutation.remove) delete parent[leaf]; else parent[leaf] = mutation.value;
  return JSON.stringify(envelope);
}
const missingKeys: Mutation[] = [
  ['consent'], ['draft'], ['draft', 'display_name'], ['draft', 'experience_level'],
  ['draft', 'updated_at'], ['completed_at'], ['onboarding_completed'], ['scope'],
  ['contract_version'], ['profile_schema_version'], ['consent_version'],
].map((path) => ({ name: 'missing ' + path.join('.'), caseId: 'initial', path: ['data', ...path], remove: true }));
const metadataMutations: Mutation[] = [
  { name: 'missing metadata', path: ['meta'], remove: true as const },
  ...['apiVersion', 'dataStatus', 'dataAsOf', 'correlationId'].map((field) => ({
    name: 'missing metadata ' + field, path: ['meta', field], remove: true as const,
  })),
  { name: 'wrong metadata version', path: ['meta', 'apiVersion'], value: 'v2' },
  { name: 'live synthetic metadata', path: ['meta', 'dataStatus'], value: 'LIVE' },
  { name: 'invented source timestamp', path: ['meta', 'dataAsOf'], value: '2026-10-11T12:00:00Z' },
  ...['', ' ', 'unsafe/trace', 'trace\n', 'trace\r\n', 'a'.repeat(129)].map((value, index) => ({
    name: 'unsafe correlation ' + index, path: ['meta', 'correlationId'], value,
  })),
  { name: 'nontext correlation', path: ['meta', 'correlationId'], value: 1 },
  { name: 'missing message', path: ['message'], remove: true as const },
  { name: 'nonboolean success', path: ['success'], value: 'true' },
].map((mutation) => ({ ...mutation, caseId: 'initial' }));
const timestampMutations: Mutation[] = [
  ['consent', 'recorded_at'], ['draft', 'updated_at'], ['completed_at'],
].flatMap((path) => [
  '2026-10-11T12:00:00', '2026-10-11T13:00:00+01:00',
  '2026-02-30T12:00:00Z', '2026-10-11T12:00:00.1234567Z',
].map((value, index) => ({ name: 'invalid UTC ' + path.join('.') + ' ' + index,
  caseId: 'completed', path: ['data', ...path], value })));
const stateMutations: Mutation[] = [
  { name: 'pilot scope', caseId: 'initial', path: ['data', 'scope'], value: 'educational_local_pilot' },
  { name: 'wrong contract', caseId: 'initial', path: ['data', 'contract_version'], value: 'local.v2' },
  { name: 'wrong profile version', caseId: 'initial', path: ['data', 'profile_schema_version'], value: 'profile.v2' },
  { name: 'wrong current consent version', caseId: 'initial', path: ['data', 'consent_version'], value: 'consent.v0' },
  { name: 'stale nested consent', caseId: 'completed', path: ['data', 'consent', 'version'], value: 'consent.v0' },
  { name: 'string consent bool', caseId: 'completed', path: ['data', 'consent', 'accepted'], value: 'true' },
  { name: 'numeric consent bool', caseId: 'completed', path: ['data', 'consent', 'accepted'], value: 1 },
  { name: 'missing nested consent time', caseId: 'completed', path: ['data', 'consent', 'recorded_at'], remove: true },
  { name: 'complete without consent', caseId: 'completed', path: ['data', 'consent'], value: null },
  { name: 'complete after withdrawal', caseId: 'completed', path: ['data', 'consent', 'accepted'], value: false },
  { name: 'complete without label', caseId: 'completed', path: ['data', 'draft', 'display_name'], value: null },
  { name: 'complete with blank label', caseId: 'completed', path: ['data', 'draft', 'display_name'], value: '' },
  { name: 'complete without experience', caseId: 'completed', path: ['data', 'draft', 'experience_level'], value: null },
  { name: 'complete without saved time', caseId: 'completed', path: ['data', 'draft', 'updated_at'], value: null },
  { name: 'complete without completion time', caseId: 'completed', path: ['data', 'completed_at'], value: null },
  { name: 'incomplete with completion time', caseId: 'initial', path: ['data', 'completed_at'], value: '2026-10-11T12:00:00Z' },
  { name: 'partial without save timestamp', caseId: 'partial_draft', path: ['data', 'draft', 'updated_at'], value: null },
  { name: 'missing identity id', caseId: 'me', path: ['data', 'user', 'id'], remove: true },
  { name: 'unknown identity alias', caseId: 'me', path: ['data', 'user', 'alias'], value: 'unapproved' },
  { name: 'unconfirmed logout', caseId: 'logged_out', path: ['data', 'signed_out'], value: false },
  { name: 'draft confirms other label', caseId: 'saved_profile', path: ['data', 'draft', 'display_name'], value: 'Different confirmation' },
  { name: 'draft confirms other experience', caseId: 'saved_profile', path: ['data', 'draft', 'experience_level'], value: 'advanced' },
  { name: 'consent confirms opposite decision', caseId: 'consent_accepted', path: ['data', 'consent', 'accepted'], value: false },
  { name: 'consent missing confirmation', caseId: 'consent_accepted', path: ['data', 'consent'], value: null },
];
const mutations = [...missingKeys, ...metadataMutations, ...timestampMutations, ...stateMutations];

for (const { label, corpus } of corpora) {
  describe('local S1 ' + label + ' captured-wire parity', () => {
    test.each(corpus.cases.map((entry) => [entry.id, entry] as const))('%s decodes through the public transport', async (_id, entry) => {
      const result = await replay(entry);
      expect(result.requestMatches).toBe(true);
      expect(result.reflectedCredential).toBe(false);
      expect(result.failed === (entry.expected.outcome === 'error')).toBe(true);
      if (entry.expected.outcome === 'error') {
        expect(result.errorCode === entry.expected.error_code).toBe(true);
      } else {
        expect(equivalent(result.value, dataOf(entry))).toBe(true);
      }
    });

    test('state transitions preserve UTC instants and require explicit recompletion', () => {
      const data = (id: string) => dataOf(caseById(corpus, id));
      const initial = data('initial');
      const partial = data('partial_draft');
      const complete = data('completed');
      expect(initial.consent === null && initial.completed_at === null && initial.onboarding_completed === false).toBe(true);
      expect(equivalent(initial.draft, { display_name: null, experience_level: null, updated_at: null })).toBe(true);
      expect((object(partial.draft).display_name === null) !== (object(partial.draft).experience_level === null) &&
        utcInstant(object(partial.draft).updated_at) !== null && partial.onboarding_completed === false).toBe(true);
      const completedAt = utcInstant(complete.completed_at);
      expect(completedAt !== null && complete.onboarding_completed === true && object(complete.consent).accepted === true).toBe(true);
      expect(utcInstant(data('repeated_complete').completed_at) === completedAt).toBe(true);
      expect(utcInstant(data('identical_draft').completed_at) === completedAt).toBe(true);
      ['changed_profile', 'withdrawn', 'reaccepted'].forEach((id) => {
        const changed = data(id);
        expect(changed.onboarding_completed === false && changed.completed_at === null).toBe(true);
      });
      expect(object(data('withdrawn').consent).accepted === false).toBe(true);
      expect(object(data('reaccepted').consent).accepted === true).toBe(true);
      expect(object(data('me').user).alias === 'learner-a').toBe(true);
      expect(data('logged_out').signed_out === true).toBe(true);
    });

    test.each(mutations.map((mutation) => [mutation.name, mutation] as const))('rejects %s', async (_name, mutation) => {
      const entry = caseById(corpus, mutation.caseId);
      const result = await replay(entry, mutate(entry, mutation));
      expect(result.failed && result.errorCode === 'RESPONSE_INVALID').toBe(true);
      expect(result.reflectedCredential).toBe(false);
    });

    test('equivalent UTC Z spelling remains accepted without millisecond truncation', async () => {
      const entry = caseById(corpus, 'completed');
      const envelope = clone(wireEnvelope(entry));
      const data = object(envelope.data);
      const original = utcInstant(data.completed_at);
      [object(data.consent), object(data.draft), data].forEach((record, index) => {
        const field = ['recorded_at', 'updated_at', 'completed_at'][index];
        record[field] = String(record[field]).replace(/\+00:00$/, 'Z');
      });
      const result = await replay(entry, JSON.stringify(envelope));
      expect(result.failed).toBe(false);
      expect(utcInstant(object(result.value).completed_at) === original).toBe(true);
    });

    test('complete cannot confirm a well-formed but incomplete state', async () => {
      const entry = caseById(corpus, 'completed');
      const envelope = clone(wireEnvelope(entry));
      const data = object(envelope.data);
      data.onboarding_completed = false;
      data.completed_at = null;
      const result = await replay(entry, JSON.stringify(envelope));
      expect(result.failed && result.errorCode === 'RESPONSE_INVALID').toBe(true);
    });

    test('an all-null replacement still needs a confirmed draft-save timestamp', async () => {
      const entry = clone(caseById(corpus, 'saved_profile'));
      entry.request = { profile_schema_version: LOCAL_PROFILE_VERSION, display_name: null, experience_level: null };
      const envelope = clone(wireEnvelope(caseById(corpus, 'initial')));
      const result = await replay(entry, JSON.stringify(envelope));
      expect(result.failed && result.errorCode === 'RESPONSE_INVALID' && result.requestMatches).toBe(true);
    });

    test('raw error text cannot reflect the memory-only credential', async () => {
      const entry = caseById(corpus, 'validation_error');
      const result = await replay(entry, (bearer) => {
        const envelope = clone(wireEnvelope(entry));
        envelope.message = bearer;
        envelope.error = { message: bearer, correlationId: bearer, fieldErrors: [{ message: bearer }] };
        return JSON.stringify(envelope);
      });
      expect(result.failed && result.errorCode === 'VALIDATION_ERROR').toBe(true);
      expect(result.reflectedCredential).toBe(false);
    });
  });
}

function safeRejected(operation: () => unknown): boolean {
  try { operation(); return false; } catch (failure) {
    return failure instanceof Error && failure.message === 'Invalid or unavailable local S1 corpus.';
  }
}
function serializedFixture(change?: (value: LocalS1Corpus) => void): string {
  const value = clone(fixture);
  change?.(value);
  return JSON.stringify(value);
}
describe('local S1 corpus guards (unit checks, not native HTTP evidence)', () => {
  test('committed data is complete and synthetic, not fabricated native proof', () => {
    expect(REQUIRED_LOCAL_S1_CASES.every((id) => fixture.cases.some((entry) => entry.id === id))).toBe(true);
    expect(fixture.provenance.kind === 'synthetic_fixture').toBe(true);
  });
  test.each(['', '{', 'null', '[]'])('malformed serialized corpus safely fails (case %s)', (serialized) => {
    expect(safeRejected(() => parseLocalS1Corpus(serialized, 'synthetic_fixture'))).toBe(true);
  });
  test.each([
    'schema', 'scope', 'contract', 'provenance', 'duplicate', 'missing', 'status', 'content_type', 'body', 'outcome',
  ])('corpus drift safely fails: %s', (kind) => {
    const serialized = serializedFixture((value) => {
      if (kind === 'schema') Object.assign(value, { schema_version: 'future.v2' });
      if (kind === 'scope') Object.assign(value, { scope: 'educational_local_pilot' });
      if (kind === 'contract') Object.assign(value, { contract_version: 'local.v2' });
      if (kind === 'provenance') Object.assign(value.provenance, { source: 'unverified' });
      if (kind === 'duplicate') value.cases.push(clone(value.cases[0]));
      if (kind === 'missing') value.cases = value.cases.filter((entry) => entry.id !== 'initial');
      if (kind === 'status') value.cases[0].status = 401;
      if (kind === 'content_type') Object.assign(value.cases[0], { content_type: 'text/plain' });
      if (kind === 'body') value.cases[0].body_utf8 = '{';
      if (kind === 'outcome') Object.assign(value.cases[0].expected, { outcome: 'error' });
    });
    expect(safeRejected(() => parseLocalS1Corpus(serialized, 'synthetic_fixture'))).toBe(true);
  });
  test('login secrets, headers and paths cannot be accepted as corpus data', () => {
    const memorySecret = randomBytes(32).toString('base64url');
    ['access_token', 'Authorization', 'headers', 'cookie', 'db_path'].forEach((key) => {
      const serialized = serializedFixture((value) => {
        const envelope = wireEnvelope(value.cases[0]);
        object(envelope.data)[key] = key === 'db_path' ? 'C:\\private\\synthetic.sqlite3' : memorySecret;
        value.cases[0].body_utf8 = JSON.stringify(envelope);
      });
      expect(safeRejected(() => parseLocalS1Corpus(serialized, 'synthetic_fixture'))).toBe(true);
    });
  });
  test('unavailable reads do not expose the diagnostic or path', () => {
    const memorySecret = randomBytes(32).toString('base64url');
    expect(safeRejected(() => readLocalS1Corpus('test-only-location', 'synthetic_fixture', () => {
      throw new Error(memorySecret);
    }))).toBe(true);
  });
  test('required native capture never falls back to handcrafted data', () => {
    const reader = () => serializedFixture();
    expect(safeRejected(() => configuredLocalS1Corpora({ requireNative: '1' }, reader))).toBe(true);
    expect(safeRejected(() => configuredLocalS1Corpora({ corpusPath: 'test-only-location', requireNative: '1' }, reader))).toBe(true);
    expect(safeRejected(() => configuredLocalS1Corpora({ corpusPath: '', requireNative: '0' }, reader))).toBe(true);
    expect(safeRejected(() => configuredLocalS1Corpora({ requireNative: 'true' }, reader))).toBe(true);
  });
  test.each([
    'extra', 'missing', 'operation', 'exchanged IDs', 'error code', 'error status', 'success status', 'outcome',
  ])('frozen case semantics reject %s drift', (kind) => {
    const serialized = serializedFixture((value) => {
      const initial = caseById(value, 'initial');
      if (kind === 'extra') value.cases.push({ ...clone(initial), id: 'additional_state' });
      if (kind === 'missing') value.cases.pop();
      if (kind === 'operation') initial.operation = 'me';
      if (kind === 'exchanged IDs') {
        initial.id = 'me';
        value.cases.find((entry) => entry.operation === 'me')!.id = 'initial';
      }
      if (kind === 'error code') {
        const entry = caseById(value, 'validation_error');
        entry.expected.error_code = 'PROFILE_INCOMPLETE';
        const envelope = wireEnvelope(entry);
        envelope.error_code = 'PROFILE_INCOMPLETE';
        entry.body_utf8 = JSON.stringify(envelope);
      }
      if (kind === 'error status') caseById(value, 'session_invalid').status = 503;
      if (kind === 'success status') initial.status = 201;
      if (kind === 'outcome') {
        initial.status = 422;
        initial.expected = { outcome: 'error', error_code: 'VALIDATION_ERROR' };
        const envelope = wireEnvelope(initial);
        envelope.success = false;
        envelope.error_code = 'VALIDATION_ERROR';
        initial.body_utf8 = JSON.stringify(envelope);
      }
    });
    expect(safeRejected(() => parseLocalS1Corpus(serialized, 'synthetic_fixture'))).toBe(true);
  });
  test('native metadata must identify this checkout, not merely look like hashes', () => {
    const commit = '1'.repeat(40);
    const tree = '2'.repeat(40);
    const native = clone(fixture);
    native.provenance = { kind: 'native_tcp_capture', source: 'owned_loopback_uvicorn',
      command: 'python verify_s1_application.py', tested_commit: commit, tested_tree: tree };
    const reader = (path: string) => path === 'test-only-native' ? JSON.stringify(native) : serializedFixture();
    const configured = configuredLocalS1Corpora({ corpusPath: 'test-only-native', requireNative: '1' }, reader,
      () => ({ commit, tree }));
    expect(configured.length === 2 && configured[1].corpus.provenance.kind === 'native_tcp_capture').toBe(true);
    expect(safeRejected(() => configuredLocalS1Corpora({ corpusPath: 'test-only-native', requireNative: '1' }, reader,
      () => ({ commit: '3'.repeat(40), tree })))).toBe(true);
    expect(safeRejected(() => configuredLocalS1Corpora({ corpusPath: 'test-only-native', requireNative: '1' }, reader,
      () => ({ commit, tree: '3'.repeat(40) })))).toBe(true);
  });
});

// Keep these version assertions explicit; operation payloads are frozen, not
// copied from an invalid captured request or inferred from an arbitrary response.
test('canonical operation inputs use the accepted versions', () => {
  expect(caseById(fixture, 'saved_profile').request?.profile_schema_version === LOCAL_PROFILE_VERSION).toBe(true);
  expect(caseById(fixture, 'consent_accepted').request?.consent_version === LOCAL_CONSENT_VERSION).toBe(true);
  const complete = caseById(fixture, 'completed').request;
  expect(complete?.profile_schema_version === LOCAL_PROFILE_VERSION && complete.consent_version === LOCAL_CONSENT_VERSION).toBe(true);
});
