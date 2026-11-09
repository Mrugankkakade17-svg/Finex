/** Historical accepted API bytes only. This does not certify current-client TCP/browser execution. */
import { createHash, randomBytes } from 'crypto';
import historical from '../testHelpers/fixtures/localS2PortfolioHistorical.json';
import { createLocalS2Client, LocalS2Api } from './localS2Client';
import { LocalApplicationError, LOCAL_SCOPE, LOCAL_CONTRACT_VERSION } from './localApplicationClient';
import { HoldingInput, HoldingUpdate, PortfolioInput, exactS2, objectS2, utf8Length } from './localS2Models';
import { holdingId, portfolioId } from '../testHelpers/localS2';

type Json = Record<string, unknown>;
type WireCase = typeof historical.cases[number];
const specs: Record<string, readonly [string, number, string?]> = {
  catalogue: ['catalogue', 200], portfolio_created: ['portfolio_create', 201],
  portfolio_list: ['portfolio_list', 200], portfolio_detail: ['portfolio_detail', 200],
  portfolio_updated: ['portfolio_update', 200], portfolio_unchanged: ['portfolio_update', 200],
  portfolio_deleted: ['portfolio_delete', 200], holding_created: ['holding_create', 201],
  holding_list: ['holding_list', 200], holding_detail: ['holding_detail', 200],
  holding_updated: ['holding_update', 200], holding_unchanged: ['holding_update', 200],
  holding_deleted: ['holding_delete', 200], golden_1: ['metrics', 200], golden_2: ['metrics', 200],
  golden_3: ['metrics', 200], golden_4: ['metrics', 200], golden_5: ['metrics', 200], golden_6: ['metrics', 200],
  empty: ['metrics', 200], zero_cost: ['metrics', 200], partial: ['metrics', 200], unavailable: ['metrics', 200],
  session_invalid: ['portfolio_list', 401, 'SESSION_INVALID'], onboarding_required: ['portfolio_list', 409, 'ONBOARDING_REQUIRED'],
  portfolio_not_found: ['portfolio_detail', 404, 'LOCAL_PORTFOLIO_NOT_FOUND'], holding_not_found: ['holding_detail', 404, 'LOCAL_HOLDING_NOT_FOUND'],
  validation_error: ['holding_create', 422, 'VALIDATION_ERROR'], unsupported_instrument: ['holding_create', 422, 'UNSUPPORTED_INSTRUMENT'],
  holding_duplicate: ['holding_create', 409, 'HOLDING_ALREADY_EXISTS'], portfolio_limit: ['portfolio_create', 409, 'PORTFOLIO_LIMIT_REACHED'],
};

function safeData(value: unknown, depth = 0): boolean {
  if (depth > 32) return false;
  if (typeof value === 'string') return !/\bBearer\s+\S+|(?:[A-Za-z]:[\\/]|file:\/\/|\/(?:Users|home|tmp|var)\/)/i.test(value) &&
    !/(?:^|[^A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?:$|[^A-Za-z0-9_-])/.test(value);
  if (Array.isArray(value)) return value.every((entry) => safeData(entry, depth + 1));
  if (value !== null && typeof value === 'object') return Object.entries(value as Json).every(([key, entry]) =>
    !['access_token', 'refresh_token', 'authorization', 'headers', 'cookie', 'cookies', 'set-cookie', 'db_path', 'database_path', 'user_id', 'owner_id', '__proto__'].includes(key.toLowerCase()) && safeData(entry, depth + 1));
  return value === null || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value));
}

function validHistorical(value: unknown): boolean {
  try {
    const root = exactS2(value, ['schema_version', 'scope', 'contract_version', 'provenance', 'source_hashes', 'source_manifest_sha256', 'cases']);
    const p = exactS2(root.provenance, ['kind', 'source', 'command', 'tested_commit', 'tested_tree']);
    if (root.schema_version !== 'finex.local_s2.portfolio_corpus.v1' || root.scope !== LOCAL_SCOPE || root.contract_version !== LOCAL_CONTRACT_VERSION ||
      p.kind !== 'native_tcp_capture' || p.source !== 'owned_loopback_uvicorn' || p.command !== 'python verify_s2_manual_portfolio.py' ||
      p.tested_commit !== 'abf5956a35fc5cf01afce58753bdbeb045a87851' || p.tested_tree !== '99c08f21b9f00a8877449cca824da9a70f7cca2d') return false;
    if (!Array.isArray(root.source_hashes) || !root.source_hashes.length || root.source_hashes.length > 256) return false;
    const paths = new Set<string>();
    const manifest = root.source_hashes.map((value) => {
      const source = exactS2(value, ['path', 'sha256']);
      if (typeof source.path !== 'string' || !/^[A-Za-z0-9_./-]+$/.test(source.path) || source.path.split('/').some((s) => ['', '.', '..'].includes(s)) ||
        source.path.startsWith('/') || typeof source.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(source.sha256) || paths.has(source.path)) throw new Error('Invalid historical source binding.');
      paths.add(source.path);
      return { path: source.path, hash: source.sha256 };
    }).sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0).map((s) => s.path + ' ' + s.hash.toUpperCase() + '\n').join('');
    if (createHash('sha256').update(manifest, 'utf8').digest('hex') !== root.source_manifest_sha256 || !Array.isArray(root.cases) || root.cases.length !== 31) return false;
    const ids = new Set<string>();
    for (const raw of root.cases) {
      const entry = exactS2(raw, ['id', 'operation', 'request', 'status', 'content_type', 'body_utf8', 'expected']);
      if (typeof entry.id !== 'string' || !Object.prototype.hasOwnProperty.call(specs, entry.id) || ids.has(entry.id) || typeof entry.body_utf8 !== 'string' || utf8Length(entry.body_utf8) > 524288 || entry.content_type !== 'application/json') return false;
      ids.add(entry.id);
      const [operation, status, code] = specs[entry.id];
      const expected = exactS2(entry.expected, code === undefined ? ['outcome'] : ['outcome', 'error_code']);
      const envelope = objectS2(JSON.parse(entry.body_utf8));
      if (entry.operation !== operation || entry.status !== status || expected.outcome !== (code === undefined ? 'success' : 'error') || expected.error_code !== code ||
        envelope.success !== (code === undefined) || (code !== undefined && envelope.error_code !== code) || !safeData(entry.request) || !safeData(envelope)) return false;
    }
    return Object.keys(specs).every((id) => ids.has(id));
  } catch { return false; }
}

function equivalent(left: unknown, right: unknown): boolean {
  const canonical = (v: unknown): unknown => Array.isArray(v) ? v.map(canonical) : v !== null && typeof v === 'object'
    ? Object.fromEntries(Object.entries(v as Json).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([key, value]) => [key, canonical(value)])) : v;
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function canonicalIssuedRequest(entry: WireCase): unknown {
  if (entry.request !== null && (entry.operation === 'portfolio_create' || entry.operation === 'portfolio_update')) {
    const request = objectS2(entry.request);
    return { ...request, name: String(request.name).trim(), description: request.description === null ? null : String(request.description).trim() };
  }
  return entry.request;
}

function dispatch(api: LocalS2Api, entry: WireCase, memoryBearer: string): Promise<unknown> {
  const envelope = objectS2(JSON.parse(entry.body_utf8));
  const data = entry.expected.outcome === 'success' ? objectS2(envelope.data) : {};
  const id = typeof data.portfolio_id === 'string' ? data.portfolio_id : portfolioId;
  const h = typeof data.holding_id === 'string' ? data.holding_id : holdingId;
  const portfolioInput: PortfolioInput = entry.expected.outcome === 'success' && entry.request !== null ? entry.request as PortfolioInput :
    { portfolio_version: 'portfolio.v1', name: 'Synthetic retry input', description: null, currency: 'USD' };
  const holdingInput: HoldingInput = entry.expected.outcome === 'success' && entry.request !== null ? entry.request as HoldingInput :
    { holding_version: 'holding.v1', quantity: '1.000000', average_cost: '1.0000', currency: 'USD', instrument_id: 'SYN:AAPL' };
  switch (entry.operation) {
    case 'catalogue': return api.catalog(memoryBearer);
    case 'portfolio_list': return api.portfolios(memoryBearer);
    case 'portfolio_create': return api.createPortfolio(memoryBearer, portfolioInput);
    case 'portfolio_detail': return api.portfolio(memoryBearer, id);
    case 'portfolio_update': return api.updatePortfolio(memoryBearer, id, portfolioInput);
    case 'portfolio_delete': return api.deletePortfolio(memoryBearer, id);
    case 'holding_list': return api.holdings(memoryBearer, id);
    case 'holding_create': return api.createHolding(memoryBearer, id, holdingInput);
    case 'holding_detail': return api.holding(memoryBearer, id, h);
    case 'holding_update': return api.updateHolding(memoryBearer, id, h, entry.request as HoldingUpdate);
    case 'holding_delete': return api.deleteHolding(memoryBearer, id, h);
    case 'metrics': return api.metrics(memoryBearer, id);
    default: throw new Error('Unsupported historical operation.');
  }
}

describe('historical accepted #191 API UTF-8 public transport replay (not current TCP proof)', () => {
  test('all31 cases and historical source provenance are complete, bound and credential-free', () => {
    expect(validHistorical(historical)).toBe(true);
  });
  test.each(historical.cases.map((entry) => [entry.id, entry] as const))('%s decodes original response bytes via public transport', async (_id, entry) => {
    const memoryBearer = randomBytes(32).toString('base64url');
    const bytes = Buffer.from(entry.body_utf8, 'utf8');
    let calls = 0;
    let safeWire = true;
    const api = createLocalS2Client({ baseOrigin: 'http://127.0.0.1:8000', fetchImpl: (async (url, options) => {
      calls++;
      try {
        const headers = objectS2(options?.headers);
        const request = typeof options?.body === 'string' ? JSON.parse(options.body) as unknown : null;
        safeWire = safeWire && String(url).startsWith('http://127.0.0.1:8000/api/v1/local-portfolios') && !String(url).includes(memoryBearer) &&
          headers.Authorization === 'Bearer ' + memoryBearer && options?.credentials === 'omit' && options.cache === 'no-store' && options.redirect === 'error' &&
          !JSON.stringify(request).includes(memoryBearer) && (entry.expected.outcome !== 'success' || equivalent(request, canonicalIssuedRequest(entry)));
      } catch { safeWire = false; }
      return { status: entry.status, ok: entry.status >= 200 && entry.status < 300, redirected: false, headers: { get: () => entry.content_type },
        text: async () => bytes.toString('utf8') } as unknown as Response;
    }) as typeof fetch });
    let passed = false;
    let reflected = false;
    try {
      const result = await dispatch(api, entry, memoryBearer);
      const envelope = objectS2(JSON.parse(entry.body_utf8));
      passed = entry.expected.outcome === 'success' && equivalent(result, { data: envelope.data, meta: envelope.meta });
      reflected = JSON.stringify(result).includes(memoryBearer);
    } catch (failure) {
      passed = entry.expected.outcome === 'error' && failure instanceof LocalApplicationError && failure.code === entry.expected.error_code;
      reflected = String(failure).includes(memoryBearer);
    }
    // Boolean diagnostics only: no raw bodies, bearer, URL, headers or exceptions on regression.
    expect(passed).toBe(true);
    expect(safeWire).toBe(true);
    expect(calls === 1).toBe(true);
    expect(reflected).toBe(false);
  });
  test.each(['missing', 'status', 'privacy', 'source', 'operation'])('fixture guard rejects %s drift without payload diagnostics', (kind) => {
    const changed = JSON.parse(JSON.stringify(historical));
    if (kind === 'missing') changed.cases.pop();
    if (kind === 'status') changed.cases[0].status = 201;
    if (kind === 'privacy') changed.cases[0].request = { access_token: randomBytes(32).toString('base64url') };
    if (kind === 'source') changed.source_hashes[0].sha256 = 'f'.repeat(64);
    if (kind === 'operation') changed.cases[0].operation = 'portfolio_list';
    expect(validHistorical(changed)).toBe(false);
  });
});
