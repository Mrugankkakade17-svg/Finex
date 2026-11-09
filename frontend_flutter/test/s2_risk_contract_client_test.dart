import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:frontend_flutter/features/risk/services/s2_risk_contract_client.dart';

Map<String, dynamic> pack() =>
    jsonDecode(File('assets/s2_risk_fixtures.v1.json').readAsStringSync())
        as Map<String, dynamic>;
FixtureS2RiskClient fixtureClient() =>
    FixtureS2RiskClient(loader: () async => jsonEncode(pack()));

void main() {
  final cases = pack()['cases'] as List;
  for (final entry in cases) {
    final row = entry as Map<String, dynamic>;
    test('fixture preserves domain vector ${row['case_id']}', () async {
      final client = fixtureClient();
      if (row.containsKey('error_code')) {
        await expectLater(
          client.submit(row['request'] as Map<String, dynamic>),
          throwsA(
            isA<S2RiskException>().having(
              (e) => e.code,
              'code',
              row['error_code'],
            ),
          ),
        );
      } else {
        final result = await client.submit(
          row['request'] as Map<String, dynamic>,
        );
        expect(result.toJson(), row['response']);
        final copy = result.toJson();
        (copy['assessment'] as Map)['composite_score'] = 999;
        expect(
          (await client.submit(row['request'] as Map<String, dynamic>))
              .composite,
          isNot(999),
        );
      }
    });
  }

  test('questionnaire contains approved logical IDs/options and key order is irrelevant', () async {
    final client = fixtureClient();
    final questions = await client.loadQuestionnaire();
    expect(questions.questions.length, 10);
    expect(questions.questions.first.options.length, 5);
    expect(client.profiles.length, 9);
    final request = Map<String, dynamic>.from(
      (cases[3] as Map)['request'] as Map,
    );
    request['answers'] = (request['answers'] as List).reversed
        .map(
          (item) => {
            'answer_code': item['answer_code'],
            'question_id': item['question_id'],
          },
        )
        .toList();
    expect((await client.submit(request)).composite, 50);
  });

  test(
    'fixture rejects unknown vectors instead of computing a new score',
    () async {
      final request = jsonDecode(
        jsonEncode((cases[3] as Map)['request']),
      ) as Map<String, dynamic>;
      (request['answers'] as List).first['answer_code'] = 'W1_D';
      await expectLater(
        fixtureClient().submit(request),
        throwsA(
          isA<S2RiskException>().having(
            (e) => e.code,
            'code',
            'FIXTURE_VECTOR_UNAVAILABLE',
          ),
        ),
      );
    },
  );

  test(
    'HTTP uses the approved path/input/header and safe error message',
    () async {
      final request = (cases[3] as Map)['request'] as Map<String, dynamic>;
      final transport = MockClient((incoming) async {
        expect(incoming.url.path, '/api/v1/risk-contract/assessments');
        expect(jsonDecode(incoming.body), request);
        expect(incoming.headers['X-Correlation-ID'], 'flutter-s2-proof');
        return http.Response(
          jsonEncode({
            'success': false,
            'error': {
              'code': 'MISSING_REQUIRED_QUESTION',
              'message': 'private-data',
            },
          }),
          400,
        );
      });
      final client = HttpS2RiskClient(
        Uri.parse('http://127.0.0.1:8000'),
        client: transport,
      );
      await expectLater(
        client.submit(request, correlationId: 'flutter-s2-proof'),
        throwsA(
          isA<S2RiskException>()
              .having((e) => e.code, 'code', 'MISSING_REQUIRED_QUESTION')
              .having(
                (e) => e.message,
                'safe message',
                isNot(contains('private-data')),
              ),
        ),
      );
      client.close();
    },
  );

  test('HTTP rejects non-loopback targets and times out safely', () async {
    expect(
      () => HttpS2RiskClient(Uri.parse('https://example.com')),
      throwsA(isA<S2RiskException>()),
    );
    final gate = Completer<http.Response>();
    final client = HttpS2RiskClient(
      Uri.parse('http://localhost:8000'),
      client: MockClient((_) => gate.future),
      timeout: const Duration(milliseconds: 1),
    );
    await expectLater(
      client.loadQuestionnaire(),
      throwsA(
        isA<S2RiskException>().having(
          (e) => e.code,
          'code',
          'RISK_ASSESSMENT_UNAVAILABLE',
        ),
      ),
    );
    gate.complete(http.Response('{}', 500));
    client.close();
  });

  test(
    'response metadata fails closed instead of rendering incompatible data',
    () async {
      for (final field in ['version', 'score', 'tension']) {
        final response = jsonDecode(
          jsonEncode((cases[3] as Map)['response']),
        ) as Map<String, dynamic>;
        final assessment = response['assessment'] as Map;
        if (field == 'version') assessment['questionnaire_version'] = 'v99';
        if (field == 'score') assessment['composite_score'] = 101;
        if (field == 'tension') {
          assessment['informational_tension'] = {
            'code': 'CAPACITY_BELOW_WILLINGNESS',
            'message': {},
          };
        }
        final client = HttpS2RiskClient(
          Uri.parse('http://localhost:8000'),
          client: MockClient(
            (_) async => http.Response(
              jsonEncode({'success': true, 'data': response}),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            ),
          ),
        );
        await expectLater(
          client.submit((cases[3] as Map)['request'] as Map<String, dynamic>),
          throwsA(
            isA<S2RiskException>().having(
              (e) => e.code,
              'code',
              'INVALID_RESPONSE',
            ),
          ),
        );
        client.close();
      }
    },
  );

  test(
    'HTTP handles a real JSON success envelope and UTF-8 questionnaire text',
    () async {
      final client = HttpS2RiskClient(
        Uri.parse('http://localhost:8000'),
        client: MockClient(
          (request) async => http.Response(
            jsonEncode({
              'success': true,
              'data': request.method == 'GET'
                  ? pack()['questionnaire']
                  : (cases[3] as Map)['response'],
            }),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          ),
        ),
      );
      expect((await client.loadQuestionnaire()).questions.length, 10);
      expect(
        (await client.submit(
          (cases[3] as Map)['request'] as Map<String, dynamic>,
        )).composite,
        50,
      );
      client.close();
    },
  );
}
