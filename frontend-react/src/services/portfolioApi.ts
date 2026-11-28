import { ApiClient, ApiClientError, finexApiClient } from './apiClient';
import { getActiveAuthSession } from './authService';
import type { LocalS2Capabilities } from '../context/localS2Capabilities';
import type { LocalS2Response, Portfolio, PortfolioMetrics } from './localS2Models';

export type PortfolioBackendMode = 'local' | 'postgres';

export interface PortfolioCapabilitiesResult {
  mode: PortfolioBackendMode;
  portfolioEnabled: boolean;
  capabilities: Record<string, boolean>;
  persistence: string | null;
}

export interface PortfolioRecord {
  portfolio_id: string;
  name: string;
  description: string | null;
  portfolio_type: string;
  currency: string;
  total_value: number | null;
  total_cost: number | null;
  total_gain_loss: number | null;
  total_gain_loss_pct: number | null;
  holdings_count: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PortfolioHoldingRecord {
  holding_id: string;
  portfolio_id: string;
  symbol: string;
  display_name: string;
  asset_class: string;
  sector: string;
  quantity: number;
  average_cost: number;
  current_price: number | null;
  current_value: number | null;
  total_cost: number | null;
  unrealized_gain_loss: number | null;
  unrealized_gain_loss_pct: number | null;
  weight_pct: number | null;
  is_stale: boolean;
}

export interface RiskFreeRateInfo {
  annual_rate: number | null;
  source: string;
  as_of: string;
}

export interface PortfolioReturnsMetrics {
  cumulative: number | null;
  annualized: number | null;
  daily_mean: number | null;
}

export interface PortfolioValueAtRisk {
  historical: number | null;
  parametric: number | null;
  confidence_level: number;
  horizon_days: number;
}

export interface PortfolioTopHolding {
  symbol: string;
  current_value: number | null;
  weight: number | null;
}

export interface PortfolioAnalytics {
  portfolio_id: string;
  backendMode: PortfolioBackendMode;
  status: 'COMPLETE' | 'INSUFFICIENT_DATA';
  dataStatus: 'CACHED' | 'UNAVAILABLE' | 'LIVE' | 'DELAYED' | 'STALE';
  dataAsOf: string | null;
  sourceLabel: string;
  observation_count: number;
  benchmark_symbol: string;
  confidence_level: number;
  risk_free_rate: RiskFreeRateInfo;
  returns: PortfolioReturnsMetrics;
  annualized_volatility: number | null;
  sharpe_ratio: number | null;
  beta: number | null;
  value_at_risk: PortfolioValueAtRisk;
  current_value: number | null;
  hhi: number | null;
  top_holdings: PortfolioTopHolding[];
  limitations: string[];
}

export interface PortfolioAnalyticsQuery {
  benchmark?: string;
  topN?: number;
  confidenceLevel?: 0.95 | 0.99;
}

export interface PortfolioApi {
  readonly mode: PortfolioBackendMode;
  readonly supportsHistoricalAnalytics: boolean;
  listPortfolios(signal?: AbortSignal): Promise<PortfolioRecord[]>;
  getPortfolio(portfolioId: string, signal?: AbortSignal): Promise<PortfolioRecord>;
  listHoldings(portfolioId: string, signal?: AbortSignal): Promise<PortfolioHoldingRecord[]>;
  getAnalytics(
    portfolioId: string,
    query?: PortfolioAnalyticsQuery,
    signal?: AbortSignal,
  ): Promise<PortfolioAnalytics>;
}

export interface PortfolioApiHttpConfig {
  apiClient?: ApiClient;
  timeoutMs?: number;
  getAuthToken?: () => string | null;
}

export interface ResolvePortfolioApiOptions extends PortfolioApiHttpConfig {
  localDomain?: LocalS2Capabilities | null;
  hasLocalSession?: boolean;
  getLocalMetricsSnapshot?: (portfolioId: string) => LocalS2Response<PortfolioMetrics> | null;
}

export class PortfolioApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly retryable: boolean;

  constructor(
    message: string,
    code = 'API_UNAVAILABLE',
    options?: { status?: number; retryable?: boolean },
  ) {
    super(message);
    this.name = 'PortfolioApiError';
    this.code = code;
    this.status = options?.status;
    this.retryable = options?.retryable ?? false;
  }
}

const DEFAULT_TIMEOUT_MS = 8000;
const NON_RETRYABLE_CODES = new Set([
  'UNAUTHORIZED',
  'FORBIDDEN',
  'PORTFOLIO_NOT_FOUND',
  'LOCAL_PORTFOLIO_NOT_FOUND',
  'VALIDATION_ERROR',
  'PORTFOLIO_UNAVAILABLE',
]);

function readSessionStorageToken(): string | null {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage.getItem('finex_access_token');
    }
  } catch {
    return null;
  }
  return null;
}

export function resolveDefaultAuthToken(): string | null {
  return getActiveAuthSession()?.access_token ?? readSessionStorageToken();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asOptionalString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asRequiredString(value: unknown, field: string): string {
  const str = asOptionalString(value);
  if (!str) {
    throw new PortfolioApiError(
      `Invalid ${field} received from portfolio API.`,
      'RESPONSE_INVALID',
    );
  }
  return str;
}

function asNullableNumber(value: unknown, field: string): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  throw new PortfolioApiError(
    `Invalid numeric ${field} received from portfolio API.`,
    'RESPONSE_INVALID',
  );
}

function asRequiredNumber(value: unknown, field: string): number {
  const num = asNullableNumber(value, field);
  if (num === null) {
    throw new PortfolioApiError(
      `Missing required ${field} received from portfolio API.`,
      'RESPONSE_INVALID',
    );
  }
  return num;
}

function normalizeBenchmark(value?: string): string {
  const cleaned = (value ?? 'SPY').trim().toUpperCase();
  if (!/^[A-Z0-9.^_-]{1,20}$/.test(cleaned)) {
    throw new PortfolioApiError(
      'Benchmark symbol must be 1-20 characters (letters, numbers, ".", "^", "_", "-").',
      'VALIDATION_ERROR',
      { retryable: false },
    );
  }
  return cleaned;
}

function normalizeTopN(value?: number): number {
  if (value === undefined) {
    return 5;
  }
  if (!Number.isInteger(value) || value < 1 || value > 100) {
    throw new PortfolioApiError('topN must be an integer between 1 and 100.', 'VALIDATION_ERROR', {
      retryable: false,
    });
  }
  return value;
}

function normalizeConfidenceLevel(value?: number): 0.95 | 0.99 {
  if (value === undefined || value === 0.95) {
    return 0.95;
  }
  if (value === 0.99) {
    return 0.99;
  }
  throw new PortfolioApiError('Confidence level must be 0.95 or 0.99.', 'VALIDATION_ERROR', {
    retryable: false,
  });
}

function mapHttpError(status: number, code: string, serverMessage?: string): PortfolioApiError {
  if (status === 401 || code === 'UNAUTHORIZED' || code === 'SESSION_INVALID') {
    return new PortfolioApiError(
      serverMessage || 'Sign in with an active FinEx session to access portfolio analytics.',
      'UNAUTHORIZED',
      { status, retryable: false },
    );
  }
  if (status === 403 || code === 'FORBIDDEN' || code === 'LOCAL_APPLICATION_ONLY') {
    return new PortfolioApiError(
      serverMessage || 'You do not have permission to access this portfolio.',
      'FORBIDDEN',
      { status, retryable: false },
    );
  }
  if (status === 404 || code === 'PORTFOLIO_NOT_FOUND' || code === 'LOCAL_PORTFOLIO_NOT_FOUND') {
    return new PortfolioApiError(
      serverMessage || 'Portfolio not found or access denied.',
      'PORTFOLIO_NOT_FOUND',
      { status, retryable: false },
    );
  }
  if (status === 422 || code === 'VALIDATION_ERROR') {
    return new PortfolioApiError(
      serverMessage || 'Invalid portfolio analytics request parameters.',
      'VALIDATION_ERROR',
      { status, retryable: false },
    );
  }
  if (status === 503 || code === 'DATABASE_UNAVAILABLE' || code === 'LOCAL_STORE_UNAVAILABLE') {
    return new PortfolioApiError(
      serverMessage || 'Portfolio service is temporarily unavailable. Please retry.',
      code || 'API_UNAVAILABLE',
      { status, retryable: true },
    );
  }
  const retryable = status >= 500 || !NON_RETRYABLE_CODES.has(code);
  return new PortfolioApiError(
    serverMessage || 'Unable to load portfolio data right now.',
    code || 'PORTFOLIO_REQUEST_FAILED',
    { status, retryable },
  );
}

async function requestFinexEnvelope(
  path: string,
  config: PortfolioApiHttpConfig,
  options: { auth?: boolean; signal?: AbortSignal } = {},
): Promise<{ status: number; data: unknown; meta: Record<string, unknown> | null }> {
  const client = config.apiClient ?? finexApiClient;
  const timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const getAuthToken = config.getAuthToken ?? resolveDefaultAuthToken;
  const signal = options.signal;

  if (signal?.aborted) {
    throw new PortfolioApiError('The portfolio request was cancelled.', 'REQUEST_CANCELLED', {
      retryable: true,
    });
  }

  const controller = new AbortController();
  let timedOut = false;
  const onCallerAbort = () => controller.abort();
  signal?.addEventListener('abort', onCallerAbort, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const token = options.auth ? getAuthToken() : null;
    if (options.auth && !token) {
      throw new PortfolioApiError(
        'Sign in with an active FinEx account session to access PostgreSQL portfolios.',
        'UNAUTHORIZED',
        { status: 401, retryable: false },
      );
    }

    const response = await client.request(path, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
      ...(token ? { accessToken: token } : {}),
    });

    const payload = await response.json().catch(() => null);
    const record = asRecord(payload);

    if (!response.ok) {
      const errorDetail = asRecord(record?.error);
      const code =
        asOptionalString(errorDetail?.code) ??
        asOptionalString(record?.error_code) ??
        (response.status === 401
          ? 'UNAUTHORIZED'
          : response.status === 404
            ? 'PORTFOLIO_NOT_FOUND'
            : response.status === 422
              ? 'VALIDATION_ERROR'
              : 'API_ERROR');
      const serverMessage =
        asOptionalString(errorDetail?.message) ??
        asOptionalString(record?.message) ??
        asOptionalString(record?.detail) ??
        undefined;
      throw mapHttpError(response.status, code, serverMessage);
    }

    if (!record || record.success !== true || !('data' in record)) {
      throw new PortfolioApiError(
        'Received an unexpected response format from the FinEx API.',
        'RESPONSE_INVALID',
        { status: response.status, retryable: true },
      );
    }

    return {
      status: response.status,
      data: record.data,
      meta: asRecord(record.meta),
    };
  } catch (error) {
    if (error instanceof PortfolioApiError) {
      throw error;
    }
    if (timedOut) {
      throw new PortfolioApiError(
        'The portfolio request timed out. You can safely retry.',
        'REQUEST_TIMEOUT',
        { retryable: true },
      );
    }
    if (signal?.aborted) {
      throw new PortfolioApiError('The portfolio request was cancelled.', 'REQUEST_CANCELLED', {
        retryable: true,
      });
    }
    if (error instanceof ApiClientError) {
      throw new PortfolioApiError(error.message, error.code, {
        status: error.status,
        retryable: true,
      });
    }
    throw new PortfolioApiError(
      'The FinEx portfolio API is unreachable. Check the connection and retry.',
      'API_UNAVAILABLE',
      { retryable: true },
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onCallerAbort);
  }
}

export function choosePortfolioBackendMode(
  data: unknown,
  context: { hasLocalSession?: boolean; hasRealAuthToken?: boolean } = {},
): PortfolioCapabilitiesResult {
  const root = asRecord(data);
  if (!root) {
    throw new PortfolioApiError('Invalid capabilities payload.', 'RESPONSE_INVALID', {
      retryable: true,
    });
  }

  const rawCaps = asRecord(root.capabilities);
  if (!rawCaps) {
    throw new PortfolioApiError('Capabilities map is missing.', 'RESPONSE_INVALID', {
      retryable: true,
    });
  }

  const capabilities: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(rawCaps)) {
    if (typeof value === 'boolean') {
      capabilities[key] = value;
    }
  }

  const portfolioEnabled = capabilities.portfolio !== false;
  const persistence =
    asOptionalString(root.persistence)?.toLowerCase() ??
    asOptionalString(root.storage)?.toLowerCase() ??
    asOptionalString(root.portfolio_backend)?.toLowerCase() ??
    null;

  let mode: PortfolioBackendMode;
  if (persistence === 'postgresql' || persistence === 'postgres') {
    mode = 'postgres';
  } else if (persistence === 'sqlite' || persistence === 'local') {
    mode = 'local';
  } else if (
    capabilities.postgres_portfolio === true ||
    capabilities.portfolio_analytics === true ||
    capabilities.postgres === true
  ) {
    mode = 'postgres';
  } else if (
    capabilities.postgres_portfolio === false ||
    capabilities.portfolio_analytics === false ||
    capabilities.postgres === false
  ) {
    mode = 'local';
  } else if (context.hasLocalSession) {
    mode = 'local';
  } else if (context.hasRealAuthToken) {
    mode = 'postgres';
  } else {
    mode = 'local';
  }

  return {
    mode,
    portfolioEnabled,
    capabilities,
    persistence,
  };
}

export async function fetchPortfolioCapabilities(
  config: PortfolioApiHttpConfig = {},
  context: { hasLocalSession?: boolean; hasRealAuthToken?: boolean } = {},
  signal?: AbortSignal,
): Promise<PortfolioCapabilitiesResult> {
  const response = await requestFinexEnvelope('/api/v1/capabilities', config, {
    auth: false,
    signal,
  });
  return choosePortfolioBackendMode(response.data, {
    hasLocalSession: context.hasLocalSession,
    hasRealAuthToken:
      context.hasRealAuthToken ??
      Boolean((config.getAuthToken ?? resolveDefaultAuthToken)()),
  });
}

function decodePostgresPortfolio(raw: unknown): PortfolioRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PortfolioApiError('Invalid portfolio record.', 'RESPONSE_INVALID');
  }
  return {
    portfolio_id: asRequiredString(rec.portfolio_id, 'portfolio_id'),
    name: asRequiredString(rec.name, 'name'),
    description: asOptionalString(rec.description),
    portfolio_type: asOptionalString(rec.portfolio_type) ?? 'INDIVIDUAL',
    currency: (asOptionalString(rec.currency) ?? 'USD').toUpperCase(),
    total_value: asNullableNumber(rec.total_value, 'total_value'),
    total_cost: asNullableNumber(rec.total_cost, 'total_cost'),
    total_gain_loss: asNullableNumber(rec.total_gain_loss, 'total_gain_loss'),
    total_gain_loss_pct: asNullableNumber(rec.total_gain_loss_pct, 'total_gain_loss_pct'),
    holdings_count: asNullableNumber(rec.holdings_count, 'holdings_count'),
    created_at: asOptionalString(rec.created_at),
    updated_at: asOptionalString(rec.updated_at),
  };
}

function decodePostgresHolding(raw: unknown): PortfolioHoldingRecord {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PortfolioApiError('Invalid holding record.', 'RESPONSE_INVALID');
  }
  const symbol = asRequiredString(rec.symbol, 'symbol').toUpperCase();
  return {
    holding_id: asRequiredString(rec.holding_id, 'holding_id'),
    portfolio_id: asRequiredString(rec.portfolio_id, 'portfolio_id'),
    symbol,
    display_name: asOptionalString(rec.display_name) ?? symbol,
    asset_class: asOptionalString(rec.asset_class) ?? 'EQUITY',
    sector: asOptionalString(rec.sector) ?? 'General',
    quantity: asRequiredNumber(rec.quantity, 'quantity'),
    average_cost: asRequiredNumber(rec.avg_buy_price, 'avg_buy_price'),
    current_price: asNullableNumber(rec.current_price, 'current_price'),
    current_value: asNullableNumber(rec.current_value, 'current_value'),
    total_cost: asNullableNumber(rec.total_cost, 'total_cost'),
    unrealized_gain_loss: asNullableNumber(rec.unrealized_gain_loss, 'unrealized_gain_loss'),
    unrealized_gain_loss_pct: asNullableNumber(
      rec.unrealized_gain_loss_pct,
      'unrealized_gain_loss_pct',
    ),
    weight_pct: asNullableNumber(rec.weight_pct, 'weight_pct'),
    is_stale: Boolean(rec.is_stale),
  };
}

function decodePostgresAnalytics(
  raw: unknown,
  meta: Record<string, unknown> | null,
): PortfolioAnalytics {
  const rec = asRecord(raw);
  if (!rec) {
    throw new PortfolioApiError('Invalid portfolio analytics payload.', 'RESPONSE_INVALID');
  }

  const statusRaw = asRequiredString(rec.status, 'status');
  if (statusRaw !== 'COMPLETE' && statusRaw !== 'INSUFFICIENT_DATA') {
    throw new PortfolioApiError('Unsupported analytics status.', 'RESPONSE_INVALID');
  }

  const riskFreeRec = asRecord(rec.risk_free_rate);
  const returnsRec = asRecord(rec.returns);
  const varRec = asRecord(rec.value_at_risk);
  if (!riskFreeRec || !returnsRec || !varRec) {
    throw new PortfolioApiError('Incomplete portfolio analytics payload.', 'RESPONSE_INVALID');
  }

  const rawTop = Array.isArray(rec.top_holdings) ? rec.top_holdings : [];
  const topHoldings: PortfolioTopHolding[] = rawTop.map((item, idx) => {
    const row = asRecord(item);
    if (!row) {
      throw new PortfolioApiError(`Invalid top_holdings[${idx}] entry.`, 'RESPONSE_INVALID');
    }
    return {
      symbol: asRequiredString(row.symbol, `top_holdings[${idx}].symbol`).toUpperCase(),
      current_value: asNullableNumber(row.current_value, `top_holdings[${idx}].current_value`),
      weight: asNullableNumber(row.weight, `top_holdings[${idx}].weight`),
    };
  });

  const limitations = Array.isArray(rec.limitations)
    ? rec.limitations.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];

  const metaStatus = asOptionalString(meta?.dataStatus)?.toUpperCase();
  const dataStatus: PortfolioAnalytics['dataStatus'] =
    metaStatus === 'LIVE' ||
    metaStatus === 'DELAYED' ||
    metaStatus === 'CACHED' ||
    metaStatus === 'STALE' ||
    metaStatus === 'UNAVAILABLE'
      ? metaStatus
      : statusRaw === 'INSUFFICIENT_DATA'
        ? 'UNAVAILABLE'
        : 'CACHED';

  return {
    portfolio_id: asRequiredString(rec.portfolio_id, 'portfolio_id'),
    backendMode: 'postgres',
    status: statusRaw,
    dataStatus,
    dataAsOf: asOptionalString(meta?.dataAsOf),
    sourceLabel: 'PostgreSQL / S3-PA01 Analytics API',
    observation_count: asRequiredNumber(rec.observation_count, 'observation_count'),
    benchmark_symbol: asRequiredString(rec.benchmark_symbol, 'benchmark_symbol').toUpperCase(),
    confidence_level: asRequiredNumber(rec.confidence_level, 'confidence_level'),
    risk_free_rate: {
      annual_rate: asNullableNumber(riskFreeRec.annual_rate, 'risk_free_rate.annual_rate'),
      source: asOptionalString(riskFreeRec.source) ?? 'Configured default',
      as_of: asOptionalString(riskFreeRec.as_of) ?? 'UNCONFIGURED',
    },
    returns: {
      cumulative: asNullableNumber(returnsRec.cumulative, 'returns.cumulative'),
      annualized: asNullableNumber(returnsRec.annualized, 'returns.annualized'),
      daily_mean: asNullableNumber(returnsRec.daily_mean, 'returns.daily_mean'),
    },
    annualized_volatility: asNullableNumber(rec.annualized_volatility, 'annualized_volatility'),
    sharpe_ratio: asNullableNumber(rec.sharpe_ratio, 'sharpe_ratio'),
    beta: asNullableNumber(rec.beta, 'beta'),
    value_at_risk: {
      historical: asNullableNumber(varRec.historical, 'value_at_risk.historical'),
      parametric: asNullableNumber(varRec.parametric, 'value_at_risk.parametric'),
      confidence_level: asRequiredNumber(varRec.confidence_level, 'value_at_risk.confidence_level'),
      horizon_days: asRequiredNumber(varRec.horizon_days, 'value_at_risk.horizon_days'),
    },
    current_value: asNullableNumber(rec.current_value, 'current_value'),
    hhi: asNullableNumber(rec.hhi, 'hhi'),
    top_holdings: topHoldings,
    limitations,
  };
}

export function createPostgresPortfolioApi(config: PortfolioApiHttpConfig = {}): PortfolioApi {
  return {
    mode: 'postgres',
    supportsHistoricalAnalytics: true,

    async listPortfolios(signal?: AbortSignal): Promise<PortfolioRecord[]> {
      const response = await requestFinexEnvelope('/api/v1/portfolios', config, {
        auth: true,
        signal,
      });
      if (!Array.isArray(response.data)) {
        throw new PortfolioApiError('Expected a list of portfolios.', 'RESPONSE_INVALID');
      }
      return response.data.map(decodePostgresPortfolio);
    },

    async getPortfolio(portfolioId: string, signal?: AbortSignal): Promise<PortfolioRecord> {
      const response = await requestFinexEnvelope(
        `/api/v1/portfolios/${encodeURIComponent(portfolioId)}`,
        config,
        { auth: true, signal },
      );
      return decodePostgresPortfolio(response.data);
    },

    async listHoldings(
      portfolioId: string,
      signal?: AbortSignal,
    ): Promise<PortfolioHoldingRecord[]> {
      const response = await requestFinexEnvelope(
        `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/holdings`,
        config,
        { auth: true, signal },
      );
      if (!Array.isArray(response.data)) {
        throw new PortfolioApiError('Expected a list of holdings.', 'RESPONSE_INVALID');
      }
      return response.data.map(decodePostgresHolding);
    },

    async getAnalytics(
      portfolioId: string,
      query: PortfolioAnalyticsQuery = {},
      signal?: AbortSignal,
    ): Promise<PortfolioAnalytics> {
      const benchmark = normalizeBenchmark(query.benchmark);
      const topN = normalizeTopN(query.topN);
      const confidenceLevel = normalizeConfidenceLevel(query.confidenceLevel);
      const params = new URLSearchParams({
        benchmark,
        top_n: String(topN),
        confidence_level: confidenceLevel.toFixed(2),
      });
      const response = await requestFinexEnvelope(
        `/api/v1/portfolios/${encodeURIComponent(portfolioId)}/analytics?${params.toString()}`,
        config,
        { auth: true, signal },
      );
      return decodePostgresAnalytics(response.data, response.meta);
    },
  };
}

function mapLocalPortfolioRecord(p: Portfolio): PortfolioRecord {
  return {
    portfolio_id: p.portfolio_id,
    name: p.name,
    description: p.description,
    portfolio_type: 'MANUAL_LOCAL',
    currency: p.currency,
    total_value: null,
    total_cost: null,
    total_gain_loss: null,
    total_gain_loss_pct: null,
    holdings_count: null,
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}

export function mapLocalMetricsToAnalytics(
  response: LocalS2Response<PortfolioMetrics>,
  query: PortfolioAnalyticsQuery = {},
): PortfolioAnalytics {
  const m = response.data;
  const topN = normalizeTopN(query.topN);
  const confidenceLevel = normalizeConfidenceLevel(query.confidenceLevel);
  const benchmark = normalizeBenchmark(query.benchmark);

  const ranked = [...m.holdings].sort((a, b) => {
    const valA = a.market_value === null ? -1 : Number(a.market_value);
    const valB = b.market_value === null ? -1 : Number(b.market_value);
    if (valA !== valB) {
      return valB - valA;
    }
    return a.instrument_id.localeCompare(b.instrument_id);
  });

  const topHoldings: PortfolioTopHolding[] = ranked.slice(0, topN).map((h) => ({
    symbol: h.instrument_id.replace(/^SYN:/, ''),
    current_value: h.market_value === null ? null : Number(h.market_value),
    weight: h.weight_percent === null ? null : Number((Number(h.weight_percent) / 100).toFixed(6)),
  }));

  const currentValue = m.totals.market_value === null ? null : Number(m.totals.market_value);
  const hhi = m.totals.hhi === null ? null : Number(m.totals.hhi);

  const localLimitation =
    m.valuation_status === 'EMPTY'
      ? 'Add holdings to compute portfolio concentration and analytics.'
      : m.valuation_status === 'INCOMPLETE' || m.valuation_status === 'UNAVAILABLE'
        ? 'Synthetic quote snapshot is incomplete or unavailable; concentration and historical analytics are not available.'
        : 'Local SQLite manual portfolios track synthetic current-snapshot valuation only; historical returns, Sharpe, beta, and VaR require PostgreSQL market history.';

  return {
    portfolio_id: m.portfolio_id,
    backendMode: 'local',
    status: 'INSUFFICIENT_DATA',
    dataStatus: response.meta.dataStatus,
    dataAsOf: response.meta.dataAsOf ?? m.fixture_as_of,
    sourceLabel: 'Local SQLite Manual Portfolio (Synthetic Snapshot)',
    observation_count: 0,
    benchmark_symbol: benchmark,
    confidence_level: confidenceLevel,
    risk_free_rate: {
      annual_rate: null,
      source: 'Not applicable in local synthetic snapshot mode',
      as_of: m.fixture_as_of,
    },
    returns: {
      cumulative: null,
      annualized: null,
      daily_mean: null,
    },
    annualized_volatility: null,
    sharpe_ratio: null,
    beta: null,
    value_at_risk: {
      historical: null,
      parametric: null,
      confidence_level: confidenceLevel,
      horizon_days: 1,
    },
    current_value: currentValue,
    hhi,
    top_holdings: topHoldings,
    limitations: [
      localLimitation,
      ...m.limitations.map((code) => code.replace(/_/g, ' ')),
    ],
  };
}

export function createLocalPortfolioApi(
  domain: LocalS2Capabilities,
  options: {
    getSnapshotMetrics?: (portfolioId: string) => LocalS2Response<PortfolioMetrics> | null;
  } = {},
): PortfolioApi {
  return {
    mode: 'local',
    supportsHistoricalAnalytics: false,

    async listPortfolios(signal?: AbortSignal): Promise<PortfolioRecord[]> {
      const outcome = await domain.portfolios({ signal });
      if (outcome.status === 'cancelled') {
        throw new PortfolioApiError('The portfolio request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (outcome.status === 'error') {
        throw new PortfolioApiError(outcome.error.message, outcome.error.code, {
          retryable: true,
        });
      }
      return outcome.value.data.items.map(mapLocalPortfolioRecord);
    },

    async getPortfolio(portfolioId: string, signal?: AbortSignal): Promise<PortfolioRecord> {
      const outcome = await domain.portfolio(portfolioId, { signal });
      if (outcome.status === 'cancelled') {
        throw new PortfolioApiError('The portfolio request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (outcome.status === 'error') {
        throw new PortfolioApiError(outcome.error.message, outcome.error.code, {
          retryable: false,
        });
      }
      return mapLocalPortfolioRecord(outcome.value.data);
    },

    async listHoldings(
      portfolioId: string,
      signal?: AbortSignal,
    ): Promise<PortfolioHoldingRecord[]> {
      const outcome = await domain.holdings(portfolioId, { signal });
      if (outcome.status === 'cancelled') {
        throw new PortfolioApiError('The holdings request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (outcome.status === 'error') {
        throw new PortfolioApiError(outcome.error.message, outcome.error.code, {
          retryable: true,
        });
      }
      return outcome.value.data.items.map((h) => ({
        holding_id: h.holding_id,
        portfolio_id: h.portfolio_id,
        symbol: h.instrument_id.replace(/^SYN:/, ''),
        display_name: h.display_name,
        asset_class: h.asset_class,
        sector: h.sector,
        quantity: Number(h.quantity),
        average_cost: Number(h.average_cost),
        current_price: null,
        current_value: null,
        total_cost: null,
        unrealized_gain_loss: null,
        unrealized_gain_loss_pct: null,
        weight_pct: null,
        is_stale: false,
      }));
    },

    async getAnalytics(
      portfolioId: string,
      query: PortfolioAnalyticsQuery = {},
      signal?: AbortSignal,
    ): Promise<PortfolioAnalytics> {
      const cached = options.getSnapshotMetrics?.(portfolioId);
      if (cached) {
        return mapLocalMetricsToAnalytics(cached, query);
      }

      const outcome = await domain.metrics(portfolioId, { signal });
      if (outcome.status === 'cancelled') {
        throw new PortfolioApiError('The analytics request was cancelled.', 'REQUEST_CANCELLED', {
          retryable: true,
        });
      }
      if (outcome.status === 'error') {
        throw new PortfolioApiError(outcome.error.message, outcome.error.code, {
          retryable: true,
        });
      }
      return mapLocalMetricsToAnalytics(outcome.value, query);
    },
  };
}

export async function resolvePortfolioApi(
  options: ResolvePortfolioApiOptions = {},
  signal?: AbortSignal,
): Promise<{ api: PortfolioApi; capabilities: PortfolioCapabilitiesResult }> {
  const capabilities = await fetchPortfolioCapabilities(
    options,
    {
      hasLocalSession: options.hasLocalSession,
      hasRealAuthToken: Boolean((options.getAuthToken ?? resolveDefaultAuthToken)()),
    },
    signal,
  );

  if (!capabilities.portfolioEnabled) {
    throw new PortfolioApiError(
      'Portfolio feature is not enabled in the current server capabilities.',
      'PORTFOLIO_UNAVAILABLE',
      { retryable: false },
    );
  }

  if (capabilities.mode === 'postgres') {
    return {
      api: createPostgresPortfolioApi(options),
      capabilities,
    };
  }

  if (!options.localDomain) {
    throw new PortfolioApiError(
      'Local portfolio session is required when running in SQLite local mode.',
      'UNAUTHORIZED',
      { status: 401, retryable: false },
    );
  }

  return {
    api: createLocalPortfolioApi(options.localDomain, {
      getSnapshotMetrics: options.getLocalMetricsSnapshot,
    }),
    capabilities,
  };
}
