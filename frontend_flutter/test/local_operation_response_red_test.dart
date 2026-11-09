import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/local_application_fake.dart';

String envelope(Map<String, dynamic> data) => jsonEncode({
  'success': true,
  'message': 'ignored',
  'data': data,
  'meta': {
    'apiVersion': 'v1',
    'dataStatus': 'CACHED',
    'dataAsOf': null,
    'correlationId': 'synthetic-test',
  },
});
void main() {
  final invalid = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'code',
      'INVALID_API_RESPONSE',
    ),
  );
  HttpLocalApplicationApi returns(Map<String, dynamic> data) {
    final api = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8000'),
      client: MockClient((_) async => http.Response(envelope(data), 200)),
    );
    addTearDown(api.close);
    return api;
  }

  test(
    'saveDraft cannot confirm a well-formed but unchanged initial DTO',
    () async {
      await expectLater(
        returns(localStateJson())
            .saveDraft('test-only', displayName: 'Synthetic A'),
        invalid,
      );
    },
  );
  test(
    'saveDraft must confirm the exact normalized full replacement',
    () async {
      await expectLater(
        returns(localStateJson(label: 'Other learner', level: 'advanced'))
            .saveDraft(
              'test-only',
              displayName: 'Synthetic A',
              experienceLevel: 'beginner',
            ),
        invalid,
      );
    },
  );
  test('consent cannot confirm success without a recorded decision', () async {
    await expectLater(
      returns(localStateJson()).consent('test-only', true),
      invalid,
    );
  });
  test(
    'consent response must confirm requested acceptance rather than withdrawal',
    () async {
      await expectLater(
        returns(localStateJson(accepted: false)).consent('test-only', true),
        invalid,
      );
    },
  );
  test(
    'complete cannot return incomplete state as a successful operation',
    () async {
      await expectLater(
        returns(localStateJson()).complete('test-only'),
        invalid,
      );
    },
  );
}
