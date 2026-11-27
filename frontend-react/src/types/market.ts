export type DataStatus =
  | 'LIVE'
  | 'DELAYED'
  | 'END_OF_DAY'
  | 'CACHED'
  | 'MARKET_CLOSED'
  | 'STALE'
  | 'UNAVAILABLE';

export type MarketMode = 'fixture' | 'api';

export interface DataFreshness {
  status: DataStatus;
  source: string;
  as_of: string | null;
  fetched_at: string | null;
  reason?: string | null;
}

export interface MarketSecurity {
  securityId: string;
  symbol: string;
  name: string;
  assetType: string;
  exchange: string;
  currency: string;
}

export interface MarketQuote {
  symbol: string;
  price: number;
  priceAvailable?: boolean;
  currency: string;
  changeValue: number;
  changePercent: number;
  source: string;
  dataAsOf: string;
  dataStatus: DataStatus;
  fetchedAt?: string | null;
  reason?: string | null;
  freshness?: DataFreshness;
}

export interface WatchlistItem {
  symbol: string;
  name: string;
  addedAt: string;
  securityId?: string;
  exchange?: string;
  currency?: string;
  price?: number | null;
  changeValue?: number | null;
  changePercent?: number | null;
  source?: string;
  dataAsOf?: string | null;
  dataStatus?: DataStatus;
  freshness?: DataFreshness;
}

export interface MarketServiceConfig {
  mode: MarketMode;
  apiBaseUrl: string;
  timeoutMs: number;
  fetchImpl?: typeof fetch;
  getAuthToken?: () => string | null;
}

export interface FreshnessBadgeMeta {
  status: DataStatus;
  label: string;
  description: string;
  color: string;
  background: string;
  borderColor: string;
}

const VALID_DATA_STATUSES: ReadonlySet<string> = new Set<DataStatus>([
  'LIVE',
  'DELAYED',
  'END_OF_DAY',
  'CACHED',
  'MARKET_CLOSED',
  'STALE',
  'UNAVAILABLE',
]);

export function normalizeDataStatus(value: unknown): DataStatus {
  if (typeof value === 'string') {
    const normalized = value.trim().toUpperCase();
    if (VALID_DATA_STATUSES.has(normalized)) {
      return normalized as DataStatus;
    }
  }
  return 'UNAVAILABLE';
}

export const FRESHNESS_BADGE_META: Record<DataStatus, FreshnessBadgeMeta> = {
  LIVE: {
    status: 'LIVE',
    label: 'Live',
    description: 'Licensed real-time market feed',
    color: '#065F46',
    background: '#ECFDF5',
    borderColor: '#6EE7B7',
  },
  DELAYED: {
    status: 'DELAYED',
    label: 'Delayed',
    description: 'Delayed upstream provider quote',
    color: '#93370D',
    background: '#FFFAEB',
    borderColor: '#FEC84B',
  },
  END_OF_DAY: {
    status: 'END_OF_DAY',
    label: 'End of day',
    description: 'Latest market close settlement price',
    color: '#1E40AF',
    background: '#EFF6FF',
    borderColor: '#93C5FD',
  },
  CACHED: {
    status: 'CACHED',
    label: 'Cached',
    description: 'Served from validated cache within TTL',
    color: '#075985',
    background: '#F0F9FF',
    borderColor: '#7DD3FC',
  },
  MARKET_CLOSED: {
    status: 'MARKET_CLOSED',
    label: 'Market closed',
    description: 'Exchange is currently closed',
    color: '#334155',
    background: '#F1F5F9',
    borderColor: '#CBD5E1',
  },
  STALE: {
    status: 'STALE',
    label: 'Stale',
    description: 'Last stored quote shown during upstream delay or outage',
    color: '#9A3412',
    background: '#FFF7ED',
    borderColor: '#FDBA74',
  },
  UNAVAILABLE: {
    status: 'UNAVAILABLE',
    label: 'Unavailable',
    description: 'No usable market price returned by provider',
    color: '#B42318',
    background: '#FEF3F2',
    borderColor: '#FDA29B',
  },
};

export function getFreshnessBadgeMeta(
  status: DataStatus | string | undefined | null
): FreshnessBadgeMeta {
  return FRESHNESS_BADGE_META[normalizeDataStatus(status)];
}
