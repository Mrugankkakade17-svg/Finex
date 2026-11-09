import 'dart:convert';
import 'dart:math';

import 'local_models.dart';

const localQuestionnaireId = 'risk_questionnaire_v1';
const localQuestionnaireVersion = 'v1';
const localScoringVersion = 'deterministic_v1.0.0';
const localExplanationVersion = 'educational_v1.0.0';
const localRiskLimitation =
    'This educational profile is based on self-reported answers and is not individualized financial, legal, tax, or investment advice.';
const localQuoteTime = '2026-01-01T00:00:00Z';
const localPortfolioLimitations = [
  'SYNTHETIC_QUOTES_NOT_MARKET_DATA',
  'MANUAL_HOLDINGS_NOT_BROKER_POSITIONS',
  'SPREAD_IS_ALLOCATION_ONLY',
  'NO_FUND_LOOKTHROUGH_OR_SUITABILITY',
];
final localQuestionIds = List<String>.unmodifiable([
  for (final prefix in ['W', 'C'])
    for (var n = 1; n <= 5; n++) '$prefix$n',
]);

Map<String, dynamic> _exact(
  Object? raw,
  List<String> keys, {
  bool scoped = false,
}) {
  final value = localObject(raw);
  final required = {
    ...keys,
    if (scoped) ...['scope', 'contract_version'],
  };
  if (value.length != required.length || !required.every(value.containsKey)) {
    invalidLocalResponse();
  }
  if (scoped) requireLocalVersion(value);
  return value;
}

String _text(Object? value, {int maximum = 4096, bool trimmed = false}) {
  if (value is! String ||
      value.isEmpty ||
      value.runes.length > maximum ||
      (trimmed && (value != value.trim() || value.trim().isEmpty))) {
    invalidLocalResponse();
  }
  return value;
}

String localUuid(Object? value) {
  if (value is! String ||
      !RegExp(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
      ).hasMatch(value)) {
    invalidLocalResponse();
  }
  return value;
}

String newLocalRetryKey() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
}

List<Object?> _array(Object? value, int maximum) {
  if (value is! List || value.length > maximum) invalidLocalResponse();
  return value;
}

void _literal(Object? value, String expected) {
  if (value != expected) invalidLocalResponse();
}

DateTime? _nullableTime(Map<String, dynamic> value, String key) {
  if (!value.containsKey(key)) invalidLocalResponse();
  return value[key] == null ? null : localUtcTimestamp(value[key]);
}

String _digest(Object? value) {
  if (value is! String || !RegExp(r'^[0-9a-f]{64}$').hasMatch(value)) {
    invalidLocalResponse();
  }
  return value;
}

void _limitation(Object? raw) {
  final value = _exact(raw, ['code', 'message']);
  _literal(value['code'], 'EDUCATIONAL_SELF_REPORTED_PROFILE');
  _literal(value['message'], localRiskLimitation);
}

class LocalRiskAnswer {
  final String questionId;
  final String answerCode;
  LocalRiskAnswer(this.questionId, this.answerCode) {
    if (!localQuestionIds.contains(questionId) ||
        ![
          'A',
          'B',
          'C',
          'D',
          'E',
        ].any((suffix) => answerCode == '${questionId}_$suffix')) {
      invalidLocalResponse();
    }
  }
  factory LocalRiskAnswer.fromJson(Object? raw) {
    final value = _exact(raw, ['question_id', 'answer_code']);
    return LocalRiskAnswer(
      _text(value['question_id'], maximum: 32),
      _text(value['answer_code'], maximum: 32),
    );
  }
  Map<String, Object?> toJson() => {
    'question_id': questionId,
    'answer_code': answerCode,
  };
}

class LocalRiskInput {
  final List<LocalRiskAnswer> answers;
  LocalRiskInput(Iterable<LocalRiskAnswer> values, {bool complete = false})
    : answers = List.unmodifiable(values) {
    if (answers.length > 10 ||
        answers.map((a) => a.questionId).toSet().length != answers.length ||
        (complete && answers.length != 10)) {
      invalidLocalResponse();
    }
  }
  factory LocalRiskInput.fromJson(Object? raw, {bool complete = false}) {
    final value = _exact(raw, [
      'questionnaire_id',
      'questionnaire_version',
      'answers',
    ]);
    _literal(value['questionnaire_id'], localQuestionnaireId);
    _literal(value['questionnaire_version'], localQuestionnaireVersion);
    return LocalRiskInput(
      _array(value['answers'], 10).map(LocalRiskAnswer.fromJson),
      complete: complete,
    );
  }
  Map<String, Object?> toJson() => {
    'questionnaire_id': localQuestionnaireId,
    'questionnaire_version': localQuestionnaireVersion,
    'answers': answers.map((a) => a.toJson()).toList(),
  };
  bool equivalent(LocalRiskInput other) {
    final mine = {for (final a in answers) a.questionId: a.answerCode};
    return mine.length == other.answers.length &&
        other.answers.every((a) => mine[a.questionId] == a.answerCode);
  }
}

class LocalRiskOption {
  final String code;
  final String label;
  const LocalRiskOption(this.code, this.label);
}

class LocalRiskQuestion {
  final String id;
  final String dimension;
  final String text;
  final List<LocalRiskOption> options;
  LocalRiskQuestion(
    this.id,
    this.dimension,
    this.text,
    Iterable<LocalRiskOption> options,
  ) : options = List.unmodifiable(options);
}

class LocalRiskQuestionnaire {
  final List<LocalRiskQuestion> questions;
  final String rulesHash;
  LocalRiskQuestionnaire._(this.questions, this.rulesHash);
  factory LocalRiskQuestionnaire.fromJson(Object? raw) {
    final value = _exact(raw, [
      'questionnaire_id',
      'questionnaire_version',
      'scoring_version',
      'explanation_version',
      'rules_sha256',
      'questions',
      'limitation',
    ], scoped: true);
    _literal(value['questionnaire_id'], localQuestionnaireId);
    _literal(value['questionnaire_version'], localQuestionnaireVersion);
    _literal(value['scoring_version'], localScoringVersion);
    _literal(value['explanation_version'], localExplanationVersion);
    _limitation(value['limitation']);
    final rows = _array(value['questions'], 10);
    if (rows.length != 10) invalidLocalResponse();
    final questions = <LocalRiskQuestion>[];
    for (var index = 0; index < rows.length; index++) {
      final q = _exact(rows[index], [
        'question_id',
        'dimension',
        'text',
        'options',
      ]);
      final id = localQuestionIds[index];
      _literal(q['question_id'], id);
      final dimension = index < 5 ? 'willingness' : 'capacity';
      _literal(q['dimension'], dimension);
      final choices = _array(q['options'], 5);
      if (choices.length != 5) invalidLocalResponse();
      final options = <LocalRiskOption>[];
      for (var number = 0; number < 5; number++) {
        final option = _exact(choices[number], ['code', 'label']);
        final code = '${id}_${['A', 'B', 'C', 'D', 'E'][number]}';
        _literal(option['code'], code);
        options.add(LocalRiskOption(code, _text(option['label'])));
      }
      questions.add(
        LocalRiskQuestion(id, dimension, _text(q['text']), options),
      );
    }
    return LocalRiskQuestionnaire._(
      List.unmodifiable(questions),
      _digest(value['rules_sha256']),
    );
  }
}

class LocalRiskDraft {
  final LocalRiskInput input;
  final DateTime? updatedAt;
  const LocalRiskDraft._(this.input, this.updatedAt);
  factory LocalRiskDraft.fromJson(Object? raw) {
    final value = _exact(raw, [
      'questionnaire_id',
      'questionnaire_version',
      'answers',
      'updated_at',
    ], scoped: true);
    final input = LocalRiskInput.fromJson({
      for (final key in [
        'questionnaire_id',
        'questionnaire_version',
        'answers',
      ])
        key: value[key],
    });
    final time = _nullableTime(value, 'updated_at');
    if (time == null && input.answers.isNotEmpty) invalidLocalResponse();
    return LocalRiskDraft._(input, time);
  }
}

Object? _immutableJson(Object? value, [int depth = 0]) {
  if (depth > 20) invalidLocalResponse();
  if (value == null || value is String || value is bool || value is int) {
    return value;
  }
  if (value is double && value.isFinite) return value;
  if (value is List) {
    return List<Object?>.unmodifiable(
      value.map((item) => _immutableJson(item, depth + 1)),
    );
  }
  if (value is Map<String, dynamic>) {
    return Map<String, Object?>.unmodifiable(
      value.map((key, item) => MapEntry(key, _immutableJson(item, depth + 1))),
    );
  }
  invalidLocalResponse();
}

num _score(Object? value) {
  if (value is! num || !value.isFinite || value < 0 || value > 100) {
    invalidLocalResponse();
  }
  return value;
}

class LocalSavedRiskAssessment {
  final String assessmentId;
  final DateTime createdAt;
  final LocalRiskInput input;
  final num willingness;
  final num capacity;
  final num composite;
  final String category;
  final String? tension;
  final String summary;
  final String dimensions;
  final String method;
  final String rulesHash;
  final Map<String, Object?> rulesSnapshot;
  const LocalSavedRiskAssessment._({
    required this.assessmentId,
    required this.createdAt,
    required this.input,
    required this.willingness,
    required this.capacity,
    required this.composite,
    required this.category,
    required this.tension,
    required this.summary,
    required this.dimensions,
    required this.method,
    required this.rulesHash,
    required this.rulesSnapshot,
  });
  factory LocalSavedRiskAssessment.fromJson(Object? raw) {
    final value = _exact(raw, [
      'persisted',
      'assessment_id',
      'created_at',
      'input',
      'assessment',
      'explanation',
      'explanation_version',
      'rules_sha256',
      'rules_snapshot',
    ], scoped: true);
    if (value['persisted'] != true) invalidLocalResponse();
    _literal(value['explanation_version'], localExplanationVersion);
    final a = _exact(value['assessment'], [
      'contract_version',
      'questionnaire_id',
      'questionnaire_version',
      'scoring_version',
      'willingness_score',
      'capacity_score',
      'composite_score',
      'risk_category',
      'calculated_at',
      'limitation',
      'informational_tension',
    ]);
    _literal(a['contract_version'], 's2-risk-contract/v1.0');
    _literal(a['questionnaire_id'], localQuestionnaireId);
    _literal(a['questionnaire_version'], localQuestionnaireVersion);
    _literal(a['scoring_version'], localScoringVersion);
    _limitation(a['limitation']);
    final created = localUtcTimestamp(value['created_at']);
    if (created != localUtcTimestamp(a['calculated_at'])) {
      invalidLocalResponse();
    }
    final category = _exact(a['risk_category'], ['code', 'label']);
    const names = {
      'CONSERVATIVE': 'Conservative',
      'MODERATE': 'Moderate',
      'AGGRESSIVE': 'Aggressive',
    };
    if (!names.containsKey(category['code']) ||
        names[category['code']] != category['label']) {
      invalidLocalResponse();
    }
    String? tension;
    if (a['informational_tension'] != null) {
      final t = _exact(a['informational_tension'], ['code', 'message']);
      if (![
        'CAPACITY_BELOW_WILLINGNESS',
        'WILLINGNESS_BELOW_CAPACITY',
      ].contains(t['code'])) {
        invalidLocalResponse();
      }
      tension = _text(t['message']);
    }
    final e = _exact(value['explanation'], [
      'summary',
      'dimensions',
      'method',
      'questionnaire_version',
      'scoring_version',
      'calculated_at',
      'limitation',
    ]);
    _literal(e['questionnaire_version'], localQuestionnaireVersion);
    _literal(e['scoring_version'], localScoringVersion);
    _literal(e['limitation'], localRiskLimitation);
    if (localUtcTimestamp(e['calculated_at']) != created) {
      invalidLocalResponse();
    }
    final snapshot = _exact(value['rules_snapshot'], [
      'questionnaire',
      'questions',
      'scoring',
    ]);
    final frozen = _immutableJson(snapshot) as Map<String, Object?>;
    if (utf8.encode(jsonEncode(frozen)).length > 65536) invalidLocalResponse();
    final metadata = localObject(snapshot['questionnaire']);
    _literal(metadata['questionnaire_id'], localQuestionnaireId);
    _literal(metadata['version_label'], localQuestionnaireVersion);
    _literal(metadata['status'], 'APPROVED');
    if (_array(snapshot['questions'], 10).length != 10) invalidLocalResponse();
    _literal(localObject(snapshot['scoring'])['status'], 'APPROVED');
    return LocalSavedRiskAssessment._(
      assessmentId: localUuid(value['assessment_id']),
      createdAt: created,
      input: LocalRiskInput.fromJson(value['input'], complete: true),
      willingness: _score(a['willingness_score']),
      capacity: _score(a['capacity_score']),
      composite: _score(a['composite_score']),
      category: category['label'] as String,
      tension: tension,
      summary: _text(e['summary']),
      dimensions: _text(e['dimensions']),
      method: _text(e['method']),
      rulesHash: _digest(value['rules_sha256']),
      rulesSnapshot: frozen,
    );
  }
}

class LocalRiskHistory {
  final List<LocalSavedRiskAssessment> items;
  final String? nextCursor;
  const LocalRiskHistory._(this.items, this.nextCursor);
  factory LocalRiskHistory.fromJson(Object? raw, {int limit = 2}) {
    if (limit < 1 || limit > 2) invalidLocalResponse();
    final value = _exact(raw, ['items', 'next_cursor'], scoped: true);
    final items = _array(
      value['items'],
      limit,
    ).map(LocalSavedRiskAssessment.fromJson).toList();
    if (items.map((a) => a.assessmentId).toSet().length != items.length) {
      invalidLocalResponse();
    }
    final cursor = value['next_cursor'];
    if (cursor != null) {
      localRiskCursor(cursor);
      if (items.length != limit) invalidLocalResponse();
    }
    return LocalRiskHistory._(List.unmodifiable(items), cursor as String?);
  }
}

String localRiskCursor(Object? value) {
  if (value is! String ||
      !RegExp(r'^[1-9][0-9]{0,18}$').hasMatch(value) ||
      BigInt.parse(value) > BigInt.parse('9223372036854775807')) {
    invalidLocalResponse();
  }
  return value;
}

String _instrument(Object? value) {
  if (value is! String ||
      !RegExp(r'^SYN:[A-Z][A-Z0-9_]{0,31}$').hasMatch(value)) {
    invalidLocalResponse();
  }
  return value;
}

String _group(Object? value) {
  if (value is! String || !RegExp(r'^[A-Z][A-Z0-9_]{0,31}$').hasMatch(value)) {
    invalidLocalResponse();
  }
  return value;
}

String _fixed(
  Object? value,
  int scale, {
  bool signed = false,
  BigInt? minimum,
  BigInt? maximum,
}) {
  if (value is! String ||
      value.length > 40 ||
      !RegExp('^${signed ? '(-)?' : ''}(0|[1-9][0-9]{0,18})\\.[0-9]{$scale}\$')
          .hasMatch(value) ||
      (value.startsWith('-') &&
          BigInt.parse(value.replaceAll('.', '')) == BigInt.zero)) {
    invalidLocalResponse();
  }
  final units = _units(value);
  if ((minimum != null && units < minimum) ||
      (maximum != null && units > maximum)) {
    invalidLocalResponse();
  }
  return value;
}

BigInt _units(String value) => BigInt.parse(value.replaceAll('.', ''));
final _moneyMaximum = BigInt.parse('10000000000000000');
final _gainPercentMaximum = BigInt.parse('100000000000000000000');
String _money(Object? value) =>
    _fixed(value, 2, minimum: BigInt.zero, maximum: _moneyMaximum);
String _boundedFixed(
  Object? value,
  int scale,
  BigInt maximum, {
  bool positive = false,
}) {
  final text = _fixed(value, scale);
  final units = _units(text);
  if (units > maximum || (positive && units == BigInt.zero)) {
    invalidLocalResponse();
  }
  return text;
}

String canonicalLocalNumber(String value, int scale, {required bool positive}) {
  if (value.length > 32 ||
      !RegExp(r'^(0|[1-9][0-9]*)(?:\.[0-9]+)?$').hasMatch(value)) {
    throw const LocalApiException('VALIDATION_ERROR');
  }
  final parts = value.split('.');
  final fraction = parts.length == 2 ? parts[1] : '';
  if (fraction.length > scale) {
    throw const LocalApiException('VALIDATION_ERROR');
  }
  final canonical = '${parts[0]}.${fraction.padRight(scale, '0')}';
  final units = _units(canonical);
  if (units > BigInt.from(1000000) * BigInt.from(10).pow(scale) ||
      (positive && units == BigInt.zero)) {
    throw const LocalApiException('VALIDATION_ERROR');
  }
  return canonical;
}

class PortfolioInput {
  final String name;
  final String? description;
  PortfolioInput({required String name, String? description})
    : name = name.trim(),
      description = description?.trim() {
    if (this.name.isEmpty ||
        this.name.runes.length > 100 ||
        (this.description?.runes.length ?? 0) > 500) {
      throw const LocalApiException('VALIDATION_ERROR');
    }
  }
  Map<String, Object?> toJson() => {
    'portfolio_version': 'portfolio.v1',
    'name': name,
    'description': description,
    'currency': 'USD',
  };
}

class HoldingInput {
  final String? instrumentId;
  final String quantity;
  final String averageCost;
  HoldingInput({
    this.instrumentId,
    required String quantity,
    required String averageCost,
  }) : quantity = canonicalLocalNumber(quantity, 6, positive: true),
       averageCost = canonicalLocalNumber(averageCost, 4, positive: false) {
    if (instrumentId != null) _instrument(instrumentId);
  }
  Map<String, Object?> toJson() => {
    'holding_version': 'holding.v1',
    if (instrumentId != null) 'instrument_id': instrumentId,
    'quantity': quantity,
    'average_cost': averageCost,
    'currency': 'USD',
  };
}

class LocalInstrument {
  final String instrumentId;
  final String displayName;
  final String assetClass;
  final String sector;
  const LocalInstrument._(
    this.instrumentId,
    this.displayName,
    this.assetClass,
    this.sector,
  );
  factory LocalInstrument.fromJson(Object? raw) {
    final value = _exact(raw, [
      'instrument_id',
      'display_name',
      'asset_class',
      'sector',
      'currency',
    ]);
    _literal(value['currency'], 'USD');
    return LocalInstrument._(
      _instrument(value['instrument_id']),
      _text(value['display_name'], maximum: 100, trimmed: true),
      _group(value['asset_class']),
      _group(value['sector']),
    );
  }
}

class LocalInstrumentCatalog {
  final List<LocalInstrument> items;
  const LocalInstrumentCatalog._(this.items);
  factory LocalInstrumentCatalog.fromJson(Object? raw) {
    final value = _exact(raw, [
      'catalog_version',
      'currency',
      'items',
      'count',
    ], scoped: true);
    _literal(value['catalog_version'], 'synthetic_catalog.v1');
    _literal(value['currency'], 'USD');
    final items = _array(
      value['items'],
      128,
    ).map(LocalInstrument.fromJson).toList();
    _count(value['count'], items.length);
    if (items.isEmpty) invalidLocalResponse();
    _sortedUnique(items.map((item) => item.instrumentId).toList());
    return LocalInstrumentCatalog._(List.unmodifiable(items));
  }
}

void _count(Object? count, int length) {
  if (count is! int || count != length) invalidLocalResponse();
}

void _sortedUnique(List<String> values) {
  for (var index = 1; index < values.length; index++) {
    if (values[index - 1].compareTo(values[index]) >= 0) invalidLocalResponse();
  }
}

void _times(DateTime created, DateTime updated) {
  if (updated.isBefore(created)) invalidLocalResponse();
}

class LocalPortfolio {
  final String portfolioId;
  final String name;
  final String? description;
  final DateTime createdAt;
  final DateTime updatedAt;
  const LocalPortfolio._(
    this.portfolioId,
    this.name,
    this.description,
    this.createdAt,
    this.updatedAt,
  );
  factory LocalPortfolio.fromJson(Object? raw) {
    final value = _exact(raw, [
      'portfolio_version',
      'portfolio_id',
      'name',
      'description',
      'currency',
      'created_at',
      'updated_at',
    ], scoped: true);
    _literal(value['portfolio_version'], 'portfolio.v1');
    _literal(value['currency'], 'USD');
    final description = value['description'];
    if (description != null &&
        (description is! String ||
            description != description.trim() ||
            description.runes.length > 500)) {
      invalidLocalResponse();
    }
    final created = localUtcTimestamp(value['created_at']);
    final updated = localUtcTimestamp(value['updated_at']);
    _times(created, updated);
    return LocalPortfolio._(
      localUuid(value['portfolio_id']),
      _text(value['name'], maximum: 100, trimmed: true),
      description as String?,
      created,
      updated,
    );
  }
}

void _orderedRecords(List<(DateTime, String)> keys) {
  for (var i = 1; i < keys.length; i++) {
    final before = keys[i - 1];
    final after = keys[i];
    if (before.$1.isAfter(after.$1) ||
        (before.$1 == after.$1 && before.$2.compareTo(after.$2) >= 0)) {
      invalidLocalResponse();
    }
  }
}

class LocalPortfolioList {
  final List<LocalPortfolio> items;
  const LocalPortfolioList._(this.items);
  factory LocalPortfolioList.fromJson(Object? raw) {
    final value = _exact(raw, [
      'portfolio_version',
      'items',
      'count',
    ], scoped: true);
    _literal(value['portfolio_version'], 'portfolio.v1');
    final items = _array(
      value['items'],
      20,
    ).map(LocalPortfolio.fromJson).toList();
    _count(value['count'], items.length);
    if (items.map((p) => p.portfolioId).toSet().length != items.length) {
      invalidLocalResponse();
    }
    _orderedRecords(items.map((p) => (p.createdAt, p.portfolioId)).toList());
    return LocalPortfolioList._(List.unmodifiable(items));
  }
}

class LocalHolding {
  final String portfolioId;
  final String holdingId;
  final LocalInstrument instrument;
  final String quantity;
  final String averageCost;
  final DateTime createdAt;
  final DateTime updatedAt;
  const LocalHolding._(
    this.portfolioId,
    this.holdingId,
    this.instrument,
    this.quantity,
    this.averageCost,
    this.createdAt,
    this.updatedAt,
  );
  factory LocalHolding.fromJson(Object? raw) {
    final value = _exact(raw, [
      'holding_version',
      'catalog_version',
      'portfolio_id',
      'holding_id',
      'instrument_id',
      'display_name',
      'asset_class',
      'sector',
      'quantity',
      'average_cost',
      'currency',
      'created_at',
      'updated_at',
    ], scoped: true);
    _literal(value['holding_version'], 'holding.v1');
    _literal(value['catalog_version'], 'synthetic_catalog.v1');
    final created = localUtcTimestamp(value['created_at']);
    final updated = localUtcTimestamp(value['updated_at']);
    _times(created, updated);
    final instrument = LocalInstrument.fromJson({
      for (final key in [
        'instrument_id',
        'display_name',
        'asset_class',
        'sector',
        'currency',
      ])
        key: value[key],
    });
    return LocalHolding._(
      localUuid(value['portfolio_id']),
      localUuid(value['holding_id']),
      instrument,
      _boundedFixed(
        value['quantity'],
        6,
        BigInt.from(1000000000000),
        positive: true,
      ),
      _boundedFixed(value['average_cost'], 4, BigInt.from(10000000000)),
      created,
      updated,
    );
  }
}

class LocalHoldingList {
  final String portfolioId;
  final List<LocalHolding> items;
  const LocalHoldingList._(this.portfolioId, this.items);
  factory LocalHoldingList.fromJson(Object? raw) {
    final value = _exact(raw, [
      'holding_version',
      'catalog_version',
      'portfolio_id',
      'items',
      'count',
    ], scoped: true);
    _literal(value['holding_version'], 'holding.v1');
    _literal(value['catalog_version'], 'synthetic_catalog.v1');
    final parent = localUuid(value['portfolio_id']);
    final items = _array(
      value['items'],
      100,
    ).map(LocalHolding.fromJson).toList();
    _count(value['count'], items.length);
    if (items.any((h) => h.portfolioId != parent) ||
        items.map((h) => h.holdingId).toSet().length != items.length ||
        items.map((h) => h.instrument.instrumentId).toSet().length !=
            items.length) {
      invalidLocalResponse();
    }
    _orderedRecords(items.map((h) => (h.createdAt, h.holdingId)).toList());
    return LocalHoldingList._(parent, List.unmodifiable(items));
  }
}

String? _nullableFixed(
  Map<String, dynamic> value,
  String field, {
  int scale = 2,
  bool signed = false,
  BigInt? maximum,
  BigInt? minimum,
}) {
  if (!value.containsKey(field)) invalidLocalResponse();
  if (value[field] == null) return null;
  return _fixed(
    value[field],
    scale,
    signed: signed,
    maximum: maximum ?? _moneyMaximum,
    minimum: minimum ?? (signed ? -_moneyMaximum : BigInt.zero),
  );
}

class LocalPortfolioQuote {
  final String? unitPrice;
  final DateTime? asOf;
  final String status;
  final String? reason;
  const LocalPortfolioQuote._(
    this.unitPrice,
    this.asOf,
    this.status,
    this.reason,
  );
  factory LocalPortfolioQuote.fromJson(Object? raw) {
    final v = _exact(raw, [
      'unit_price',
      'data_status',
      'quote_as_of',
      'reason',
    ]);
    if (v['data_status'] == 'CACHED') {
      final price = _boundedFixed(
        v['unit_price'],
        4,
        BigInt.from(10000000000),
        positive: true,
      );
      final time = localUtcTimestamp(v['quote_as_of']);
      if (time != DateTime.utc(2026) || v['reason'] != null) {
        invalidLocalResponse();
      }
      return LocalPortfolioQuote._(price, time, 'CACHED', null);
    }
    if (v['data_status'] != 'UNAVAILABLE' ||
        v['unit_price'] != null ||
        v['quote_as_of'] != null ||
        v['reason'] != 'SYNTHETIC_QUOTE_UNAVAILABLE') {
      invalidLocalResponse();
    }
    return const LocalPortfolioQuote._(
      null,
      null,
      'UNAVAILABLE',
      'SYNTHETIC_QUOTE_UNAVAILABLE',
    );
  }
}

class LocalMetricHolding {
  final String portfolioId;
  final String holdingId;
  final LocalInstrument instrument;
  final String quantity;
  final String averageCost;
  final String costBasis;
  final LocalPortfolioQuote quote;
  final String? marketValue;
  final String? gainLoss;
  final String? gainPercent;
  final String? weightPercent;
  const LocalMetricHolding._(
    this.portfolioId,
    this.holdingId,
    this.instrument,
    this.quantity,
    this.averageCost,
    this.costBasis,
    this.quote,
    this.marketValue,
    this.gainLoss,
    this.gainPercent,
    this.weightPercent,
  );
  factory LocalMetricHolding.fromJson(Object? raw) {
    final v = _exact(raw, [
      'holding_version',
      'portfolio_id',
      'holding_id',
      'instrument_id',
      'display_name',
      'asset_class',
      'sector',
      'currency',
      'quantity',
      'average_cost',
      'cost_basis',
      'quote',
      'market_value',
      'gain_loss',
      'gain_loss_percent',
      'weight_percent',
    ]);
    _literal(v['holding_version'], 'holding.v1');
    final instrument = LocalInstrument.fromJson({
      for (final key in [
        'instrument_id',
        'display_name',
        'asset_class',
        'sector',
        'currency',
      ])
        key: v[key],
    });
    final quote = LocalPortfolioQuote.fromJson(v['quote']);
    final result = LocalMetricHolding._(
      localUuid(v['portfolio_id']),
      localUuid(v['holding_id']),
      instrument,
      _boundedFixed(
        v['quantity'],
        6,
        BigInt.from(1000000000000),
        positive: true,
      ),
      _boundedFixed(v['average_cost'], 4, BigInt.from(10000000000)),
      _money(v['cost_basis']),
      quote,
      _nullableFixed(v, 'market_value'),
      _nullableFixed(v, 'gain_loss', signed: true),
      _nullableFixed(
        v,
        'gain_loss_percent',
        signed: true,
        minimum: -BigInt.from(10000),
        maximum: _gainPercentMaximum,
      ),
      _nullableFixed(v, 'weight_percent', maximum: BigInt.from(10000)),
    );
    if ((quote.unitPrice == null &&
            (result.marketValue != null ||
                result.gainLoss != null ||
                result.gainPercent != null)) ||
        (quote.unitPrice != null &&
            (result.marketValue == null ||
                result.gainLoss == null ||
                ((result.costBasis == '0.00') !=
                    (result.gainPercent == null))))) {
      invalidLocalResponse();
    }
    return result;
  }
}

class LocalPortfolioAllocation {
  final String group;
  final String marketValue;
  final String? weightPercent;
  const LocalPortfolioAllocation._(
    this.group,
    this.marketValue,
    this.weightPercent,
  );
  factory LocalPortfolioAllocation.fromJson(Object? raw) {
    final v = _exact(raw, ['group', 'market_value', 'weight_percent']);
    return LocalPortfolioAllocation._(
      _group(v['group']),
      _money(v['market_value']),
      _nullableFixed(v, 'weight_percent', maximum: BigInt.from(10000)),
    );
  }
}

List<LocalPortfolioAllocation>? _allocations(Object? raw) {
  if (raw == null) return null;
  final items = _array(
    raw,
    100,
  ).map(LocalPortfolioAllocation.fromJson).toList();
  _sortedUnique(items.map((a) => a.group).toList());
  return List.unmodifiable(items);
}

class LocalPortfolioTotals {
  final String costBasis;
  final String? marketValue;
  final String? gainLoss;
  final String? gainPercent;
  final List<LocalPortfolioAllocation>? assetAllocation;
  final List<LocalPortfolioAllocation>? sectorAllocation;
  final String? concentration;
  final String? hhi;
  final String? spread;
  const LocalPortfolioTotals._(
    this.costBasis,
    this.marketValue,
    this.gainLoss,
    this.gainPercent,
    this.assetAllocation,
    this.sectorAllocation,
    this.concentration,
    this.hhi,
    this.spread,
  );
  factory LocalPortfolioTotals.fromJson(Object? raw) {
    final v = _exact(raw, [
      'cost_basis',
      'market_value',
      'gain_loss',
      'gain_loss_percent',
      'allocation_by_asset_class',
      'allocation_by_sector',
      'concentration_percent',
      'hhi',
      'educational_spread_percent',
    ]);
    return LocalPortfolioTotals._(
      _money(v['cost_basis']),
      _nullableFixed(v, 'market_value'),
      _nullableFixed(v, 'gain_loss', signed: true),
      _nullableFixed(
        v,
        'gain_loss_percent',
        signed: true,
        minimum: -BigInt.from(10000),
        maximum: _gainPercentMaximum,
      ),
      _allocations(v['allocation_by_asset_class']),
      _allocations(v['allocation_by_sector']),
      _nullableFixed(v, 'concentration_percent', maximum: BigInt.from(10000)),
      _nullableFixed(v, 'hhi', scale: 6, maximum: BigInt.from(1000000)),
      _nullableFixed(
        v,
        'educational_spread_percent',
        maximum: BigInt.from(10000),
      ),
    );
  }
}

class LocalPortfolioMetrics {
  final String portfolioId;
  final String status;
  final DateTime calculatedAt;
  final List<String> missingInstrumentIds;
  final List<LocalMetricHolding> holdings;
  final LocalPortfolioTotals totals;
  const LocalPortfolioMetrics._(
    this.portfolioId,
    this.status,
    this.calculatedAt,
    this.missingInstrumentIds,
    this.holdings,
    this.totals,
  );
  factory LocalPortfolioMetrics.fromJson(Object? raw) {
    final v = _exact(raw, [
      'metrics_version',
      'formula_version',
      'catalog_version',
      'quote_snapshot_version',
      'portfolio_id',
      'currency',
      'valuation_status',
      'source',
      'source_type',
      'fixture_as_of',
      'calculated_at',
      'missing_instrument_ids',
      'limitations',
      'holdings',
      'totals',
    ], scoped: true);
    for (final entry in {
      'metrics_version': 'portfolio_metrics.v1',
      'formula_version': 'manual_portfolio_math.v1',
      'catalog_version': 'synthetic_catalog.v1',
      'quote_snapshot_version': 'synthetic_quotes.v1',
      'currency': 'USD',
      'source': 'finex.synthetic.portfolio',
      'source_type': 'SYNTHETIC',
    }.entries) {
      _literal(v[entry.key], entry.value);
    }
    if (localUtcTimestamp(v['fixture_as_of']) != DateTime.utc(2026)) {
      invalidLocalResponse();
    }
    final limitations = _array(v['limitations'], 4);
    if (limitations.length != 4 ||
        List.generate(
          4,
          (i) => limitations[i] == localPortfolioLimitations[i],
        ).contains(false)) {
      invalidLocalResponse();
    }
    final parent = localUuid(v['portfolio_id']);
    final status = v['valuation_status'];
    if (!['EMPTY', 'COMPLETE', 'INCOMPLETE', 'UNAVAILABLE'].contains(status)) {
      invalidLocalResponse();
    }
    final holdings = _array(
      v['holdings'],
      100,
    ).map(LocalMetricHolding.fromJson).toList();
    if (holdings.any((h) => h.portfolioId != parent) ||
        holdings.map((h) => h.holdingId).toSet().length != holdings.length ||
        holdings.map((h) => h.instrument.instrumentId).toSet().length !=
            holdings.length) {
      invalidLocalResponse();
    }
    final missing = _array(
      v['missing_instrument_ids'],
      100,
    ).map(_instrument).toList();
    _sortedUnique(missing);
    final actualMissing =
        holdings
            .where((h) => h.quote.unitPrice == null)
            .map((h) => h.instrument.instrumentId)
            .toList()
          ..sort();
    if (missing.length != actualMissing.length ||
        List.generate(
          missing.length,
          (i) => missing[i] == actualMissing[i],
        ).contains(false)) {
      invalidLocalResponse();
    }
    final totals = LocalPortfolioTotals.fromJson(v['totals']);
    final unavailable = status == 'INCOMPLETE' || status == 'UNAVAILABLE';
    if (status == 'EMPTY') {
      if (holdings.isNotEmpty ||
          totals.costBasis != '0.00' ||
          totals.marketValue != '0.00' ||
          totals.gainLoss != '0.00' ||
          totals.gainPercent != null ||
          totals.assetAllocation?.isEmpty != true ||
          totals.sectorAllocation?.isEmpty != true ||
          totals.concentration != null ||
          totals.hhi != null ||
          totals.spread != null) {
        invalidLocalResponse();
      }
    } else if (holdings.isEmpty) {
      invalidLocalResponse();
    } else if (unavailable) {
      if (missing.isEmpty ||
          (status == 'UNAVAILABLE') != (missing.length == holdings.length) ||
          totals.marketValue != null ||
          totals.gainLoss != null ||
          totals.gainPercent != null ||
          totals.assetAllocation != null ||
          totals.sectorAllocation != null ||
          totals.concentration != null ||
          totals.hhi != null ||
          totals.spread != null ||
          holdings.any((h) => h.weightPercent != null)) {
        invalidLocalResponse();
      }
    } else {
      if (missing.isNotEmpty ||
          totals.marketValue == null ||
          totals.gainLoss == null ||
          ((totals.costBasis == '0.00') != (totals.gainPercent == null)) ||
          totals.assetAllocation == null ||
          totals.sectorAllocation == null) {
        invalidLocalResponse();
      }
      final zero = totals.marketValue == '0.00';
      if ((totals.concentration == null) != zero ||
          (totals.hhi == null) != zero ||
          (totals.spread == null) != zero ||
          holdings.any((h) => (h.weightPercent == null) != zero) ||
          [
            ...totals.assetAllocation!,
            ...totals.sectorAllocation!,
          ].any((a) => (a.weightPercent == null) != zero)) {
        invalidLocalResponse();
      }
      for (final pair in [
        (
          totals.assetAllocation!,
          holdings.map((h) => h.instrument.assetClass).toSet(),
        ),
        (
          totals.sectorAllocation!,
          holdings.map((h) => h.instrument.sector).toSet(),
        ),
      ]) {
        if (pair.$1.length != pair.$2.length ||
            pair.$1.any((a) => !pair.$2.contains(a.group))) {
          invalidLocalResponse();
        }
      }
    }
    return LocalPortfolioMetrics._(
      parent,
      status as String,
      localUtcTimestamp(v['calculated_at']),
      List.unmodifiable(missing),
      List.unmodifiable(holdings),
      totals,
    );
  }
  String get dataStatus => status == 'INCOMPLETE' || status == 'UNAVAILABLE'
      ? 'UNAVAILABLE'
      : 'CACHED';
  DateTime? get dataAsOf => status == 'COMPLETE' ? DateTime.utc(2026) : null;
}

class LocalS2Reply<T> {
  final T value;
  final String dataStatus;
  final DateTime? dataAsOf;
  const LocalS2Reply(this.value, this.dataStatus, this.dataAsOf);
}
