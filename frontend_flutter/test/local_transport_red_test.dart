import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'non401 SESSION_INVALID cannot masquerade as confirmed session revocation',
    () async {
      final api = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:8000'),
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'success': false,
              'error_code': 'SESSION_INVALID',
              'message': 'untrusted-secret-body',
            }),
            503,
          ),
        ),
      );
      addTearDown(api.close);
      await expectLater(
        api.logout('test-only'),
        throwsA(
          isA<LocalApiException>()
              .having(
                (error) => error.code,
                'safe incompatible code',
                'REQUEST_FAILED',
              )
              .having((error) => error.status, 'real status', 503),
        ),
      );
    },
  );

  test(
    '401 status expires a session without waiting for an unreadable body',
    () async {
      final stalled = StreamController<List<int>>();
      final api = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:8000'),
        timeout: const Duration(milliseconds: 30),
        client: MockClient.streaming(
          (_, _) async => http.StreamedResponse(stalled.stream, 401),
        ),
      );
      addTearDown(() {
        api.close();
        unawaited(stalled.close());
      });
      await expectLater(
        api.state('test-only'),
        throwsA(
          isA<LocalApiException>()
              .having(
                (error) => error.code,
                'status before body',
                'SESSION_INVALID',
              )
              .having((error) => error.status, 'real status', 401),
        ),
      );
    },
  );

  test('loopback with port zero is not a valid API origin', () {
    expect(
      () => HttpLocalApplicationApi.validateOrigin(
        Uri.parse('http://localhost:0'),
      ),
      throwsA(
        isA<LocalApiException>().having(
          (error) => error.code,
          'code',
          'INVALID_API_ORIGIN',
        ),
      ),
    );
  });
}
