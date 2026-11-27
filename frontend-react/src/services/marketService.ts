import { ApiClient, createApiClient, finexApiClient, getApiBaseUrl } from './apiClient';
import {
  DataFreshness,
  DataStatus,
  MarketMode,
  MarketQuote,
  MarketSecurity,
  MarketServiceConfig,
  WatchlistItem,
  normalizeDataStatus,
} from '../types/market';

// Canonical prototype security master used in fixture mode.
const SECURITY_CATALOG: MarketSecurity[] = [
  {
    securityId: 'sec_aapl',
    symbol: 'AAPL',
    name: 'Apple Inc.',
    assetType: 'EQUITY',
    exchange: 'NASDAQ',
    currency: 'USD',
  },
  {
    securityId: 'sec_msft',
    symbol: 'MSFT',
    name: 'Microsoft Corporation',
    assetType: 'EQUITY',
    exchange: 'NASDAQ',
    currency: 'USD',
  },
  {
    securityId: 'sec_nvda',
    symbol: 'NVDA',
    name: 'NVIDIA Corporation',
    assetType: 'EQUITY',
    exchange: 'NASDAQ',
    currency: 'USD',
  },
  {
    securityId: 'sec_googl',
    symbol: 'GOOGL',
    name: 'Alphabet Inc.',
    assetType: 'EQUITY',
    exchange: 'NASDAQ',
    currency: 'USD',
  },
  {
    securityId: 'sec_vti',
    symbol: 'VTI',
    name: 'Vanguard Total Stock Market ETF',
    assetType: 'ETF',
    exchange: 'NYSEARCA',
    currency: 'USD',
  },
  {
    securityId: 'sec_reliance_ns',
    symbol: 'RELIANCE.NS',
    name: 'Reliance Industries Limited',
    assetType: 'EQUITY',
    exchange: 'NSE',
    currency: 'INR',
  },
  {
    securityId: 'sec_tcs_ns',
    symbol: 'TCS.NS',
    name: 'Tata Consultancy Services Limited',
    assetType: 'EQUITY',
    exchange: 'NSE',
    currency: 'INR',
  },
  {
    securityId: 'sec_infy_bo',
    symbol: 'INFY.BO',
    name: 'Infosys Limited',
    assetType: 'EQUITY',
    exchange: 'BSE',
    currency: 'INR',
  },
  {
    securityId: 'sec_down',
    symbol: 'DOWN',
    name: 'Provider Outage Demo Security',
    assetType: 'EQUITY',
    exchange: 'DEMO',
    currency: 'USD',
  },
];

interface FixtureQuoteRecord {
  price: number;
  currency: string;
  changeValue: number;
  changePercent: number;
  source: string;
  dataStatus: DataStatus;
  reason?: string | null;
}

const QUOTE_CACHE: Record<string, FixtureQuoteRecord> = {
  AAPL: {
    price: 227.52,
    currency: 'USD',
    changeValue: 1.84,
    changePercent: 0.0082,
    source: 'yfinance-fixture',
    dataStatus: 'CACHED',
  },
  MSFT: {
    price: 421.1,
    currency: 'USD',
    changeValue: -2.35,
    changePercent: -0.0055,
    source: 'yfinance-fixture',
    dataStatus: 'CACHED',
  },
  NVDA: {
    price: 138.07,
    currency: 'USD',
    changeValue: -1.12,
    changePercent: -0.008,
    source: 'yfinance-fixture',
    dataStatus: 'DELAYED',
  },
  GOOGL: {
    price: 176.4,
    currency: 'USD',
    changeValue: 0.65,
    changePercent: 0.0037,
    source: 'yfinance-fixture',
    dataStatus: 'CACHED',
  },
  VTI: {
    price: 289.33,
    currency: 'USD',
    changeValue: 0.42,
    changePercent: 0.0015,
    source: 'yfinance-fixture',
    dataStatus: 'END_OF_DAY',
  },
  'RELIANCE.NS': {
    price: 1295.4,
    currency: 'INR',
    changeValue: 14.25,
    changePercent: 0.0111,
    source: 'yfinance-fixture',
    dataStatus: 'DELAYED',
  },
  'TCS.NS': {
    price: 4120.0,
    currency: 'INR',
    changeValue: 0,
    changePercent: 0,
    source: 'market-calendar-fixture',
    dataStatus: 'MARKET_CLOSED',
    reason: 'NSE market session closed',
  },
  'INFY.BO': {
    price: 1842.75,
    currency: 'INR',
    changeValue: -6.1,
    changePercent: -0.0033,
    source: 'quotes-latest-fixture',
    dataStatus: 'STALE',
    reason: 'Upstream provider timed out; showing last stored quote',
  },
};

const UNAVAILABLE_SYMBOL = 'DOWN';

function createInitialFixtureWatchlist(): WatchlistItem[] {
  const nowIso = new Date().toISOString();
  return [
    {
      symbol: 'AAPL',
      name: 'Apple Inc.',
      addedAt: nowIso,
      securityId: 'sec_aapl',
      exchange: 'NASDAQ',
      currency: 'USD',
      price: QUOTE_CACHE.AAPL.price,
      changeValue: QUOTE_CACHE.AAPL.changeValue,
      changePercent: QUOTE_CACHE.AAPL.changePercent,
      source: QUOTE_CACHE.AAPL.source,
      dataAsOf: nowIso,
      dataStatus: QUOTE_CACHE.AAPL.dataStatus,
      freshness: {
        status: QUOTE_CACHE.AAPL.dataStatus,
        source: QUOTE_CACHE.AAPL.source,
        as_of: nowIso,
        fetched_at: nowIso,
        reason: null,
      },
    },
  ];
}

let watchlist: WatchlistItem[] = createInitialFixtureWatchlist();
let runtimeOverrides: Partial<MarketServiceConfig> = {};

function defaultAuthToken(): string | null {
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      return window.sessionStorage.getItem('finex_access_token');
    }
  } catch {
    return null;
  }
  return null;
}

export function getMarketConfig(): MarketServiceConfig {
  const configuredMode = (runtimeOverrides.mode ?? process.env.REACT_APP_MARKET_MODE ?? 'fixture')
    .toString()
    .trim()
    .toLowerCase();
  const mode: MarketMode = configuredMode === 'api' ? 'api' : 'fixture';
  const apiBaseUrl = runtimeOverrides.apiBaseUrl
    ? runtimeOverrides.apiBaseUrl.trim().replace(/\/+$/, '')
    : getApiBaseUrl();

  return {
    mode,
    apiBaseUrl,
    timeoutMs: runtimeOverrides.timeoutMs ?? 8000,
    fetchImpl: runtimeOverrides.fetchImpl,
    getAuthToken: runtimeOverrides.getAuthToken ?? defaultAuthToken,
  };
}

export function configureMarketService(overrides: Partial<MarketServiceConfig>): void {
  runtimeOverrides = { ...runtimeOverrides, ...overrides };
}

export function resetMarketServiceConfig(): void {
  runtimeOverrides = {};
}

export function resetFixtureWatchlist(): void {
  watchlist = createInitialFixtureWatchlist();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function unwrapEnvelope(payload: unknown): { data: unknown; meta: Record<string, unknown> | null } {
  const rec = asRecord(payload);
  if (!rec) {
    return { data: payload, meta: null };
  }
  const meta = asRecord(rec.meta);
  if ('data' in rec) {
    return { data: rec.data, meta };
  }
  return { data: payload, meta };
}

function parseFreshness(
  rec: Record<string, unknown>,
  meta: Record<string, unknown> | null,
  fallbackSource = 'market-api'
): DataFreshness {
  const freshnessRec = asRecord(rec.freshness);
  let status = normalizeDataStatus(
    freshnessRec?.status ??
      (typeof rec.freshness === 'string' ? rec.freshness : undefined) ??
      rec.dataStatus ??
      rec.status ??
      meta?.dataStatus ??
      'UNAVAILABLE'
  );
  const source =
    asString(freshnessRec?.source) ??
    asString(rec.source) ??
    asString(meta?.source) ??
    fallbackSource;

  // Enforce locked FinEx invariant: yfinance never emits LIVE.
  if (source.toLowerCase().includes('yfinance') && status === 'LIVE') {
    status = 'DELAYED';
  }

  const asOf =
    asString(freshnessRec?.as_of) ??
    asString(rec.dataAsOf) ??
    asString(rec.as_of) ??
    asString(rec.quote_as_of) ??
    asString(meta?.dataAsOf) ??
    null;
  const fetchedAt =
    asString(freshnessRec?.fetched_at) ??
    asString(rec.fetchedAt) ??
    asString(rec.fetched_at) ??
    null;
  const reason =
    asString(freshnessRec?.reason) ??
    asString(rec.reason) ??
    asString(rec.error) ??
    null;

  return {
    status,
    source,
    as_of: asOf,
    fetched_at: fetchedAt,
    reason,
  };
}

function mapSecurity(raw: unknown): MarketSecurity | null {
  const rec = asRecord(raw);
  if (!rec) {
    return null;
  }
  const symbol = asString(rec.symbol) ?? asString(rec.ticker) ?? asString(rec.instrument_id);
  if (!symbol) {
    return null;
  }
  const normalizedSymbol = symbol.toUpperCase();
  const exchange = (asString(rec.exchange) ?? 'UNKNOWN').toUpperCase();
  const securityId =
    asString(rec.securityId) ??
    asString(rec.security_id) ??
    asString(rec.instrument_id) ??
    asString(rec.id) ??
    `${normalizedSymbol}:${exchange}`;

  return {
    securityId,
    symbol: normalizedSymbol,
    name: asString(rec.name) ?? asString(rec.display_name) ?? normalizedSymbol,
    assetType:
      asString(rec.assetType) ??
      asString(rec.asset_type) ??
      asString(rec.asset_class) ??
      'EQUITY',
    exchange,
    currency: (asString(rec.currency) ?? (exchange === 'NSE' || exchange === 'BSE' ? 'INR' : 'USD')).toUpperCase(),
  };
}

function mapQuote(
  raw: unknown,
  meta: Record<string, unknown> | null,
  requestedSymbol: string
): MarketQuote {
  const rec = asRecord(raw) ?? {};
  const freshness = parseFreshness(rec, meta);
  const symbol = (asString(rec.symbol) ?? asString(rec.instrument_id) ?? requestedSymbol).toUpperCase();
  const parsedPrice = asNumber(rec.price) ?? asNumber(rec.unit_price) ?? asNumber(rec.last_price);
  const priceAvailable =
    freshness.status !== 'UNAVAILABLE' && parsedPrice !== undefined && Number.isFinite(parsedPrice);
  const nowIso = new Date().toISOString();

  return {
    symbol,
    price: priceAvailable && parsedPrice !== undefined ? parsedPrice : 0,
    priceAvailable,
    currency: asString(rec.currency) ?? 'USD',
    changeValue: asNumber(rec.changeValue) ?? asNumber(rec.change_value) ?? asNumber(rec.change) ?? 0,
    changePercent:
      asNumber(rec.changePercent) ??
      asNumber(rec.change_percent) ??
      asNumber(rec.change_pct) ??
      0,
    source: freshness.source,
    dataAsOf: freshness.as_of ?? freshness.fetched_at ?? nowIso,
    dataStatus: freshness.status,
    fetchedAt: freshness.fetched_at,
    reason: freshness.reason,
    freshness,
  };
}

function mapWatchlistItem(raw: unknown, meta: Record<string, unknown> | null): WatchlistItem | null {
  const rec = asRecord(raw);
  if (!rec) {
    return null;
  }
  const symbol = asString(rec.symbol) ?? asString(rec.instrument_id);
  if (!symbol) {
    return null;
  }

  const hasFreshness =
    asRecord(rec.freshness) !== null ||
    typeof rec.freshness === 'string' ||
    rec.dataStatus !== undefined ||
    rec.status !== undefined;
  const freshness = hasFreshness ? parseFreshness(rec, meta) : undefined;
  const price = asNumber(rec.price) ?? asNumber(rec.unit_price) ?? null;

  return {
    symbol: symbol.toUpperCase(),
    name: asString(rec.name) ?? asString(rec.display_name) ?? symbol.toUpperCase(),
    addedAt:
      asString(rec.addedAt) ??
      asString(rec.added_at) ??
      asString(rec.created_at) ??
      new Date().toISOString(),
    securityId: asString(rec.securityId) ?? asString(rec.security_id) ?? asString(rec.instrument_id),
    exchange: asString(rec.exchange),
    currency: asString(rec.currency),
    price,
    changeValue: asNumber(rec.changeValue) ?? asNumber(rec.change_value) ?? asNumber(rec.change) ?? null,
    changePercent:
      asNumber(rec.changePercent) ?? asNumber(rec.change_percent) ?? asNumber(rec.change_pct) ?? null,
    source: freshness?.source ?? asString(rec.source),
    dataAsOf: freshness?.as_of ?? asString(rec.dataAsOf) ?? null,
    dataStatus: freshness?.status,
    freshness,
  };
}

function isWatchlistSummaryArray(items: unknown[]): boolean {
  if (items.length === 0) {
    return false;
  }
  const first = asRecord(items[0]);
  return Boolean(first && typeof first.watchlist_id === 'string' && !first.symbol && !first.instrument_id);
}

function extractItemsContainer(data: unknown): unknown[] {
  if (Array.isArray(data)) {
    return data;
  }
  const rec = asRecord(data);
  if (!rec) {
    return [];
  }
  const candidate = rec.items ?? rec.watchlists ?? rec.results;
  return Array.isArray(candidate) ? candidate : [];
}

function getActiveApiClient(config: MarketServiceConfig): ApiClient {
  if (!config.fetchImpl && config.apiBaseUrl === finexApiClient.baseUrl) {
    return finexApiClient;
  }
  return createApiClient({
    baseUrl: config.apiBaseUrl,
    fetchImpl: config.fetchImpl,
  });
}

async function apiRequest(
  path: string,
  init: RequestInit = {}
): Promise<{ status: number; ok: boolean; payload: unknown }> {
  const config = getMarketConfig();
  const client = getActiveApiClient(config);

  const controller = typeof AbortController === 'function' ? new AbortController() : undefined;
  const timeoutId = controller
    ? setTimeout(() => {
        controller.abort();
      }, config.timeoutMs)
    : undefined;

  try {
    const token = config.getAuthToken?.() ?? undefined;
    const response = await client.request(path, {
      ...init,
      accessToken: token,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers as Record<string, string> | undefined),
      },
      signal: init.signal ?? controller?.signal,
    });

    if (response.status === 204) {
      return { status: 204, ok: response.ok, payload: null };
    }

    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    return { status: response.status, ok: response.ok, payload };
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
  }
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  const rec = asRecord(payload);
  if (!rec) {
    return fallback;
  }
  const errorRec = asRecord(rec.error);
  return asString(errorRec?.message) ?? asString(rec.message) ?? asString(rec.detail) ?? fallback;
}

function extractErrorCode(payload: unknown): string | undefined {
  const rec = asRecord(payload);
  if (!rec) {
    return undefined;
  }
  const errorRec = asRecord(rec.error);
  return asString(errorRec?.code) ?? asString(rec.error_code);
}

function buildUnavailableQuote(symbol: string, reason: string, source = 'market-api'): MarketQuote {
  const nowIso = new Date().toISOString();
  return {
    symbol,
    price: 0,
    priceAvailable: false,
    currency: 'USD',
    changeValue: 0,
    changePercent: 0,
    source,
    dataAsOf: nowIso,
    dataStatus: 'UNAVAILABLE',
    fetchedAt: nowIso,
    reason,
    freshness: {
      status: 'UNAVAILABLE',
      source,
      as_of: null,
      fetched_at: nowIso,
      reason,
    },
  };
}

async function resolveDefaultWatchlistId(): Promise<{ watchlistId: string | null; flatItems: WatchlistItem[] | null }> {
  const { ok, payload } = await apiRequest('/api/v1/watchlists');
  if (!ok) {
    throw new Error(extractErrorMessage(payload, 'Unable to load your watchlist right now.'));
  }
  const { data, meta } = unwrapEnvelope(payload);
  const rawItems = extractItemsContainer(data);

  if (isWatchlistSummaryArray(rawItems)) {
    const firstSummary = asRecord(rawItems[0]);
    return { watchlistId: asString(firstSummary?.watchlist_id) ?? null, flatItems: null };
  }

  // Handle single WatchlistResponse object { watchlist_id, items: [...] }
  const rec = asRecord(data);
  if (rec && typeof rec.watchlist_id === 'string' && Array.isArray(rec.items)) {
    const mapped = rec.items
      .map((item) => mapWatchlistItem(item, meta))
      .filter((item): item is WatchlistItem => item !== null);
    return { watchlistId: rec.watchlist_id, flatItems: mapped };
  }

  // Handle flat item array
  const mapped = rawItems
    .map((item) => mapWatchlistItem(item, meta))
    .filter((item): item is WatchlistItem => item !== null);
  return { watchlistId: null, flatItems: mapped };
}

export const marketService = {
  /**
   * MKT-01: search securities by symbol or name.
   * Calls GET /api/v1/market/instruments?query=... in API mode or uses fixture catalog in fixture mode.
   */
  search: async (query: string): Promise<MarketSecurity[]> => {
    const trimmed = query.trim();
    if (trimmed.length < 1) {
      throw new Error('Enter at least one character to search.');
    }

    const config = getMarketConfig();
    if (config.mode === 'api') {
      const { ok, payload } = await apiRequest(
        `/api/v1/market/instruments?query=${encodeURIComponent(trimmed)}`
      );
      if (!ok) {
        throw new Error(extractErrorMessage(payload, 'Search is temporarily unavailable.'));
      }
      const { data } = unwrapEnvelope(payload);
      return extractItemsContainer(data)
        .map(mapSecurity)
        .filter((item): item is MarketSecurity => item !== null);
    }

    await new Promise((resolve) => setTimeout(resolve, 100));
    const lowered = trimmed.toLowerCase();
    return SECURITY_CATALOG.filter(
      (security) =>
        security.symbol.toLowerCase().includes(lowered) ||
        security.name.toLowerCase().includes(lowered)
    );
  },

  /**
   * MKT-02: get the latest available quote for a symbol.
   * Calls GET /api/v1/market/quotes/{symbol} in API mode.
   * Returns an explicit UNAVAILABLE status instead of fabricating a price on outage.
   */
  getQuote: async (symbol: string): Promise<MarketQuote> => {
    const normalized = symbol.trim().toUpperCase();
    if (!normalized) {
      throw new Error('SYMBOL_NOT_SUPPORTED');
    }

    const config = getMarketConfig();
    if (config.mode === 'api') {
      try {
        const { status, ok, payload } = await apiRequest(
          `/api/v1/market/quotes/${encodeURIComponent(normalized)}`
        );
        if (status === 404) {
          throw new Error('SYMBOL_NOT_SUPPORTED');
        }
        const errorCode = extractErrorCode(payload);
        if (errorCode === 'SYMBOL_NOT_SUPPORTED' || errorCode === 'INSTRUMENT_NOT_FOUND') {
          throw new Error('SYMBOL_NOT_SUPPORTED');
        }
        if (!ok) {
          return buildUnavailableQuote(
            normalized,
            extractErrorMessage(payload, 'Market data provider unavailable.')
          );
        }
        const { data, meta } = unwrapEnvelope(payload);
        return mapQuote(data, meta, normalized);
      } catch (err) {
        if (err instanceof Error && err.message === 'SYMBOL_NOT_SUPPORTED') {
          throw err;
        }
        return buildUnavailableQuote(
          normalized,
          err instanceof Error ? err.message : 'Market data provider unreachable.'
        );
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 100));

    if (normalized === UNAVAILABLE_SYMBOL) {
      return buildUnavailableQuote(
        normalized,
        'Simulated provider outage',
        'yfinance-fixture'
      );
    }

    const cached = QUOTE_CACHE[normalized];
    if (!cached) {
      throw new Error('SYMBOL_NOT_SUPPORTED');
    }

    const nowIso = new Date().toISOString();
    const freshness: DataFreshness = {
      status: cached.dataStatus,
      source: cached.source,
      as_of: nowIso,
      fetched_at: nowIso,
      reason: cached.reason ?? null,
    };

    return {
      symbol: normalized,
      price: cached.price,
      priceAvailable: true,
      currency: cached.currency,
      changeValue: cached.changeValue,
      changePercent: cached.changePercent,
      source: cached.source,
      dataAsOf: nowIso,
      dataStatus: cached.dataStatus,
      fetchedAt: nowIso,
      reason: cached.reason ?? null,
      freshness,
    };
  },

  /**
   * WAT-01: fetch the current user's default watchlist items.
   * Calls GET /api/v1/watchlists (and /api/v1/watchlists/{id}/items when nested) in API mode.
   */
  getWatchlist: async (): Promise<WatchlistItem[]> => {
    const config = getMarketConfig();
    if (config.mode === 'api') {
      const { watchlistId, flatItems } = await resolveDefaultWatchlistId();
      if (flatItems !== null) {
        return flatItems;
      }
      if (!watchlistId) {
        return [];
      }
      const { ok, payload } = await apiRequest(`/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items`);
      if (!ok) {
        throw new Error(extractErrorMessage(payload, 'Unable to load your watchlist right now.'));
      }
      const { data, meta } = unwrapEnvelope(payload);
      return extractItemsContainer(data)
        .map((item) => mapWatchlistItem(item, meta))
        .filter((item): item is WatchlistItem => item !== null);
    }

    await new Promise((resolve) => setTimeout(resolve, 80));
    return [...watchlist];
  },

  /**
   * WAT-01: add a security to the default watchlist.
   * Adding an already-present symbol is idempotent.
   */
  addToWatchlist: async (security: MarketSecurity): Promise<WatchlistItem[]> => {
    const config = getMarketConfig();
    if (config.mode === 'api') {
      const { watchlistId, flatItems } = await resolveDefaultWatchlistId();
      if (watchlistId) {
        const { ok, payload } = await apiRequest(
          `/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(security.symbol)}`,
          { method: 'PUT' }
        );
        if (!ok) {
          throw new Error(extractErrorMessage(payload, 'Unable to add security to watchlist.'));
        }
        return marketService.getWatchlist();
      }

      if (flatItems !== null && flatItems.length === 0) {
        const createRes = await apiRequest('/api/v1/watchlists', {
          method: 'POST',
          body: JSON.stringify({ name: 'Default' }),
        });
        if (!createRes.ok) {
          throw new Error(extractErrorMessage(createRes.payload, 'Unable to add security to watchlist.'));
        }
        const { data, meta } = unwrapEnvelope(createRes.payload);
        const createdRec = asRecord(data);
        if (createdRec && typeof createdRec.watchlist_id === 'string') {
          const addRes = await apiRequest(
            `/api/v1/watchlists/${encodeURIComponent(createdRec.watchlist_id)}/items/${encodeURIComponent(security.symbol)}`,
            { method: 'PUT' }
          );
          if (!addRes.ok) {
            throw new Error(extractErrorMessage(addRes.payload, 'Unable to add security to watchlist.'));
          }
          return marketService.getWatchlist();
        }
        const items = extractItemsContainer(data)
          .map((item) => mapWatchlistItem(item, meta))
          .filter((item): item is WatchlistItem => item !== null);
        return items.length > 0 ? items : marketService.getWatchlist();
      }

      const { ok, payload } = await apiRequest('/api/v1/watchlists', {
        method: 'POST',
        body: JSON.stringify({ symbol: security.symbol }),
      });
      if (!ok) {
        throw new Error(extractErrorMessage(payload, 'Unable to add security to watchlist.'));
      }
      const { data, meta } = unwrapEnvelope(payload);
      const items = extractItemsContainer(data)
        .map((item) => mapWatchlistItem(item, meta))
        .filter((item): item is WatchlistItem => item !== null);
      return items.length > 0 ? items : marketService.getWatchlist();
    }

    await new Promise((resolve) => setTimeout(resolve, 80));
    const exists = watchlist.some((item) => item.symbol === security.symbol);
    if (!exists) {
      const quote = QUOTE_CACHE[security.symbol];
      const nowIso = new Date().toISOString();
      const status: DataStatus =
        security.symbol === UNAVAILABLE_SYMBOL ? 'UNAVAILABLE' : quote?.dataStatus ?? 'UNAVAILABLE';
      const source =
        security.symbol === UNAVAILABLE_SYMBOL
          ? 'yfinance-fixture'
          : quote?.source ?? 'yfinance-fixture';

      watchlist = [
        ...watchlist,
        {
          symbol: security.symbol,
          name: security.name,
          addedAt: nowIso,
          securityId: security.securityId,
          exchange: security.exchange,
          currency: security.currency,
          price: quote?.price ?? null,
          changeValue: quote?.changeValue ?? null,
          changePercent: quote?.changePercent ?? null,
          source,
          dataAsOf: status === 'UNAVAILABLE' ? null : nowIso,
          dataStatus: status,
          freshness: {
            status,
            source,
            as_of: status === 'UNAVAILABLE' ? null : nowIso,
            fetched_at: nowIso,
            reason: quote?.reason ?? null,
          },
        },
      ];
    }

    return [...watchlist];
  },

  /**
   * WAT-01: remove a security from the default watchlist.
   * Removing an absent symbol is idempotent.
   */
  removeFromWatchlist: async (symbol: string): Promise<WatchlistItem[]> => {
    const normalized = symbol.trim().toUpperCase();
    const config = getMarketConfig();

    if (config.mode === 'api') {
      const { watchlistId } = await resolveDefaultWatchlistId();
      const path = watchlistId
        ? `/api/v1/watchlists/${encodeURIComponent(watchlistId)}/items/${encodeURIComponent(normalized)}`
        : `/api/v1/watchlists/${encodeURIComponent(normalized)}`;

      const { ok, payload } = await apiRequest(path, { method: 'DELETE' });
      if (!ok) {
        throw new Error(extractErrorMessage(payload, 'Unable to remove security from watchlist.'));
      }
      if (!watchlistId && payload !== null) {
        const { data, meta } = unwrapEnvelope(payload);
        const rec = asRecord(data);
        if (Array.isArray(data) || (rec && Array.isArray(rec.items))) {
          return extractItemsContainer(data)
            .map((item) => mapWatchlistItem(item, meta))
            .filter((item): item is WatchlistItem => item !== null);
        }
      }
      return marketService.getWatchlist();
    }

    await new Promise((resolve) => setTimeout(resolve, 80));
    watchlist = watchlist.filter((item) => item.symbol !== normalized && item.symbol !== symbol);
    return [...watchlist];
  },
};
