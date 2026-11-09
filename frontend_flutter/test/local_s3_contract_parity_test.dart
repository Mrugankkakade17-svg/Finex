// Current native capture replay, not a network/native-device execution.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';

import 'support/local_s3_corpus.dart';

Future<LocalS3Reply<Object?>> dispatch(
  HttpLocalApplicationApi api,
  Map<String, dynamic> entry,
  String bearer,
) {
  final target = entry['target'] as Map<String, dynamic>?;
  final request = entry['request'] as Map<String, dynamic>?;
  // Illegal captured error requests are intentionally absent; replay only the
  // original error response through a legal typed operation and captured target.
  return switch (entry['operation']) {
    'search' => api.marketSearch(
      bearer,
      query: target!['query'] as String,
      limit: target['limit'] as int,
    ),
    'quote' => api.marketQuote(bearer, target!['instrument_id'] as String),
    'watchlists' => api.watchlists(bearer),
    'watchlist_create' => api.createWatchlist(
      bearer,
      request?['name'] as String? ?? 'Synthetic error replay',
    ),
    'watchlist_update' => api.updateWatchlist(
      bearer,
      target!['watchlist_id'] as String,
      request!['name'] as String,
    ),
    'watchlist_detail' => api.watchlist(
      bearer,
      target!['watchlist_id'] as String,
    ),
    'watchlist_delete' => api.deleteWatchlist(
      bearer,
      target!['watchlist_id'] as String,
    ),
    'watchlist_item_put' => api.putWatchlistItem(
      bearer,
      target!['watchlist_id'] as String,
      target['instrument_id'] as String,
    ),
    'watchlist_item_delete' => api.removeWatchlistItem(
      bearer,
      target!['watchlist_id'] as String,
      target['instrument_id'] as String,
    ),
    'account' => api.paperAccount(bearer),
    'account_open' => api.openPaperAccount(bearer),
    'ledger' => api.paperLedger(
      bearer,
      after: target!['after_sequence'] as int,
      limit: target['limit'] as int,
    ),
    _ => throw const FormatException('Unsupported safe S3 replay operation.'),
  };
}

bool requestMatches(
  http.Request request,
  Map<String, dynamic> entry,
  String token,
) {
  try {
    if (request.headers['authorization'] != 'Bearer $token') return false;
    final operation = entry['operation'];
    final target = entry['target'] as Map<String, dynamic>?;
    final input = entry['request'] as Map<String, dynamic>?;
    final expectedMethod = switch (operation) {
      'watchlist_create' || 'account_open' => 'POST',
      'watchlist_update' || 'watchlist_item_put' => 'PUT',
      'watchlist_delete' || 'watchlist_item_delete' => 'DELETE',
      _ => 'GET',
    };
    final path = switch (operation) {
      'search' => '/api/v1/local-market/instruments',
      'quote' =>
        '/api/v1/local-market/quotes/${Uri.encodeComponent(target!['instrument_id'] as String)}',
      'watchlists' || 'watchlist_create' => '/api/v1/local-watchlists',
      'watchlist_detail' || 'watchlist_update' || 'watchlist_delete' =>
        '/api/v1/local-watchlists/${target!['watchlist_id']}',
      'watchlist_item_put' || 'watchlist_item_delete' =>
        '/api/v1/local-watchlists/${target!['watchlist_id']}/items/${Uri.encodeComponent(target['instrument_id'] as String)}',
      'account' => '/api/v1/local-paper/account',
      'account_open' => '/api/v1/local-paper/account/open',
      'ledger' => '/api/v1/local-paper/account/ledger',
      _ => '',
    };
    if (request.method != expectedMethod ||
        request.url.path != path ||
        request.followRedirects) {
      return false;
    }
    final query = request.url.queryParameters;
    if (operation == 'search' &&
        (query.length != 2 ||
            query['query'] != target!['query'] ||
            query['limit'] != '${target['limit']}')) {
      return false;
    }
    if (operation == 'ledger' &&
        (query.length != 2 ||
            query['limit'] != '${target!['limit']}' ||
            query['after_sequence'] != '${target['after_sequence']}')) {
      return false;
    }
    if (operation != 'search' && operation != 'ledger' && query.isNotEmpty) {
      return false;
    }
    if (operation == 'watchlist_create' || operation == 'watchlist_update') {
      final body = jsonDecode(request.body);
      final name = input?['name'] as String? ?? 'Synthetic error replay';
      return body is Map &&
          body.length == 1 &&
          body['name'] == localS3Name(name);
    }
    if (operation == 'account_open') {
      final body = jsonDecode(request.body);
      return body is Map &&
          body.length == 2 &&
          body['foundation_version'] == localFoundationVersion &&
          body['currency'] == 'USD';
    }
    return request.body.isEmpty;
  } catch (_) {
    return false;
  }
}

void main() {
  final corpus = loadLocalS3Corpus(Platform.environment);
  if (corpus == null) {
    test(
      'current native S3 parity requires an explicit capture/report pair',
      () {},
      skip: 'No optional current-native S3 capture supplied; no fallback fixture.',
    );
    return;
  }
  final random = Random.secure();
  final token = base64Url
      .encode(List.generate(32, (_) => random.nextInt(256)))
      .replaceAll('=', '');
  for (final entry in corpus.cases) {
    test('native original S3 wire ${entry['id']}', () async {
      var calls = 0;
      final api = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:8080'),
        client: MockClient((request) async {
          calls++;
          expect(
            requestMatches(request, entry, token),
            isTrue,
            reason: 'Safe canonical typed dispatch must match operation/target. Padded native names are normalized; error request replay is response-only.',
          );
          return http.Response.bytes(
            utf8.encode(entry['body_utf8'] as String),
            entry['status'] as int,
            headers: {'content-type': entry['content_type'] as String},
          );
        }),
      );
      try {
        final expected = entry['expected'] as Map<String, dynamic>;
        if (expected['outcome'] == 'error') {
          await expectLater(
            dispatch(api, entry, token),
            throwsA(
              isA<LocalApiException>()
                  .having((e) => e.code, 'safe code', expected['error_code'])
                  .having((e) => e.status, 'status', entry['status']),
            ),
          );
        } else {
          final reply = await dispatch(api, entry, token);
          final envelope =
              jsonDecode(entry['body_utf8'] as String) as Map<String, dynamic>;
          final meta = envelope['meta'] as Map<String, dynamic>;
          expect(
            reply.dataStatus == meta['dataStatus'] &&
                reply.dataAsOf ==
                    (meta['dataAsOf'] == null
                        ? null
                        : localUtcTimestamp(meta['dataAsOf'])),
            isTrue,
          );
          expect(reply.value, isNotNull);
        }
        expect(calls, 1);
      } finally {
        api.close();
      }
    });
  }
}
