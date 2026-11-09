/** Test-only wire-corpus reader. Never imported by the application. */
import { readFileSync } from 'fs';
import { execFileSync } from 'child_process';
import { resolve } from 'path';
import { LOCAL_CONTRACT_VERSION, LOCAL_SCOPE } from '../services/localApplicationClient';

export const REQUIRED_LOCAL_S1_CASES = [
  'initial', 'me', 'partial_draft', 'saved_profile', 'consent_accepted', 'completed',
  'repeated_complete', 'identical_draft', 'changed_profile', 'withdrawn', 'reaccepted',
  'logged_out', 'session_invalid', 'consent_required', 'profile_incomplete', 'validation_error',
  'consent_version_mismatch', 'profile_version_mismatch',
] as const;
export type CorpusKind = 'synthetic_fixture' | 'native_tcp_capture';
export type CorpusOperation = 'state' | 'draft' | 'consent' | 'complete' | 'me' | 'logout';
type LocalS1CaseId = typeof REQUIRED_LOCAL_S1_CASES[number];
const caseSpecs: Record<LocalS1CaseId, readonly [CorpusOperation, 'success' | 'error', number, string?]> = {
  initial: ['state', 'success', 200],
  me: ['me', 'success', 200],
  partial_draft: ['draft', 'success', 200],
  saved_profile: ['draft', 'success', 200],
  consent_accepted: ['consent', 'success', 200],
  completed: ['complete', 'success', 200],
  repeated_complete: ['complete', 'success', 200],
  identical_draft: ['draft', 'success', 200],
  changed_profile: ['draft', 'success', 200],
  withdrawn: ['consent', 'success', 200],
  reaccepted: ['consent', 'success', 200],
  logged_out: ['logout', 'success', 200],
  session_invalid: ['state', 'error', 401, 'SESSION_INVALID'],
  consent_required: ['complete', 'error', 409, 'CONSENT_REQUIRED'],
  profile_incomplete: ['complete', 'error', 409, 'PROFILE_INCOMPLETE'],
  validation_error: ['draft', 'error', 422, 'VALIDATION_ERROR'],
  consent_version_mismatch: ['consent', 'error', 409, 'CONSENT_VERSION_MISMATCH'],
  profile_version_mismatch: ['draft', 'error', 409, 'PROFILE_VERSION_MISMATCH'],
};
export interface LocalS1WireCase {
  id: string;
  operation: CorpusOperation;
  request: Record<string, unknown> | null;
  status: number;
  content_type: 'application/json';
  body_utf8: string;
  expected: { outcome: 'success' | 'error'; error_code?: string };
}
export interface LocalS1Corpus {
  schema_version: 'finex.local_s1.corpus.v1';
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  provenance: {
    kind: CorpusKind;
    source: 'handcrafted' | 'owned_loopback_uvicorn';
    command: string;
    tested_commit?: string;
    tested_tree?: string;
  };
  cases: LocalS1WireCase[];
}
type JsonRecord = Record<string, unknown>;
type CorpusReader = (path: string) => string;
type RevisionReader = () => { commit: string; tree: string };
const operations = ['state', 'draft', 'consent', 'complete', 'me', 'logout'];
const errorCodes = new Set([
  'SESSION_INVALID', 'LOCAL_APPLICATION_ONLY', 'LOCAL_STORE_UNAVAILABLE', 'VALIDATION_ERROR',
  'UNKNOWN_LOCAL_ALIAS', 'CONSENT_REQUIRED', 'PROFILE_INCOMPLETE', 'PROFILE_VERSION_MISMATCH',
  'CONSENT_VERSION_MISMATCH', 'ONBOARDING_REQUIRED',
]);
const forbiddenKeys = new Set([
  'access_token', 'refresh_token', 'authorization', 'headers', 'cookie', 'cookies',
  'set-cookie', 'db_path', 'database_path', 'local_db_path',
]);

function invalid(): never { throw new Error('Invalid or unavailable local S1 corpus.'); }
function object(value: unknown): JsonRecord {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) invalid();
  return value as JsonRecord;
}
function exactKeys(value: JsonRecord, required: string[], optional: string[] = []): void {
  if (required.some((key) => !Object.prototype.hasOwnProperty.call(value, key)) ||
      Object.keys(value).some((key) => !required.includes(key) && !optional.includes(key))) invalid();
}
function boundedText(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > maximum) invalid();
  return value as string;
}
function json(value: string): unknown {
  try { return JSON.parse(value) as unknown; } catch { return invalid(); }
}

/** Defence in depth: the producer must already omit login, credentials and paths. */
function requireSafeData(value: unknown, depth = 0): void {
  if (depth > 16) invalid();
  if (typeof value === 'string') {
    if (/(?:^|[^A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?:$|[^A-Za-z0-9_-])/.test(value) ||
        /\bBearer[ \t]+[A-Za-z0-9_-]+/i.test(value) ||
        /(?:[A-Za-z]:[\\/]|file:\/\/|\/(?:Users|home|tmp|var)\/)/.test(value)) invalid();
  } else if (Array.isArray(value)) {
    value.forEach((item) => requireSafeData(item, depth + 1));
  } else if (value !== null && typeof value === 'object') {
    Object.entries(value as JsonRecord).forEach(([key, item]) => {
      if (forbiddenKeys.has(key.toLowerCase()) || key === '__proto__') invalid();
      requireSafeData(item, depth + 1);
    });
  }
}

export function wireEnvelope(wireCase: LocalS1WireCase): JsonRecord {
  return object(json(wireCase.body_utf8));
}

export function parseLocalS1Corpus(serialized: string, requiredKind: CorpusKind): LocalS1Corpus {
  if (serialized.length > 1024 * 1024) invalid();
  const value = object(json(serialized));
  exactKeys(value, ['schema_version', 'scope', 'contract_version', 'provenance', 'cases']);
  if (value.schema_version !== 'finex.local_s1.corpus.v1' || value.scope !== LOCAL_SCOPE ||
      value.contract_version !== LOCAL_CONTRACT_VERSION) invalid();
  const provenance = object(value.provenance);
  const native = requiredKind === 'native_tcp_capture';
  exactKeys(provenance, native
    ? ['kind', 'source', 'command', 'tested_commit', 'tested_tree']
    : ['kind', 'source', 'command']);
  if (provenance.kind !== requiredKind ||
      provenance.source !== (native ? 'owned_loopback_uvicorn' : 'handcrafted') ||
      provenance.command !== (native ? 'python verify_s1_application.py' : 'handcrafted local S1 contract fixture')) invalid();
  if (native && (!/^[a-f0-9]{40}$/.test(boundedText(provenance.tested_commit, 40)) ||
      !/^[a-f0-9]{40}$/.test(boundedText(provenance.tested_tree, 40)))) invalid();
  if (!Array.isArray(value.cases) || value.cases.length !== REQUIRED_LOCAL_S1_CASES.length) invalid();
  const ids = new Set<string>();
  const cases = (value.cases as unknown[]).map((raw): LocalS1WireCase => {
    const entry = object(raw);
    exactKeys(entry, ['id', 'operation', 'request', 'status', 'content_type', 'body_utf8', 'expected']);
    const id = boundedText(entry.id, 64);
    if (!Object.prototype.hasOwnProperty.call(caseSpecs, id) || ids.has(id) || typeof entry.operation !== 'string' ||
        !operations.includes(entry.operation)) invalid();
    ids.add(id);
    const expected = object(entry.expected);
    if (expected.outcome !== 'success' && expected.outcome !== 'error') invalid();
    exactKeys(expected, expected.outcome === 'success' ? ['outcome'] : ['outcome', 'error_code']);
    if (expected.outcome === 'error' && (typeof expected.error_code !== 'string' ||
        !errorCodes.has(expected.error_code))) invalid();
    const [operation, outcome, status, code] = caseSpecs[id as LocalS1CaseId];
    if (entry.operation !== operation || expected.outcome !== outcome ||
        entry.status !== status || expected.error_code !== code) invalid();
    if (!Number.isInteger(entry.status) || (entry.status as number) < 200 || (entry.status as number) > 599 ||
        (expected.outcome === 'success' ? (entry.status as number) >= 300 : (entry.status as number) < 400) ||
        entry.content_type !== 'application/json') invalid();
    const request = entry.request === null ? null : object(entry.request);
    if (request !== null && Object.keys(request).length > 12) invalid();
    if (['state', 'me', 'logout'].includes(String(entry.operation)) ? request !== null : request === null) invalid();
    const body = boundedText(entry.body_utf8, 64 * 1024);
    const envelope = object(json(body));
    if (envelope.success !== (expected.outcome === 'success') ||
        (expected.outcome === 'error' && envelope.error_code !== expected.error_code)) invalid();
    requireSafeData(request);
    requireSafeData(envelope);
    return { id, operation: entry.operation as CorpusOperation, request,
      status: entry.status as number, content_type: 'application/json', body_utf8: body,
      expected: expected as LocalS1WireCase['expected'] };
  });
  if (REQUIRED_LOCAL_S1_CASES.some((id) => !ids.has(id))) invalid();
  return { schema_version: 'finex.local_s1.corpus.v1', scope: LOCAL_SCOPE,
    contract_version: LOCAL_CONTRACT_VERSION, provenance: provenance as unknown as LocalS1Corpus['provenance'], cases };
}

export function readLocalS1Corpus(path: string, kind: CorpusKind,
  reader: CorpusReader = (location) => readFileSync(location, 'utf8')): LocalS1Corpus {
  try { return parseLocalS1Corpus(reader(path), kind); } catch { return invalid(); }
}

export function configuredLocalS1Corpora(
  environment: { corpusPath?: string; requireNative?: string },
  reader: CorpusReader = (location) => readFileSync(location, 'utf8'),
  revision: RevisionReader = () => {
    const cwd = resolve(__dirname, '../../..');
    const readRevision = (ref: string) => execFileSync('git', ['rev-parse', ref], {
      cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    return { commit: readRevision('HEAD'), tree: readRevision('HEAD^{tree}') };
  },
): Array<{ label: 'fixture' | 'native'; corpus: LocalS1Corpus }> {
  if (environment.requireNative !== undefined && environment.requireNative !== '0' &&
      environment.requireNative !== '1') invalid();
  const fixturePath = resolve(__dirname, '../../../data/fixtures/local_s1/contract_cases.v1.json');
  const corpora: Array<{ label: 'fixture' | 'native'; corpus: LocalS1Corpus }> = [
    { label: 'fixture', corpus: readLocalS1Corpus(fixturePath, 'synthetic_fixture', reader) },
  ];
  const path = environment.corpusPath;
  if (environment.requireNative === '1' && !path) invalid();
  if (path !== undefined) {
    if (!path.trim()) invalid();
    const nativeCorpus = readLocalS1Corpus(path, 'native_tcp_capture', reader);
    let current: ReturnType<RevisionReader>;
    try { current = revision(); } catch { return invalid(); }
    if (nativeCorpus.provenance.tested_commit !== current.commit ||
        nativeCorpus.provenance.tested_tree !== current.tree) invalid();
    corpora.push({ label: 'native', corpus: nativeCorpus });
  }
  return corpora;
}
