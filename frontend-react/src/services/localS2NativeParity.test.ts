/** Native pair gate plus original UTF-8 public-method replay; no server is launched here. */
import { createHash, randomBytes } from 'crypto';
import historicalPortfolio from '../testHelpers/fixtures/localS2PortfolioHistorical.json';
import {
  LOCAL_S2_CORPUS_FAILURE, configuredLocalS2Corpora, LocalS2CorpusEnvironment,
  LocalS2CorpusIo, LocalS2NativePair, LocalS2PortfolioWireCase, LocalS2RiskWireCase,
} from '../testHelpers/localS2Corpus';
import {
  draftFixture, inputFixture, questionnaireFixture, s2Scope,
  s2Time, savedFixture,
} from '../testHelpers/localS2';
import { LocalApplicationError, LOCAL_CONTRACT_VERSION, LOCAL_SCOPE } from './localApplicationBoundary';
import { createLocalS2Client, LocalS2Api } from './localS2Client';
import {
  HoldingInput, HoldingUpdate, PortfolioInput, RiskInput, RiskSubmission,
  objectS2, utcInstant,
} from './localS2Models';

type Json = Record<string, unknown>;
type Case = LocalS2RiskWireCase | LocalS2PortfolioWireCase;
type Spec = readonly [string, number, string | null];
const RISK_SPECS: Record<string, Spec> = {
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
const PORTFOLIO_SPECS: Record<string, Spec> = {
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
const UNIT_COMMIT = '1'.repeat(40), UNIT_TREE = '2'.repeat(40);
const ISSUED_ORIGIN = 'http://127.0.0.1:8000';
const SYNTHETIC_TARGET = '00000000-0000-4000-8000-000000000070';
const SYNTHETIC_HOLDING_TARGET = '00000000-0000-4000-8000-000000000071';
const ENV: LocalS2CorpusEnvironment = {
  required: '1', riskCorpus: 'unit-risk-corpus', riskReport: 'unit-risk-report',
  portfolioCorpus: 'unit-portfolio-corpus', portfolioReport: 'unit-portfolio-report',
};
function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
function hash(value: Buffer | string): string { return createHash('sha256').update(value).digest('hex'); }
function jsonBytes(value: unknown): Buffer { return Buffer.from(JSON.stringify(value, null, 2) + '\n', 'utf8'); }
function canonical(value: unknown): unknown {
  return Array.isArray(value) ? value.map(canonical) : value !== null && typeof value === 'object'
    ? Object.fromEntries(Object.entries(value as Json).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)
      .map(([key, entry]) => [key, canonical(entry)])) : value;
}
function equivalent(a: unknown, b: unknown): boolean { return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b)); }
function envelope(data: unknown, asOf: string | null = null): string {
  return JSON.stringify({ success: true, message: 'Unit-only synthetic response, not native evidence.', data,
    meta: { apiVersion: 'v1', dataStatus: 'CACHED', dataAsOf: asOf, correlationId: 'unit-s2-wire' } });
}
function errorEnvelope(code: string): string {
  const message = 'Unit-only synthetic failure, not native evidence.';
  return JSON.stringify({ success: false, message, detail: message, error_code: code,
    error: { code, message, fieldErrors: [], correlationId: 'unit-s2-failure' } });
}
function input(letter = 'C'): RiskInput {
  return { ...inputFixture(), answers: inputFixture().answers.map((a) => ({ ...a, answer_code: a.question_id + '_' + letter })) };
}
function saved(letter: string, digit: string) {
  const value = savedFixture();
  return { ...value, assessment_id: '00000000-0000-4000-8000-00000000000' + digit, input: input(letter),
    assessment: { ...value.assessment, willingness_score: letter === 'E' ? 100 : letter === 'A' ? 0 : letter === 'D' ? 75 : 50,
      capacity_score: letter === 'E' ? 100 : letter === 'A' ? 0 : letter === 'D' ? 75 : 50,
      composite_score: letter === 'E' ? 100 : letter === 'A' ? 0 : letter === 'D' ? 75 : 50,
      risk_category: letter === 'E' ? { code: 'AGGRESSIVE', label: 'Aggressive' } : letter === 'A'
        ? { code: 'CONSERVATIVE', label: 'Conservative' } : { code: 'MODERATE', label: 'Moderate' } } };
}
/** Handcrafted dependency-injected documents only; never used as a native fallback. */
function riskUnitCases(): LocalS2RiskWireCase[] {
  const original = saved('C', '3'), aggressive = saved('E', '4'), conservative = saved('A', '5'), inserted = saved('D', '6');
  const partial = { ...draftFixture(), answers: input().answers.slice(0, 2), updated_at: s2Time };
  const cleared = { ...draftFixture(), updated_at: s2Time };
  const fullRequest = { ...input(), idempotency_key: '00000000-0000-4000-8000-000000000010' };
  const bodies: Record<string, string> = {
    questionnaire: envelope(questionnaireFixture()), draft_initial: envelope(draftFixture()),
    draft_partial_saved: envelope(partial, s2Time), draft_partial_resumed: envelope(partial, s2Time),
    history_initial: envelope({ ...s2Scope, items: [], next_cursor: null }),
    assessment_created: envelope(original, s2Time), assessment_equivalent_replay: envelope(original, s2Time),
    assessment_detail: envelope(original, s2Time), history_single: envelope({ ...s2Scope, items: [original], next_cursor: null }),
    other_owner_history_empty: envelope({ ...s2Scope, items: [], next_cursor: null }),
    draft_cleared: envelope(cleared, s2Time), draft_after_restart: envelope(cleared, s2Time),
    assessment_after_restart: envelope(original, s2Time), assessment_aggressive: envelope(aggressive, s2Time),
    assessment_conservative: envelope(conservative, s2Time),
    history_page_first: envelope({ ...s2Scope, items: [conservative, aggressive], next_cursor: '2' }),
    assessment_inserted_between_pages: envelope(inserted, s2Time),
    history_page_next: envelope({ ...s2Scope, items: [original], next_cursor: null }),
    history_after_relogin: envelope({ ...s2Scope, items: [inserted, conservative], next_cursor: '3' }),
  };
  return Object.entries(RISK_SPECS).map(([id, [operation, status, code]]) => {
    const request = operation === 'draft_put' && code === null ? { ...input(), answers: id === 'draft_cleared' ? [] : input().answers.slice(0, 2) }
      : operation === 'assessment_create' && code === null ? id === 'assessment_equivalent_replay'
        ? { ...clone(fullRequest), answers: [...fullRequest.answers].reverse() }
        : id === 'assessment_created' ? clone(fullRequest)
          : { ...input(id === 'assessment_aggressive' ? 'E' : id === 'assessment_conservative' ? 'A' : 'D'),
            idempotency_key: '00000000-0000-4000-8000-' + String(11 + Object.keys(RISK_SPECS).indexOf(id)).padStart(12, '0') }
        : null;
    return { id, operation: operation as LocalS2RiskWireCase['operation'], status, content_type: 'application/json',
      target: operation === 'history' ? { limit: 2, before: id === 'history_page_next' ? '2' : null }
        : operation === 'assessment_detail' ? { assessment_id: id === 'assessment_missing' ? SYNTHETIC_TARGET : original.assessment_id } : null,
      request, body_utf8: code === null ? bodies[id] : errorEnvelope(code),
      expected: code === null ? { outcome: 'success' } : { outcome: 'error', error_code: code } };
  });
}
interface UnitEvidence { risk: Json; riskReport: Json; portfolio: Json; portfolioReport: Json; sources: Record<string, Buffer>; }
function manifest(sources: { path: string; sha256: string }[]): string {
  return hash([...sources].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)
    .map((s) => s.path + ' ' + s.sha256.toUpperCase() + '\n').join(''));
}
function unitEvidence(): UnitEvidence {
  const sources: Record<string, Buffer> = {
    'backend/local_s2_evidence.py': Buffer.from('unit-only evidence source\n'),
    'backend/verify_s2_saved_risk.py': Buffer.from('unit-only risk source\n'),
    'backend/verify_s2_manual_portfolio.py': Buffer.from('unit-only portfolio source\n'),
  };
  const sourceHashes = Object.keys(sources).sort().map((path) => ({ path, sha256: hash(sources[path]) }));
  const makeCorpus = (kind: 'risk' | 'portfolio', cases: unknown[]) => ({
    schema_version: 'finex.local_s2.' + (kind === 'risk' ? 'saved_risk' : 'portfolio') + '_corpus.v1',
    scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION,
    provenance: { kind: 'native_tcp_capture', source: 'owned_loopback_uvicorn',
      command: 'python verify_s2_' + (kind === 'risk' ? 'saved_risk' : 'manual_portfolio') + '.py',
      tested_commit: UNIT_COMMIT, tested_tree: UNIT_TREE },
    source_hashes: clone(sourceHashes), source_manifest_sha256: manifest(sourceHashes), cases,
  });
  const risk = makeCorpus('risk', riskUnitCases());
  // Old public bytes are used only as unit inputs with fake I/O, never native proof.
  const portfolio = makeCorpus('portfolio', clone(historicalPortfolio.cases));
  const report = (kind: 'risk' | 'portfolio', corpus: Json, checks: string[]) => ({
    schema_version: 'finex.local_s2.' + (kind === 'risk' ? 'saved_risk' : 'manual_portfolio') + '.acceptance.v1',
    scope: LOCAL_SCOPE, contract_version: LOCAL_CONTRACT_VERSION, success: true, mode: 'owned_native_tcp',
    tested_commit: UNIT_COMMIT, tested_tree: UNIT_TREE, working_tree_dirty: false, tracked_dirty: false,
    source_hashes: clone(sourceHashes), source_manifest_sha256: manifest(sourceHashes),
    checks: checks.map((id) => ({ id, passed: true })), required_checks: [...checks], failures: [],
    responses_checked: (corpus.cases as unknown[]).length, corpus_sha256: hash(jsonBytes(corpus)),
    corpus_case_ids: (corpus.cases as Case[]).map((entry) => entry.id),
    native_process: { starts: kind === 'risk' ? 4 : 5, application_restarts: 2,
      owned_pids: kind === 'risk' ? [1001, 1002, 1003, 1004] : [1005, 1006, 1007, 1008, 1009],
      child_reaped: true, temporary_directory_removed: true, session_ttl_minutes: 1,
      real_expiry_elapsed_seconds: kind === 'risk' ? null : 60.125, shutdown: 'owned_terminate_and_reap' },
    python_version: '3.13.0', limitations: ['UNIT_TEST_DOCUMENT_NOT_NATIVE_EVIDENCE'],
  });
  return { risk, portfolio, riskReport: report('risk', risk, RISK_CHECKS),
    portfolioReport: report('portfolio', portfolio, PORTFOLIO_CHECKS), sources };
}
function bindDocuments(documents: UnitEvidence): void {
  for (const [corpus, report] of [[documents.risk, documents.riskReport], [documents.portfolio, documents.portfolioReport]]) {
    report.corpus_sha256 = hash(jsonBytes(corpus));
  }
}
function unitIo(documents: UnitEvidence): LocalS2CorpusIo {
  const files: Record<string, Buffer> = {
    'unit-risk-corpus': jsonBytes(documents.risk), 'unit-risk-report': jsonBytes(documents.riskReport),
    'unit-portfolio-corpus': jsonBytes(documents.portfolio), 'unit-portfolio-report': jsonBytes(documents.portfolioReport),
  };
  return { revision: () => ({ commit: UNIT_COMMIT, tree: UNIT_TREE, workingTreeDirty: false, trackedDirty: false }),
    readSource: (path) => { if (!Object.prototype.hasOwnProperty.call(documents.sources, path)) throw new Error('unit source unavailable'); return documents.sources[path]; },
    readArtifact: (location) => { if (!Object.prototype.hasOwnProperty.call(files, location)) throw new Error('unit artifact unavailable'); return files[location]; } };
}
function accepted(documents = unitEvidence(), io = unitIo(documents)): boolean {
  try { return configuredLocalS2Corpora(ENV, io) !== null; } catch { return false; }
}
function safelyRejected(environment: LocalS2CorpusEnvironment, io: LocalS2CorpusIo): boolean {
  try { configuredLocalS2Corpora(environment, io); return false; }
  catch (failure) { return failure instanceof Error && failure.message === LOCAL_S2_CORPUS_FAILURE; }
}
function mutated(body: string, action: (value: Json) => void): string {
  const value = objectS2(JSON.parse(body)); action(value); return JSON.stringify(value);
}
type ArtifactSlot = 'riskCorpus' | 'riskReport' | 'portfolioCorpus' | 'portfolioReport';
type DuplicateSpelling = 'literal' | 'escapedFirst' | 'escapedLast';
function duplicateMember(serialized: string, key: string, value: unknown, spelling: DuplicateSpelling): string {
  const quote = JSON.stringify(key), escaped = '"' + '\\u' + key.charCodeAt(0).toString(16).padStart(4, '0') + key.slice(1) + '"';
  const regexEscape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const needle = new RegExp(regexEscape(quote) + '(\\s*:\\s*)' + regexEscape(JSON.stringify(value)));
  const first = spelling === 'escapedFirst' ? escaped : quote, last = spelling === 'escapedLast' ? escaped : quote;
  // The earlier credential-shaped value must not disappear under last-member wins.
  const hidden = JSON.stringify(randomBytes(32).toString('base64url'));
  const result = serialized.replace(needle, (_match, separator: string) => first + separator + hidden + ',' + last + separator + JSON.stringify(value));
  expect(result !== serialized).toBe(true);
  return result;
}
function artifactIo(documents: UnitEvidence, slot: ArtifactSlot, bytes: Buffer): LocalS2CorpusIo {
  const original = unitIo(documents), overrides: Record<string, Buffer> = { [ENV[slot]!]: bytes };
  if (slot === 'riskCorpus' || slot === 'portfolioCorpus') {
    const reportSlot = slot === 'riskCorpus' ? 'riskReport' : 'portfolioReport';
    const report = clone(slot === 'riskCorpus' ? documents.riskReport : documents.portfolioReport);
    report.corpus_sha256 = hash(bytes);
    overrides[ENV[reportSlot]!] = jsonBytes(report);
  }
  return { ...original, readArtifact: (location, limit) => overrides[location] ?? original.readArtifact(location, limit) };
}

describe('S2 native pair guards (synthetic unit I/O, not native acceptance)', () => {
  test('accepts complete cleanup-bound paired evidence and legitimate repository source paths', () => {
    expect(accepted()).toBe(true);
  });
  test.each([
    'backend/tests/unit/test_s2_saved_risk_corpus.py',
    'backend/tests/unit/test_local_s2_shared_evidence.py',
    'backend/tests/unit/test_local_s2_portfolio_expiry_risk.py',
  ])('accepts the current producer guard source %s', (path) => {
    const documents = unitEvidence();
    documents.sources[path] = Buffer.from('synthetic unit-only producer guard source\n');
    const rows = Object.keys(documents.sources).sort().map((sourcePath) => ({
      path: sourcePath, sha256: hash(documents.sources[sourcePath]),
    }));
    for (const [corpus, report] of [
      [documents.risk, documents.riskReport], [documents.portfolio, documents.portfolioReport],
    ]) {
      corpus.source_hashes = clone(rows);
      report.source_hashes = clone(rows);
      corpus.source_manifest_sha256 = manifest(rows);
      report.source_manifest_sha256 = manifest(rows);
    }
    bindDocuments(documents);
    expect(accepted(documents)).toBe(true);
  });
  test.each([
    'backend/verify_s2_evidence_pair.py',
    'backend/tests/unit/test_s2_evidence_pair_validation.py',
  ])('accepts the explicit passive pair-guard source %s', (path) => {
    const documents = unitEvidence();
    documents.sources[path] = Buffer.from('synthetic unit-only passive pair guard source\n');
    const rows = Object.keys(documents.sources).sort().map((sourcePath) => ({ path: sourcePath, sha256: hash(documents.sources[sourcePath]) }));
    for (const [corpus, report] of [[documents.risk, documents.riskReport], [documents.portfolio, documents.portfolioReport]]) {
      corpus.source_hashes = clone(rows); report.source_hashes = clone(rows);
      corpus.source_manifest_sha256 = manifest(rows); report.source_manifest_sha256 = manifest(rows);
    }
    bindDocuments(documents);
    expect(accepted(documents)).toBe(true);
  });
  const artifactDuplicates = (['riskCorpus', 'riskReport', 'portfolioCorpus', 'portfolioReport'] as const).flatMap((slot) =>
    (['top', 'nested'] as const).flatMap((position) => (['literal', 'escapedFirst', 'escapedLast'] as const).map((spelling) => [slot, position, spelling] as const)));
  test.each(artifactDuplicates)('%s rejects %s duplicate keys (%s), even after exact digest rebinding', (slot, position, spelling) => {
    const documents = unitEvidence(), isCorpus = slot.endsWith('Corpus');
    const document = slot === 'riskCorpus' ? documents.risk : slot === 'portfolioCorpus' ? documents.portfolio
      : slot === 'riskReport' ? documents.riskReport : documents.portfolioReport;
    const key = position === 'top' ? isCorpus ? 'scope' : 'success' : isCorpus ? 'command' : 'shutdown';
    const value = position === 'top' ? document[key] : objectS2(document[isCorpus ? 'provenance' : 'native_process'])[key];
    const raw = Buffer.from(duplicateMember(jsonBytes(document).toString('utf8'), key, value, spelling), 'utf8');
    expect(safelyRejected(ENV, artifactIo(documents, slot, raw))).toBe(true);
  });
  const bodyDuplicates = (['risk', 'portfolio'] as const).flatMap((kind) =>
    (['top', 'meta', 'data', 'arrayObject'] as const).flatMap((position) => (['literal', 'escapedFirst', 'escapedLast'] as const).map((spelling) => [kind, position, spelling] as const)));
  test.each(bodyDuplicates)('%s raw body rejects %s duplicate keys (%s), without hiding earlier credentials', (kind, position, spelling) => {
    const documents = unitEvidence(), corpus = kind === 'risk' ? documents.risk : documents.portfolio;
    const first = (corpus.cases as Case[])[0], body = objectS2(JSON.parse(first.body_utf8)), data = objectS2(body.data);
    const key = position === 'top' ? 'message' : position === 'meta' ? 'correlationId' : position === 'data' ? 'scope'
      : kind === 'risk' ? 'code' : 'instrument_id';
    const value = position === 'top' ? body[key] : position === 'meta' ? objectS2(body.meta)[key] : position === 'data' ? data[key]
      : kind === 'risk' ? objectS2((objectS2((data.questions as Json[])[0]).options as Json[])[0])[key]
        : objectS2((data.items as Json[])[0])[key];
    first.body_utf8 = duplicateMember(first.body_utf8, key, value, spelling);
    bindDocuments(documents);
    expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
  });
  test.each(['riskCorpus', 'riskReport', 'portfolioCorpus', 'portfolioReport'] as const)('%s accepts a single escaped key and separate nested objects', (slot) => {
    const documents = unitEvidence(), document = slot === 'riskCorpus' ? documents.risk : slot === 'portfolioCorpus' ? documents.portfolio
      : slot === 'riskReport' ? documents.riskReport : documents.portfolioReport;
    const bytes = Buffer.from(jsonBytes(document).toString('utf8').replace('"scope"', '"sco\\u0070e"'), 'utf8');
    expect(accepted(documents, artifactIo(documents, slot, bytes))).toBe(true);
  });
  test.each(['risk', 'portfolio'] as const)('%s preserves valid nested Unicode, escaped quotes and braces', (kind) => {
    const documents = unitEvidence(), corpus = kind === 'risk' ? documents.risk : documents.portfolio;
    const first = (corpus.cases as Case[])[0];
    first.body_utf8 = mutated(first.body_utf8, (value) => { value.message = 'Unit-only "escaped" quote, braces { }, literal \\u1234 and π — Ω'; });
    bindDocuments(documents);
    expect(accepted(documents)).toBe(true);
  });
  test.each([
    'user', 'user_id', 'owner', 'owner_id', 'alias', 'session', 'session_id',
    'token', 'bearer', 'digest', 'db_path', 'database', 'headers', 'path',
    'logs', 'diagnostics', 'nonce', 'password', 'secret', 'authorization',
    'access_token', 'refresh_token', 'cookie', 'cookies', 'set-cookie',
    'expires_at', 'api_key', 'credentials', 'accessToken', 'sessionId', 'DB-Path',
  ])('rules snapshots reject recursive private field %s without printing its value', (key) => {
    const documents = unitEvidence();
    let changed = 0;
    const addPrivateField = (value: unknown): void => {
      if (Array.isArray(value)) value.forEach(addPrivateField);
      else if (value !== null && typeof value === 'object') {
        const row = value as Json;
        // Keep every immutable replay/history snapshot consistent. Rejection
        // must be the privacy boundary, not a broken cross-case relationship.
        if (Object.prototype.hasOwnProperty.call(row, 'rules_snapshot')) {
          objectS2(row.rules_snapshot)[key] = 'synthetic-unit-only-private-value';
          changed++;
        }
        Object.values(row).forEach(addPrivateField);
      }
    };
    for (const item of documents.risk.cases as Case[]) {
      item.body_utf8 = mutated(item.body_utf8, addPrivateField);
    }
    expect(changed > 0).toBe(true);
    bindDocuments(documents);
    expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
  });
  test.each([undefined, '0'])('absence is explicit without a fallback (flag %s)', (required) => {
    let correct = false;
    try { correct = configuredLocalS2Corpora({ required }, unitIo(unitEvidence())) === null; } catch { /* safe boolean only */ }
    expect(correct).toBe(true);
  });
  test.each(['true', 'false', '', '2'])('unknown required flag fails closed (case %s)', (required) => {
    expect(safelyRejected({ ...ENV, required }, unitIo(unitEvidence()))).toBe(true);
  });
  test.each(['riskCorpus', 'riskReport', 'portfolioCorpus', 'portfolioReport'] as const)('required pair rejects missing %s', (field) => {
    expect(safelyRejected({ ...ENV, [field]: undefined }, unitIo(unitEvidence()))).toBe(true);
  });
  test.each(['riskCorpus', 'riskReport', 'portfolioCorpus', 'portfolioReport'] as const)('partial optional configuration rejects %s alone', (field) => {
    expect(safelyRejected({ required: '0', [field]: ENV[field] }, unitIo(unitEvidence()))).toBe(true);
  });
  test.each(['risk', 'portfolio'] as const)('%s evidence must identify current clean checkout', (kind) => {
    const documents = unitEvidence();
    const io = unitIo(documents);
    for (const revision of [
      { commit: '3'.repeat(40), tree: UNIT_TREE, workingTreeDirty: false, trackedDirty: false },
      { commit: UNIT_COMMIT, tree: '3'.repeat(40), workingTreeDirty: false, trackedDirty: false },
      { commit: UNIT_COMMIT, tree: UNIT_TREE, workingTreeDirty: true, trackedDirty: false },
      { commit: UNIT_COMMIT, tree: UNIT_TREE, workingTreeDirty: false, trackedDirty: true },
    ]) expect(safelyRejected(ENV, { ...io, revision: () => revision })).toBe(true);
  });
  test.each(['risk', 'portfolio'] as const)('%s source bytes are actually rehashed, not only self-consistent', (kind) => {
    const documents = unitEvidence(), io = unitIo(documents);
    expect(safelyRejected(ENV, { ...io, readSource: () => Buffer.from('different actual source') })).toBe(true);
  });
  test.each(['risk', 'portfolio'] as const)('%s digest is exact bytes, not parsed/reserialized JSON', (kind) => {
    const documents = unitEvidence(), io = unitIo(documents);
    const location = kind === 'risk' ? ENV.riskCorpus! : ENV.portfolioCorpus!;
    expect(safelyRejected(ENV, { ...io, readArtifact: (path, limit) => {
      const raw = io.readArtifact(path, limit); return path === location ? Buffer.concat([raw, Buffer.from(' ')]) : raw;
    } })).toBe(true);
  });
  const reportMutations = [
    'schema', 'scope', 'contract', 'unsuccessful', 'failure', 'dirty', 'trackedDirty',
    'commit', 'tree', 'manifest', 'sourceList', 'digest', 'missingCheck', 'duplicateCheck',
    'wrongCheckOrder', 'falseCheck', 'requiredCheckOrder', 'missingCase', 'caseOrder',
    'starts', 'restarts', 'pids', 'reaped', 'removed', 'ttl', 'expiry', 'shutdown', 'responses',
  ];
  test.each((['risk', 'portfolio'] as const).flatMap((kind) => reportMutations.map((mutation) => [kind, mutation] as const)))('%s report rejects %s', (kind, mutation) => {
    const documents = unitEvidence(), report = kind === 'risk' ? documents.riskReport : documents.portfolioReport;
    const native = objectS2(report.native_process);
    if (mutation === 'schema') report.schema_version = 'future.v2';
    if (mutation === 'scope') report.scope = 'educational_local_pilot';
    if (mutation === 'contract') report.contract_version = 'local.v2';
    if (mutation === 'unsuccessful') report.success = false;
    if (mutation === 'failure') report.failures = [{ code: 'PROBE_FAILED' }];
    if (mutation === 'dirty') report.working_tree_dirty = true;
    if (mutation === 'trackedDirty') report.tracked_dirty = true;
    if (mutation === 'commit') report.tested_commit = '3'.repeat(40);
    if (mutation === 'tree') report.tested_tree = '3'.repeat(40);
    if (mutation === 'manifest') report.source_manifest_sha256 = 'f'.repeat(64);
    if (mutation === 'sourceList') report.source_hashes = [];
    if (mutation === 'digest') report.corpus_sha256 = 'f'.repeat(64);
    if (mutation === 'missingCheck') (report.checks as unknown[]).pop();
    if (mutation === 'duplicateCheck') (report.checks as unknown[])[1] = (report.checks as unknown[])[0];
    if (mutation === 'wrongCheckOrder') (report.checks as unknown[]).reverse();
    if (mutation === 'falseCheck') objectS2((report.checks as unknown[])[0]).passed = false;
    if (mutation === 'requiredCheckOrder') (report.required_checks as unknown[]).reverse();
    if (mutation === 'missingCase') (report.corpus_case_ids as unknown[]).pop();
    if (mutation === 'caseOrder') (report.corpus_case_ids as unknown[]).reverse();
    if (mutation === 'starts') native.starts = 3;
    if (mutation === 'restarts') native.application_restarts = 1;
    if (mutation === 'pids') native.owned_pids = [1001, 1001];
    if (mutation === 'reaped') native.child_reaped = false;
    if (mutation === 'removed') native.temporary_directory_removed = false;
    if (mutation === 'ttl') native.session_ttl_minutes = 2;
    if (mutation === 'expiry') native.real_expiry_elapsed_seconds = kind === 'risk' ? 60 : 58.999;
    if (mutation === 'shutdown') native.shutdown = 'unowned';
    if (mutation === 'responses') report.responses_checked = 1;
    expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
  });
  const corpusMutations = ['schema', 'scope', 'contract', 'provenance', 'command', 'commit', 'tree', 'manifest', 'sourcePath',
    'sourceDuplicate', 'sourceMissingShared', 'sourceByte', 'caseMissing', 'caseDuplicate', 'caseExtra', 'caseOrder',
    'operation', 'status', 'outcome', 'error', 'contentType', 'unknownField', 'secret', 'owner', 'privatePath', 'requestPrivacy', 'largeBody', 'invalidBody'];
  test.each((['risk', 'portfolio'] as const).flatMap((kind) => corpusMutations.map((mutation) => [kind, mutation] as const)))('%s corpus rejects %s', (kind, mutation) => {
    const documents = unitEvidence(), corpus = kind === 'risk' ? documents.risk : documents.portfolio;
    const p = objectS2(corpus.provenance), cases = corpus.cases as Case[], first = cases[0];
    if (mutation === 'schema') corpus.schema_version = 'future.v2';
    if (mutation === 'scope') corpus.scope = 'educational_local_pilot';
    if (mutation === 'contract') corpus.contract_version = 'local.v2';
    if (mutation === 'provenance') p.kind = 'synthetic_fixture';
    if (mutation === 'command') p.command = 'unapproved observer';
    if (mutation === 'commit') p.tested_commit = '3'.repeat(40);
    if (mutation === 'tree') p.tested_tree = '3'.repeat(40);
    if (mutation === 'manifest') corpus.source_manifest_sha256 = 'f'.repeat(64);
    if (mutation === 'sourcePath') objectS2((corpus.source_hashes as unknown[])[0]).path = '../private.sqlite3';
    if (mutation === 'sourceDuplicate') (corpus.source_hashes as unknown[]).push(clone((corpus.source_hashes as unknown[])[0]));
    if (mutation === 'sourceMissingShared') corpus.source_hashes = (corpus.source_hashes as { path: string }[]).filter((s) => s.path !== 'backend/local_s2_evidence.py');
    if (mutation === 'sourceByte') objectS2((corpus.source_hashes as unknown[])[0]).sha256 = 'f'.repeat(64);
    if (mutation === 'caseMissing') cases.pop();
    if (mutation === 'caseDuplicate') cases[1] = clone(first);
    if (mutation === 'caseExtra') cases.push({ ...clone(first), id: 'extra' });
    if (mutation === 'caseOrder') cases.reverse();
    if (mutation === 'operation') first.operation = 'history';
    if (mutation === 'status') first.status = 201;
    if (mutation === 'outcome') first.expected = { outcome: 'error', error_code: 'SESSION_INVALID' };
    if (mutation === 'error') cases[cases.length - 1].expected.error_code = 'LOCAL_STORE_UNAVAILABLE';
    if (mutation === 'contentType') Object.assign(first, { content_type: 'text/html' });
    if (mutation === 'unknownField') Object.assign(first, { native_url: 'http://127.0.0.1:8000' });
    if (mutation === 'secret') first.body_utf8 = mutated(first.body_utf8, (v) => { objectS2(v.data).access_token = randomBytes(32).toString('base64url'); });
    if (mutation === 'owner') first.body_utf8 = mutated(first.body_utf8, (v) => { objectS2(v.data).owner_id = SYNTHETIC_TARGET; });
    if (mutation === 'privatePath') first.body_utf8 = mutated(first.body_utf8, (v) => { v.message = 'C:\\private\\unit.sqlite3'; });
    if (mutation === 'requestPrivacy') first.request = { Authorization: 'unit-only forbidden field' };
    if (mutation === 'largeBody') first.body_utf8 = ' '.repeat(262145);
    if (mutation === 'invalidBody') first.body_utf8 = '{';
    bindDocuments(documents);
    expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
  });
  test.each(['riskCorpus', 'riskReport', 'portfolioCorpus', 'portfolioReport'] as const)('blank %s is not an artifact', (field) => {
    expect(safelyRejected({ ...ENV, [field]: ' ' }, unitIo(unitEvidence()))).toBe(true);
  });
  test.each(['invalidUtf8', 'overBudget', 'unavailable'])('raw artifact %s safely fails', (mutation) => {
    const documents = unitEvidence(), io = unitIo(documents);
    expect(safelyRejected(ENV, { ...io, readArtifact: () => {
      if (mutation === 'unavailable') throw new Error(randomBytes(32).toString('base64url'));
      return mutation === 'invalidUtf8' ? Buffer.from([0xff]) : Buffer.alloc(2097153, 32);
    } })).toBe(true);
  });
  test.each(['limit', 'cursor', 'cursorBinding', 'detail', 'missingTarget', 'extraTarget', 'errorRequest', 'putRequest', 'extraRequest', 'wrongKey'])(
    'risk request/target rejects %s', (mutation) => {
      const documents = unitEvidence(), cases = documents.risk.cases as LocalS2RiskWireCase[];
      const history = cases.find((c) => c.id === 'history_page_next')!, detail = cases.find((c) => c.id === 'assessment_detail')!;
      if (mutation === 'limit') Object.assign(history.target!, { limit: 3 });
      if (mutation === 'cursor') Object.assign(history.target!, { before: '01' });
      if (mutation === 'cursorBinding') Object.assign(history.target!, { before: '3' });
      if (mutation === 'detail') Object.assign(detail.target!, { assessment_id: 'invalid' });
      if (mutation === 'missingTarget') delete (detail as unknown as Json).target;
      if (mutation === 'extraTarget') cases[0].target = { assessment_id: SYNTHETIC_TARGET };
      if (mutation === 'errorRequest') cases.find((c) => c.expected.outcome === 'error')!.request = input() as unknown as Json;
      if (mutation === 'putRequest') cases.find((c) => c.id === 'draft_partial_saved')!.request = null;
      if (mutation === 'extraRequest') cases.find((c) => c.id === 'draft_partial_saved')!.request!.owner_id = SYNTHETIC_TARGET;
      if (mutation === 'wrongKey') cases.find((c) => c.id === 'assessment_created')!.request!.idempotency_key = 'invalid';
      bindDocuments(documents);
      expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
    });
  test('portfolio v1 rejects an invented target field', () => {
    const documents = unitEvidence(); Object.assign((documents.portfolio.cases as Case[])[0], { target: null }); bindDocuments(documents);
    expect(safelyRejected(ENV, unitIo(documents))).toBe(true);
  });
  test('privacy traverses bodies and requests, not legitimate repository source provenance', () => {
    expect(accepted()).toBe(true);
  });
});

interface Dispatch { method: 'GET' | 'PUT' | 'POST' | 'DELETE'; path: string; request: unknown; invoke: (api: LocalS2Api, bearer: string) => Promise<unknown>; }
function riskDispatch(entry: LocalS2RiskWireCase): Dispatch {
  const base = '/api/v1/local-risk';
  const request = entry.expected.outcome === 'success' && entry.request !== null ? clone(entry.request)
    : entry.operation === 'draft_put' ? clone(input()) : { ...input(), idempotency_key: SYNTHETIC_TARGET };
  switch (entry.operation) {
    case 'questionnaire': return { method: 'GET', path: base + '/questionnaire', request: null, invoke: (a, t) => a.questionnaire(t) };
    case 'draft_get': return { method: 'GET', path: base + '/draft', request: null, invoke: (a, t) => a.riskDraft(t) };
    case 'draft_put': return { method: 'PUT', path: base + '/draft', request, invoke: (a, t) => a.saveRiskDraft(t, request as unknown as RiskInput) };
    case 'assessment_create': return { method: 'POST', path: base + '/assessments', request, invoke: (a, t) => a.submitRisk(t, request as unknown as RiskSubmission) };
    case 'history': {
      const target = entry.target as { limit: 2; before: string | null };
      return { method: 'GET', path: base + '/assessments?limit=2' + (target.before === null ? '' : '&before=' + target.before), request: null,
        invoke: (a, t) => a.riskHistory(t, target.before) };
    }
    case 'assessment_detail': {
      const target = entry.target as { assessment_id: string };
      return { method: 'GET', path: base + '/assessments/' + target.assessment_id, request: null, invoke: (a, t) => a.riskDetail(t, target.assessment_id) };
    }
  }
}
function portfolioDispatch(entry: LocalS2PortfolioWireCase): Dispatch {
  const base = '/api/v1/local-portfolios', original = objectS2(JSON.parse(entry.body_utf8));
  const data = entry.expected.outcome === 'success' ? objectS2(original.data) : {};
  // Consumer targets only. v1 does not certify the URL of the native capture.
  const p = typeof data.portfolio_id === 'string' ? data.portfolio_id : SYNTHETIC_TARGET;
  const h = typeof data.holding_id === 'string' ? data.holding_id : SYNTHETIC_HOLDING_TARGET;
  const portfolio: PortfolioInput = entry.operation.startsWith('portfolio_') && entry.expected.outcome === 'success' && entry.request !== null ? clone(entry.request) as unknown as PortfolioInput
    : { portfolio_version: 'portfolio.v1', name: 'Canonical legal replay', description: null, currency: 'USD' };
  const normalized = { ...portfolio, name: portfolio.name.trim(), description: portfolio.description === null ? null : portfolio.description.trim() };
  const holding: HoldingInput = entry.operation.startsWith('holding_') && entry.expected.outcome === 'success' && entry.request !== null ? clone(entry.request) as unknown as HoldingInput
    : { holding_version: 'holding.v1', instrument_id: 'SYN:AAPL', quantity: '1.000000', average_cost: '1.0000', currency: 'USD' };
  switch (entry.operation) {
    case 'catalogue': return { method: 'GET', path: base + '/instruments', request: null, invoke: (a, t) => a.catalog(t) };
    case 'portfolio_list': return { method: 'GET', path: base, request: null, invoke: (a, t) => a.portfolios(t) };
    case 'portfolio_create': return { method: 'POST', path: base, request: normalized, invoke: (a, t) => a.createPortfolio(t, portfolio) };
    case 'portfolio_detail': return { method: 'GET', path: base + '/' + p, request: null, invoke: (a, t) => a.portfolio(t, p) };
    case 'portfolio_update': return { method: 'PUT', path: base + '/' + p, request: normalized, invoke: (a, t) => a.updatePortfolio(t, p, portfolio) };
    case 'portfolio_delete': return { method: 'DELETE', path: base + '/' + p, request: null, invoke: (a, t) => a.deletePortfolio(t, p) };
    case 'holding_list': return { method: 'GET', path: base + '/' + p + '/holdings', request: null, invoke: (a, t) => a.holdings(t, p) };
    case 'holding_create': return { method: 'POST', path: base + '/' + p + '/holdings', request: holding, invoke: (a, t) => a.createHolding(t, p, holding) };
    case 'holding_detail': return { method: 'GET', path: base + '/' + p + '/holdings/' + h, request: null, invoke: (a, t) => a.holding(t, p, h) };
    case 'holding_update': return { method: 'PUT', path: base + '/' + p + '/holdings/' + h, request: holding, invoke: (a, t) => a.updateHolding(t, p, h, holding as HoldingUpdate) };
    case 'holding_delete': return { method: 'DELETE', path: base + '/' + p + '/holdings/' + h, request: null, invoke: (a, t) => a.deleteHolding(t, p, h) };
    case 'metrics': return { method: 'GET', path: base + '/' + p + '/metrics', request: null, invoke: (a, t) => a.metrics(t, p) };
  }
}
interface Replay { success: boolean; code: string; wire: boolean; once: boolean; reflected: boolean; value?: unknown; }
async function replay(kind: 'risk' | 'portfolio', entry: Case, replacement?: string): Promise<Replay> {
  const bearer = randomBytes(32).toString('base64url');
  // Freeze dispatch against the ORIGINAL entry before mutating the received response.
  const dispatch = kind === 'risk' ? riskDispatch(entry as LocalS2RiskWireCase) : portfolioDispatch(entry as LocalS2PortfolioWireCase);
  const bytes = Buffer.from(replacement === undefined ? entry.body_utf8 : replacement, 'utf8');
  let calls = 0, wire = true;
  const client = createLocalS2Client({ baseOrigin: ISSUED_ORIGIN, fetchImpl: (async (url, options) => {
    calls++;
    try {
      const headers = objectS2(options?.headers), payload = typeof options?.body === 'string' ? JSON.parse(options.body) as unknown : null;
      wire = wire && String(url) === ISSUED_ORIGIN + dispatch.path && options?.method === dispatch.method &&
        headers.Authorization === 'Bearer ' + bearer && headers.Accept === 'application/json' &&
        options.credentials === 'omit' && options.cache === 'no-store' && options.redirect === 'error' &&
        equivalent(payload, dispatch.request) && !String(url).includes(bearer) && !(options.body || '').toString().includes(bearer) &&
        (dispatch.request === null ? headers['Content-Type'] === undefined : headers['Content-Type'] === 'application/json');
    } catch { wire = false; }
    return { status: entry.status, ok: entry.status >= 200 && entry.status < 300, redirected: false,
      headers: { get: () => entry.content_type }, text: async () => bytes.toString('utf8') } as unknown as Response;
  }) as typeof fetch });
  try {
    const value = await dispatch.invoke(client, bearer);
    return { success: true, code: '', wire, once: calls === 1, reflected: JSON.stringify(value).includes(bearer), value };
  } catch (failure) {
    return { success: false, code: failure instanceof LocalApplicationError ? failure.code : 'UNCLASSIFIED_FAILURE',
      wire, once: calls === 1, reflected: String(failure).includes(bearer) };
  }
}
function sameSuccess(value: unknown, entry: Case): boolean {
  try {
    const actual = objectS2(value), expected = objectS2(JSON.parse(entry.body_utf8));
    const am = objectS2(actual.meta), em = objectS2(expected.meta);
    return equivalent(actual.data, expected.data) && am.apiVersion === em.apiVersion && am.dataStatus === em.dataStatus &&
      am.correlationId === em.correlationId && (em.dataAsOf === null ? am.dataAsOf === null :
        typeof am.dataAsOf === 'string' && typeof em.dataAsOf === 'string' && utcInstant(am.dataAsOf) === utcInstant(em.dataAsOf));
  } catch { return false; }
}
function assertReplay(result: Replay, entry: Case): void {
  // Boolean-only diagnostics: no credentials, raw payload, URL or parser exception.
  expect(result.wire && result.once && !result.reflected).toBe(true);
  expect(result.success === (entry.expected.outcome === 'success')).toBe(true);
  expect(entry.expected.outcome === 'success' ? sameSuccess(result.value, entry) : result.code === entry.expected.error_code).toBe(true);
}
const unitRisk = riskUnitCases();
const unitPortfolio = clone(historicalPortfolio.cases) as LocalS2PortfolioWireCase[];
const unitReplays: { kind: 'risk' | 'portfolio'; cases: Case[] }[] = [
  { kind: 'risk', cases: unitRisk }, { kind: 'portfolio', cases: unitPortfolio },
];
for (const { kind, cases } of unitReplays) {
  describe(kind + ' replay controls (unit/historical bytes, not current native acceptance)', () => {
    test('unit case table matches the frozen complete operation/status/error order', () => {
      const specs = kind === 'risk' ? RISK_SPECS : PORTFOLIO_SPECS;
      expect(equivalent(cases.map((entry) => [entry.id, entry.operation, entry.status, entry.expected.error_code ?? null]),
        Object.entries(specs).map(([id, spec]) => [id, ...spec]))).toBe(true);
    });
    test.each(cases.map((entry) => [entry.id, entry] as const))('%s uses public method and confirms safe issued request', async (_id, entry) => {
      assertReplay(await replay(kind, entry), entry);
    });
  });
}
test.each(['risk', 'portfolio'] as const)('%s mutated detail ID cannot choose its own dispatch target', async (kind) => {
  const entry = kind === 'risk' ? unitRisk.find((c) => c.id === 'assessment_detail')! : unitPortfolio.find((c) => c.id === 'holding_detail')!;
  const changed = mutated(entry.body_utf8, (v) => { objectS2(v.data)[kind === 'risk' ? 'assessment_id' : 'holding_id'] = SYNTHETIC_TARGET; });
  const result = await replay(kind, entry, changed);
  expect(!result.success && result.code === 'RESPONSE_INVALID' && result.wire && result.once && !result.reflected).toBe(true);
});

const environment: LocalS2CorpusEnvironment = {
  required: process.env.FINEX_REQUIRE_LOCAL_S2_CORPUS,
  riskCorpus: process.env.FINEX_LOCAL_S2_RISK_CORPUS, riskReport: process.env.FINEX_LOCAL_S2_RISK_REPORT,
  portfolioCorpus: process.env.FINEX_LOCAL_S2_PORTFOLIO_CORPUS, portfolioReport: process.env.FINEX_LOCAL_S2_PORTFOLIO_REPORT,
};
let nativePair: LocalS2NativePair | null = null, configured = true;
try { nativePair = configuredLocalS2Corpora(environment); } catch { configured = false; }
test('current native pair is fully verified or explicitly absent; required mode never falls back', () => {
  expect(configured).toBe(true);
  if (environment.required === '1') expect(nativePair !== null).toBe(true);
});
if (nativePair !== null) {
  const captures: { kind: 'risk' | 'portfolio'; cases: Case[] }[] = [
    { kind: 'risk', cases: nativePair.risk.corpus.cases }, { kind: 'portfolio', cases: nativePair.portfolio.corpus.cases },
  ];
  for (const { kind, cases } of captures) {
    describe(kind + ' current-checkout native UTF-8 pair replay (not browser or human UAT)', () => {
      test.each(cases.map((entry) => [entry.id, entry] as const))('%s replays original bytes publicly', async (_id, entry) => {
        assertReplay(await replay(kind, entry), entry);
      });
    });
  }
}
