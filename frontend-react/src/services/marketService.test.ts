import { marketService } from './marketService';

describe('marketService', () => {
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
    });

    test('rejects an unsupported symbol', async () => {
      await expect(marketService.getQuote('NOPE')).rejects.toThrow(
        'SYMBOL_NOT_SUPPORTED'
      );
    });

    test('returns an explicit UNAVAILABLE status instead of throwing when the provider has no usable price', async () => {
      const quote = await marketService.getQuote('DOWN');

      expect(quote.dataStatus).toBe('UNAVAILABLE');
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
});
