// Current native report/corpus gate, then original UTF8 replay through the
// production public API. MockClient replay is not browser/native TCP evidence.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/local_s2_corpus.dart';

const _ids = [
  'questionnaire',
  'draft_initial',
  'draft_partial_saved',
  'draft_partial_resumed',
  'history_initial',
  'assessment_created',
  'assessment_equivalent_replay',
  'assessment_detail',
  'history_single',
  'other_owner_history_empty',
  'draft_cleared',
  'draft_after_restart',
  'assessment_after_restart',
  'assessment_aggressive',
  'assessment_conservative',
  'history_page_first',
  'assessment_inserted_between_pages',
  'history_page_next',
  'history_after_relogin',
  'idempotency_conflict',
  'assessment_other_owner',
  'assessment_missing',
  'onboarding_withdrawn',
  'onboarding_reaccepted',
  'session_invalid',
  'session_restart_invalid',
  'unsupported_version',
  'missing_required_question',
  'validation_error',
];

Map<String, dynamic> _object(Object? value) => value as Map<String, dynamic>;
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    _object(jsonDecode(jsonEncode(value)));
DateTime? _time(Object? value) =>
    value == null ? null : DateTime.parse(value as String).toUtc();

bool _same(Object? left, Object? right) {
  if (left is Map && right is Map) {
    return left.length == right.length &&
        left.keys.every(
          (key) => right.containsKey(key) && _same(left[key], right[key]),
        );
  }
  if (left is List && right is List) {
    return left.length == right.length &&
        List.generate(
          left.length,
          (index) => _same(left[index], right[index]),
        ).every((value) => value);
  }
  return left == right;
}

bool _safeRequestBody(String raw, Object? expected) {
  try {
    return expected == null ? raw.isEmpty : _same(jsonDecode(raw), expected);
  } catch (_) {
    return false;
  }
}

String _memoryBearer() => base64Url
    .encode(List.generate(32, (_) => Random.secure().nextInt(256)))
    .replaceAll('=', '');

LocalRiskInput _legalInput({bool complete = false}) => LocalRiskInput([
  if (complete)
    for (final id in localQuestionIds) LocalRiskAnswer(id, '${id}_C'),
], complete: complete);

class _RiskDispatch {
  final String method;
  final String path;
  final Map<String, String> query;
  final Map<String, dynamic>? expectedRequest;
  final Future<LocalS2Reply<Object>> Function(HttpLocalApplicationApi, String)
  invoke;

  const _RiskDispatch({
    required this.method,
    required this.path,
    required this.query,
    required this.expectedRequest,
    required this.invoke,
  });
}

_RiskDispatch _dispatch(LocalS2CorpusCase item) {
  const root = '/api/v1/local-risk';
  final success = item.outcome == 'success';
  final request = item.request == null ? null : _copy(item.request!);
  if (item.operation == 'questionnaire') {
    return _RiskDispatch(
      method: 'GET',
      path: '$root/questionnaire',
      query: {},
      expectedRequest: null,
      invoke: (api, bearer) => api.riskQuestionnaire(bearer),
    );
  }
  if (item.operation == 'draft_get') {
    return _RiskDispatch(
      method: 'GET',
      path: '$root/draft',
      query: {},
      expectedRequest: null,
      invoke: (api, bearer) => api.riskDraft(bearer),
    );
  }
  if (item.operation == 'draft_put') {
    final input = success ? LocalRiskInput.fromJson(request) : _legalInput();
    return _RiskDispatch(
      method: 'PUT',
      path: '$root/draft',
      query: {},
      expectedRequest: Map<String, dynamic>.from(input.toJson()),
      invoke: (api, bearer) => api.saveRiskDraft(bearer, input),
    );
  }
  if (item.operation == 'assessment_create') {
    final key = success
        ? request!['idempotency_key'] as String
        : newLocalRetryKey();
    final input = success
        ? LocalRiskInput.fromJson(
            {...request!}..remove('idempotency_key'),
            complete: true,
          )
        : _legalInput(complete: true);
    return _RiskDispatch(
      method: 'POST',
      path: '$root/assessments',
      query: {},
      expectedRequest: {...input.toJson(), 'idempotency_key': key},
      invoke: (api, bearer) => api.assessRisk(bearer, input, key),
    );
  }
  if (item.operation == 'history') {
    final target = _copy(item.target!);
    final before = target['before'] as String?;
    return _RiskDispatch(
      method: 'GET',
      path: '$root/assessments',
      query: {'limit': '2', 'before': ?before},
      expectedRequest: null,
      invoke: (api, bearer) => api.riskHistory(bearer, before: before),
    );
  }
  if (item.operation == 'assessment_detail') {
    // This ID comes from the original validated capture, never a mutated body.
    final id = item.target!['assessment_id'] as String;
    return _RiskDispatch(
      method: 'GET',
      path: '$root/assessments/$id',
      query: {},
      expectedRequest: null,
      invoke: (api, bearer) => api.riskAssessment(bearer, id),
    );
  }
  throw StateError('Unsupported bounded saved-risk corpus operation.');
}

HttpLocalApplicationApi _api(
  LocalS2CorpusCase item,
  _RiskDispatch dispatch,
  String bearer, {
  String? responseBody,
}) => HttpLocalApplicationApi(
  Uri.parse('http://127.0.0.1:8082'),
  client: MockClient((request) async {
    // Only booleans reach diagnostic matchers; no raw URL/header/body/token.
    expect(request.method == dispatch.method, isTrue);
    expect(request.url.path == dispatch.path, isTrue);
    expect(_same(request.url.queryParameters, dispatch.query), isTrue);
    expect(request.headers['authorization'] == 'Bearer $bearer', isTrue);
    expect(request.headers.containsKey('cookie'), isFalse);
    expect(request.followRedirects, isFalse);
    expect(_safeRequestBody(request.body, dispatch.expectedRequest), isTrue);
    return http.Response.bytes(
      utf8.encode(responseBody ?? item.bodyUtf8),
      item.status,
      headers: {'content-type': item.contentType},
    );
  }),
);

void _expectAssessment(
  LocalSavedRiskAssessment value,
  Map<String, dynamic> data,
) {
  final assessment = _object(data['assessment']);
  final explanation = _object(data['explanation']);
  expect(value.assessmentId == data['assessment_id'], isTrue);
  expect(value.createdAt == _time(data['created_at']), isTrue);
  expect(_same(value.input.toJson(), data['input']), isTrue);
  expect(value.willingness == assessment['willingness_score'], isTrue);
  expect(value.capacity == assessment['capacity_score'], isTrue);
  expect(value.composite == assessment['composite_score'], isTrue);
  expect(
    value.category == _object(assessment['risk_category'])['label'],
    isTrue,
  );
  final tension = assessment['informational_tension'];
  expect(
    value.tension == (tension == null ? null : _object(tension)['message']),
    isTrue,
  );
  expect(value.summary == explanation['summary'], isTrue);
  expect(value.dimensions == explanation['dimensions'], isTrue);
  expect(value.method == explanation['method'], isTrue);
  expect(value.rulesHash == data['rules_sha256'], isTrue);
  expect(_same(value.rulesSnapshot, data['rules_snapshot']), isTrue);
}

void _expectReply(LocalS2Reply<Object> reply, LocalS2CorpusCase item) {
  final body = _object(jsonDecode(item.bodyUtf8));
  final data = _object(body['data']);
  final meta = _object(body['meta']);
  expect(reply.dataStatus == meta['dataStatus'], isTrue);
  expect(reply.dataAsOf == _time(meta['dataAsOf']), isTrue);
  final value = reply.value;
  if (value is LocalRiskQuestionnaire) {
    final raw = (data['questions'] as List).cast<Map<String, dynamic>>();
    expect(value.questions.length, 10);
    expect(value.rulesHash == data['rules_sha256'], isTrue);
    for (var index = 0; index < raw.length; index++) {
      final question = value.questions[index];
      final row = raw[index];
      expect(question.id == row['question_id'], isTrue);
      expect(question.dimension == row['dimension'], isTrue);
      expect(question.text == row['text'], isTrue);
      expect(
        _same([
          for (final option in question.options)
            {'code': option.code, 'label': option.label},
        ], row['options']),
        isTrue,
      );
    }
  } else if (value is LocalRiskDraft) {
    expect(
      _same(value.input.toJson(), {
        'questionnaire_id': data['questionnaire_id'],
        'questionnaire_version': data['questionnaire_version'],
        'answers': data['answers'],
      }),
      isTrue,
    );
    expect(value.updatedAt == _time(data['updated_at']), isTrue);
  } else if (value is LocalSavedRiskAssessment) {
    _expectAssessment(value, data);
  } else if (value is LocalRiskHistory) {
    final raw = (data['items'] as List).cast<Map<String, dynamic>>();
    expect(value.items.length <= 2, isTrue);
    expect(value.nextCursor == data['next_cursor'], isTrue);
    expect(
      _same(
        value.items.map((row) => row.assessmentId).toList(),
        raw.map((row) => row['assessment_id']).toList(),
      ),
      isTrue,
    );
    for (var index = 0; index < raw.length; index++) {
      _expectAssessment(value.items[index], raw[index]);
    }
  } else {
    fail('The public saved-risk method returned an unexpected safe type.');
  }
}

void main() {
  test('parity request comparison rejects malformed or bearer-bearing bodies safely', () {
    final marker = _memoryBearer();
    final cases = [
      '{"authorization":"$marker"',
      jsonEncode({'token': marker}),
      marker,
    ];
    for (final raw in cases) {
      var rejected = false;
      try {
        rejected = !_safeRequestBody(raw, {'answers': []});
      } catch (_) {
        // A parser diagnostic must never escape even this test-only comparer.
      }
      expect(rejected, isTrue);
    }
    expect(_safeRequestBody('{"answers":[]}', {'answers': []}), isTrue);
  });

  final pair = loadLocalS2Corpora(Platform.environment);
  if (pair == null) {
    test(
      'current saved-risk native corpus replay is not claimed without inputs',
      () {},
      skip: 'Optional complete native inputs absent; required/partial inputs must fail the loader.',
    );
    return;
  }
  final corpus = pair.risk;
  for (final id in _ids) {
    test('current raw UTF8 public saved-risk parity: $id', () async {
      final item = corpus.caseById(id);
      final dispatch = _dispatch(item);
      final bearer = _memoryBearer();
      final api = _api(item, dispatch, bearer);
      addTearDown(api.close);
      if (item.outcome == 'error') {
        // Invalid captured mutations have null request: canonical legal public
        // input proves response mapping, not emission of that invalid request.
        await expectLater(
          dispatch.invoke(api, bearer),
          throwsA(
            isA<LocalApiException>()
                .having((error) => error.code, 'safe API code', item.errorCode)
                .having((error) => error.status, 'HTTP status', item.status),
          ),
        );
      } else {
        _expectReply(await dispatch.invoke(api, bearer), item);
      }
    });
  }
  test(
    'reordered retry preserves the original stored typed input/identity/time',
    () async {
      final original = corpus.caseById('assessment_created');
      final replay = corpus.caseById('assessment_equivalent_replay');
      final token = _memoryBearer();
      final firstDispatch = _dispatch(original);
      final replayDispatch = _dispatch(replay);
      final firstApi = _api(original, firstDispatch, token);
      final replayApi = _api(replay, replayDispatch, token);
      addTearDown(firstApi.close);
      addTearDown(replayApi.close);
      final first =
          (await firstDispatch.invoke(firstApi, token)).value
              as LocalSavedRiskAssessment;
      final again =
          (await replayDispatch.invoke(replayApi, token)).value
              as LocalSavedRiskAssessment;
      expect(first.assessmentId == again.assessmentId, isTrue);
      expect(first.createdAt == again.createdAt, isTrue);
      expect(_same(first.input.toJson(), again.input.toJson()), isTrue);
      expect(_same(first.rulesSnapshot, again.rulesSnapshot), isTrue);
      expect(
        _same(original.request!['answers'], replay.request!['answers']),
        isFalse,
      );
      expect(
        LocalRiskInput.fromJson(
          {...replay.request!}..remove('idempotency_key'),
          complete: true,
        ).equivalent(first.input),
        isTrue,
      );
    },
  );
  test(
    'saved typed snapshot and original input cannot be mutated by a caller',
    () async {
      final item = corpus.caseById('assessment_detail');
      final dispatch = _dispatch(item);
      final token = _memoryBearer();
      final api = _api(item, dispatch, token);
      addTearDown(api.close);
      final value =
          (await dispatch.invoke(api, token)).value as LocalSavedRiskAssessment;
      expect(() => value.input.answers.clear(), throwsUnsupportedError);
      expect(
        () => value.rulesSnapshot['questionnaire'] = null,
        throwsUnsupportedError,
      );
      final nested = value.rulesSnapshot['questionnaire'] as Map;
      expect(() => nested['status'] = 'UNAPPROVED', throwsUnsupportedError);
    },
  );
  test(
    'mutated detail response ID cannot retarget the frozen captured request',
    () async {
      final item = corpus.caseById('assessment_detail');
      final dispatch = _dispatch(item);
      final body = _object(jsonDecode(item.bodyUtf8));
      _object(body['data'])['assessment_id'] = newLocalRetryKey();
      final token = _memoryBearer();
      final api = _api(item, dispatch, token, responseBody: jsonEncode(body));
      addTearDown(api.close);
      await expectLater(
        dispatch.invoke(api, token),
        throwsA(
          isA<LocalApiException>().having(
            (error) => error.code,
            'safe API code',
            'INVALID_API_RESPONSE',
          ),
        ),
      );
    },
  );
  test('stable next page retains original record and ignores the between-page insert', () async {
    final first = corpus.caseById('history_page_first');
    final next = corpus.caseById('history_page_next');
    final original = corpus.caseById('assessment_created');
    final inserted = corpus.caseById('assessment_inserted_between_pages');
    final token = _memoryBearer();
    final firstDispatch = _dispatch(first);
    final nextDispatch = _dispatch(next);
    final firstApi = _api(first, firstDispatch, token);
    final nextApi = _api(next, nextDispatch, token);
    addTearDown(firstApi.close);
    addTearDown(nextApi.close);
    final page1 =
        (await firstDispatch.invoke(firstApi, token)).value as LocalRiskHistory;
    final page2 =
        (await nextDispatch.invoke(nextApi, token)).value as LocalRiskHistory;
    expect(page1.items.length, 2);
    expect(page1.nextCursor == next.target!['before'], isTrue);
    final originalId = _object(
      _object(jsonDecode(original.bodyUtf8))['data'],
    )['assessment_id'];
    final insertedId = _object(
      _object(jsonDecode(inserted.bodyUtf8))['data'],
    )['assessment_id'];
    expect(page2.items.length, 1);
    expect(page2.items.single.assessmentId == originalId, isTrue);
    expect(page2.items.any((row) => row.assessmentId == insertedId), isFalse);
    expect(
      page1.items.any(
        (row) => row.assessmentId == page2.items.single.assessmentId,
      ),
      isFalse,
    );
  });
}
