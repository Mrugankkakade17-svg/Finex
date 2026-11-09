import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

// Optional, explicitly historical review proof, not a current-client/native CI
// acceptance corpus. There is no generated fallback or response reshaping.
// Login responses, credentials and request headers are never loaded or saved.
List<Map<String, dynamic>> _readObservation(String path) {
  try {
    final file = File(path);
    if (!file.isAbsolute || file.lengthSync() > 8 * 1024 * 1024) {
      throw const FormatException();
    }
    final value = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
    final proof = value['accepted_driver_result'] as Map<String, dynamic>;
    if (value['schema_version'] !=
            'finex.review.saved_risk_wire_observation.v1' ||
        value['scope'] != localApplicationScope ||
        value['contract_version'] != localContractVersion ||
        proof['success'] != true ||
        proof['mode'] != 'owned_native_tcp' ||
        proof['working_tree_dirty'] != false ||
        proof['tested_commit'] != 'abf5956a35fc5cf01afce58753bdbeb045a87851' ||
        proof['tested_tree'] != '99c08f21b9f00a8877449cca824da9a70f7cca2d') {
      throw const FormatException();
    }
    final cases = (value['cases'] as List).cast<Map<String, dynamic>>();
    if (cases.length != 33) throw const FormatException();
    for (var index = 0; index < cases.length; index++) {
      final item = cases[index];
      if (item['id'] != 'risk_wire_${(index + 1).toString().padLeft(2, '0')}' ||
          item['body_utf8'] is! String ||
          utf8.encode(item['body_utf8'] as String).length > 262144 ||
          item['content_type'] != 'application/json') {
        throw const FormatException();
      }
    }
    return cases;
  } catch (_) {
    // File/JSON diagnostics could include raw captured content or paths.
    throw StateError(
      'Historical saved-risk review input is unavailable or invalid.',
    );
  }
}

bool _sameWire(Object? first, Object? second) {
  if (first is Map && second is Map) {
    return first.length == second.length &&
        first.keys.every(
          (key) =>
              second.containsKey(key) && _sameWire(first[key], second[key]),
        );
  }
  if (first is List && second is List) {
    return first.length == second.length &&
        List.generate(
          first.length,
          (index) => _sameWire(first[index], second[index]),
        ).every((value) => value);
  }
  return first == second;
}

bool _requestMatches(String rawBody, Object? capturedRequest) {
  try {
    return _sameWire(jsonDecode(rawBody), capturedRequest);
  } catch (_) {
    // Even synthetic opaque values must never enter parser diagnostics.
    return false;
  }
}

void main() {
  test('malformed request comparison safely rejects without diagnostics', () {
    final random = Random.secure();
    final syntheticOpaque = base64Url
        .encode(List<int>.generate(32, (_) => random.nextInt(256)))
        .replaceAll('=', '');
    final malformed = '{"synthetic_body":"$syntheticOpaque"';
    var safelyRejected = false;
    try {
      safelyRejected = !_requestMatches(malformed, <String, Object?>{});
    } catch (_) {
      // The regression itself never exposes a parser diagnostic or body.
    }
    expect(safelyRejected, isTrue);
    expect(
      _requestMatches('{"answers":[]}', <String, Object?>{'answers': []}),
      isTrue,
    );
  });
  final path = Platform.environment['FINEX_S2_REVIEW_RISK_WIRE'];
  if (path == null) {
    test(
      'historical saved-risk wire replay requires its explicit review input',
      () {},
      skip: 'Optional historical input was not supplied; no native proof claimed.',
    );
    return;
  }
  final cases = _readObservation(path);
  // These captures used limit1 or a default limit20 three-item page. They are
  // not the client limit2 contract, so do not trim or relabel them as equivalent.
  const differentPageContracts = {
    'risk_wire_22',
    'risk_wire_24',
    'risk_wire_27',
    'risk_wire_30',
  };
  for (final item in cases.where(
    (c) => !differentPageContracts.contains(c['id']),
  )) {
    test('historical raw UTF8 public risk replay ${item['id']}', () async {
      final random = Random.secure();
      final token = base64Url
          .encode(List<int>.generate(32, (_) => random.nextInt(256)))
          .replaceAll('=', '');
      final method = item['method'] as String;
      final suffix = item['suffix'] as String;
      final capturedRequest = item['request'];
      final value = HttpLocalApplicationApi(
        Uri.parse('http://127.0.0.1:8082'),
        client: MockClient((request) async {
          expect(request.method == method, isTrue);
          expect(request.headers['authorization'] == 'Bearer $token', isTrue);
          expect(request.followRedirects, isFalse);
          expect(
            request.url.path == '/api/v1/local-risk${Uri.parse(suffix).path}',
            isTrue,
          );
          if (capturedRequest != null) {
            expect(_requestMatches(request.body, capturedRequest), isTrue);
          }
          if (method == 'GET' && Uri.parse(suffix).path == '/assessments') {
            expect(request.url.queryParameters['limit'], '2');
            if (suffix.contains('limit=2')) {
              expect(request.url.query == Uri.parse(suffix).query, isTrue);
            }
            // Default-limit historical pages with <=2 items are response-byte
            // compatibility only, not identical issued-query evidence.
          }
          return http.Response.bytes(
            utf8.encode(item['body_utf8'] as String),
            item['status'] as int,
            headers: {'content-type': item['content_type'] as String},
          );
        }),
      );
      addTearDown(value.close);
      Future<Object> invoke() {
        if (method == 'GET' && suffix == '/questionnaire') {
          return value.riskQuestionnaire(token);
        }
        if (method == 'GET' && suffix == '/draft') {
          return value.riskDraft(token);
        }
        if (method == 'PUT' && suffix == '/draft') {
          return value.saveRiskDraft(
            token,
            LocalRiskInput.fromJson(capturedRequest),
          );
        }
        if (method == 'POST' && suffix == '/assessments') {
          final request = Map<String, dynamic>.from(capturedRequest as Map);
          final key = request.remove('idempotency_key') as String;
          return value.assessRisk(
            token,
            LocalRiskInput.fromJson(request, complete: true),
            key,
          );
        }
        if (method == 'GET' && suffix.startsWith('/assessments/')) {
          return value.riskAssessment(token, suffix.split('/').last);
        }
        if (method == 'GET' && Uri.parse(suffix).path == '/assessments') {
          return value.riskHistory(
            token,
            before: Uri.parse(suffix).queryParameters['before'],
          );
        }
        throw StateError('Unrecognized safe historical review operation.');
      }

      if (item['expected_error_code'] != null) {
        await expectLater(
          invoke(),
          throwsA(
            isA<LocalApiException>().having(
              (e) => e.code,
              'safe API code',
              item['expected_error_code'],
            ),
          ),
        );
      } else {
        expect(await invoke(), isA<LocalS2Reply<Object>>());
      }
    });
  }
}
