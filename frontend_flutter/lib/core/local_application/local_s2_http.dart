part of 'local_api_client.dart';

Map<String, dynamic> _s2WireObject(Object? raw, List<String> keys) {
  final value = localObject(raw);
  if (value.length != keys.length || !keys.every(value.containsKey)) {
    invalidLocalResponse();
  }
  return value;
}

bool _safeCorrelation(Object? value) =>
    value is String &&
    RegExp(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$').hasMatch(value);
const _s2ErrorStatuses = {
  'LOCAL_APPLICATION_ONLY': 403,
  'ONBOARDING_REQUIRED': 409,
  'LOCAL_STORE_UNAVAILABLE': 503,
  'MALFORMED_ANSWER': 400,
  'UNSUPPORTED_QUESTIONNAIRE_VERSION': 400,
  'DUPLICATE_QUESTION_ANSWER': 400,
  'UNKNOWN_QUESTION_ID': 400,
  'MISSING_REQUIRED_QUESTION': 400,
  'INVALID_ANSWER_CODE': 400,
  'ANSWER_NOT_PERMITTED_FOR_QUESTION': 400,
  'IDEMPOTENCY_CONFLICT': 409,
  'RISK_ASSESSMENT_NOT_FOUND': 404,
  'VALIDATION_ERROR': 422,
  'RISK_ASSESSMENT_UNAVAILABLE': 503,
  'UNSUPPORTED_INSTRUMENT': 422,
  'LOCAL_PORTFOLIO_NOT_FOUND': 404,
  'LOCAL_HOLDING_NOT_FOUND': 404,
  'HOLDING_ALREADY_EXISTS': 409,
  'PORTFOLIO_LIMIT_REACHED': 409,
  'HOLDING_LIMIT_REACHED': 409,
  'LOCAL_CATALOG_UNAVAILABLE': 503,
  'LOCAL_QUOTE_UNAVAILABLE': 503,
};
Set<String> _s2AllowedErrors(String method, String requestPath) {
  final path = requestPath.split('?').first;
  final allowed = {
    'LOCAL_APPLICATION_ONLY',
    'ONBOARDING_REQUIRED',
    'LOCAL_STORE_UNAVAILABLE',
    'VALIDATION_ERROR',
  };
  if (path.startsWith('/api/v1/local-risk/')) {
    allowed.add('RISK_ASSESSMENT_UNAVAILABLE');
    if ((method == 'PUT' && path.endsWith('/draft')) ||
        (method == 'POST' && path.endsWith('/assessments'))) {
      allowed.addAll([
        'MALFORMED_ANSWER',
        'UNSUPPORTED_QUESTIONNAIRE_VERSION',
        'DUPLICATE_QUESTION_ANSWER',
        'UNKNOWN_QUESTION_ID',
        'INVALID_ANSWER_CODE',
        'ANSWER_NOT_PERMITTED_FOR_QUESTION',
      ]);
    }
    if (method == 'POST') {
      allowed.addAll(['IDEMPOTENCY_CONFLICT', 'MISSING_REQUIRED_QUESTION']);
    }
    if (method == 'GET' && path.contains('/assessments/')) {
      allowed.add('RISK_ASSESSMENT_NOT_FOUND');
    }
  } else {
    const root = '/api/v1/local-portfolios';
    if (path == '$root/instruments') {
      allowed.add('LOCAL_CATALOG_UNAVAILABLE');
    } else if (path == root) {
      if (method == 'POST') allowed.add('PORTFOLIO_LIMIT_REACHED');
    } else {
      allowed.add('LOCAL_PORTFOLIO_NOT_FOUND');
      if (path.contains('/holdings')) {
        allowed.add('LOCAL_CATALOG_UNAVAILABLE');
        if (path.endsWith('/holdings') && method == 'POST') {
          allowed.addAll([
            'UNSUPPORTED_INSTRUMENT',
            'HOLDING_ALREADY_EXISTS',
            'HOLDING_LIMIT_REACHED',
          ]);
        }
        if (path.contains('/holdings/')) allowed.add('LOCAL_HOLDING_NOT_FOUND');
      }
      if (path.endsWith('/metrics')) {
        allowed.addAll([
          'LOCAL_CATALOG_UNAVAILABLE',
          'LOCAL_QUOTE_UNAVAILABLE',
        ]);
      }
    }
  }
  return allowed;
}

Map<String, dynamic> _decodeS2Response(
  http.Response response,
  int expectedStatus,
  String method,
  String path, {
  Set<String>? allowedErrors,
  Map<String, int> errorStatuses = _s2ErrorStatuses,
}) {
  if (response.bodyBytes.length > 262144 ||
      !RegExp(
        r'^application/json(?:\s*;|$)',
        caseSensitive: false,
      ).hasMatch(response.headers['content-type'] ?? '')) {
    invalidLocalResponse();
  }
  Object? decoded;
  try {
    decoded = jsonDecode(utf8.decode(response.bodyBytes));
  } on FormatException {
    invalidLocalResponse();
  }
  final root = localObject(decoded);
  if (root['success'] == false &&
      response.statusCode >= 400 &&
      response.statusCode <= 599) {
    final envelope = _s2WireObject(root, [
      'success',
      'message',
      'error_code',
      'error',
      'detail',
    ]);
    final error = _s2WireObject(envelope['error'], [
      'code',
      'message',
      'fieldErrors',
      'correlationId',
    ]);
    final message = envelope['message'];
    final code = envelope['error_code'];
    if (message is! String ||
        message.length > 4096 ||
        code is! String ||
        !RegExp(r'^[A-Z][A-Z0-9_]{0,79}$').hasMatch(code) ||
        error['code'] != code ||
        error['message'] != message ||
        envelope['detail'] != message ||
        !_safeCorrelation(error['correlationId'])) {
      invalidLocalResponse();
    }
    final rawFields = error['fieldErrors'];
    if (rawFields is! List || rawFields.length > 64) invalidLocalResponse();
    final fields = <String>{};
    const safeFields = {
      'name',
      'description',
      'currency',
      'instrument_id',
      'quantity',
      'average_cost',
      'questionnaire_id',
      'questionnaire_version',
      'answers',
      'idempotency_key',
    };
    for (final raw in rawFields) {
      final field = _s2WireObject(raw, ['field', 'code']);
      if (field['field'] is! String ||
          (field['field'] as String).length > 128 ||
          field['code'] is! String ||
          (field['code'] as String).length > 128) {
        invalidLocalResponse();
      }
      final name = (field['field'] as String).split('.').last;
      if (safeFields.contains(name)) fields.add(name);
    }
    if (!(allowedErrors ?? _s2AllowedErrors(method, path)).contains(code) ||
        errorStatuses[code] != response.statusCode) {
      invalidLocalResponse();
    }
    throw LocalApiException(
      code,
      status: response.statusCode,
      fields: Set.unmodifiable(fields),
    );
  }
  if (root['success'] != true || response.statusCode != expectedStatus) {
    invalidLocalResponse();
  }
  final envelope = _s2WireObject(root, ['success', 'message', 'data', 'meta']);
  if (envelope['message'] is! String ||
      (envelope['message'] as String).length > 4096) {
    invalidLocalResponse();
  }
  final meta = _s2WireObject(envelope['meta'], [
    'apiVersion',
    'dataStatus',
    'dataAsOf',
    'correlationId',
  ]);
  if (meta['apiVersion'] != 'v1' ||
      !['CACHED', 'UNAVAILABLE'].contains(meta['dataStatus']) ||
      !_safeCorrelation(meta['correlationId'])) {
    invalidLocalResponse();
  }
  if (meta['dataAsOf'] != null) localUtcTimestamp(meta['dataAsOf']);
  requireLocalVersion(localObject(envelope['data']));
  return envelope;
}

mixin _LocalS2HttpMethods implements LocalS2Api {
  Future<Map<String, dynamic>> _request(
    String method,
    String path, {
    String? bearer,
    Map<String, Object?>? body,
    bool s2 = false,
    int expectedStatus = 200,
  });
  Future<LocalS2Reply<T>> _s2<T>(
    String method,
    String path,
    String bearer,
    T Function(Object?) decode, {
    Map<String, Object?>? body,
    int status = 200,
    DateTime? Function(T)? asOf,
    String Function(T)? dataStatus,
  }) async {
    final envelope = await _request(
      method,
      path,
      bearer: bearer,
      body: body,
      s2: true,
      expectedStatus: status,
    );
    final value = decode(envelope['data']);
    final meta = localObject(envelope['meta']);
    final expectedTime = asOf?.call(value);
    final actualTime = meta['dataAsOf'] == null
        ? null
        : localUtcTimestamp(meta['dataAsOf']);
    final expectedDataStatus = dataStatus?.call(value) ?? 'CACHED';
    if (actualTime != expectedTime ||
        meta['dataStatus'] != expectedDataStatus) {
      invalidLocalResponse();
    }
    return LocalS2Reply(value, expectedDataStatus, actualTime);
  }

  @override
  Future<LocalS2Reply<LocalRiskQuestionnaire>> riskQuestionnaire(
    String bearer,
  ) => _s2(
    'GET',
    '/api/v1/local-risk/questionnaire',
    bearer,
    LocalRiskQuestionnaire.fromJson,
  );
  @override
  Future<LocalS2Reply<LocalRiskDraft>> riskDraft(String bearer) => _s2(
    'GET',
    '/api/v1/local-risk/draft',
    bearer,
    LocalRiskDraft.fromJson,
    asOf: (v) => v.updatedAt,
  );
  @override
  Future<LocalS2Reply<LocalRiskDraft>> saveRiskDraft(
    String bearer,
    LocalRiskInput input,
  ) async {
    final reply = await _s2(
      'PUT',
      '/api/v1/local-risk/draft',
      bearer,
      LocalRiskDraft.fromJson,
      body: input.toJson(),
      asOf: (v) => v.updatedAt,
    );
    final actual = reply.value.input.answers;
    final expected = input.answers;
    if (reply.value.updatedAt == null ||
        actual.length != expected.length ||
        List.generate(
          actual.length,
          (i) =>
              actual[i].questionId == expected[i].questionId &&
              actual[i].answerCode == expected[i].answerCode,
        ).contains(false)) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> assessRisk(
    String bearer,
    LocalRiskInput input,
    String retryKey,
  ) async {
    localUuid(retryKey);
    if (input.answers.length != 10) invalidLocalResponse();
    final reply = await _s2(
      'POST',
      '/api/v1/local-risk/assessments',
      bearer,
      LocalSavedRiskAssessment.fromJson,
      body: {...input.toJson(), 'idempotency_key': retryKey},
      asOf: (v) => v.createdAt,
    );
    if (!reply.value.input.equivalent(input)) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalRiskHistory>> riskHistory(
    String bearer, {
    String? before,
  }) {
    if (before != null) localRiskCursor(before);
    final query = Uri(queryParameters: {'limit': '2', 'before': ?before}).query;
    return _s2(
      'GET',
      '/api/v1/local-risk/assessments?$query',
      bearer,
      LocalRiskHistory.fromJson,
    );
  }

  @override
  Future<LocalS2Reply<LocalSavedRiskAssessment>> riskAssessment(
    String bearer,
    String id,
  ) async {
    localUuid(id);
    final reply = await _s2(
      'GET',
      '/api/v1/local-risk/assessments/$id',
      bearer,
      LocalSavedRiskAssessment.fromJson,
      asOf: (v) => v.createdAt,
    );
    if (reply.value.assessmentId != id) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments(String bearer) =>
      _s2(
        'GET',
        '/api/v1/local-portfolios/instruments',
        bearer,
        LocalInstrumentCatalog.fromJson,
      );
  @override
  Future<LocalS2Reply<LocalPortfolioList>> portfolios(String bearer) => _s2(
    'GET',
    '/api/v1/local-portfolios',
    bearer,
    LocalPortfolioList.fromJson,
  );
  @override
  Future<LocalS2Reply<LocalPortfolio>> portfolio(
    String bearer,
    String id,
  ) async {
    localUuid(id);
    final reply = await _s2(
      'GET',
      '/api/v1/local-portfolios/$id',
      bearer,
      LocalPortfolio.fromJson,
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.portfolioId != id) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalPortfolio>> createPortfolio(
    String bearer,
    PortfolioInput input,
  ) async {
    final reply = await _s2(
      'POST',
      '/api/v1/local-portfolios',
      bearer,
      LocalPortfolio.fromJson,
      status: 201,
      body: input.toJson(),
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.name != input.name ||
        reply.value.description != input.description) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalPortfolio>> updatePortfolio(
    String bearer,
    String id,
    PortfolioInput input,
  ) async {
    localUuid(id);
    final reply = await _s2(
      'PUT',
      '/api/v1/local-portfolios/$id',
      bearer,
      LocalPortfolio.fromJson,
      body: input.toJson(),
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.portfolioId != id ||
        reply.value.name != input.name ||
        reply.value.description != input.description) {
      invalidLocalResponse();
    }
    return reply;
  }

  bool _deletion(Object? raw, {required String parent, String? holding}) {
    final keys = holding == null
        ? [
            'scope',
            'contract_version',
            'portfolio_version',
            'portfolio_id',
            'entity_type',
            'deleted',
          ]
        : [
            'scope',
            'contract_version',
            'holding_version',
            'portfolio_id',
            'holding_id',
            'entity_type',
            'deleted',
          ];
    final value = _s2WireObject(raw, keys);
    requireLocalVersion(value);
    if (value['portfolio_id'] != parent ||
        value['deleted'] != true ||
        value['entity_type'] != (holding == null ? 'portfolio' : 'holding') ||
        value[holding == null ? 'portfolio_version' : 'holding_version'] !=
            (holding == null ? 'portfolio.v1' : 'holding.v1') ||
        (holding != null && value['holding_id'] != holding)) {
      invalidLocalResponse();
    }
    return true;
  }

  @override
  Future<LocalS2Reply<bool>> deletePortfolio(String bearer, String id) {
    localUuid(id);
    return _s2(
      'DELETE',
      '/api/v1/local-portfolios/$id',
      bearer,
      (v) => _deletion(v, parent: id),
    );
  }

  @override
  Future<LocalS2Reply<LocalHoldingList>> holdings(
    String bearer,
    String parent,
  ) async {
    localUuid(parent);
    final reply = await _s2(
      'GET',
      '/api/v1/local-portfolios/$parent/holdings',
      bearer,
      LocalHoldingList.fromJson,
    );
    if (reply.value.portfolioId != parent) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalHolding>> holding(
    String bearer,
    String parent,
    String id,
  ) async {
    localUuid(parent);
    localUuid(id);
    final reply = await _s2(
      'GET',
      '/api/v1/local-portfolios/$parent/holdings/$id',
      bearer,
      LocalHolding.fromJson,
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.portfolioId != parent || reply.value.holdingId != id) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalHolding>> createHolding(
    String bearer,
    String parent,
    HoldingInput input,
  ) async {
    localUuid(parent);
    if (input.instrumentId == null) invalidLocalResponse();
    final reply = await _s2(
      'POST',
      '/api/v1/local-portfolios/$parent/holdings',
      bearer,
      LocalHolding.fromJson,
      status: 201,
      body: input.toJson(),
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.portfolioId != parent ||
        reply.value.instrument.instrumentId != input.instrumentId ||
        reply.value.quantity != input.quantity ||
        reply.value.averageCost != input.averageCost) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS2Reply<LocalHolding>> updateHolding(
    String bearer,
    String parent,
    String id,
    HoldingInput input,
  ) async {
    localUuid(parent);
    localUuid(id);
    if (input.instrumentId != null) invalidLocalResponse();
    final reply = await _s2(
      'PUT',
      '/api/v1/local-portfolios/$parent/holdings/$id',
      bearer,
      LocalHolding.fromJson,
      body: input.toJson(),
      asOf: (v) => v.updatedAt,
    );
    if (reply.value.portfolioId != parent ||
        reply.value.holdingId != id ||
        reply.value.quantity != input.quantity ||
        reply.value.averageCost != input.averageCost) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS2Reply<bool>> deleteHolding(
    String bearer,
    String parent,
    String id,
  ) {
    localUuid(parent);
    localUuid(id);
    return _s2(
      'DELETE',
      '/api/v1/local-portfolios/$parent/holdings/$id',
      bearer,
      (v) => _deletion(v, parent: parent, holding: id),
    );
  }

  @override
  Future<LocalS2Reply<LocalPortfolioMetrics>> metrics(
    String bearer,
    String parent,
  ) async {
    localUuid(parent);
    final reply = await _s2(
      'GET',
      '/api/v1/local-portfolios/$parent/metrics',
      bearer,
      LocalPortfolioMetrics.fromJson,
      asOf: (v) => v.dataAsOf,
      dataStatus: (v) => v.dataStatus,
    );
    if (reply.value.portfolioId != parent) invalidLocalResponse();
    return reply;
  }
}
