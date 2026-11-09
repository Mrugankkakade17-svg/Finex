import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/local_s2_data.dart';

void main() {
  HttpLocalApplicationApi api(
    Future<http.Response> Function(http.Request) handler,
  ) {
    final value = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8082'),
      client: MockClient((request) async {
        final response = await handler(request);
        return http.Response.bytes(
          response.bodyBytes,
          response.statusCode,
          headers: {...response.headers, 'content-type': 'application/json'},
        );
      }),
    );
    addTearDown(value.close);
    return value;
  }

  final invalid = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'safe code',
      'INVALID_API_RESPONSE',
    ),
  );
  test(
    'risk draft confirms exact replacement and persisted source time',
    () async {
      final raw = riskDraftData(partial: true);
      final value = api((r) async {
        expect(r.method, 'PUT');
        expect(r.url.path, '/api/v1/local-risk/draft');
        expect(jsonDecode(r.body), riskInput(partial: true));
        expect(r.followRedirects, isFalse);
        expect(r.url.query, isEmpty);
        return http.Response(s2Envelope(raw, asOf: s2Time), 200);
      });
      final result = await value.saveRiskDraft(
        'shape-only',
        LocalRiskInput.fromJson(riskInput(partial: true)),
      );
      expect(result.value.input.answers.length, 1);
      expect(result.dataAsOf, DateTime.utc(2030));
    },
  );
  test(
    'history explicitly requests bounded limit2 and exact string cursor',
    () async {
      final value = api((r) async {
        expect(r.url.path, '/api/v1/local-risk/assessments');
        expect(r.url.queryParameters, {
          'limit': '2',
          'before': '9223372036854775807',
        });
        return http.Response(
          s2Envelope(s2Scoped({'items': <Object?>[], 'next_cursor': null})),
          200,
        );
      });
      expect(
        (await value.riskHistory(
          'shape-only',
          before: '9223372036854775807',
        )).value.items,
        isEmpty,
      );
    },
  );
  test(
    'equivalent assessment replay permits original immutable answer order',
    () async {
      final input = riskInput();
      (input['answers'] as List).insert(
        0,
        (input['answers'] as List).removeLast(),
      );
      final value = api(
        (r) async => http.Response.bytes(
          utf8.encode(s2Envelope(savedRiskData(), asOf: s2Time)),
          200,
          headers: {'content-type': 'application/json'},
        ),
      );
      final reply = await value.assessRisk(
        'shape-only',
        LocalRiskInput.fromJson(input, complete: true),
        newLocalRetryKey(),
      );
      expect(reply.value.input.answers.first.questionId, 'W1');
    },
  );
  test(
    'portfolio create uses201 and normalized complete confirmation',
    () async {
      final value = api((r) async {
        expect(r.method, 'POST');
        expect(r.url.path, '/api/v1/local-portfolios');
        expect(jsonDecode(r.body), {
          'portfolio_version': 'portfolio.v1',
          'name': 'Synthetic portfolio',
          'description': null,
          'currency': 'USD',
        });
        return http.Response(s2Envelope(portfolioData(), asOf: s2Time), 201);
      });
      expect(
        (await value.createPortfolio(
          'shape-only',
          PortfolioInput(name: ' Synthetic portfolio '),
        )).value.name,
        'Synthetic portfolio',
      );
    },
  );
  test(
    'holding create exact canonical units and owned parent confirmation',
    () async {
      final value = api((r) async {
        expect(jsonDecode(r.body), {
          'holding_version': 'holding.v1',
          'instrument_id': 'SYN:AAPL',
          'quantity': '10.000000',
          'average_cost': '150.0000',
          'currency': 'USD',
        });
        return http.Response(s2Envelope(holdingData(), asOf: s2Time), 201);
      });
      expect(
        (await value.createHolding(
          'shape-only',
          portfolioA,
          HoldingInput(
            instrumentId: 'SYN:AAPL',
            quantity: '10.0',
            averageCost: '150',
          ),
        )).value.quantity,
        '10.000000',
      );
    },
  );
  test('DELETE accepts only exact owned resource acknowledgement', () async {
    final value = api((r) async {
      expect(r.method, 'DELETE');
      expect(r.body, isEmpty);
      return http.Response(
        s2Envelope(
          s2Scoped({
            'portfolio_version': 'portfolio.v1',
            'portfolio_id': portfolioA,
            'entity_type': 'portfolio',
            'deleted': true,
          }),
        ),
        200,
      );
    });
    expect(
      (await value.deletePortfolio('shape-only', portfolioA)).value,
      isTrue,
    );
  });
  test(
    'unavailable metrics retain UNAVAILABLE/null metadata and null outputs',
    () async {
      final value = api(
        (_) async => http.Response(
          s2Envelope(metricsData(unavailable: true), status: 'UNAVAILABLE'),
          200,
        ),
      );
      final reply = await value.metrics('shape-only', portfolioA);
      expect(reply.dataStatus, 'UNAVAILABLE');
      expect(reply.dataAsOf, isNull);
      expect(reply.value.totals.marketValue, isNull);
    },
  );
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'omitted detail': (v) => v.remove('detail'),
    'different legacy detail': (v) => v['detail'] = 'raw-diagnostic',
    'different nested message': (v) =>
        (v['error'] as Map)['message'] = 'raw-diagnostic',
    'different nested code': (v) => (v['error'] as Map)['code'] = 'UNKNOWN',
    'extra field': (v) => v['database_path'] = 'untrusted',
    'bad correlation': (v) =>
        (v['error'] as Map)['correlationId'] = 'invalid trace with spaces',
  }.entries) {
    test('reject malformed real five-key error: ${mutation.key}', () async {
      final raw = jsonDecode(
        s2Error('LOCAL_STORE_UNAVAILABLE'),
      ) as Map<String, dynamic>;
      mutation.value(raw);
      await expectLater(
        api((_) async => http.Response(jsonEncode(raw), 503))
            .portfolios('shape-only'),
        invalid,
      );
    });
  }
  test(
    'known API codes use local safe copy, never server diagnostics',
    () async {
      final value = api(
        (_) async => http.Response(
          s2Error('HOLDING_ALREADY_EXISTS', message: 'untrusted bearer-secret'),
          409,
        ),
      );
      try {
        await value.createHolding(
          'shape-only',
          portfolioA,
          HoldingInput(
            instrumentId: 'SYN:AAPL',
            quantity: '1',
            averageCost: '0',
          ),
        );
        fail('Expected safe API error');
      } on LocalApiException catch (e) {
        expect(e.code, 'HOLDING_ALREADY_EXISTS');
        expect(e.message.contains('bearer-secret'), isFalse);
        expect(e.toString().contains('bearer-secret'), isFalse);
      }
    },
  );
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'wrong status': (v) => (v['meta'] as Map)['dataStatus'] = 'LIVE',
    'wrong asof': (v) =>
        (v['meta'] as Map)['dataAsOf'] = '2030-01-02T00:00:00Z',
    'missing nullable asof': (v) => (v['meta'] as Map).remove('dataAsOf'),
    'wrong version': (v) => (v['meta'] as Map)['apiVersion'] = 'v2',
    'malformed correlation': (v) => (v['meta'] as Map)['correlationId'] = 'x y',
  }.entries) {
    test('operation metadata rejects ${mutation.key}', () async {
      final raw = jsonDecode(
        s2Envelope(portfolioData(), asOf: s2Time),
      ) as Map<String, dynamic>;
      mutation.value(raw);
      await expectLater(
        api((_) async => http.Response(jsonEncode(raw), 200))
            .portfolio('shape-only', portfolioA),
        invalid,
      );
    });
  }
  test(
    'malformed resource ID fails before any credential-bearing request',
    () async {
      var calls = 0;
      final value = api((_) async {
        calls++;
        return http.Response('', 500);
      });
      await expectLater(value.portfolio('shape-only', '../../auth'), invalid);
      expect(calls, 0);
    },
  );
  test('bounded body timeout remains authoritative for S2', () async {
    final stream = StreamController<List<int>>();
    final value = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8082'),
      timeout: const Duration(milliseconds: 30),
      client: MockClient.streaming(
        (_, _) async => http.StreamedResponse(stream.stream, 200),
      ),
    );
    addTearDown(() {
      value.close();
      unawaited(stream.close());
    });
    await expectLater(
      value.portfolios('shape-only'),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'safe code',
          'REQUEST_TIMEOUT',
        ),
      ),
    );
  });
  for (final code in [
    'UNKNOWN_CODE',
    'IDEMPOTENCY_CONFLICT',
    'HOLDING_ALREADY_EXISTS',
    'LOCAL_QUOTE_UNAVAILABLE',
  ]) {
    test('catalogue rejects unknown or wrong-operation error $code', () async {
      final status = code == 'UNKNOWN_CODE'
          ? 503
          : code == 'LOCAL_QUOTE_UNAVAILABLE'
          ? 503
          : 409;
      await expectLater(
        api((_) async => http.Response(s2Error(code), status))
            .instruments('shape-only'),
        invalid,
      );
    });
  }
  test('risk GET rejects portfolio mutation error', () async {
    await expectLater(
      api((_) async => http.Response(s2Error('HOLDING_ALREADY_EXISTS'), 409))
          .riskDraft('shape-only'),
      invalid,
    );
  });
  test(
    'partial draft rejects MISSING_REQUIRED_QUESTION from its operation',
    () async {
      await expectLater(
        api(
          (_) async => http.Response(s2Error('MISSING_REQUIRED_QUESTION'), 400),
        ).saveRiskDraft('shape-only', LocalRiskInput([])),
        invalid,
      );
    },
  );
  test(
    'complete assessment accepts its MISSING_REQUIRED_QUESTION error',
    () async {
      await expectLater(
        api(
          (_) async => http.Response(s2Error('MISSING_REQUIRED_QUESTION'), 400),
        ).assessRisk(
          'shape-only',
          LocalRiskInput.fromJson(riskInput(), complete: true),
          newLocalRetryKey(),
        ),
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'safe code',
            'MISSING_REQUIRED_QUESTION',
          ),
        ),
      );
    },
  );
}
