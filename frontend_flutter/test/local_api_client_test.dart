import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'local_operation_response_red_test.dart' show envelope;
import 'support/local_application_fake.dart';

void main() {
  HttpLocalApplicationApi mock(
    Future<http.Response> Function(http.Request) handler, {
    Duration timeout = const Duration(seconds: 8),
  }) {
    final api = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8000'),
      client: MockClient(handler),
      timeout: timeout,
    );
    addTearDown(api.close);
    return api;
  }

  Map<String, dynamic> localData(Map<String, dynamic> data) => {
    'scope': localApplicationScope,
    'contract_version': localContractVersion,
    ...data,
  };
  final invalid = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'code',
      'INVALID_API_RESPONSE',
    ),
  );
  test(
    'login sends exact synthetic alias and no bearer, does not redirect',
    () async {
      final api = mock((request) async {
        expect(request.method, 'POST');
        expect(request.url.path, '/api/v1/local-auth/mock-login');
        expect(jsonDecode(request.body), {'alias': 'learner-a'});
        expect(request.headers['Authorization'], isNull);
        expect(request.followRedirects, isFalse);
        expect(
          request.headers['X-Correlation-ID'],
          startsWith('flutter-local-'),
        );
        return http.Response(
          envelope(
            localData({
              'access_token': testBearer('learner-a'),
              'token_type': 'Bearer',
              'expires_at': localTestTime.toIso8601String(),
              'user': {'id': 'synthetic-a', 'alias': 'learner-a'},
            }),
          ),
          200,
        );
      });
      expect((await api.login('learner-a')).user.alias, 'learner-a');
    },
  );
  test('unknown alias never reaches transport', () async {
    var calls = 0;
    final api = mock((_) async {
      calls++;
      return http.Response('', 500);
    });
    await expectLater(
      api.login('real-name'),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'code',
          'UNKNOWN_LOCAL_ALIAS',
        ),
      ),
    );
    expect(calls, 0);
  });
  test('me sends bearer in header only and verifies owned shape', () async {
    final api = mock((request) async {
      expect(request.url.path, '/api/v1/local-auth/me');
      expect(request.url.query, isEmpty);
      expect(request.body, isEmpty);
      expect(request.headers['Authorization'], 'Bearer test-only');
      return http.Response(
        envelope(
          localData({
            'user': {'id': 'synthetic-a', 'alias': 'learner-a'},
          }),
        ),
        200,
      );
    });
    expect((await api.me('test-only')).alias, 'learner-a');
  });
  test(
    'GET state accepts initial nullable draft without mutation postconditions',
    () async {
      final api = mock((request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/api/v1/local-onboarding/state');
        return http.Response(envelope(localStateJson()), 200);
      });
      expect((await api.state('test-only')).completed, isFalse);
    },
  );
  test(
    'draft is exact full replacement with trimmed label and nullable level',
    () async {
      final api = mock((request) async {
        expect(request.method, 'PUT');
        expect(request.url.path, '/api/v1/local-onboarding/draft');
        expect(jsonDecode(request.body), {
          'profile_schema_version': 'profile.v1',
          'display_name': 'Synthetic A',
          'experience_level': null,
        });
        return http.Response(
          envelope(localStateJson(label: 'Synthetic A')),
          200,
        );
      });
      expect(
        (await api.saveDraft(
          'test-only',
          displayName: ' Synthetic A ',
        )).displayName,
        'Synthetic A',
      );
    },
  );
  test('blank draft replaces both fields with null and requires confirmed timestamp', () async {
    final raw = localStateJson();
    (raw['draft'] as Map)['updated_at'] = localTestTime.toIso8601String();
    final api = mock((request) async {
      expect(jsonDecode(request.body), {
        'profile_schema_version': 'profile.v1',
        'display_name': null,
        'experience_level': null,
      });
      return http.Response(envelope(raw), 200);
    });
    expect(
      (await api.saveDraft('test-only', displayName: ' ')).draftUpdatedAt,
      isNotNull,
    );
  });
  for (final accepted in [true, false]) {
    test('consent sends exact version and $accepted decision', () async {
      final api = mock((request) async {
        expect(request.url.path, '/api/v1/local-onboarding/consent');
        expect(jsonDecode(request.body), {
          'consent_version': 'consent.v1',
          'consent_given': accepted,
        });
        return http.Response(envelope(localStateJson(accepted: accepted)), 200);
      });
      expect(
        (await api.consent('test-only', accepted)).consent!.accepted,
        accepted,
      );
    });
  }
  test(
    'complete sends versions only and accepts true server completion',
    () async {
      final api = mock((request) async {
        expect(request.url.path, '/api/v1/local-onboarding/complete');
        expect(jsonDecode(request.body), {
          'consent_version': 'consent.v1',
          'profile_schema_version': 'profile.v1',
        });
        return http.Response(
          envelope(
            localStateJson(
              label: 'Synthetic A',
              level: 'beginner',
              accepted: true,
              completed: true,
            ),
          ),
          200,
        );
      });
      expect((await api.complete('test-only')).completed, isTrue);
    },
  );
  test('logout requires explicit server confirmation', () async {
    await expectLater(
      mock(
        (_) async =>
            http.Response(envelope(localData({'signed_out': false})), 200),
      ).logout('test-only'),
      invalid,
    );
  });
  test(
    'confirmed logout sends empty object, not a token-bearing body',
    () async {
      final api = mock((request) async {
        expect(request.url.path, '/api/v1/local-auth/logout');
        expect(jsonDecode(request.body), isEmpty);
        return http.Response(envelope(localData({'signed_out': true})), 200);
      });
      await api.logout('test-only');
    },
  );
  test(
    'raw server diagnostics and unknown fields cannot become UI messages',
    () async {
      final api = mock(
        (_) async => http.Response(
          jsonEncode({
            'success': false,
            'message': 'untrusted bearer-secret',
            'error_code': 'UNTRUSTED_CODE',
            'error': {
              'message': 'untrusted bearer-secret',
              'fieldErrors': [
                {'field': 'untrusted-secret'},
              ],
            },
          }),
          500,
        ),
      );
      try {
        await api.state('test-only');
        fail('Expected safe error');
      } on LocalApiException catch (error) {
        expect(error.code, 'REQUEST_FAILED');
        expect(error.fields, isEmpty);
        expect(error.message, isNot(contains('secret')));
        expect(error.toString(), isNot(contains('secret')));
      }
    },
  );
  test(
    'structured known field failures are whitelisted without server text',
    () async {
      final api = mock(
        (_) async => http.Response(
          jsonEncode({
            'success': false,
            'error_code': 'VALIDATION_ERROR',
            'error': {
              'fieldErrors': [
                {'field': 'display_name'},
                {'field': 'experience_level'},
                {'field': 'secret'},
              ],
            },
          }),
          422,
        ),
      );
      await expectLater(
        api.state('test-only'),
        throwsA(
          isA<LocalApiException>().having((e) => e.fields, 'safe fields', {
            'display_name',
            'experience_level',
          }),
        ),
      );
    },
  );
  for (final badBody in ['<html>proxy error</html>', '{}', 'null', '[]']) {
    test('reject malformed response $badBody', () async {
      await expectLater(
        mock((_) async => http.Response(badBody, 200)).state('test-only'),
        invalid,
      );
    });
  }
  test('success envelope must include exact meta and local scope', () async {
    final raw = jsonDecode(envelope(localStateJson())) as Map<String, dynamic>;
    (raw['meta'] as Map)['dataStatus'] = 'LIVE';
    await expectLater(
      mock((_) async => http.Response(jsonEncode(raw), 200)).state('test-only'),
      invalid,
    );
  });
  test('redirect is never followed or promoted to success', () async {
    final api = mock((request) async {
      expect(request.followRedirects, isFalse);
      return http.Response(
        '',
        302,
        headers: {'location': 'https://untrusted.example'},
      );
    });
    await expectLater(api.state('test-only'), invalid);
  });
  test('network error has safe retryable message', () async {
    final api = mock(
      (_) async => throw http.ClientException('raw bearer-secret'),
    );
    await expectLater(
      api.state('test-only'),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'code',
          'API_UNAVAILABLE',
        ),
      ),
    );
  });
  test('timeout bounds complete response body, not only connection', () async {
    final body = StreamController<List<int>>();
    final api = HttpLocalApplicationApi(
      Uri.parse('http://127.0.0.1:8000'),
      timeout: const Duration(milliseconds: 20),
      client: MockClient.streaming(
        (_, _) async => http.StreamedResponse(body.stream, 200),
      ),
    );
    addTearDown(() {
      api.close();
      unawaited(body.close());
    });
    await expectLater(
      api.state('test-only'),
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'code',
          'REQUEST_TIMEOUT',
        ),
      ),
    );
  });
  for (final address in [
    'https://remote.example',
    'http://127.0.0.1.evil.test',
    'file:///tmp/api',
    'http://user:secret@localhost:8000',
    'http://localhost:8000/api',
    'http://localhost:8000?token=x',
    'http://localhost:8000#token',
    'http://localhost:0',
    'http://localhost:65536',
  ]) {
    test('reject unsafe origin $address before transport construction', () {
      expect(
        () => HttpLocalApplicationApi(Uri.parse(address)),
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'code',
            'INVALID_API_ORIGIN',
          ),
        ),
      );
    });
  }
  for (final address in [
    'http://localhost:8000',
    'http://127.0.0.1:8081/',
    'http://[::1]:8000',
  ]) {
    test('allow explicit loopback origin $address', () {
      expect(
        HttpLocalApplicationApi.validateOrigin(Uri.parse(address)).host,
        isNotEmpty,
      );
    });
  }
}
