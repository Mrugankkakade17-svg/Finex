// Fidelity controls for the test-only default teaching fixture, not native proof.
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';

import 'support/local_s3_data.dart';
import 'support/local_s3_fake.dart';

void main() {
  late FakeLocalS3Api api;
  final token = List.filled(43, 'A').join();
  const ids = ['SYN:AAPL', 'SYN:BND', 'SYN:MSFT', 'SYN:UNAVAILABLE'];
  setUp(() => api = FakeLocalS3Api());
  test('data helper contains the exact sorted four default instruments', () {
    final raw = s3Search();
    expect((raw['items'] as List).map((v) => v['instrument_id']).toList(), ids);
    expect(raw['count'], 4);
    expect(s3Instrument('SYN:BND')['asset_class'], 'BOND');
    expect(s3Instrument('SYN:BND')['sector'], 'FIXED_INCOME');
  });
  test(
    'fake default search includes all four, not an AAPL-only shortcut',
    () async {
      expect(
        (await api.marketSearch(token)).value.items
            .map((v) => v.instrumentId)
            .toList(),
        ids,
      );
    },
  );
  test('fake search trims and filters known IDs case-insensitively', () async {
    final result = await api.marketSearch(token, query: ' bNd ', limit: 2);
    expect(result.value.query, 'bNd');
    expect(result.value.items.map((v) => v.instrumentId).toList(), ['SYN:BND']);
  });
  test('fake bounded search preserves sorted first two items', () async {
    expect(
      (await api.marketSearch(
        token,
        limit: 2,
      )).value.items.map((v) => v.instrumentId).toList(),
      ids.take(2).toList(),
    );
  });
  test('no-match remains a genuine empty result', () async {
    expect(
      (await api.marketSearch(token, query: 'no-match')).value.items,
      isEmpty,
    );
  });
  for (final pair in [
    ('SYN:AAPL', '200.0000'),
    ('SYN:BND', '80.0000'),
    ('SYN:MSFT', '400.0000'),
  ]) {
    test('fake ${pair.$1} returns its exact per-ID synthetic price', () async {
      final reply = await api.marketQuote(token, pair.$1);
      expect(reply.value.instrumentId, pair.$1);
      expect(reply.value.unitPrice, pair.$2);
      expect(reply.value.status, 'CACHED');
      expect(reply.dataStatus, 'CACHED');
    });
  }
  test(
    'default unavailable instrument has explicit null price and metadata',
    () async {
      final reply = await api.marketQuote(token, 'SYN:UNAVAILABLE');
      expect(reply.value.unitPrice, isNull);
      expect(reply.value.quoteAsOf, isNull);
      expect(reply.value.status, 'UNAVAILABLE');
      expect(reply.dataStatus, 'UNAVAILABLE');
      expect(reply.dataAsOf, isNull);
      expect(reply.value.reason, 'SYNTHETIC_QUOTE_UNAVAILABLE');
    },
  );
  test('unknown quote is typed404, never a fabricated200 price', () async {
    await expectLater(
      api.marketQuote(token, 'SYN:UNKNOWN'),
      throwsA(
        isA<LocalApiException>()
            .having((e) => e.code, 'safe code', 'INSTRUMENT_NOT_FOUND')
            .having((e) => e.status, 'status', 404),
      ),
    );
  });
  for (final add in [true, false]) {
    test(
      'unknown ${add ? 'add' : 'remove'} with known owned parent is rejected before mutation',
      () async {
        api.saved['A']![s3Id] = s3Watchlist(item: true);
        await expectLater(
          add
              ? api.putWatchlistItem(token, s3Id, 'SYN:UNKNOWN')
              : api.removeWatchlistItem(token, s3Id, 'SYN:UNKNOWN'),
          throwsA(
            isA<LocalApiException>()
                .having((e) => e.code, 'safe code', 'INSTRUMENT_NOT_FOUND')
                .having((e) => e.status, 'status', 404),
          ),
        );
        expect(
          (await api.watchlist(
            token,
            s3Id,
          )).value.items.single.instrument.instrumentId,
          'SYN:AAPL',
        );
      },
    );
  }
  test(
    'adding and removing supported items preserves other saved instruments',
    () async {
      api.saved['A']![s3Id] = s3Watchlist();
      final first = await api.putWatchlistItem(token, s3Id, 'SYN:AAPL');
      await api.putWatchlistItem(token, s3Id, 'SYN:BND');
      final replay = await api.putWatchlistItem(token, s3Id, 'SYN:AAPL');
      expect(replay.value.item.addedAt, first.value.item.addedAt);
      expect((await api.watchlist(token, s3Id)).value.items.length, 2);
      await api.removeWatchlistItem(token, s3Id, 'SYN:AAPL');
      expect(
        (await api.watchlist(
          token,
          s3Id,
        )).value.items.single.instrument.instrumentId,
        'SYN:BND',
      );
    },
  );
  for (final operation in ['detail', 'update', 'delete']) {
    test(
      'missing owned watchlist $operation is typed404 without other mutation',
      () async {
        api.saved['A']![s3Id] = s3Watchlist(name: 'Unchanged existing list');
        final pending = switch (operation) {
          'detail' => api.watchlist(token, s3OtherId),
          'update' => api.updateWatchlist(token, s3OtherId, 'Must not save'),
          _ => api.deleteWatchlist(token, s3OtherId),
        };
        await expectLater(
          pending,
          throwsA(
            isA<LocalApiException>()
                .having((e) => e.code, 'safe code', 'WATCHLIST_NOT_FOUND')
                .having((e) => e.status, 'status', 404),
          ),
        );
        expect(api.saved['A']!.keys, [s3Id]);
        expect(
          (await api.watchlist(token, s3Id)).value.summary.name,
          'Unchanged existing list',
        );
      },
    );
  }
  test(
    'repeat delete is typed404, never a second confirmed deletion',
    () async {
      api.saved['A']![s3Id] = s3Watchlist();
      await api.deleteWatchlist(token, s3Id);
      await expectLater(
        api.deleteWatchlist(token, s3Id),
        throwsA(
          isA<LocalApiException>()
              .having((e) => e.code, 'safe code', 'WATCHLIST_NOT_FOUND')
              .having((e) => e.status, 'status', 404),
        ),
      );
      expect(api.saved['A'], isEmpty);
    },
  );
}
