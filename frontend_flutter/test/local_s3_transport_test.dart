import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';

// Import only the public evidence matcher; this library's main is not invoked
// and no native artifact is loaded by these synthetic guard-unit tests.
import 'local_s3_contract_parity_test.dart' as native_parity;
import 'support/local_s3_data.dart';

void main() {
  late HttpLocalApplicationApi api;
  late Map<String, dynamic> response;
  late int status;
  final requests = <http.Request>[];
  setUp(() {
    status = 200;
    requests.clear();
    response = s3Success(s3Search(), time: s3FixtureTime);
    api = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8080'),
      client: MockClient((request) async {
        requests.add(request);
        return http.Response.bytes(
          utf8.encode(jsonEncode(response)),
          status,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
  });
  tearDown(() => api.close());
  final token = List.filled(43, 'T').join();
  const matcherOperations = [
    'quote',
    'watchlist_item_put',
    'watchlist_item_delete',
  ];
  Map<String, dynamic> matcherEntry(String operation) => {
    'operation': operation,
    'target': {
      if (operation != 'quote') 'watchlist_id': s3Id,
      'instrument_id': 'SYN:AAPL',
    },
    'request': null,
  };
  Future<Object?> sendMatcherRequest(String operation) {
    if (operation == 'quote') {
      response = s3Success(s3Quote(), time: s3FixtureTime);
      return api.marketQuote(token, 'SYN:AAPL');
    }
    if (operation == 'watchlist_item_put') {
      response = s3Success({
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_item_version': 'watchlist_item.v1',
        'watchlist_id': s3Id,
        'item': s3Item(),
      }, time: s3Time);
      return api.putWatchlistItem(token, s3Id, 'SYN:AAPL');
    }
    if (operation == 'watchlist_item_delete') {
      response = s3Success({
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_item_version': 'watchlist_item.v1',
        'watchlist_id': s3Id,
        'instrument_id': 'SYN:AAPL',
        'removed': true,
      }, time: s3Time);
      return api.removeWatchlistItem(token, s3Id, 'SYN:AAPL');
    }
    throw StateError('Synthetic matcher test setup has an unknown operation.');
  }

  for (final operation in matcherOperations) {
    test(
      'native request matcher accepts canonical encoded $operation',
      () async {
        final value = await sendMatcherRequest(operation);
        expect(value, isNotNull);
        expect(requests.length, 1);
        final request = requests.single;
        final expectedPath = operation == 'quote'
            ? '/api/v1/local-market/quotes/SYN%3AAAPL'
            : '/api/v1/local-watchlists/$s3Id/items/SYN%3AAAPL';
        // Uri.path preserves escapes; only pathSegments decode the colon. The
        // production request uses the canonical percent-encoded wire spelling.
        expect(request.url.path == expectedPath, isTrue);
        expect(request.url.pathSegments.last == 'SYN:AAPL', isTrue);
        expect(
          native_parity.requestMatches(request, matcherEntry(operation), token),
          isTrue,
        );
      },
    );
    for (final variant in [
      'wrong instrument',
      if (operation != 'quote') 'wrong owned parent',
      'wrong method',
      'missing authorization',
      'wrong authorization',
      'unexpected query',
      'redirect enabled',
      'unencoded instrument',
      'double-encoded instrument',
    ]) {
      test('native request matcher rejects $variant for $operation', () async {
        await sendMatcherRequest(operation);
        final original = requests.single;
        final entry = matcherEntry(operation);
        // Pair every invalid control with an accepted actual typed request, so
        // a matcher that rejects everything cannot satisfy these guard tests.
        expect(native_parity.requestMatches(original, entry, token), isTrue);
        final canonical = original.url.path;
        final changedPath = switch (variant) {
          'wrong instrument' => canonical.replaceFirst(
            'SYN%3AAAPL',
            'SYN%3AMSFT',
          ),
          'wrong owned parent' => canonical.replaceFirst(s3Id, s3OtherId),
          'unencoded instrument' => canonical.replaceFirst(
            'SYN%3AAAPL',
            'SYN:AAPL',
          ),
          'double-encoded instrument' => canonical.replaceFirst(
            'SYN%3AAAPL',
            'SYN%253AAAPL',
          ),
          _ => canonical,
        };
        var url = Uri.parse('http://127.0.0.1:8080$changedPath');
        if (variant == 'unexpected query') {
          url = url.replace(query: 'unexpected=1');
        }
        final modified =
            http.Request(
                variant == 'wrong method' ? 'POST' : original.method,
                url,
              )
              ..headers.addAll(original.headers)
              ..body = original.body
              ..followRedirects = variant == 'redirect enabled';
        if (variant == 'missing authorization') {
          modified.headers.remove('authorization');
        }
        if (variant == 'wrong authorization') {
          modified.headers['authorization'] = 'Bearer synthetic-wrong-marker';
        }
        // Only the boolean result is exposed, never headers/body/bearer data.
        expect(native_parity.requestMatches(modified, entry, token), isFalse);
      });
    }
  }
  test(
    'search requests the normalized query and preserves fixture metadata',
    () async {
      response = s3Success(s3Search(query: 'Synthetic'), time: s3FixtureTime);
      final result = await api.marketSearch(token, query: ' Synthetic ');
      expect(result.value.query, 'Synthetic');
      expect(
        requests.single.url.queryParameters['query'] == 'Synthetic' &&
            requests.single.url.queryParameters['limit'] == '20',
        isTrue,
      );
    },
  );
  test(
    'quote reads the exact requested instrument and nullable source state',
    () async {
      response = s3Success(s3Quote(), time: s3FixtureTime);
      expect(
        (await api.marketQuote(token, 'SYN:AAPL')).value.unitPrice,
        '200.0000',
      );
    },
  );
  test(
    'watchlist create POST is explicit, normalized and exactly201',
    () async {
      status = 201;
      response = s3Success(s3Watchlist(), time: s3Time);
      expect(
        (await api.createWatchlist(token, ' Synthetic list ')).value.summary.id,
        s3Id,
      );
      expect(
        requests.single.method == 'POST' &&
            requests.single.body == '{"name":"Synthetic list"}',
        isTrue,
      );
    },
  );
  test('read of unopened account never dispatches opening', () async {
    response = s3Success(s3Account(opened: false));
    expect((await api.paperAccount(token)).value.account, isNull);
    expect(
      requests.single.method == 'GET' &&
          requests.single.url.path == '/api/v1/local-paper/account',
      isTrue,
    );
  });
  test(
    'explicit open sends versions only and confirms immutable original',
    () async {
      response = s3Success(s3Account(), time: s3Time);
      expect(
        (await api.openPaperAccount(token)).value.account!.openingCash,
        '10000.00',
      );
      expect(
        requests.single.body ==
            '{"foundation_version":"market_foundation.v1","currency":"USD"}',
        isTrue,
      );
    },
  );
  test('ledger explicit limit2 request uses integer page cursor', () async {
    response = s3Success(s3Ledger(limit: 2), time: s3Time);
    expect(
      (await api.paperLedger(token, limit: 2)).value.items.single.sequence,
      1,
    );
    expect(
      requests.single.url.queryParameters['after_sequence'] == '0',
      isTrue,
    );
  });
  test('public ledger default is the exact contract limit100', () async {
    response = s3Success(s3Ledger(), time: s3Time);
    final reply = await api.paperLedger(token);
    expect(reply.value.limit, 100);
    expect(requests.single.url.queryParameters['limit'] == '100', isTrue);
  });
  for (final error in {
    'LOCAL_STORE_UNAVAILABLE': 503,
    'ONBOARDING_REQUIRED': 409,
    'LOCAL_APPLICATION_ONLY': 403,
    'VALIDATION_ERROR': 422,
  }.entries) {
    test(
      'known ${error.key} is mapped from actual five-field envelope',
      () async {
        response = s3Error(error.key);
        status = error.value;
        await expectLater(
          api.watchlists(token),
          throwsA(
            isA<LocalApiException>().having(
              (e) => e.code,
              'safe code',
              error.key,
            ),
          ),
        );
      },
    );
  }
  test(
    'non401 contradictory session code is invalid and never authority',
    () async {
      response = s3Error('SESSION_INVALID');
      status = 503;
      await expectLater(
        api.watchlists(token),
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'safe code',
            'INVALID_API_RESPONSE',
          ),
        ),
      );
    },
  );
  test('unknown operation code is rejected instead of reflected', () async {
    response = s3Error('WATCHLIST_LIMIT');
    status = 409;
    await expectLater(
      api.paperAccount(token),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'safe code',
          'INVALID_API_RESPONSE',
        ),
      ),
    );
  });
  test('rename maps catalogue failure for stored supported items', () async {
    response = s3Error('LOCAL_CATALOG_UNAVAILABLE');
    status = 503;
    await expectLater(
      api.updateWatchlist(token, s3Id, 'Synthetic rename'),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'safe code',
          'LOCAL_CATALOG_UNAVAILABLE',
        ),
      ),
    );
  });
}
