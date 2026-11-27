import {
  configureMarketService,
  getMarketConfig,
  marketService,
  resetFixtureWatchlist,
  resetMarketServiceConfig,
} from './marketService';
import { DataStatus, getFreshnessBadgeMeta } from '../types/market';

describe('marketService', () => {
  beforeEach(() => {
    resetMarketServiceConfig();
    resetFixtureWatchlist();
  });

  afterEach(() => {
    resetMarketServiceConfig();
  });

  describe('search (MKT-01)', () => {
    test('returns matching securities for a valid symbol query', async () => {
      const results = await marketService.search('AAPL');

      expect(results.length).toBeGreaterThan(0);
      expect(results[0].symbol).toBe('AAPL');
    });

    test('returns matching securities for a partial name query', async () => {
      const results = await marketService.search('Microsoft');

      expect(results.some((r) => r.symbol === 'MSFT')).toBe(true);
    });

    test('returns NSE and BSE securities with exchange and currency', async () => {
      const results = await marketService.search('RELIANCE');

      expect(results).toHaveLength(1);
      expect(results[0].symbol).toBe('RELIANCE.NS');
      expect(results[0].exchange).toBe('NSE');
      expect(results[0].currency).toBe('INR');
    });

    test('returns an empty array for an unmatched query', async () => {
      const results = await marketService.search('ZZZUNKNOWN');

      expect(results).toEqual([]);
    });

    test('rejects an empty query', async () => {
      await expect(marketService.search('')).rejects.toThrow(
        'Enter at least one character to search.'
      );
    });
  });

  describe('getQuote (MKT-02)', () => {
    test('returns a canonical quote with source and freshness for a supported symbol', async () => {
      const quote = await marketService.getQuote('AAPL');

      expect(quote.symbol).toBe('AAPL');
      expect(quote.source).toBeTruthy();
      expect(quote.dataAsOf).toBeTruthy();
      expect(quote.dataStatus).not.toBe('UNAVAILABLE');
      expect(quote.freshness?.status).toBe('CACHED');
    });

    test('returns honest MARKET_CLOSED, STALE, and DELAYED statuses in fixture mode', async () => {
      const tcs = await marketService.getQuote('TCS.NS');
      const infy = await marketService.getQuote('INFY.BO');
      const nvda = await marketService.getQuote('NVDA');

      expect(tcs.dataStatus).toBe('MARKET_CLOSED');
      expect(tcs.freshness?.status).toBe('MARKET_CLOSED');
      expect(infy.dataStatus).toBe('STALE');
      expect(infy.freshness?.status).toBe('STALE');
      expect(nvda.dataStatus).toBe('DELAYED');
      expect(nvda.freshness?.status).toBe('DELAYED');
    });

    test('rejects an unsupported symbol', async () => {
      await expect(marketService.getQuote('NOPE')).rejects.toThrow(
        'SYMBOL_NOT_SUPPORTED'
      );
    });

    test('returns an explicit UNAVAILABLE status instead of throwing when the provider has no usable price', async () => {
      const quote = await marketService.getQuote('DOWN');

      expect(quote.dataStatus).toBe('UNAVAILABLE');
      expect(quote.priceAvailable).toBe(false);
      expect(quote.freshness?.status).toBe('UNAVAILABLE');
    });
  });

  describe('watchlist (WAT-01)', () => {
    test('adding a security is idempotent on duplicate add', async () => {
      const security = {
        securityId: 'sec_msft',
        symbol: 'MSFT',
        name: 'Microsoft Corporation',
        assetType: 'EQUITY',
        exchange: 'NASDAQ',
        currency: 'USD',
      };

      const first = await marketService.addToWatchlist(security);
      const second = await marketService.addToWatchlist(security);

      expect(second.filter((item) => item.symbol === 'MSFT')).toHaveLength(1);
      expect(second.length).toBe(first.length);
    });

    test('removing an absent security is idempotent', async () => {
      const before = await marketService.getWatchlist();
      const after = await marketService.removeFromWatchlist('NOTINLIST');

      expect(after.length).toBe(before.length);
    });
  });

  describe('API mode (/market/* and /watchlists)', () => {
    test('calls /api/v1/market/instruments with Bearer auth and maps S2-PA03 items', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 200,
        ok: true,
        json: async () => ({
          success: true,
          message: 'Instrument search completed',
          data: {
            items: [
              {
                symbol: 'RELIANCE',
                name: 'Reliance Industries Limited',
                exchange: 'NSE',
                asset_class: 'EQUITY',
                currency: 'INR',
              },
              {
                symbol: 'RELIANCE',
                name: 'Reliance Industries Limited',
                exchange: 'BSE',
                asset_class: 'EQUITY',
                currency: 'INR',
              },
            ],
            count: 2,
          },
        }),
      });

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
        getAuthToken: () => 'test-bearer-token',
      });

      expect(getMarketConfig().mode).toBe('api');
      const results = await marketService.search('RELIANCE');

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/v1/market/instruments?query=RELIANCE',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-bearer-token',
          }),
        })
      );
      expect(results).toEqual([
        {
          securityId: 'RELIANCE:NSE',
          symbol: 'RELIANCE',
          name: 'Reliance Industries Limited',
          assetType: 'EQUITY',
          exchange: 'NSE',
          currency: 'INR',
        },
        {
          securityId: 'RELIANCE:BSE',
          symbol: 'RELIANCE',
          name: 'Reliance Industries Limited',
          assetType: 'EQUITY',
          exchange: 'BSE',
          currency: 'INR',
        },
      ]);
    });

    test('calls /api/v1/market/quotes/{symbol} and handles S2-PA01 MarketQuoteResponse + yfinance LIVE guard', async () => {
      const mockFetch = jest
        .fn()
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: {
              symbol: 'TCS.NS',
              price: 4125.5,
              currency: 'INR',
              change: 12.5,
              change_pct: 0.003,
              source: 'market-calendar',
              as_of: '2026-11-26T10:00:00Z',
              fetched_at: '2026-11-26T17:00:00Z',
              freshness: 'MARKET_CLOSED',
              error: 'Exchange closed',
            },
          }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: {
              symbol: 'AAPL',
              price: 227.5,
              currency: 'USD',
              change: 1.0,
              change_pct: 0.004,
              source: 'yfinance',
              as_of: '2026-11-26T17:00:00Z',
              fetched_at: '2026-11-26T17:01:00Z',
              freshness: 'LIVE',
            },
          }),
        });

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      });

      const tcs = await marketService.getQuote('TCS.NS');
      expect(mockFetch).toHaveBeenNthCalledWith(
        1,
        'http://127.0.0.1:8000/api/v1/market/quotes/TCS.NS',
        expect.any(Object)
      );
      expect(tcs.price).toBe(4125.5);
      expect(tcs.currency).toBe('INR');
      expect(tcs.dataStatus).toBe('MARKET_CLOSED');
      expect(tcs.reason).toBe('Exchange closed');

      const aapl = await marketService.getQuote('AAPL');
      expect(aapl.dataStatus).toBe('DELAYED');
    });

    test('returns UNAVAILABLE without fabricating a price when API quote fails or times out', async () => {
      const mockFetch = jest.fn().mockRejectedValue(new Error('Network timeout'));

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      });

      const quote = await marketService.getQuote('AAPL');
      expect(quote.dataStatus).toBe('UNAVAILABLE');
      expect(quote.priceAvailable).toBe(false);
    });

    test('throws SYMBOL_NOT_SUPPORTED on 404 from /api/v1/market/quotes/{symbol}', async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        status: 404,
        ok: false,
        json: async () => ({ error: { code: 'INSTRUMENT_NOT_FOUND', message: 'Not found' } }),
      });

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      });

      await expect(marketService.getQuote('UNKNOWN')).rejects.toThrow('SYMBOL_NOT_SUPPORTED');
    });

    test('calls S2-PA06 /api/v1/watchlists and /items routes', async () => {
      const summaries = [
        {
          watchlist_id: 'wl-1',
          name: 'Default Watchlist',
          created_at: '2026-11-26T10:00:00Z',
          updated_at: '2026-11-26T10:00:00Z',
          item_count: 1,
        },
      ];
      const items = [
        {
          instrument_id: 'AAPL',
          added_at: '2026-11-26T12:00:00Z',
        },
      ];

      const mockFetch = jest
        .fn()
        // getWatchlist -> GET /watchlists -> GET /watchlists/wl-1/items
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: summaries, count: 1 } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items, count: 1 } }),
        })
        // addToWatchlist -> GET /watchlists -> PUT /watchlists/wl-1/items/MSFT -> getWatchlist
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: summaries, count: 1 } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { instrument_id: 'MSFT', added_at: '2026-11-26T12:05:00Z' } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: summaries, count: 1 } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: {
              items: [...items, { instrument_id: 'MSFT', added_at: '2026-11-26T12:05:00Z' }],
              count: 2,
            },
          }),
        })
        // removeFromWatchlist -> GET /watchlists -> DELETE /watchlists/wl-1/items/MSFT -> getWatchlist
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: summaries, count: 1 } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { watchlist_id: 'wl-1', instrument_id: 'MSFT', removed: true } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: summaries, count: 1 } }),
        })
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items, count: 1 } }),
        });

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      });

      const list = await marketService.getWatchlist();
      expect(list.map((i) => i.symbol)).toEqual(['AAPL']);

      const added = await marketService.addToWatchlist({
        securityId: 'sec_msft',
        symbol: 'MSFT',
        name: 'Microsoft Corporation',
        assetType: 'EQUITY',
        exchange: 'NASDAQ',
        currency: 'USD',
      });
      expect(added.map((i) => i.symbol)).toEqual(['AAPL', 'MSFT']);
      expect(mockFetch).toHaveBeenNthCalledWith(
        4,
        'http://127.0.0.1:8000/api/v1/watchlists/wl-1/items/MSFT',
        expect.objectContaining({ method: 'PUT' })
      );

      const afterRemove = await marketService.removeFromWatchlist('MSFT');
      expect(afterRemove.map((i) => i.symbol)).toEqual(['AAPL']);
      expect(mockFetch).toHaveBeenNthCalledWith(
        8,
        'http://127.0.0.1:8000/api/v1/watchlists/wl-1/items/MSFT',
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    test('creates a named Default watchlist before adding item when GET /api/v1/watchlists is empty', async () => {
      const createdWatchlist = {
        watchlist_id: 'wl-new',
        name: 'Default',
        created_at: '2026-11-27T07:00:00Z',
        updated_at: '2026-11-27T07:00:00Z',
        item_count: 0,
      };
      const items = [
        {
          instrument_id: 'AAPL',
          added_at: '2026-11-27T07:00:01Z',
        },
      ];

      const mockFetch = jest
        .fn()
        // 1. resolveDefaultWatchlistId -> GET /watchlists -> empty
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items: [], count: 0 } }),
        })
        // 2. POST /watchlists with { name: 'Default' }
        .mockResolvedValueOnce({
          status: 201,
          ok: true,
          json: async () => ({ success: true, data: createdWatchlist }),
        })
        // 3. PUT /watchlists/wl-new/items/AAPL
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: items[0] }),
        })
        // 4. getWatchlist -> GET /watchlists -> summary
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({
            success: true,
            data: { items: [{ ...createdWatchlist, item_count: 1 }], count: 1 },
          }),
        })
        // 5. getWatchlist -> GET /watchlists/wl-new/items
        .mockResolvedValueOnce({
          status: 200,
          ok: true,
          json: async () => ({ success: true, data: { items, count: 1 } }),
        });

      configureMarketService({
        mode: 'api',
        apiBaseUrl: 'http://127.0.0.1:8000',
        fetchImpl: mockFetch as unknown as typeof fetch,
      });

      const result = await marketService.addToWatchlist({
        securityId: 'sec_aapl',
        symbol: 'AAPL',
        name: 'Apple Inc.',
        assetType: 'EQUITY',
        exchange: 'NASDAQ',
        currency: 'USD',
      });

      expect(mockFetch).toHaveBeenNthCalledWith(
        2,
        'http://127.0.0.1:8000/api/v1/watchlists',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Default' }),
        })
      );
      expect(mockFetch).toHaveBeenNthCalledWith(
        3,
        'http://127.0.0.1:8000/api/v1/watchlists/wl-new/items/AAPL',
        expect.objectContaining({ method: 'PUT' })
      );
      expect(result.map((item) => item.symbol)).toEqual(['AAPL']);
    });
  });

  describe('freshness badge metadata', () => {
    test.each<[DataStatus, string]>([
      ['LIVE', 'Live'],
      ['DELAYED', 'Delayed'],
      ['CACHED', 'Cached'],
      ['MARKET_CLOSED', 'Market closed'],
      ['STALE', 'Stale'],
      ['UNAVAILABLE', 'Unavailable'],
      ['END_OF_DAY', 'End of day'],
    ])('maps %s to badge label %s', (status, expectedLabel) => {
      const meta = getFreshnessBadgeMeta(status);
      expect(meta.status).toBe(status);
      expect(meta.label).toBe(expectedLabel);
    });

    test('unknown status defaults safely to Unavailable', () => {
      const meta = getFreshnessBadgeMeta('BOGUS');
      expect(meta.status).toBe('UNAVAILABLE');
      expect(meta.label).toBe('Unavailable');
    });
  });
});
