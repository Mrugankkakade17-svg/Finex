import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/features/market/models/market_models.dart';
import 'package:frontend_flutter/features/market/services/market_service.dart';

void main() {
  group('MarketService', () {
    test('search (MKT-01) returns matching securities for a symbol query', () async {
      final service = MarketService();
      final results = await service.search('AAPL');

      expect(results, isNotEmpty);
      expect(results.first.symbol, 'AAPL');
    });

    test('search (MKT-01) returns matching securities for a partial name query', () async {
      final service = MarketService();
      final results = await service.search('Microsoft');

      expect(results.any((r) => r.symbol == 'MSFT'), isTrue);
    });

    test('search (MKT-01) returns an empty list for an unmatched query', () async {
      final service = MarketService();
      final results = await service.search('ZZZUNKNOWN');

      expect(results, isEmpty);
    });

    test('search (MKT-01) rejects an empty query', () async {
      final service = MarketService();

      expect(() => service.search(''), throwsException);
    });

    test('getQuote (MKT-02) returns a canonical quote with source and freshness', () async {
      final service = MarketService();
      final quote = await service.getQuote('AAPL');

      expect(quote.symbol, 'AAPL');
      expect(quote.source, isNotEmpty);
      expect(quote.dataStatus, isNot(DataStatus.unavailable));
    });

    test('getQuote (MKT-02) rejects an unsupported symbol', () async {
      final service = MarketService();

      expect(() => service.getQuote('NOPE'), throwsException);
    });

    test('getQuote (MKT-02) returns UNAVAILABLE status instead of throwing for the outage symbol', () async {
      final service = MarketService();
      final quote = await service.getQuote(kUnavailableSymbol);

      expect(quote.dataStatus, DataStatus.unavailable);
    });

    test('addToWatchlist (WAT-01) is idempotent on duplicate add', () async {
      final service = MarketService();
      const security = MarketSecurity(
        securityId: 'sec_googl',
        symbol: 'GOOGL',
        name: 'Alphabet Inc.',
        assetType: 'EQUITY',
        exchange: 'NASDAQ',
        currency: 'USD',
      );

      final first = await service.addToWatchlist(security);
      final second = await service.addToWatchlist(security);

      expect(
        second.where((item) => item.symbol == 'GOOGL').length,
        1,
      );
      expect(second.length, first.length);
    });

    test('removeFromWatchlist (WAT-01) is idempotent for an absent symbol', () async {
      final service = MarketService();
      final before = await service.getWatchlist();
      final after = await service.removeFromWatchlist('NOTINLIST');

      expect(after.length, before.length);
    });
  });
}
