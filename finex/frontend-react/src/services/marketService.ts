import { MarketQuote, MarketSecurity, WatchlistItem } from '../types/market';

// Canonical prototype security master.
// Mirrors the shape of market.securities (MKT-01) until the real
// FastAPI endpoint is available.
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
    securityId: 'sec_down',
    symbol: 'DOWN',
    name: 'Provider Outage Demo Security',
    assetType: 'EQUITY',
    exchange: 'DEMO',
    currency: 'USD',
  },
];

// Mock cached quotes. Every quote carries a source and an explicit
// dataAsOf/dataStatus label, matching the handbook rule that prototype
// market data must never be presented as guaranteed live.
const QUOTE_CACHE: Record<string, Omit<MarketQuote, 'symbol' | 'dataAsOf'>> = {
  AAPL: {
    price: 227.52,
    currency: 'USD',
    changeValue: 1.84,
    changePercent: 0.0082,
    source: 'yfinance-prototype',
    dataStatus: 'CACHED',
  },
  MSFT: {
    price: 421.1,
    currency: 'USD',
    changeValue: -2.35,
    changePercent: -0.0055,
    source: 'yfinance-prototype',
    dataStatus: 'CACHED',
  },
  NVDA: {
    price: 138.07,
    currency: 'USD',
    changeValue: -1.12,
    changePercent: -0.0080,
    source: 'yfinance-prototype',
    dataStatus: 'DELAYED',
  },
  GOOGL: {
    price: 176.4,
    currency: 'USD',
    changeValue: 0.65,
    changePercent: 0.0037,
    source: 'yfinance-prototype',
    dataStatus: 'CACHED',
  },
  VTI: {
    price: 289.33,
    currency: 'USD',
    changeValue: 0.42,
    changePercent: 0.0015,
    source: 'yfinance-prototype',
    dataStatus: 'END_OF_DAY',
  },
};

// Symbol explicitly wired to simulate a provider outage so the
// PRICE_UNAVAILABLE / provider-unavailable UI state is testable.
const UNAVAILABLE_SYMBOL = 'DOWN';

let watchlist: WatchlistItem[] = [
  { symbol: 'AAPL', name: 'Apple Inc.', addedAt: new Date().toISOString() },
];

export const marketService = {
  /**
   * MKT-01: search securities by symbol or name.
   * Mock service while backend API is pending.
   */
  search: async (query: string): Promise<MarketSecurity[]> => {
    await new Promise((resolve) => setTimeout(resolve, 300));

    const trimmed = query.trim();
    if (trimmed.length < 1) {
      throw new Error('Enter at least one character to search.');
    }

    const lowered = trimmed.toLowerCase();
    return SECURITY_CATALOG.filter(
      (security) =>
        security.symbol.toLowerCase().includes(lowered) ||
        security.name.toLowerCase().includes(lowered)
    );
  },

  /**
   * MKT-02: get the latest available quote for a symbol.
   * Returns an explicit unavailable status instead of throwing so the
   * client can render a PRICE_UNAVAILABLE state per the handbook.
   */
  getQuote: async (symbol: string): Promise<MarketQuote> => {
    await new Promise((resolve) => setTimeout(resolve, 400));

    const normalized = symbol.trim().toUpperCase();

    if (normalized === UNAVAILABLE_SYMBOL) {
      return {
        symbol: normalized,
        price: 0,
        currency: 'USD',
        changeValue: 0,
        changePercent: 0,
        source: 'yfinance-prototype',
        dataAsOf: new Date().toISOString(),
        dataStatus: 'UNAVAILABLE',
      };
    }

    const cached = QUOTE_CACHE[normalized];
    if (!cached) {
      throw new Error('SYMBOL_NOT_SUPPORTED');
    }

    return {
      symbol: normalized,
      dataAsOf: new Date().toISOString(),
      ...cached,
    };
  },

  /**
   * WAT-01: fetch the current user's default watchlist.
   */
  getWatchlist: async (): Promise<WatchlistItem[]> => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    return [...watchlist];
  },

  /**
   * WAT-01: add a security to the default watchlist.
   * Adding an already-present symbol is idempotent per the handbook.
   */
  addToWatchlist: async (security: MarketSecurity): Promise<WatchlistItem[]> => {
    await new Promise((resolve) => setTimeout(resolve, 250));

    const exists = watchlist.some((item) => item.symbol === security.symbol);
    if (!exists) {
      watchlist = [
        ...watchlist,
        { symbol: security.symbol, name: security.name, addedAt: new Date().toISOString() },
      ];
    }

    return [...watchlist];
  },

  /**
   * WAT-01: remove a security from the default watchlist.
   * Removing an absent symbol is idempotent per the handbook.
   */
  removeFromWatchlist: async (symbol: string): Promise<WatchlistItem[]> => {
    await new Promise((resolve) => setTimeout(resolve, 250));

    watchlist = watchlist.filter((item) => item.symbol !== symbol);
    return [...watchlist];
  },
};
