// Replays current original native bytes through public typed methods. This is
// MockClient parity, not a native/browser run. Portfolio corpus v1 has no target
// field: success targets are frozen from ORIGINAL DTOs; null-request errors use
// legal canonical targets/input and prove response mapping only.
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'support/local_s2_corpus.dart';
import 'support/local_s2_data.dart';

const _ids = [
  'catalogue',
  'portfolio_created',
  'portfolio_list',
  'portfolio_detail',
  'portfolio_updated',
  'portfolio_unchanged',
  'portfolio_deleted',
  'holding_created',
  'holding_list',
  'holding_detail',
  'holding_updated',
  'holding_unchanged',
  'holding_deleted',
  'golden_1',
  'golden_2',
  'golden_3',
  'golden_4',
  'golden_5',
  'golden_6',
  'empty',
  'zero_cost',
  'partial',
  'unavailable',
  'session_invalid',
  'onboarding_required',
  'portfolio_not_found',
  'holding_not_found',
  'validation_error',
  'unsupported_instrument',
  'holding_duplicate',
  'portfolio_limit',
];
// Independent frozen string expectations; no client arithmetic or float math.
const _goldens = <List<String?>>[
  ['3500.00', '4000.00', '500.00', '14.29', '50.00', '0.500000', '50.00'],
  ['2500.00', '2000.00', '-500.00', '-20.00', '100.00', '1.000000', '0.00'],
  ['600.00', '600.00', '0.00', '0.00', '33.33', '0.333333', '66.67'],
  ['1.00', '2.02', '1.02', '102.00', '50.00', '0.500000', '50.00'],
  ['1.00', '0.00', '-1.00', '-100.00', null, null, null],
  [
    '1000000000000.00',
    '400000000.00',
    '-999600000000.00',
    '-99.96',
    '100.00',
    '1.000000',
    '0.00',
  ],
];

Map<String, dynamic> _object(Object? value) => value as Map<String, dynamic>;
Map<String, dynamic> _copy(Map<String, dynamic> value) =>
    _object(jsonDecode(jsonEncode(value)));
DateTime? _time(Object? value) =>
    value == null ? null : DateTime.parse(value as String).toUtc();
Map<String, dynamic> _data(LocalS2CorpusCase item) =>
    _object(_object(jsonDecode(item.bodyUtf8))['data']);

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

// Only successful portfolio name/description fields have a documented trim
// boundary. The actual emitted body remains exact public input.toJson().
bool _safeCapturedRequestBody(String raw, LocalS2CorpusCase item) {
  if (item.outcome != 'success' ||
      !['portfolio_create', 'portfolio_update'].contains(item.operation)) {
    return _safeRequestBody(raw, item.request);
  }
  try {
    final request = item.request;
    const keys = {'portfolio_version', 'name', 'description', 'currency'};
    if (request == null ||
        request.length != keys.length ||
        !keys.every(request.containsKey) ||
        request['portfolio_version'] != 'portfolio.v1' ||
        request['currency'] != 'USD') {
      return false;
    }
    final input = PortfolioInput(
      name: request['name'] as String,
      description: request['description'] as String?,
    );
    final canonicalRequest = {
      ...request,
      'name': (request['name'] as String).trim(),
      'description': (request['description'] as String?)?.trim(),
    };
    return _same(input.toJson(), canonicalRequest) &&
        _safeRequestBody(raw, canonicalRequest);
  } catch (_) {
    // Do not expose request/parser diagnostics, including memory-only bearer.
    return false;
  }
}

LocalS2Corpus _portfolioTrimUnitCorpus(String id, {bool padded = true}) {
  final record = portfolioData(name: 'Synthetic trim boundary');
  record['description'] = 'Synthetic note';
  final originalResponse = s2Envelope(record, asOf: s2Time);
  final input = PortfolioInput(
    name: record['name'] as String,
    description: record['description'] as String,
  );
  final request = Map<String, dynamic>.from(input.toJson());
  if (padded) {
    request['name'] = ' \t${request['name']}\n ';
    request['description'] = ' \t${request['description']}\n ';
  }
  LocalS2CorpusCase item(
    String caseId,
    String operation,
    String response,
    Map<String, dynamic>? request,
  ) => LocalS2CorpusCase(
    id: caseId,
    operation: operation,
    target: null,
    request: request,
    status: 200,
    contentType: 'application/json',
    bodyUtf8: response,
    outcome: 'success',
    errorCode: null,
  );
  // This is a minimal synthetic dispatch unit, not a configured loader/native
  // corpus. No native artifact or runtime/source provenance is substituted.
  return LocalS2Corpus(
    kind: LocalS2CorpusKind.portfolio,
    originalBytes: Uint8List.fromList(utf8.encode('{"unit_only":true}')),
    document: const {'unit_only': true},
    report: const {'native_acceptance': false},
    cases: [
      item('portfolio_detail', 'portfolio_detail', originalResponse, null),
      item(
        'holding_detail',
        'holding_detail',
        s2Envelope(holdingData(), asOf: s2Time),
        null,
      ),
      item(id, 'portfolio_update', originalResponse, request),
    ],
  );
}

LocalS2CorpusCase _capturedUnitRequest(
  LocalS2CorpusCase original,
  Map<String, dynamic> request, {
  String? operation,
}) => LocalS2CorpusCase(
  id: original.id,
  operation: operation ?? original.operation,
  target: original.target,
  request: request,
  status: original.status,
  contentType: original.contentType,
  bodyUtf8: original.bodyUtf8,
  outcome: original.outcome,
  errorCode: original.errorCode,
);

String _memoryBearer() => base64Url
    .encode(List.generate(32, (_) => Random.secure().nextInt(256)))
    .replaceAll('=', '');

class _PortfolioDispatch {
  final String method;
  final String path;
  final Map<String, dynamic>? expectedRequest;
  final Future<LocalS2Reply<Object>> Function(HttpLocalApplicationApi, String)
  invoke;

  const _PortfolioDispatch({
    required this.method,
    required this.path,
    required this.expectedRequest,
    required this.invoke,
  });
}

_PortfolioDispatch _dispatch(LocalS2Corpus corpus, LocalS2CorpusCase item) {
  const root = '/api/v1/local-portfolios';
  final success = item.outcome == 'success';
  final original = success ? _copy(_data(item)) : null;
  final request = item.request == null ? null : _copy(item.request!);
  final parent = success && original!['portfolio_id'] != null
      ? original['portfolio_id'] as String
      : _data(corpus.caseById('portfolio_detail'))['portfolio_id'] as String;
  final holding = success && original!['holding_id'] != null
      ? original['holding_id'] as String
      : _data(corpus.caseById('holding_detail'))['holding_id'] as String;
  if (item.operation == 'catalogue') {
    return _PortfolioDispatch(
      method: 'GET',
      path: '$root/instruments',
      expectedRequest: null,
      invoke: (api, token) => api.instruments(token),
    );
  }
  if (item.operation == 'portfolio_list') {
    return _PortfolioDispatch(
      method: 'GET',
      path: root,
      expectedRequest: null,
      invoke: (api, token) => api.portfolios(token),
    );
  }
  if (item.operation == 'portfolio_detail') {
    return _PortfolioDispatch(
      method: 'GET',
      path: '$root/$parent',
      expectedRequest: null,
      invoke: (api, token) => api.portfolio(token, parent),
    );
  }
  if (item.operation == 'portfolio_create' ||
      item.operation == 'portfolio_update') {
    final input = success
        ? PortfolioInput(
            name: request!['name'] as String,
            description: request['description'] as String?,
          )
        : PortfolioInput(name: 'Synthetic legal response probe');
    final create = item.operation == 'portfolio_create';
    return _PortfolioDispatch(
      method: create ? 'POST' : 'PUT',
      path: create ? root : '$root/$parent',
      expectedRequest: Map<String, dynamic>.from(input.toJson()),
      invoke: (api, token) => create
          ? api.createPortfolio(token, input)
          : api.updatePortfolio(token, parent, input),
    );
  }
  if (item.operation == 'portfolio_delete') {
    return _PortfolioDispatch(
      method: 'DELETE',
      path: '$root/$parent',
      expectedRequest: null,
      invoke: (api, token) => api.deletePortfolio(token, parent),
    );
  }
  if (item.operation == 'holding_list') {
    return _PortfolioDispatch(
      method: 'GET',
      path: '$root/$parent/holdings',
      expectedRequest: null,
      invoke: (api, token) => api.holdings(token, parent),
    );
  }
  if (item.operation == 'holding_detail') {
    return _PortfolioDispatch(
      method: 'GET',
      path: '$root/$parent/holdings/$holding',
      expectedRequest: null,
      invoke: (api, token) => api.holding(token, parent, holding),
    );
  }
  if (item.operation == 'holding_create' ||
      item.operation == 'holding_update') {
    final create = item.operation == 'holding_create';
    final input = success
        ? HoldingInput(
            instrumentId: create ? request!['instrument_id'] as String : null,
            quantity: request!['quantity'] as String,
            averageCost: request['average_cost'] as String,
          )
        : HoldingInput(
            instrumentId: create ? 'SYN:AAPL' : null,
            quantity: '1.000000',
            averageCost: '0.0000',
          );
    return _PortfolioDispatch(
      method: create ? 'POST' : 'PUT',
      path: create
          ? '$root/$parent/holdings'
          : '$root/$parent/holdings/$holding',
      expectedRequest: Map<String, dynamic>.from(input.toJson()),
      invoke: (api, token) => create
          ? api.createHolding(token, parent, input)
          : api.updateHolding(token, parent, holding, input),
    );
  }
  if (item.operation == 'holding_delete') {
    return _PortfolioDispatch(
      method: 'DELETE',
      path: '$root/$parent/holdings/$holding',
      expectedRequest: null,
      invoke: (api, token) => api.deleteHolding(token, parent, holding),
    );
  }
  if (item.operation == 'metrics') {
    return _PortfolioDispatch(
      method: 'GET',
      path: '$root/$parent/metrics',
      expectedRequest: null,
      invoke: (api, token) => api.metrics(token, parent),
    );
  }
  throw StateError('Unsupported bounded portfolio corpus operation.');
}

HttpLocalApplicationApi _api(
  LocalS2CorpusCase item,
  _PortfolioDispatch dispatch,
  String token, {
  String? responseBody,
}) => HttpLocalApplicationApi(
  Uri.parse('http://127.0.0.1:8082'),
  client: MockClient((request) async {
    expect(request.method == dispatch.method, isTrue);
    expect(request.url.path == dispatch.path, isTrue);
    expect(request.url.query.isEmpty, isTrue);
    expect(request.headers['authorization'] == 'Bearer $token', isTrue);
    expect(request.headers.containsKey('cookie'), isFalse);
    expect(request.followRedirects, isFalse);
    expect(_safeRequestBody(request.body, dispatch.expectedRequest), isTrue);
    if (item.outcome == 'success' && item.request != null) {
      expect(_safeCapturedRequestBody(request.body, item), isTrue);
    }
    return http.Response.bytes(
      utf8.encode(responseBody ?? item.bodyUtf8),
      item.status,
      headers: {'content-type': item.contentType},
    );
  }),
);

Map<String, Object?> _instrument(LocalInstrument value) => {
  'instrument_id': value.instrumentId,
  'display_name': value.displayName,
  'asset_class': value.assetClass,
  'sector': value.sector,
  'currency': 'USD',
};

void _expectPortfolio(LocalPortfolio value, Map<String, dynamic> raw) {
  expect(value.portfolioId == raw['portfolio_id'], isTrue);
  expect(value.name == raw['name'], isTrue);
  expect(value.description == raw['description'], isTrue);
  expect(value.createdAt == _time(raw['created_at']), isTrue);
  expect(value.updatedAt == _time(raw['updated_at']), isTrue);
}

void _expectHolding(LocalHolding value, Map<String, dynamic> raw) {
  expect(value.portfolioId == raw['portfolio_id'], isTrue);
  expect(value.holdingId == raw['holding_id'], isTrue);
  expect(value.quantity == raw['quantity'], isTrue);
  expect(value.averageCost == raw['average_cost'], isTrue);
  expect(value.createdAt == _time(raw['created_at']), isTrue);
  expect(value.updatedAt == _time(raw['updated_at']), isTrue);
  expect(
    _same(_instrument(value.instrument), {
      for (final key in [
        'instrument_id',
        'display_name',
        'asset_class',
        'sector',
        'currency',
      ])
        key: raw[key],
    }),
    isTrue,
  );
}

Object? _allocations(List<LocalPortfolioAllocation>? values) => values == null
    ? null
    : [
        for (final value in values)
          {
            'group': value.group,
            'market_value': value.marketValue,
            'weight_percent': value.weightPercent,
          },
      ];

Map<String, Object?> _totals(LocalPortfolioTotals value) => {
  'cost_basis': value.costBasis,
  'market_value': value.marketValue,
  'gain_loss': value.gainLoss,
  'gain_loss_percent': value.gainPercent,
  'allocation_by_asset_class': _allocations(value.assetAllocation),
  'allocation_by_sector': _allocations(value.sectorAllocation),
  'concentration_percent': value.concentration,
  'hhi': value.hhi,
  'educational_spread_percent': value.spread,
};

void _expectMetrics(LocalPortfolioMetrics value, Map<String, dynamic> raw) {
  expect(value.portfolioId == raw['portfolio_id'], isTrue);
  expect(value.status == raw['valuation_status'], isTrue);
  expect(value.calculatedAt == _time(raw['calculated_at']), isTrue);
  expect(
    _same(value.missingInstrumentIds, raw['missing_instrument_ids']),
    isTrue,
  );
  expect(_same(_totals(value.totals), raw['totals']), isTrue);
  final rows = (raw['holdings'] as List).cast<Map<String, dynamic>>();
  expect(value.holdings.length == rows.length, isTrue);
  for (var index = 0; index < rows.length; index++) {
    final actual = value.holdings[index];
    final row = rows[index];
    expect(
      _same({
        'holding_version': 'holding.v1',
        'portfolio_id': actual.portfolioId,
        'holding_id': actual.holdingId,
        ..._instrument(actual.instrument),
        'quantity': actual.quantity,
        'average_cost': actual.averageCost,
        'cost_basis': actual.costBasis,
        'market_value': actual.marketValue,
        'gain_loss': actual.gainLoss,
        'gain_loss_percent': actual.gainPercent,
        'weight_percent': actual.weightPercent,
      }, {...row}..remove('quote')),
      isTrue,
    );
    final quote = _object(row['quote']);
    expect(actual.quote.unitPrice == quote['unit_price'], isTrue);
    expect(actual.quote.status == quote['data_status'], isTrue);
    expect(actual.quote.asOf == _time(quote['quote_as_of']), isTrue);
    expect(actual.quote.reason == quote['reason'], isTrue);
  }
}

void _expectReply(LocalS2Reply<Object> reply, LocalS2CorpusCase item) {
  final body = _object(jsonDecode(item.bodyUtf8));
  final data = _object(body['data']);
  final meta = _object(body['meta']);
  expect(reply.dataStatus == meta['dataStatus'], isTrue);
  expect(reply.dataAsOf == _time(meta['dataAsOf']), isTrue);
  final value = reply.value;
  if (value is LocalInstrumentCatalog) {
    expect(_same(value.items.map(_instrument).toList(), data['items']), isTrue);
    expect(value.items.length == data['count'], isTrue);
  } else if (value is LocalPortfolio) {
    _expectPortfolio(value, data);
  } else if (value is LocalHolding) {
    _expectHolding(value, data);
  } else if (value is LocalPortfolioList) {
    final rows = (data['items'] as List).cast<Map<String, dynamic>>();
    expect(value.items.length == data['count'], isTrue);
    expect(
      _same(
        value.items.map((row) => row.portfolioId).toList(),
        rows.map((row) => row['portfolio_id']).toList(),
      ),
      isTrue,
    );
    for (var index = 0; index < rows.length; index++) {
      _expectPortfolio(value.items[index], rows[index]);
    }
  } else if (value is LocalHoldingList) {
    final rows = (data['items'] as List).cast<Map<String, dynamic>>();
    expect(value.portfolioId == data['portfolio_id'], isTrue);
    expect(value.items.length == data['count'], isTrue);
    expect(
      _same(
        value.items.map((row) => row.holdingId).toList(),
        rows.map((row) => row['holding_id']).toList(),
      ),
      isTrue,
    );
    for (var index = 0; index < rows.length; index++) {
      _expectHolding(value.items[index], rows[index]);
    }
  } else if (value is LocalPortfolioMetrics) {
    _expectMetrics(value, data);
  } else if (value is bool) {
    expect(value, isTrue);
    expect(data['deleted'] == true, isTrue);
  } else {
    fail('The public portfolio method returned an unexpected safe type.');
  }
}

void main() {
  test(
    'portfolio parity diagnostic comparer rejects malformed input safely',
    () {
      final marker = _memoryBearer();
      var safelyRejected = false;
      try {
        safelyRejected = !_safeRequestBody('{"token":"$marker"', {});
      } catch (_) {}
      expect(safelyRejected, isTrue);
      expect(
        _safeRequestBody(jsonEncode({'authorization': marker}), {}),
        isFalse,
      );
      expect(_safeRequestBody('', null), isTrue);
    },
  );

  for (final id in ['portfolio_updated', 'portfolio_unchanged']) {
    test('portfolio trim boundary public replay accepts original padded $id', () async {
      final corpus = _portfolioTrimUnitCorpus(id);
      final item = corpus.caseById(id);
      final originalRequest = jsonEncode(item.request);
      final originalResponse = item.bodyUtf8;
      final input = PortfolioInput(
        name: item.request!['name'] as String,
        description: item.request!['description'] as String,
      );
      final dispatch = _dispatch(corpus, item);
      // _api also requires the outgoing HTTP body to equal this exact public
      // input.toJson(); padded captures are NOT claimed as exact emitted bytes.
      expect(_same(dispatch.expectedRequest, input.toJson()), isTrue);
      final token = _memoryBearer();
      final api = _api(item, dispatch, token);
      addTearDown(api.close);
      _expectReply(await dispatch.invoke(api, token), item);
      expect(jsonEncode(item.request) == originalRequest, isTrue);
      expect(item.bodyUtf8 == originalResponse, isTrue);
    });
  }

  test('portfolio trim boundary comparer keeps canonical exact control', () {
    final item = _portfolioTrimUnitCorpus(
      'portfolio_updated',
      padded: false,
    ).caseById('portfolio_updated');
    expect(_safeCapturedRequestBody(jsonEncode(item.request), item), isTrue);
  });
  final capturedMutations = <String, void Function(Map<String, dynamic>)>{
    'interior name alteration': (value) =>
        value['name'] = (value['name'] as String).replaceFirst(' ', '  '),
    'different name': (value) => value['name'] = 'Different synthetic name',
    'different description': (value) => value['description'] = 'Different note',
    'null description': (value) => value['description'] = null,
    'empty description': (value) => value['description'] = '',
    'wrong name type': (value) => value['name'] = true,
    'wrong description type': (value) => value['description'] = 1,
    'wrong version': (value) => value['portfolio_version'] = 'portfolio.v0',
    'wrong currency': (value) => value['currency'] = 'EUR',
    'extra field': (value) => value['unexpected'] = true,
    'private field': (value) =>
        value['secret'] = 'synthetic-private-trim-marker',
  };
  for (final entry in capturedMutations.entries) {
    test('portfolio trim boundary comparer rejects ${entry.key}', () {
      final item = _portfolioTrimUnitCorpus(
        'portfolio_updated',
        padded: false,
      ).caseById('portfolio_updated');
      final outgoing = jsonEncode(item.request);
      final changed = _copy(item.request!);
      entry.value(changed);
      expect(
        _safeCapturedRequestBody(outgoing, _capturedUnitRequest(item, changed)),
        isFalse,
      );
    });
  }
  for (final operation in ['holding_update', 'draft_put', 'portfolio_detail']) {
    test('portfolio trim boundary comparer stays exact for $operation', () {
      final item = _portfolioTrimUnitCorpus('portfolio_updated')
          .caseById('portfolio_updated');
      final input = PortfolioInput(
        name: item.request!['name'] as String,
        description: item.request!['description'] as String,
      );
      expect(
        _safeCapturedRequestBody(
          jsonEncode(input.toJson()),
          _capturedUnitRequest(item, item.request!, operation: operation),
        ),
        isFalse,
      );
    });
  }

  final pair = loadLocalS2Corpora(Platform.environment);
  if (pair == null) {
    test(
      'current portfolio native corpus replay is not claimed without inputs',
      () {},
      skip: 'Optional complete native inputs absent; required/partial inputs must fail the loader.',
    );
    return;
  }
  final corpus = pair.portfolio;
  for (final id in _ids) {
    test('current raw UTF8 public portfolio parity: $id', () async {
      final item = corpus.caseById(id);
      final dispatch = _dispatch(corpus, item);
      final token = _memoryBearer();
      final api = _api(item, dispatch, token);
      addTearDown(api.close);
      if (item.outcome == 'error') {
        // These targets are legal canonical test targets, NOT the unrecorded
        // native error URL. Native driver/HTTP tests separately prove routing.
        await expectLater(
          dispatch.invoke(api, token),
          throwsA(
            isA<LocalApiException>()
                .having((error) => error.code, 'safe API code', item.errorCode)
                .having((error) => error.status, 'HTTP status', item.status),
          ),
        );
      } else {
        _expectReply(await dispatch.invoke(api, token), item);
      }
    });
  }
  for (var index = 0; index < _goldens.length; index++) {
    test(
      'native golden ${index + 1} exact server strings, without recalculation',
      () async {
        final item = corpus.caseById('golden_${index + 1}');
        final dispatch = _dispatch(corpus, item);
        final token = _memoryBearer();
        final api = _api(item, dispatch, token);
        addTearDown(api.close);
        final result =
            (await dispatch.invoke(api, token)).value as LocalPortfolioMetrics;
        final totals = result.totals;
        expect(
          _same([
            totals.costBasis,
            totals.marketValue,
            totals.gainLoss,
            totals.gainPercent,
            totals.concentration,
            totals.hhi,
            totals.spread,
          ], _goldens[index]),
          isTrue,
        );
        expect(result.status, 'COMPLETE');
        if (index == 2) {
          expect(
            result.holdings.every((row) => row.weightPercent == '33.33'),
            isTrue,
          );
        }
        if (index == 4) {
          expect(
            result.holdings.every((row) => row.weightPercent == null),
            isTrue,
          );
          expect(
            totals.assetAllocation!.every((row) => row.weightPercent == null),
            isTrue,
          );
        }
      },
    );
  }
  for (final id in ['empty', 'zero_cost', 'partial', 'unavailable']) {
    test('native $id preserves honest nullable server results', () async {
      final item = corpus.caseById(id);
      final dispatch = _dispatch(corpus, item);
      final token = _memoryBearer();
      final api = _api(item, dispatch, token);
      addTearDown(api.close);
      final reply = await dispatch.invoke(api, token);
      final value = reply.value as LocalPortfolioMetrics;
      if (id == 'empty') {
        expect(value.status, 'EMPTY');
        expect(value.holdings.isEmpty, isTrue);
        expect(value.totals.marketValue, '0.00');
        expect(value.totals.assetAllocation!.isEmpty, isTrue);
        expect(reply.dataAsOf, isNull);
      } else if (id == 'zero_cost') {
        expect(value.totals.costBasis, '0.00');
        expect(value.totals.gainPercent, isNull);
        expect(value.totals.gainLoss, '2000.00');
      } else {
        expect(value.status, id == 'partial' ? 'INCOMPLETE' : 'UNAVAILABLE');
        expect(reply.dataStatus, 'UNAVAILABLE');
        expect(reply.dataAsOf, isNull);
        expect(value.totals.marketValue, isNull);
        expect(value.totals.gainLoss, isNull);
        expect(value.totals.gainPercent, isNull);
        expect(value.totals.assetAllocation, isNull);
        expect(value.totals.sectorAllocation, isNull);
        expect(value.totals.concentration, isNull);
        expect(value.totals.hhi, isNull);
        expect(value.totals.spread, isNull);
        expect(
          value.holdings.every((row) => row.weightPercent == null),
          isTrue,
        );
        expect(value.missingInstrumentIds.isNotEmpty, isTrue);
      }
    });
  }
  for (final id in [
    'portfolio_detail',
    'holding_detail',
    'holding_list',
    'portfolio_deleted',
    'holding_deleted',
    'golden_1',
  ]) {
    test(
      'mutated $id response cannot retarget original public dispatch',
      () async {
        final item = corpus.caseById(id);
        final dispatch = _dispatch(corpus, item);
        final body = _object(jsonDecode(item.bodyUtf8));
        final data = _object(body['data']);
        final other = newLocalRetryKey();
        if (id == 'holding_detail' || id == 'holding_deleted') {
          data['holding_id'] = other;
        } else {
          data['portfolio_id'] = other;
          if (id == 'holding_list' || id == 'golden_1') {
            for (final row
                in (data[id == 'holding_list' ? 'items' : 'holdings']
                    as List)) {
              _object(row)['portfolio_id'] = other;
            }
          }
        }
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
  }
  test(
    'no-op portfolio and holding updates retain original UTC instants',
    () async {
      for (final prefix in ['portfolio', 'holding']) {
        final updated = corpus.caseById('${prefix}_updated');
        final unchanged = corpus.caseById('${prefix}_unchanged');
        final first = _data(updated);
        final again = _data(unchanged);
        expect(
          _time(first['created_at']) == _time(again['created_at']),
          isTrue,
        );
        expect(
          _time(first['updated_at']) == _time(again['updated_at']),
          isTrue,
        );
        expect(
          _same(
            {...first}
              ..remove('created_at')
              ..remove('updated_at'),
            {...again}
              ..remove('created_at')
              ..remove('updated_at'),
          ),
          isTrue,
        );
      }
    },
  );
}
