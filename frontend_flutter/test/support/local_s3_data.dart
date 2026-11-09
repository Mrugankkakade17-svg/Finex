import 'package:frontend_flutter/core/local_application/local_models.dart';

const s3Id = '00000000-0000-4000-8000-000000000197';
const s3OtherId = '00000000-0000-4000-8000-000000000198';
const s3Time = '2030-01-01T00:00:00Z';
const s3FixtureTime = '2026-01-01T00:00:00Z';
Map<String, dynamic> s3Root() => {
  'scope': localApplicationScope,
  'contract_version': localContractVersion,
  'foundation_version': 'market_foundation.v1',
};
// The default fixture is exact and fixed. Capacity/provider fault controls must
// use explicit separate test injection, never a permissive default fallback.
const _defaultInstruments = [
  ('SYN:AAPL', 'Synthetic Apple example', 'EQUITY', 'TECHNOLOGY', '200.0000'),
  ('SYN:BND', 'Synthetic bond-fund example', 'BOND', 'FIXED_INCOME', '80.0000'),
  (
    'SYN:MSFT',
    'Synthetic Microsoft example',
    'EQUITY',
    'TECHNOLOGY',
    '400.0000',
  ),
  (
    'SYN:UNAVAILABLE',
    'Synthetic unavailable-price example',
    'EQUITY',
    'GENERAL',
    null,
  ),
];
(String, String, String, String, String?) _knownInstrument(String id) {
  for (final value in _defaultInstruments) {
    if (value.$1 == id) return value;
  }
  throw const LocalApiException('INSTRUMENT_NOT_FOUND', status: 404);
}

Map<String, dynamic> s3Instrument([String id = 'SYN:AAPL']) {
  final value = _knownInstrument(id);
  return {
    'instrument_id': value.$1,
    'display_name': value.$2,
    'asset_class': value.$3,
    'sector': value.$4,
    'currency': 'USD',
  };
}

Map<String, dynamic> s3Search({String query = '', int limit = 20}) {
  final normalized = query.trim();
  if (limit < 1 ||
      limit > 20 ||
      normalized.runes.length > 80 ||
      RegExp(r'[\x00-\x1f\x7f-\x9f]').hasMatch(normalized)) {
    throw const LocalApiException('VALIDATION_ERROR', status: 422);
  }
  final needle = normalized.toLowerCase();
  final items = _defaultInstruments
      .where(
        (v) =>
            v.$1.toLowerCase().contains(needle) ||
            v.$2.toLowerCase().contains(needle),
      )
      .take(limit)
      .map((v) => s3Instrument(v.$1))
      .toList();
  return {
    ...s3Root(),
    'catalog_version': 'synthetic_catalog.v1',
    'query': normalized,
    'limit': limit,
    'count': items.length,
    'items': items,
  };
}

Map<String, dynamic> s3Quote({String instrument = 'SYN:AAPL', String? status}) {
  final value = _knownInstrument(instrument);
  final actualStatus = status ?? (value.$5 == null ? 'UNAVAILABLE' : 'CACHED');
  return {
    ...s3Root(),
    'catalog_version': 'synthetic_catalog.v1',
    'quote_snapshot_version': 'synthetic_quotes.v1',
    'source': 'finex.synthetic.portfolio',
    'source_type': 'SYNTHETIC',
    'fixture_as_of': s3FixtureTime,
    'instrument_id': instrument,
    'currency': 'USD',
    'status': actualStatus,
    'unit_price': actualStatus == 'UNAVAILABLE' ? null : value.$5,
    'quote_as_of': actualStatus == 'UNAVAILABLE' ? null : s3FixtureTime,
    'fetched_at': s3Time,
    'cache_expires_at': '2030-01-01T00:01:00Z',
    'reason': actualStatus == 'STALE'
        ? 'SYNTHETIC_PROVIDER_STALE'
        : actualStatus == 'UNAVAILABLE'
        ? value.$5 == null
              ? 'SYNTHETIC_QUOTE_UNAVAILABLE'
              : 'SYNTHETIC_PROVIDER_UNAVAILABLE'
        : null,
  };
}

Map<String, dynamic> s3Summary({
  String id = s3Id,
  String name = 'Synthetic list',
  int count = 0,
}) => {
  'watchlist_id': id,
  'name': name,
  'created_at': s3Time,
  'updated_at': s3Time,
  'item_count': count,
};
Map<String, dynamic> s3Item([String id = 'SYN:AAPL']) => {
  ...s3Instrument(id),
  'added_at': s3Time,
};
Map<String, dynamic> s3Watchlist({
  String id = s3Id,
  String name = 'Synthetic list',
  bool item = false,
}) => {
  ...s3Root(),
  'watchlist_version': 'watchlist.v1',
  ...s3Summary(id: id, name: name, count: item ? 1 : 0),
  'items': item ? [s3Item()] : <Object?>[],
};
Map<String, dynamic> s3Watchlists() => {
  ...s3Root(),
  'watchlist_version': 'watchlist.v1',
  'limit': 10,
  'count': 1,
  'items': [s3Summary()],
};
Map<String, dynamic> s3Account({bool opened = true}) => {
  ...s3Root(),
  'paper_account_version': 'paper_account.v1',
  'simulation': true,
  'account': !opened
      ? null
      : {
          'account_id': s3Id,
          'opening_ledger_id': s3OtherId,
          'currency': 'USD',
          'opening_cash': '10000.00',
          'cash_balance': '10000.00',
          'created_at': s3Time,
        },
};
Map<String, dynamic> s3Ledger({int after = 0, int limit = 100}) => {
  ...s3Root(),
  'paper_ledger_version': 'paper_ledger.v1',
  'simulation': true,
  'account_id': s3Id,
  'limit': limit,
  'after_sequence': after,
  'count': after == 0 ? 1 : 0,
  'items': after == 0
      ? [
          {
            'ledger_id': s3OtherId,
            'account_id': s3Id,
            'sequence': 1,
            'entry_type': 'OPENING',
            'cash_delta': '10000.00',
            'cash_after': '10000.00',
            'instrument_id': null,
            'quantity_delta': null,
            'position_after': null,
            'order_id': null,
            'trade_id': null,
            'corrects_ledger_id': null,
            'created_at': s3Time,
          },
        ]
      : <Object?>[],
  'next_cursor': null,
};
Map<String, dynamic> s3Success(
  Map<String, dynamic> data, {
  String status = 'CACHED',
  String? time,
}) => {
  'success': true,
  'message': 'Synthetic reviewed fixture',
  'data': data,
  'meta': {
    'apiVersion': 'v1',
    'dataStatus': status,
    'dataAsOf': time,
    'correlationId': 's3-test',
  },
};
Map<String, dynamic> s3Error(String code) => {
  'success': false,
  'message': 'Safe synthetic failure',
  'error_code': code,
  'detail': 'Safe synthetic failure',
  'error': {
    'code': code,
    'message': 'Safe synthetic failure',
    'fieldErrors': <Object?>[],
    'correlationId': 's3-test',
  },
};
