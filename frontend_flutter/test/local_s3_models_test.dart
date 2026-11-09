import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';

import 'support/local_s3_data.dart';

Map<String, dynamic> copy(Map<String, dynamic> raw) =>
    jsonDecode(jsonEncode(raw)) as Map<String, dynamic>;
void main() {
  test('search preserves exact strings and genuine empty results', () {
    expect(LocalMarketSearch.fromJson(s3Search(limit: 1)).items.length, 1);
    final raw = s3Search()
      ..['count'] = 0
      ..['items'] = <Object?>[];
    expect(LocalMarketSearch.fromJson(raw).items, isEmpty);
  });
  for (final status in ['CACHED', 'STALE', 'UNAVAILABLE']) {
    test('quote $status is a truthful nullable DTO', () {
      final quote = LocalMarketQuote.fromJson(s3Quote(status: status));
      expect(quote.status, status);
      expect(quote.unitPrice, status == 'UNAVAILABLE' ? null : '200.0000');
    });
  }
  test('first provider failure permits both retrieval times null', () {
    final raw = s3Quote(status: 'UNAVAILABLE')
      ..['reason'] = 'SYNTHETIC_PROVIDER_UNAVAILABLE'
      ..['fetched_at'] = null
      ..['cache_expires_at'] = null;
    expect(LocalMarketQuote.fromJson(raw).fetchedAt, isNull);
  });
  for (final field in ['fixture_as_of', 'quote_as_of']) {
    test('immutable $field requires the literal frozen Z timestamp', () {
      final raw = s3Quote()..[field] = '2026-01-01T00:00:00+00:00';
      expect(
        () => LocalMarketQuote.fromJson(raw),
        throwsA(isA<LocalApiException>()),
      );
    });
  }
  test('retrieval UTC aliases and microsecond precision remain supported', () {
    final raw = s3Quote()
      ..['fetched_at'] = '2030-01-01T00:00:00.000001+00:00'
      ..['cache_expires_at'] = '2030-01-01T00:01:00.000001+00:00';
    expect(
      LocalMarketQuote.fromJson(raw).fetchedAt,
      DateTime.utc(2030, 1, 1, 0, 0, 0, 0, 1),
    );
  });
  test('watchlists, detail and items decode nested unscoped records', () {
    expect(LocalWatchlistList.fromJson(s3Watchlists()).items.single.id, s3Id);
    expect(
      LocalWatchlist.fromJson(s3Watchlist(item: true))
          .items
          .single
          .instrument
          .instrumentId,
      'SYN:AAPL',
    );
  });
  test('account read remains truly unopened instead of zero cash', () {
    expect(
      LocalPaperAccountState.fromJson(s3Account(opened: false)).account,
      isNull,
    );
    expect(
      LocalPaperAccountState.fromJson(s3Account()).account!.cashBalance,
      '10000.00',
    );
  });
  test('opening ledger uses integer cursor and immutable opening strings', () {
    final value = LocalPaperLedger.fromJson(s3Ledger());
    expect(value.items.single.sequence, 1);
    expect(value.items.single.cashDelta, '10000.00');
    expect(LocalPaperLedger.fromJson(s3Ledger(after: 1)).items, isEmpty);
  });
  final corruptions = <String, void Function(Map<String, dynamic>)>{
    'LIVE status': (v) => v['status'] = 'LIVE',
    'zero quote': (v) => v['unit_price'] = '0.0000',
    'numeric quote': (v) => v['unit_price'] = 200,
    'overbound price': (v) => v['unit_price'] = '1000000.0001',
    'non-UTC': (v) => v['fetched_at'] = '2030-01-01T01:00:00+01:00',
    'unequal cache TTL': (v) => v['cache_expires_at'] = '2030-01-01T00:01:01Z',
    'missing nullable key': (v) => v.remove('reason'),
    'wrong source': (v) => v['source'] = 'yfinance',
    'wrong foundation': (v) => v['foundation_version'] = 'v0',
    'extra owner': (v) => v['user_id'] = 'synthetic-owner',
  };
  for (final entry in corruptions.entries) {
    test('quote rejects ${entry.key}', () {
      final raw = copy(s3Quote());
      entry.value(raw);
      expect(
        () => LocalMarketQuote.fromJson(raw),
        throwsA(isA<LocalApiException>()),
      );
    });
  }
  test('watchlist rejects duplicate items and count lies', () {
    final raw = s3Watchlist(item: true);
    raw['items'] = [s3Item(), s3Item()];
    raw['item_count'] = 2;
    expect(
      () => LocalWatchlist.fromJson(raw),
      throwsA(isA<LocalApiException>()),
    );
  });
  test(
    'search trusts server Unicode casefold matching without local replacement',
    () {
      final raw = s3Search(query: 'STRASSE');
      raw['items'] = [
        s3Instrument()..['display_name'] = 'Straße teaching example',
      ];
      raw['count'] = 1;
      expect(LocalMarketSearch.fromJson(raw).items.length, 1);
    },
  );
  for (final sequence in ['1', true, 1.5, 9007199254740992]) {
    test('ledger rejects unsafe integer ${sequence.runtimeType}', () {
      final raw = copy(s3Ledger());
      (raw['items'] as List).first['sequence'] = sequence;
      expect(
        () => LocalPaperLedger.fromJson(raw),
        throwsA(isA<LocalApiException>()),
      );
    });
  }
}
