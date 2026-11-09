/** Test-only native S2 evidence boundary. Never imported by the application. */
import { createHash } from 'crypto';
import { execFileSync } from 'child_process';
import { closeSync, fstatSync, lstatSync, openSync, readSync, realpathSync } from 'fs';
import { isAbsolute, relative, resolve } from 'path';
import { TextDecoder } from 'util';
import { LOCAL_CONTRACT_VERSION, LOCAL_SCOPE } from '../services/localApplicationBoundary';
import {
  decodeCatalog, decodeHolding, decodeHoldingDeletion, decodeHoldingList, decodeMetrics,
  decodePortfolio, decodePortfolioDeletion, decodePortfolioList, decodeQuestionnaire,
  decodeRiskDraft, decodeRiskHistory, decodeSavedRisk, riskInput, sameRiskInput,
  cursorS2, uuidS2, RISK_QUESTION_IDS,
} from '../services/localS2Models';
import { checkedS2, metricsMeta, nullMeta, riskMeta, updatedMeta } from '../services/localS2Client';

export const LOCAL_S2_CORPUS_FAILURE = 'Invalid or unavailable local S2 native evidence.';
export type LocalS2CorpusKind = 'risk' | 'portfolio';
export type LocalS2RiskOperation = 'questionnaire' | 'draft_get' | 'draft_put' |
  'assessment_create' | 'history' | 'assessment_detail';
export type LocalS2PortfolioOperation = 'catalogue' | 'portfolio_create' | 'portfolio_list' |
  'portfolio_detail' | 'portfolio_update' | 'portfolio_delete' | 'holding_create' |
  'holding_list' | 'holding_detail' | 'holding_update' | 'holding_delete' | 'metrics';
export interface LocalS2SourceHash { path: string; sha256: string; }
export interface LocalS2Expected { outcome: 'success' | 'error'; error_code?: string; }
interface WireCase {
  id: string;
  request: Record<string, unknown> | null;
  status: number;
  content_type: 'application/json';
  body_utf8: string;
  expected: LocalS2Expected;
}
export interface LocalS2RiskWireCase extends WireCase {
  operation: LocalS2RiskOperation;
  target: { limit: 2; before: string | null } | { assessment_id: string } | null;
}
/** Portfolio v1 intentionally has no captured request-target field. */
export interface LocalS2PortfolioWireCase extends WireCase {
  operation: LocalS2PortfolioOperation;
}
export interface LocalS2NativeCorpus<T extends WireCase> {
  schema_version: string;
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  provenance: {
    kind: 'native_tcp_capture'; source: 'owned_loopback_uvicorn'; command: string;
    tested_commit: string; tested_tree: string;
  };
  source_hashes: LocalS2SourceHash[];
  source_manifest_sha256: string;
  cases: T[];
}
export interface LocalS2NativeReport {
  schema_version: string;
  scope: typeof LOCAL_SCOPE;
  contract_version: typeof LOCAL_CONTRACT_VERSION;
  success: true;
  mode: 'owned_native_tcp';
  tested_commit: string;
  tested_tree: string;
  working_tree_dirty: false;
  tracked_dirty: false;
  source_hashes: LocalS2SourceHash[];
  source_manifest_sha256: string;
  checks: { id: string; passed: true }[];
  required_checks: string[];
  failures: [];
  responses_checked: number;
  corpus_sha256: string;
  corpus_case_ids: string[];
  native_process: {
    starts: number; application_restarts: 2; owned_pids: number[];
    child_reaped: true; temporary_directory_removed: true; session_ttl_minutes: 1;
    real_expiry_elapsed_seconds: number | null; shutdown: 'owned_terminate_and_reap';
  };
  python_version: string;
  limitations: string[];
}
export interface LocalS2NativePair {
  risk: { corpus: LocalS2NativeCorpus<LocalS2RiskWireCase>; report: LocalS2NativeReport };
  portfolio: { corpus: LocalS2NativeCorpus<LocalS2PortfolioWireCase>; report: LocalS2NativeReport };
}
export interface LocalS2CorpusEnvironment {
  required?: string;
  riskCorpus?: string;
  riskReport?: string;
  portfolioCorpus?: string;
  portfolioReport?: string;
}
/** Explicitly unit-only injection: these values do not constitute native proof. */
export interface LocalS2CorpusIo {
  readArtifact(location: string, maximumBytes: number): Buffer;
  readSource(repositoryPath: string): Buffer;
  revision(): { commit: string; tree: string; workingTreeDirty: boolean; trackedDirty: boolean };
}

type Json = Record<string, unknown>;
type Specification = readonly [string, number, string | null];
const RISK_CASES: Record<string, Specification> = {
  questionnaire: ['questionnaire', 200, null], draft_initial: ['draft_get', 200, null],
  draft_partial_saved: ['draft_put', 200, null], draft_partial_resumed: ['draft_get', 200, null],
  history_initial: ['history', 200, null], assessment_created: ['assessment_create', 200, null],
  assessment_equivalent_replay: ['assessment_create', 200, null], assessment_detail: ['assessment_detail', 200, null],
  history_single: ['history', 200, null], other_owner_history_empty: ['history', 200, null],
  draft_cleared: ['draft_put', 200, null], draft_after_restart: ['draft_get', 200, null],
  assessment_after_restart: ['assessment_detail', 200, null], assessment_aggressive: ['assessment_create', 200, null],
  assessment_conservative: ['assessment_create', 200, null], history_page_first: ['history', 200, null],
  assessment_inserted_between_pages: ['assessment_create', 200, null], history_page_next: ['history', 200, null],
  history_after_relogin: ['history', 200, null], idempotency_conflict: ['assessment_create', 409, 'IDEMPOTENCY_CONFLICT'],
  assessment_other_owner: ['assessment_detail', 404, 'RISK_ASSESSMENT_NOT_FOUND'],
  assessment_missing: ['assessment_detail', 404, 'RISK_ASSESSMENT_NOT_FOUND'],
  onboarding_withdrawn: ['history', 409, 'ONBOARDING_REQUIRED'], onboarding_reaccepted: ['history', 409, 'ONBOARDING_REQUIRED'],
  session_invalid: ['draft_get', 401, 'SESSION_INVALID'], session_restart_invalid: ['history', 401, 'SESSION_INVALID'],
  unsupported_version: ['draft_put', 400, 'UNSUPPORTED_QUESTIONNAIRE_VERSION'],
  missing_required_question: ['assessment_create', 400, 'MISSING_REQUIRED_QUESTION'],
  validation_error: ['assessment_create', 422, 'VALIDATION_ERROR'],
};
const PORTFOLIO_CASES: Record<string, Specification> = {
  catalogue: ['catalogue', 200, null], portfolio_created: ['portfolio_create', 201, null],
  portfolio_list: ['portfolio_list', 200, null], portfolio_detail: ['portfolio_detail', 200, null],
  portfolio_updated: ['portfolio_update', 200, null], portfolio_unchanged: ['portfolio_update', 200, null],
  portfolio_deleted: ['portfolio_delete', 200, null], holding_created: ['holding_create', 201, null],
  holding_list: ['holding_list', 200, null], holding_detail: ['holding_detail', 200, null],
  holding_updated: ['holding_update', 200, null], holding_unchanged: ['holding_update', 200, null],
  holding_deleted: ['holding_delete', 200, null], golden_1: ['metrics', 200, null], golden_2: ['metrics', 200, null],
  golden_3: ['metrics', 200, null], golden_4: ['metrics', 200, null], golden_5: ['metrics', 200, null], golden_6: ['metrics', 200, null],
  empty: ['metrics', 200, null], zero_cost: ['metrics', 200, null], partial: ['metrics', 200, null], unavailable: ['metrics', 200, null],
  session_invalid: ['portfolio_list', 401, 'SESSION_INVALID'], onboarding_required: ['portfolio_list', 409, 'ONBOARDING_REQUIRED'],
  portfolio_not_found: ['portfolio_detail', 404, 'LOCAL_PORTFOLIO_NOT_FOUND'], holding_not_found: ['holding_detail', 404, 'LOCAL_HOLDING_NOT_FOUND'],
  validation_error: ['holding_create', 422, 'VALIDATION_ERROR'], unsupported_instrument: ['holding_create', 422, 'UNSUPPORTED_INSTRUMENT'],
  holding_duplicate: ['holding_create', 409, 'HOLDING_ALREADY_EXISTS'], portfolio_limit: ['portfolio_create', 409, 'PORTFOLIO_LIMIT_REACHED'],
};
const RISK_CHECKS = [
  'disabled_prebody_no_database', 'missing_bearer_no_database', 'current_s1_prerequisites',
  'ordered_ten_question_contract', 'owned_partial_draft', 'saved_numeric_rules_snapshot',
  'original_equivalent_replay', 'conflict_unchanged_history', 'owner_scoped_history_detail',
  'empty_draft_preserves_history', 'first_native_restart', 'bounded_stable_cursor',
  'withdrawal_reacceptance_gate', 'durable_session_logout', 'second_native_restart',
  'safe_wire_without_credentials', 'complete_safe_wire_corpus', 'owned_cleanup',
];
const PORTFOLIO_CHECKS = [
  'disabled_prebody_no_database', 'remote_configuration_no_database', 'missing_bearer_no_database',
  'current_s1_prerequisites', 'schema3_preserves_s1_and_risk', 'versioned_synthetic_catalog',
  'owned_portfolio_crud_noop', 'owned_holding_crud_noop', 'canonical_input_rejections_unchanged',
  'cross_owner_and_parent_isolation', 'duplicate_and_portfolio_capacity', 'six_decimal_golden_cases',
  'zero_cost_and_rounded_zero', 'honest_empty_partial_unavailable', 'first_native_restart',
  'persisted_portfolios_holdings_and_risk', 'withdrawal_reacceptance_gates', 'no_implicit_record_erasure',
  'durable_per_session_logout', 'second_native_restart', 'real_one_minute_expiry',
  'records_preserved_after_expiry', 'digest_only_storage_no_reflection', 'safe_wire_and_diagnostics',
  'complete_safe_wire_corpus', 'owned_cleanup',
];
const CORPUS_KEYS = ['schema_version', 'scope', 'contract_version', 'provenance', 'source_hashes', 'source_manifest_sha256', 'cases'];
const REPORT_KEYS = ['schema_version', 'scope', 'contract_version', 'success', 'mode', 'tested_commit', 'tested_tree',
  'working_tree_dirty', 'tracked_dirty', 'source_hashes', 'source_manifest_sha256', 'checks', 'required_checks',
  'failures', 'responses_checked', 'corpus_sha256', 'corpus_case_ids', 'native_process', 'python_version', 'limitations'];
const PROCESS_KEYS = ['starts', 'application_restarts', 'owned_pids', 'child_reaped', 'temporary_directory_removed',
  'session_ttl_minutes', 'real_expiry_elapsed_seconds', 'shutdown'];
const PROVENANCE_KEYS = ['kind', 'source', 'command', 'tested_commit', 'tested_tree'];
const CASE_KEYS = ['id', 'operation', 'request', 'status', 'content_type', 'body_utf8', 'expected'];
const MAX_BODY = 262144, MAX_ARTIFACT = 2097152, MAX_SOURCE = 4194304;
const HASH = /^[a-f0-9]{64}$/, REVISION = /^[a-f0-9]{40}$/;
// Body/request fields only: repository-relative source paths are provenance.
// Compare decoded, canonical names so casing and separators cannot turn a
// credential/owner field into a harmless-looking saved rules-snapshot member.
const PRIVATE_KEYS = new Set(['user', 'userid', 'owner', 'ownerid', 'alias', 'session', 'sessionid',
  'token', 'bearer', 'digest', 'dbpath', 'database', 'databasepath', 'localdbpath', 'headers', 'path',
  'logs', 'diagnostics', 'nonce', 'password', 'secret', 'authorization', 'accesstoken', 'refreshtoken',
  'cookie', 'cookies', 'setcookie', 'expiresat', 'apikey', 'credentials', 'proto', 'prototype', 'constructor']);

function invalid(): never { throw new Error(LOCAL_S2_CORPUS_FAILURE); }
function requireValid(condition: unknown): asserts condition { if (!condition) invalid(); }
function object(value: unknown): Json {
  requireValid(value !== null && typeof value === 'object' && !Array.isArray(value));
  return value as Json;
}
function exact(value: unknown, keys: readonly string[]): Json {
  const row = object(value);
  requireValid(Object.keys(row).length === keys.length && keys.every((key) => Object.prototype.hasOwnProperty.call(row, key)));
  return row;
}
function array(value: unknown, maximum: number): unknown[] {
  requireValid(Array.isArray(value) && value.length <= maximum);
  return value as unknown[];
}
function text(value: unknown, maximum = 4096): string {
  requireValid(typeof value === 'string' && value.length > 0 && value.length <= maximum &&
    Buffer.from(value, 'utf8').toString('utf8') === value);
  return value;
}
function hash(bytes: Buffer | string): string { return createHash('sha256').update(bytes).digest('hex'); }
function equal(a: unknown, b: unknown): boolean {
  const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
    : value !== null && typeof value === 'object' ? Object.fromEntries(Object.entries(value as Json)
      .sort(([x], [y]) => x < y ? -1 : x > y ? 1 : 0).map(([key, child]) => [key, canonical(child)])) : value;
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}
function safeData(value: unknown, depth = 0): void {
  requireValid(depth <= 32);
  if (typeof value === 'string') {
    requireValid(Buffer.from(value, 'utf8').toString('utf8') === value &&
      !/(?:^|[^A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?:$|[^A-Za-z0-9_-])/.test(value) &&
      !/\bBearer[ \t]+\S+|(?:[A-Za-z]:[\\/]|file:\/\/|\/(?:Users|home|tmp|var)\/)/i.test(value));
  } else if (Array.isArray(value)) {
    value.forEach((child) => safeData(child, depth + 1));
  } else if (value !== null && typeof value === 'object') {
    Object.entries(value as Json).forEach(([key, child]) => {
      requireValid(!PRIVATE_KEYS.has(key.toLowerCase().replace(/[^a-z0-9]/g, ''))); safeData(child, depth + 1);
    });
  } else {
    requireValid(value === null || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)));
  }
}
function strictJson(serialized: string): Json {
  let offset = 0;
  const whitespace = () => { while (offset < serialized.length && /[ \t\r\n]/.test(serialized[offset])) offset++; };
  const string = (): string => {
    requireValid(serialized[offset] === '"');
    const start = offset++;
    while (offset < serialized.length) {
      const character = serialized[offset++];
      if (character === '"') return JSON.parse(serialized.slice(start, offset)) as string;
      if (character === '\\') { requireValid(offset < serialized.length); offset++; }
    }
    return invalid();
  };
  const value = (depth: number): void => {
    requireValid(depth <= 32); whitespace();
    const character = serialized[offset];
    if (character === '{') {
      offset++; whitespace();
      const keys = new Set<string>();
      if (serialized[offset] === '}') { offset++; return; }
      for (;;) {
        const key = string();
        requireValid(!keys.has(key)); keys.add(key);
        whitespace(); requireValid(serialized[offset++] === ':'); value(depth + 1); whitespace();
        if (serialized[offset] === '}') { offset++; return; }
        requireValid(serialized[offset++] === ','); whitespace();
      }
    }
    if (character === '[') {
      offset++; whitespace();
      if (serialized[offset] === ']') { offset++; return; }
      for (;;) {
        value(depth + 1); whitespace();
        if (serialized[offset] === ']') { offset++; return; }
        requireValid(serialized[offset++] === ','); whitespace();
      }
    }
    if (character === '"') { string(); return; }
    const start = offset;
    while (offset < serialized.length && !/[ \t\r\n,\]}]/.test(serialized[offset])) offset++;
    requireValid(offset > start);
    const scalar = JSON.parse(serialized.slice(start, offset)) as unknown;
    requireValid(scalar === null || typeof scalar === 'boolean' || (typeof scalar === 'number' && Number.isFinite(scalar)));
  };
  value(0); whitespace(); requireValid(offset === serialized.length);
  // Duplicate detection precedes ordinary decoding; captured bytes are untouched.
  return object(JSON.parse(serialized) as unknown);
}
function parse(bytes: Buffer): Json {
  requireValid(Buffer.isBuffer(bytes) && bytes.length > 0 && bytes.length <= MAX_ARTIFACT &&
    !(bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf));
  return strictJson(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}
function scoped(row: Json): void { requireValid(row.scope === LOCAL_SCOPE && row.contract_version === LOCAL_CONTRACT_VERSION); }
function sourceAllowed(path: string): boolean {
  return /^backend\/app\/(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.py$/.test(path) || [
    'backend/local_s2_evidence.py', 'backend/verify_s1_application.py', 'backend/verify_s2_saved_risk.py',
    'backend/verify_s2_manual_portfolio.py', 'backend/data/questionnaire/risk_questionnaire_v1.json',
    'backend/tests/unit/test_local_s2_portfolio_native_harness.py',
    'backend/tests/unit/test_local_s2_risk_native_harness.py',
    'backend/tests/unit/test_s2_saved_risk_corpus.py',
    'backend/tests/unit/test_local_s2_shared_evidence.py',
    'backend/tests/unit/test_local_s2_portfolio_expiry_risk.py',
    'backend/verify_s2_evidence_pair.py',
    'backend/tests/unit/test_s2_evidence_pair_validation.py',
    'data/fixtures/local_s1/contract_cases.v1.json', 'ai/risk/contract.py', 'ai/risk/scoring.py',
    'docs/features/local-application/S2-saved-risk-contract.md',
    'docs/features/local-application/S2-manual-portfolio-contract.md',
  ].includes(path);
}
function sources(value: unknown, expectedManifest: unknown, kind: LocalS2CorpusKind, io: LocalS2CorpusIo): LocalS2SourceHash[] {
  const rows = array(value, 256).map((raw) => {
    const row = exact(raw, ['path', 'sha256']), path = text(row.path, 256), sha256 = text(row.sha256, 64);
    requireValid(sourceAllowed(path) && /^[A-Za-z0-9_./-]+$/.test(path) &&
      path.split('/').every((part) => part !== '' && part !== '.' && part !== '..') && HASH.test(sha256));
    const actual = io.readSource(path);
    requireValid(Buffer.isBuffer(actual) && actual.length <= MAX_SOURCE && hash(actual) === sha256);
    return { path, sha256 };
  });
  requireValid(rows.length >= 2 && new Set(rows.map((row) => row.path)).size === rows.length &&
    rows.some((row) => row.path === 'backend/local_s2_evidence.py') &&
    rows.some((row) => row.path === 'backend/verify_s2_' + (kind === 'risk' ? 'saved_risk' : 'manual_portfolio') + '.py'));
  requireValid(rows.every((row, index) => index === 0 || rows[index - 1].path < row.path));
  const manifest = rows.map((row) => row.path + ' ' + row.sha256.toUpperCase() + '\n').join('');
  requireValid(typeof expectedManifest === 'string' && HASH.test(expectedManifest) && hash(manifest) === expectedManifest);
  return rows;
}
function errorBody(body: Json, code: string): void {
  exact(body, ['success', 'message', 'detail', 'error_code', 'error']);
  const nested = exact(body.error, ['code', 'message', 'fieldErrors', 'correlationId']);
  const message = text(body.message), correlation = text(nested.correlationId, 128);
  requireValid(body.success === false && body.detail === message && body.error_code === code &&
    nested.code === code && nested.message === message && /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(correlation));
  array(nested.fieldErrors, 64).forEach((raw) => { const field = exact(raw, ['field', 'code']); text(field.field, 128); text(field.code, 128); });
}
function wireBody(bodyText: unknown, operation: string, code: string | null): Json {
  const serialized = text(bodyText, MAX_BODY);
  requireValid(Buffer.byteLength(serialized, 'utf8') <= MAX_BODY);
  const body = strictJson(serialized);
  safeData(body);
  if (code !== null) { errorBody(body, code); return body; }
  exact(body, ['success', 'message', 'data', 'meta']);
  requireValid(body.success === true); text(body.message);
  const response = { data: body.data, meta: body.meta };
  switch (operation) {
    case 'questionnaire': checkedS2(response, decodeQuestionnaire, nullMeta); break;
    case 'draft_get': case 'draft_put': checkedS2(response, decodeRiskDraft, updatedMeta); break;
    case 'assessment_create': case 'assessment_detail': checkedS2(response, decodeSavedRisk, riskMeta); break;
    case 'history': checkedS2(response, decodeRiskHistory, nullMeta); break;
    case 'catalogue': checkedS2(response, decodeCatalog, nullMeta); break;
    case 'portfolio_create': case 'portfolio_detail': case 'portfolio_update': checkedS2(response, decodePortfolio, updatedMeta); break;
    case 'portfolio_list': checkedS2(response, decodePortfolioList, nullMeta); break;
    case 'portfolio_delete': checkedS2(response, decodePortfolioDeletion, nullMeta); break;
    case 'holding_create': case 'holding_detail': case 'holding_update': checkedS2(response, decodeHolding, updatedMeta); break;
    case 'holding_list': checkedS2(response, decodeHoldingList, nullMeta); break;
    case 'holding_delete': checkedS2(response, decodeHoldingDeletion, nullMeta); break;
    case 'metrics': checkedS2(response, decodeMetrics, metricsMeta); break;
    default: invalid();
  }
  return body;
}
function decimal(value: unknown, places: number, maximum: string, positive: boolean): void {
  const number = text(value, 32), parts = number.split('.');
  requireValid(new RegExp('^(?:0|[1-9][0-9]*)\\.[0-9]{' + places + '}$').test(number));
  const scaled = parts[0] + parts[1], bound = maximum + '0'.repeat(places);
  const normalized = scaled.replace(/^0+/, '') || '0';
  requireValid((!positive || normalized !== '0') && (normalized.length < bound.length ||
    (normalized.length === bound.length && normalized <= bound)));
}
function requestPayload(entry: Json, body: Json): void {
  const operation = entry.operation, success = object(entry.expected).outcome === 'success';
  if (!success || !['draft_put', 'assessment_create', 'portfolio_create', 'portfolio_update', 'holding_create', 'holding_update'].includes(String(operation))) {
    requireValid(entry.request === null); return;
  }
  const request = object(entry.request); safeData(request);
  const data = object(body.data);
  if (operation === 'draft_put' || operation === 'assessment_create') {
    exact(request, ['questionnaire_id', 'questionnaire_version', 'answers', ...(operation === 'assessment_create' ? ['idempotency_key'] : [])]);
    const input = riskInput({ questionnaire_id: request.questionnaire_id, questionnaire_version: request.questionnaire_version, answers: request.answers }, operation === 'assessment_create');
    if (operation === 'assessment_create') {
      uuidS2(request.idempotency_key);
      requireValid(sameRiskInput(decodeSavedRisk(data).input, input));
    } else {
      const saved = decodeRiskDraft(data); requireValid(saved.updated_at !== null && sameRiskInput(saved, input));
    }
  } else if (operation === 'portfolio_create' || operation === 'portfolio_update') {
    exact(request, ['portfolio_version', 'name', 'description', 'currency']);
    const name = text(request.name, 10000).trim();
    const description = request.description === null ? null : typeof request.description === 'string' ? request.description.trim() : invalid();
    requireValid(request.portfolio_version === 'portfolio.v1' && request.currency === 'USD' && name.length > 0 &&
      Array.from(name).length <= 100 && (description === null || Array.from(description).length <= 500) &&
      data.name === name && data.description === description && data.currency === 'USD');
  } else {
    exact(request, ['holding_version', 'quantity', 'average_cost', 'currency', ...(operation === 'holding_create' ? ['instrument_id'] : [])]);
    requireValid(request.holding_version === 'holding.v1' && request.currency === 'USD');
    decimal(request.quantity, 6, '1000000', true); decimal(request.average_cost, 4, '1000000', false);
    requireValid(request.quantity === data.quantity && request.average_cost === data.average_cost && data.currency === 'USD');
    if (operation === 'holding_create') requireValid(typeof request.instrument_id === 'string' &&
      /^SYN:[A-Z][A-Z0-9_]{0,31}$/.test(request.instrument_id) && request.instrument_id === data.instrument_id);
  }
}
function riskTarget(entry: Json, body: Json): void {
  if (entry.operation === 'history') {
    const target = exact(entry.target, ['limit', 'before']);
    requireValid(target.limit === 2 && (entry.id === 'history_page_next' ? target.before !== null : target.before === null));
    cursorS2(target.before);
  } else if (entry.operation === 'assessment_detail') {
    const target = exact(entry.target, ['assessment_id']); uuidS2(target.assessment_id);
    if (object(entry.expected).outcome === 'success') requireValid(object(body.data).assessment_id === target.assessment_id);
  } else requireValid(entry.target === null);
}
function riskRelationships(cases: LocalS2RiskWireCase[]): void {
  const find = (id: string) => cases.find((entry) => entry.id === id) || invalid();
  const data = (id: string) => object(strictJson(find(id).body_utf8).data);
  const created = data('assessment_created');
  ['assessment_equivalent_replay', 'assessment_detail', 'assessment_after_restart'].forEach((id) => requireValid(equal(data(id), created)));
  const initialRequest = object(find('assessment_created').request), retry = object(find('assessment_equivalent_replay').request);
  requireValid(initialRequest.idempotency_key === retry.idempotency_key &&
    equal(retry.answers, [...array(initialRequest.answers, 10)].reverse()));
  for (const [id, letter] of [['assessment_created', 'C'], ['assessment_aggressive', 'E'], ['assessment_conservative', 'A'], ['assessment_inserted_between_pages', 'D']]) {
    const saved = decodeSavedRisk(data(id));
    requireValid(equal(saved.input.answers, RISK_QUESTION_IDS.map((question_id) => ({ question_id, answer_code: question_id + '_' + letter }))));
  }
  requireValid(array(data('draft_initial').answers, 10).length === 0 && data('draft_initial').updated_at === null &&
    array(data('draft_partial_saved').answers, 10).length === 2 && equal(data('draft_partial_saved'), data('draft_partial_resumed')) &&
    array(data('draft_cleared').answers, 10).length === 0 && equal(data('draft_cleared'), data('draft_after_restart')));
  requireValid(array(data('history_initial').items, 2).length === 0 && data('history_initial').next_cursor === null &&
    array(data('other_owner_history_empty').items, 2).length === 0 && data('other_owner_history_empty').next_cursor === null &&
    equal(data('history_single').items, [created]) && data('history_single').next_cursor === null);
  const first = data('history_page_first'), next = data('history_page_next');
  requireValid(equal(first.items, [data('assessment_conservative'), data('assessment_aggressive')]) && first.next_cursor !== null &&
    object(find('history_page_next').target).before === first.next_cursor && equal(next.items, [created]) && next.next_cursor === null &&
    equal(data('history_after_relogin').items, [data('assessment_inserted_between_pages'), data('assessment_conservative')]));
}
function corpus(raw: Buffer, kind: LocalS2CorpusKind, io: LocalS2CorpusIo): Json {
  const value = exact(parse(raw), CORPUS_KEYS); scoped(value);
  requireValid(value.schema_version === 'finex.local_s2.' + (kind === 'risk' ? 'saved_risk' : 'portfolio') + '_corpus.v1');
  const provenance = exact(value.provenance, PROVENANCE_KEYS);
  requireValid(provenance.kind === 'native_tcp_capture' && provenance.source === 'owned_loopback_uvicorn' &&
    provenance.command === 'python verify_s2_' + (kind === 'risk' ? 'saved_risk' : 'manual_portfolio') + '.py' &&
    REVISION.test(text(provenance.tested_commit, 40)) && REVISION.test(text(provenance.tested_tree, 40)));
  sources(value.source_hashes, value.source_manifest_sha256, kind, io);
  const specs = kind === 'risk' ? RISK_CASES : PORTFOLIO_CASES, identifiers = Object.keys(specs);
  const cases = array(value.cases, identifiers.length);
  requireValid(cases.length === identifiers.length);
  cases.forEach((rawCase, index) => {
    const entry = exact(rawCase, kind === 'risk' ? [...CASE_KEYS, 'target'] : CASE_KEYS);
    requireValid(entry.id === identifiers[index]);
    const [operation, status, code] = specs[identifiers[index]], expected = exact(entry.expected, code === null ? ['outcome'] : ['outcome', 'error_code']);
    requireValid(entry.operation === operation && entry.status === status && entry.content_type === 'application/json' &&
      expected.outcome === (code === null ? 'success' : 'error') && expected.error_code === (code === null ? undefined : code));
    const body = wireBody(entry.body_utf8, operation, code);
    requestPayload(entry, body);
    if (kind === 'risk') riskTarget(entry, body);
  });
  if (kind === 'risk') riskRelationships(cases as unknown as LocalS2RiskWireCase[]);
  return value;
}
function report(raw: Buffer, rawCorpus: Buffer, parsedCorpus: Json, kind: LocalS2CorpusKind, io: LocalS2CorpusIo): Json {
  const value = exact(parse(raw), REPORT_KEYS); scoped(value);
  const provenance = object(parsedCorpus.provenance);
  requireValid(value.schema_version === 'finex.local_s2.' + (kind === 'risk' ? 'saved_risk' : 'manual_portfolio') + '.acceptance.v1' &&
    value.success === true && value.mode === 'owned_native_tcp' && value.working_tree_dirty === false && value.tracked_dirty === false &&
    value.tested_commit === provenance.tested_commit && value.tested_tree === provenance.tested_tree &&
    value.corpus_sha256 === hash(rawCorpus));
  sources(value.source_hashes, value.source_manifest_sha256, kind, io);
  requireValid(equal(value.source_hashes, parsedCorpus.source_hashes) && value.source_manifest_sha256 === parsedCorpus.source_manifest_sha256);
  const checks = kind === 'risk' ? RISK_CHECKS : PORTFOLIO_CHECKS, ids = Object.keys(kind === 'risk' ? RISK_CASES : PORTFOLIO_CASES);
  requireValid(equal(value.required_checks, checks) && equal(value.corpus_case_ids, ids) && array(value.failures, 0).length === 0 &&
    typeof value.responses_checked === 'number' && Number.isSafeInteger(value.responses_checked) && value.responses_checked >= ids.length);
  const actualChecks = array(value.checks, checks.length);
  requireValid(actualChecks.length === checks.length);
  actualChecks.forEach((item, index) => { const row = exact(item, ['id', 'passed']); requireValid(row.id === checks[index] && row.passed === true); });
  const native = exact(value.native_process, PROCESS_KEYS), starts = kind === 'risk' ? 4 : 5;
  const pids = array(native.owned_pids, starts);
  requireValid(native.starts === starts && native.application_restarts === 2 && pids.length === starts &&
    pids.every((pid) => typeof pid === 'number' && Number.isSafeInteger(pid) && pid > 0) && new Set(pids).size === starts &&
    native.child_reaped === true && native.temporary_directory_removed === true && native.session_ttl_minutes === 1 &&
    native.shutdown === 'owned_terminate_and_reap' && (kind === 'risk' ? native.real_expiry_elapsed_seconds === null :
      typeof native.real_expiry_elapsed_seconds === 'number' && Number.isFinite(native.real_expiry_elapsed_seconds) &&
      native.real_expiry_elapsed_seconds >= 59 && native.real_expiry_elapsed_seconds <= 75));
  requireValid(/^\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(text(value.python_version, 32)));
  const limits = array(value.limitations, 32); requireValid(limits.length > 0);
  limits.forEach((limit) => { text(limit, 1024); safeData(limit); });
  return value;
}
function regularBytes(location: string, maximum: number): Buffer {
  const initial = lstatSync(location); requireValid(initial.isFile() && !initial.isSymbolicLink() && initial.size <= maximum);
  const fd = openSync(location, 'r');
  try {
    const opened = fstatSync(fd); requireValid(opened.isFile() && opened.dev === initial.dev && opened.ino === initial.ino && opened.size === initial.size);
    const bytes = Buffer.alloc(opened.size + 1);
    let count = 0;
    while (count < bytes.length) { const read = readSync(fd, bytes, count, bytes.length - count, null); if (read === 0) break; count += read; }
    const final = fstatSync(fd), named = lstatSync(location);
    requireValid(count === opened.size && final.size === opened.size && final.mtimeMs === opened.mtimeMs &&
      named.dev === opened.dev && named.ino === opened.ino && named.size === opened.size && !named.isSymbolicLink());
    return bytes.subarray(0, count);
  } finally { closeSync(fd); }
}
function defaultIo(): LocalS2CorpusIo {
  const root = realpathSync(resolve(__dirname, '../../..'));
  const git = (args: string[]) => execFileSync('git', ['--no-replace-objects', '-c', 'safe.directory=' + root, ...args],
    { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 10000, maxBuffer: 2097152 }).trim();
  return {
    revision: () => ({ commit: git(['rev-parse', '--verify', 'HEAD^{commit}']), tree: git(['rev-parse', '--verify', 'HEAD^{tree}']),
      workingTreeDirty: git(['status', '--porcelain', '--untracked-files=normal']) !== '', trackedDirty: git(['diff', '--name-only', 'HEAD', '--']) !== '' }),
    readArtifact: (location, maximum) => {
      requireValid(location.length <= 4096 && location === location.trim() && location.length > 0 &&
        !location.includes('\0') && !/^(?:\\\\|\/\/)/.test(location));
      return regularBytes(location, maximum);
    },
    readSource: (repositoryPath) => {
      requireValid(sourceAllowed(repositoryPath));
      let directory = root;
      for (const part of repositoryPath.split('/').slice(0, -1)) {
        directory = resolve(directory, part);
        const info = lstatSync(directory);
        requireValid(info.isDirectory() && !info.isSymbolicLink());
      }
      const path = resolve(root, repositoryPath), resolved = realpathSync(path), local = relative(root, resolved);
      requireValid(!isAbsolute(local) && local !== '..' && !local.startsWith('../') && !local.startsWith('..\\'));
      return regularBytes(path, MAX_SOURCE);
    },
  };
}
function freeze(value: unknown): void {
  if (value !== null && typeof value === 'object') { Object.values(value as Json).forEach(freeze); Object.freeze(value); }
}
/** Real artifacts are mandatory together; injected unit seams never become a fallback. */
export function configuredLocalS2Corpora(
  environment: LocalS2CorpusEnvironment,
  injectedIo?: LocalS2CorpusIo,
): LocalS2NativePair | null {
  try {
    requireValid(environment.required === undefined || environment.required === '0' || environment.required === '1');
    const paths = [environment.riskCorpus, environment.riskReport, environment.portfolioCorpus, environment.portfolioReport];
    if (paths.every((path) => path === undefined)) { requireValid(environment.required !== '1'); return null; }
    requireValid(paths.every((path) => typeof path === 'string' && path.length > 0 && path.trim() === path));
    const io = injectedIo ?? defaultIo(), before = io.revision();
    requireValid(REVISION.test(before.commit) && REVISION.test(before.tree) && before.workingTreeDirty === false && before.trackedDirty === false);
    const [riskBytes, riskReportBytes, portfolioBytes, portfolioReportBytes] = paths.map((path) => io.readArtifact(path!, MAX_ARTIFACT));
    const risk = corpus(riskBytes, 'risk', io), portfolio = corpus(portfolioBytes, 'portfolio', io);
    const riskReport = report(riskReportBytes, riskBytes, risk, 'risk', io), portfolioReport = report(portfolioReportBytes, portfolioBytes, portfolio, 'portfolio', io);
    for (const item of [risk, portfolio]) {
      const provenance = object(item.provenance);
      requireValid(provenance.tested_commit === before.commit && provenance.tested_tree === before.tree);
      sources(item.source_hashes, item.source_manifest_sha256, item === risk ? 'risk' : 'portfolio', io);
    }
    requireValid(equal(before, io.revision()));
    const pair = { risk: { corpus: risk, report: riskReport }, portfolio: { corpus: portfolio, report: portfolioReport } } as unknown as LocalS2NativePair;
    freeze(pair);
    return pair;
  } catch { return invalid(); }
}
