import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

const s2RiskLimitation =
    'This educational profile is based on self-reported answers and is not individualized financial, legal, tax, or investment advice.';
const _tensionMessage =
    'The two self-reported dimensions are in different model bands. This is informational context, not a recommendation or suitability decision.';
const _contract = 's2-risk-contract/v1.0';
const _questionnaire = 'risk_questionnaire_v1';
const _scorer = 'deterministic_v1.0.0';

class S2RiskException implements Exception {
  final String code;
  const S2RiskException(this.code);
  String get message =>
      const {
        'MALFORMED_ANSWER':
            'The assessment format is invalid. Restart and try again.',
        'UNSUPPORTED_QUESTIONNAIRE_VERSION': 'This questionnaire version is unsupported. Reload the questionnaire.',
        'DUPLICATE_QUESTION_ANSWER':
            'A question has more than one answer. Restart and try again.',
        'UNKNOWN_QUESTION_ID':
            'An unknown question was submitted. Reload the questionnaire.',
        'MISSING_REQUIRED_QUESTION': 'Please answer every required question.',
        'INVALID_ANSWER_CODE':
            'An option is not recognized. Reload and choose a listed option.',
        'ANSWER_NOT_PERMITTED_FOR_QUESTION':
            'An option belongs to another question. Restart and try again.',
        'LOCAL_PILOT_ONLY': 'This educational pilot is available only on a local development API.',
        'INVALID_RESPONSE': 'The service returned an incompatible risk contract. Reload or contact the team.',
        'FIXTURE_VECTOR_UNAVAILABLE': 'Choose an approved synthetic profile in fixture mode, or use the local API.',
      }[code] ??
      'The assessment service is unavailable. Please retry.';
}

Map<String, dynamic> _object(Object? value) {
  if (value is! Map<String, dynamic>) {
    throw const S2RiskException('INVALID_RESPONSE');
  }
  return value;
}

Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    jsonDecode(jsonEncode(value)) as Map<String, dynamic>;
String _text(Object? value) {
  if (value is! String || value.isEmpty) {
    throw const S2RiskException('INVALID_RESPONSE');
  }
  return value;
}

void _version(Map<String, dynamic> value) {
  if (value['contract_version'] != _contract ||
      value['questionnaire_id'] != _questionnaire ||
      value['questionnaire_version'] != 'v1') {
    throw const S2RiskException('INVALID_RESPONSE');
  }
}

void _limitation(Object? value) {
  final limitation = _object(value);
  if (limitation['code'] != 'EDUCATIONAL_SELF_REPORTED_PROFILE' ||
      limitation['message'] != s2RiskLimitation) {
    throw const S2RiskException('INVALID_RESPONSE');
  }
}

class S2Option {
  final String code;
  final String label;
  const S2Option(this.code, this.label);
}

class S2Question {
  final String id;
  final String dimension;
  final String text;
  final List<S2Option> options;
  const S2Question(this.id, this.dimension, this.text, this.options);
}

class S2Questionnaire {
  final List<S2Question> questions;
  String get id => _questionnaire;
  String get version => 'v1';
  String get contractVersion => _contract;
  const S2Questionnaire(this.questions);
  factory S2Questionnaire.fromJson(Object? value) {
    final raw = _object(value);
    _version(raw);
    _limitation(raw['limitation']);
    final rows = raw['questions'];
    if (rows is! List || rows.length != 10) {
      throw const S2RiskException('INVALID_RESPONSE');
    }
    final questions = <S2Question>[];
    for (final prefix in ['W', 'C']) {
      for (var number = 1; number <= 5; number++) {
        final id = '$prefix$number';
        final matches = rows
            .where((row) => row is Map && row['question_id'] == id)
            .toList();
        if (matches.length != 1) {
          throw const S2RiskException('INVALID_RESPONSE');
        }
        final row = _object(matches.single);
        final dimension = prefix == 'W' ? 'willingness' : 'capacity';
        final choices = row['options'];
        if (row['dimension'] != dimension ||
            choices is! List ||
            choices.length != 5) {
          throw const S2RiskException('INVALID_RESPONSE');
        }
        final options = <S2Option>[];
        for (final suffix in ['A', 'B', 'C', 'D', 'E']) {
          final code = '${id}_$suffix';
          final matched = choices
              .where((option) => option is Map && option['code'] == code)
              .toList();
          if (matched.length != 1) {
            throw const S2RiskException('INVALID_RESPONSE');
          }
          options.add(S2Option(code, _text(_object(matched.single)['label'])));
        }
        questions.add(
          S2Question(
            id,
            dimension,
            _text(row['text']),
            List.unmodifiable(options),
          ),
        );
      }
    }
    return S2Questionnaire(List.unmodifiable(questions));
  }
}

class S2RiskResult {
  final Map<String, dynamic> _raw;
  S2RiskResult._(this._raw);
  Map<String, dynamic> get _assessment =>
      _raw['assessment'] as Map<String, dynamic>;
  Map<String, dynamic> get _explanation =>
      _raw['explanation'] as Map<String, dynamic>;
  num get composite => _assessment['composite_score'] as num;
  num get willingness => _assessment['willingness_score'] as num;
  num get capacity => _assessment['capacity_score'] as num;
  String get category =>
      (_assessment['risk_category'] as Map)['label'] as String;
  String get calculatedAt => _assessment['calculated_at'] as String;
  String get questionnaireVersion =>
      _assessment['questionnaire_version'] as String;
  String get scoringVersion => _assessment['scoring_version'] as String;
  String get summary => _explanation['summary'] as String;
  String get dimensions => _explanation['dimensions'] as String;
  String get method => _explanation['method'] as String;
  String? get tension =>
      (_assessment['informational_tension'] as Map?)?['message'] as String?;
  Map<String, dynamic> toJson() => _copy(_raw);
  factory S2RiskResult.fromJson(Object? value) {
    final raw = _object(value);
    final assessment = _object(raw['assessment']);
    _version(assessment);
    _limitation(assessment['limitation']);
    final category = _object(assessment['risk_category']);
    const categories = {
      'CONSERVATIVE': 'Conservative',
      'MODERATE': 'Moderate',
      'AGGRESSIVE': 'Aggressive',
    };
    if (raw['scope'] != 'local_educational_pilot' ||
        raw['persisted'] != false ||
        assessment['scoring_version'] != _scorer ||
        !categories.containsKey(category['code']) ||
        categories[category['code']] != category['label']) {
      throw const S2RiskException('INVALID_RESPONSE');
    }
    for (final field in [
      'composite_score',
      'willingness_score',
      'capacity_score',
    ]) {
      final score = assessment[field];
      if (score is! num || !score.isFinite || score < 0 || score > 100) {
        throw const S2RiskException('INVALID_RESPONSE');
      }
    }
    final timestamp = _text(assessment['calculated_at']);
    if (DateTime.tryParse(timestamp) == null ||
        !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(timestamp)) {
      throw const S2RiskException('INVALID_RESPONSE');
    }
    if (assessment.containsKey('informational_tension')) {
      final tension = _object(assessment['informational_tension']);
      if (![
            'WILLINGNESS_BELOW_CAPACITY',
            'CAPACITY_BELOW_WILLINGNESS',
          ].contains(tension['code']) ||
          tension['message'] != _tensionMessage) {
        throw const S2RiskException('INVALID_RESPONSE');
      }
    }
    final explanation = _object(raw['explanation']);
    for (final field in ['summary', 'dimensions', 'method', 'limitation']) {
      _text(explanation[field]);
    }
    if (explanation['questionnaire_version'] !=
            assessment['questionnaire_version'] ||
        explanation['scoring_version'] != assessment['scoring_version'] ||
        explanation['calculated_at'] != timestamp ||
        explanation['limitation'] != s2RiskLimitation) {
      throw const S2RiskException('INVALID_RESPONSE');
    }
    return S2RiskResult._(_copy(raw));
  }
}

abstract class S2RiskClient {
  List<Map<String, dynamic>> get profiles => const [];
  Future<S2Questionnaire> loadQuestionnaire();
  Future<S2RiskResult> submit(
    Map<String, dynamic> request, {
    String? correlationId,
  });
  void close() {}
}

class FixtureS2RiskClient extends S2RiskClient {
  final Future<String> Function() _loader;
  Future<Map<String, dynamic>>? _pack;
  List<Map<String, dynamic>> _profiles = [];
  FixtureS2RiskClient({Future<String> Function()? loader})
    : _loader =
          loader ??
          (() => rootBundle.loadString('assets/s2_risk_fixtures.v1.json'));
  @override
  List<Map<String, dynamic>> get profiles =>
      _profiles.map(_copy).toList(growable: false);
  Future<Map<String, dynamic>> _load() async {
    try {
      return await (_pack ??= _read());
    } catch (_) {
      _pack = null;
      rethrow;
    }
  }

  Future<Map<String, dynamic>> _read() async {
    final pack = _object(jsonDecode(await _loader()));
    if (pack['schema_version'] != 's2-client-fixtures/v1' ||
        pack['synthetic'] != true ||
        pack['contract_version'] != _contract ||
        pack['cases'] is! List) {
      throw const S2RiskException('INVALID_RESPONSE');
    }
    _profiles = (pack['cases'] as List)
        .where((row) => row is Map && row.containsKey('response'))
        .map((row) => _copy(_object(row)))
        .toList(growable: false);
    return pack;
  }

  @override
  Future<S2Questionnaire> loadQuestionnaire() async =>
      S2Questionnaire.fromJson((await _load())['questionnaire']);
  String _key(Map<String, dynamic> request) {
    final answers =
        (request['answers'] as List)
            .map(
              (answer) =>
                  jsonEncode([answer['question_id'], answer['answer_code']]),
            )
            .toList()
          ..sort();
    return jsonEncode([
      request['questionnaire_id'],
      request['questionnaire_version'],
      answers,
    ]);
  }

  @override
  Future<S2RiskResult> submit(
    Map<String, dynamic> request, {
    String? correlationId,
  }) async {
    final rows = (await _load())['cases'] as List;
    final matched = rows
        .where((row) => _key(_object(row['request'])) == _key(request))
        .toList();
    if (matched.length != 1) {
      throw const S2RiskException('FIXTURE_VECTOR_UNAVAILABLE');
    }
    final row = _object(matched.single);
    if (row['error_code'] is String) {
      throw S2RiskException(row['error_code'] as String);
    }
    return S2RiskResult.fromJson(row['response']);
  }
}

class HttpS2RiskClient extends S2RiskClient {
  final Uri baseUri;
  final http.Client _client;
  final Duration timeout;
  HttpS2RiskClient(
    this.baseUri, {
    http.Client? client,
    this.timeout = const Duration(seconds: 8),
  }) : _client = client ?? http.Client() {
    if (!['localhost', '127.0.0.1', '::1'].contains(baseUri.host) ||
        !['http', 'https'].contains(baseUri.scheme) ||
        baseUri.userInfo.isNotEmpty ||
        baseUri.hasQuery ||
        baseUri.hasFragment ||
        !['', '/'].contains(baseUri.path)) {
      throw const S2RiskException('LOCAL_PILOT_ONLY');
    }
  }
  Future<Object?> _call(
    String path, {
    Map<String, dynamic>? request,
    String? correlationId,
  }) async {
    final uri = baseUri.resolve('/api/v1/risk-contract/$path');
    final headers = {
      'Content-Type': 'application/json',
      'X-Correlation-ID': ?correlationId,
    };
    try {
      final response =
          await (request == null
                  ? _client.get(uri, headers: headers)
                  : _client.post(
                      uri,
                      headers: headers,
                      body: jsonEncode(request),
                    ))
              .timeout(timeout);
      final body = _object(jsonDecode(response.body));
      if (response.statusCode != 200 || body['success'] != true) {
        final error = body['error'];
        final code = error is Map ? error['code'] : body['error_code'];
        throw S2RiskException(
          code is String ? code : 'RISK_ASSESSMENT_UNAVAILABLE',
        );
      }
      return body['data'];
    } on S2RiskException {
      rethrow;
    } catch (_) {
      throw const S2RiskException('RISK_ASSESSMENT_UNAVAILABLE');
    }
  }

  @override
  Future<S2Questionnaire> loadQuestionnaire() async =>
      S2Questionnaire.fromJson(await _call('questionnaire'));
  @override
  Future<S2RiskResult> submit(
    Map<String, dynamic> request, {
    String? correlationId,
  }) async => S2RiskResult.fromJson(
    await _call('assessments', request: request, correlationId: correlationId),
  );
  @override
  void close() => _client.close();
}
