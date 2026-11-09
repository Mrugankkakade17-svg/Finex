import 'local_models.dart';
import 'local_s2_models.dart';

const localFoundationVersion = 'market_foundation.v1';
const localS3CatalogueVersion = 'synthetic_catalog.v1';
const localS3FixtureTime = '2026-01-01T00:00:00Z';

Map<String, dynamic> s3Object(
  Object? raw,
  Iterable<String> keys, {
  bool scoped = true,
}) {
  final value = localObject(raw);
  final required = {
    ...keys,
    if (scoped) ...['scope', 'contract_version', 'foundation_version'],
  };
  if (value.length != required.length || !required.every(value.containsKey)) {
    invalidLocalResponse();
  }
  if (scoped) {
    requireLocalVersion(value);
    if (value['foundation_version'] != localFoundationVersion) {
      invalidLocalResponse();
    }
  }
  return value;
}

int localS3Integer(Object? value, {int maximum = 9007199254740991}) {
  if (value is! int || value < 0 || value > maximum) invalidLocalResponse();
  return value;
}

String localS3Name(String raw) {
  final value = raw.trim();
  if (value.isEmpty ||
      value.runes.length > 100 ||
      RegExp(r'[\x00-\x1f\x7f-\x9f]').hasMatch(value)) {
    throw const LocalApiException('VALIDATION_ERROR', fields: {'name'});
  }
  return value;
}

String localS3Query(String raw) {
  final value = raw.trim();
  if (value.runes.length > 80 ||
      RegExp(r'[\x00-\x1f\x7f-\x9f]').hasMatch(value)) {
    throw const LocalApiException('VALIDATION_ERROR', fields: {'query'});
  }
  return value;
}

String localS3InstrumentId(Object? raw) {
  if (raw is! String || !RegExp(r'^SYN:[A-Z][A-Z0-9_]{0,31}$').hasMatch(raw)) {
    invalidLocalResponse();
  }
  return raw;
}

List<Object?> _s3Array(Object? raw, int maximum) {
  if (raw is! List || raw.length > maximum) invalidLocalResponse();
  return raw;
}

void _s3Version(Object? raw, String version) {
  if (raw != version) invalidLocalResponse();
}

DateTime? _s3NullableTime(Object? raw) =>
    raw == null ? null : localUtcTimestamp(raw);

const _summaryKeys = [
  'watchlist_id',
  'name',
  'created_at',
  'updated_at',
  'item_count',
];
const _instrumentKeys = [
  'instrument_id',
  'display_name',
  'asset_class',
  'sector',
  'currency',
];

LocalWatchlistSummary _s3Summary(Map<String, dynamic> raw) {
  final name = raw['name'];
  if (name is! String ||
      name != name.trim() ||
      name.isEmpty ||
      name.runes.length > 100 ||
      RegExp(r'[\x00-\x1f\x7f-\x9f]').hasMatch(name)) {
    invalidLocalResponse();
  }
  final created = localUtcTimestamp(raw['created_at']);
  final updated = localUtcTimestamp(raw['updated_at']);
  if (updated.isBefore(created)) invalidLocalResponse();
  return LocalWatchlistSummary._(
    localUuid(raw['watchlist_id']),
    name,
    created,
    updated,
    localS3Integer(raw['item_count'], maximum: 100),
  );
}

LocalWatchlistItem _s3Item(Object? raw) {
  final value = s3Object(raw, [..._instrumentKeys, 'added_at'], scoped: false);
  return LocalWatchlistItem._(
    LocalInstrument.fromJson({
      for (final key in _instrumentKeys) key: value[key],
    }),
    localUtcTimestamp(value['added_at']),
  );
}

class LocalS3Reply<T> {
  final T value;
  final String dataStatus;
  final DateTime? dataAsOf;
  const LocalS3Reply(this.value, this.dataStatus, this.dataAsOf);
}

class LocalMarketSearch {
  final String query;
  final int limit;
  final List<LocalInstrument> items;
  LocalMarketSearch._(this.query, this.limit, this.items);
  factory LocalMarketSearch.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'catalog_version',
      'query',
      'limit',
      'count',
      'items',
    ]);
    _s3Version(value['catalog_version'], localS3CatalogueVersion);
    final query = value['query'];
    if (query is! String ||
        query != query.trim() ||
        query.runes.length > 80 ||
        RegExp(r'[\x00-\x1f\x7f-\x9f]').hasMatch(query)) {
      invalidLocalResponse();
    }
    final limit = localS3Integer(value['limit'], maximum: 20);
    if (limit < 1) invalidLocalResponse();
    final items = _s3Array(
      value['items'],
      limit,
    ).map(LocalInstrument.fromJson).toList();
    if (localS3Integer(value['count'], maximum: limit) != items.length) {
      invalidLocalResponse();
    }
    for (var i = 0; i < items.length; i++) {
      localS3InstrumentId(items[i].instrumentId);
      if (i > 0 &&
          items[i - 1].instrumentId.compareTo(items[i].instrumentId) >= 0) {
        invalidLocalResponse();
      }
    }
    return LocalMarketSearch._(query, limit, List.unmodifiable(items));
  }
}

class LocalMarketQuote {
  final String instrumentId;
  final String status;
  final String? unitPrice;
  final DateTime? quoteAsOf;
  final DateTime? fetchedAt;
  final DateTime? cacheExpiresAt;
  final String? reason;
  LocalMarketQuote._(
    this.instrumentId,
    this.status,
    this.unitPrice,
    this.quoteAsOf,
    this.fetchedAt,
    this.cacheExpiresAt,
    this.reason,
  );
  String get dataStatus => status == 'UNAVAILABLE' ? 'UNAVAILABLE' : 'CACHED';
  factory LocalMarketQuote.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'catalog_version',
      'quote_snapshot_version',
      'source',
      'source_type',
      'fixture_as_of',
      'instrument_id',
      'currency',
      'status',
      'unit_price',
      'quote_as_of',
      'fetched_at',
      'cache_expires_at',
      'reason',
    ]);
    _s3Version(value['catalog_version'], localS3CatalogueVersion);
    _s3Version(value['quote_snapshot_version'], 'synthetic_quotes.v1');
    _s3Version(value['source'], 'finex.synthetic.portfolio');
    _s3Version(value['source_type'], 'SYNTHETIC');
    _s3Version(value['currency'], 'USD');
    _s3Version(value['fixture_as_of'], localS3FixtureTime);
    final fixture = localUtcTimestamp(value['fixture_as_of']);
    if (fixture != localUtcTimestamp(localS3FixtureTime)) {
      invalidLocalResponse();
    }
    final status = value['status'];
    if (!['CACHED', 'STALE', 'UNAVAILABLE'].contains(status)) {
      invalidLocalResponse();
    }
    final price = value['unit_price'];
    if (price != null) {
      if (price is! String ||
          !RegExp(r'^(0|[1-9][0-9]*)\.[0-9]{4}$').hasMatch(price) ||
          price.length > 12) {
        invalidLocalResponse();
      }
      final units = BigInt.parse(price.replaceAll('.', ''));
      if (units <= BigInt.zero || units > BigInt.from(10000000000)) {
        invalidLocalResponse();
      }
    }
    final quote = _s3NullableTime(value['quote_as_of']);
    final fetched = _s3NullableTime(value['fetched_at']);
    final expires = _s3NullableTime(value['cache_expires_at']);
    final reason = value['reason'];
    if ((fetched == null) != (expires == null) ||
        (fetched != null &&
            expires!.difference(fetched) != const Duration(seconds: 60))) {
      invalidLocalResponse();
    }
    if (status == 'UNAVAILABLE') {
      if (price != null ||
          quote != null ||
          ![
            'SYNTHETIC_QUOTE_UNAVAILABLE',
            'SYNTHETIC_PROVIDER_UNAVAILABLE',
          ].contains(reason) ||
          (reason == 'SYNTHETIC_QUOTE_UNAVAILABLE' && fetched == null)) {
        invalidLocalResponse();
      }
    } else if (price == null ||
        value['quote_as_of'] != localS3FixtureTime ||
        quote != fixture ||
        fetched == null ||
        reason != (status == 'STALE' ? 'SYNTHETIC_PROVIDER_STALE' : null)) {
      invalidLocalResponse();
    }
    return LocalMarketQuote._(
      localS3InstrumentId(value['instrument_id']),
      status as String,
      price as String?,
      quote,
      fetched,
      expires,
      reason as String?,
    );
  }
}

class LocalWatchlistSummary {
  final String id;
  final String name;
  final DateTime createdAt;
  final DateTime updatedAt;
  final int itemCount;
  LocalWatchlistSummary._(
    this.id,
    this.name,
    this.createdAt,
    this.updatedAt,
    this.itemCount,
  );
}

class LocalWatchlistItem {
  final LocalInstrument instrument;
  final DateTime addedAt;
  LocalWatchlistItem._(this.instrument, this.addedAt);
}

class LocalWatchlistList {
  final List<LocalWatchlistSummary> items;
  LocalWatchlistList._(this.items);
  factory LocalWatchlistList.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'watchlist_version',
      'limit',
      'count',
      'items',
    ]);
    _s3Version(value['watchlist_version'], 'watchlist.v1');
    if (value['limit'] is! int || value['limit'] != 10) invalidLocalResponse();
    final items = _s3Array(value['items'], 10)
        .map((raw) => _s3Summary(s3Object(raw, _summaryKeys, scoped: false)))
        .toList();
    if (localS3Integer(value['count'], maximum: 10) != items.length) {
      invalidLocalResponse();
    }
    final seen = <String>{};
    for (var i = 0; i < items.length; i++) {
      if (!seen.add(items[i].id)) invalidLocalResponse();
      if (i > 0) {
        final previous = items[i - 1];
        final current = items[i];
        if (current.createdAt.isBefore(previous.createdAt) ||
            (current.createdAt == previous.createdAt &&
                previous.id.compareTo(current.id) >= 0)) {
          invalidLocalResponse();
        }
      }
    }
    return LocalWatchlistList._(List.unmodifiable(items));
  }
}

class LocalWatchlist {
  final LocalWatchlistSummary summary;
  final List<LocalWatchlistItem> items;
  LocalWatchlist._(this.summary, this.items);
  factory LocalWatchlist.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'watchlist_version',
      ..._summaryKeys,
      'items',
    ]);
    _s3Version(value['watchlist_version'], 'watchlist.v1');
    final summary = _s3Summary(value);
    final items = _s3Array(value['items'], 100).map(_s3Item).toList();
    if (summary.itemCount != items.length) invalidLocalResponse();
    final seen = <String>{};
    for (var i = 0; i < items.length; i++) {
      final item = items[i];
      if (!seen.add(item.instrument.instrumentId) ||
          item.addedAt.isBefore(summary.createdAt) ||
          item.addedAt.isAfter(summary.updatedAt)) {
        invalidLocalResponse();
      }
      if (i > 0 &&
          (item.addedAt.isBefore(items[i - 1].addedAt) ||
              (item.addedAt == items[i - 1].addedAt &&
                  items[i - 1].instrument.instrumentId.compareTo(
                        item.instrument.instrumentId,
                      ) >=
                      0))) {
        invalidLocalResponse();
      }
    }
    return LocalWatchlist._(summary, List.unmodifiable(items));
  }
}

class LocalWatchlistItemSaved {
  final String watchlistId;
  final LocalWatchlistItem item;
  LocalWatchlistItemSaved._(this.watchlistId, this.item);
  factory LocalWatchlistItemSaved.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'watchlist_version',
      'watchlist_item_version',
      'watchlist_id',
      'item',
    ]);
    _s3Version(value['watchlist_version'], 'watchlist.v1');
    _s3Version(value['watchlist_item_version'], 'watchlist_item.v1');
    return LocalWatchlistItemSaved._(
      localUuid(value['watchlist_id']),
      _s3Item(value['item']),
    );
  }
}

class LocalWatchlistConfirmation {
  final String watchlistId;
  final String? instrumentId;
  LocalWatchlistConfirmation._(this.watchlistId, this.instrumentId);
  factory LocalWatchlistConfirmation.fromJson(
    Object? raw, {
    bool item = false,
  }) => _confirmation(raw, item);
  static LocalWatchlistConfirmation _confirmation(Object? raw, bool item) {
    final value = s3Object(raw, [
      'watchlist_version',
      'watchlist_id',
      if (item) ...[
        'watchlist_item_version',
        'instrument_id',
        'removed',
      ] else
        'deleted',
    ]);
    _s3Version(value['watchlist_version'], 'watchlist.v1');
    if (value[item ? 'removed' : 'deleted'] != true) invalidLocalResponse();
    if (item) _s3Version(value['watchlist_item_version'], 'watchlist_item.v1');
    return LocalWatchlistConfirmation._(
      localUuid(value['watchlist_id']),
      item ? localS3InstrumentId(value['instrument_id']) : null,
    );
  }
}

class LocalPaperAccount {
  final String id;
  final String openingLedgerId;
  final String openingCash;
  final String cashBalance;
  final DateTime createdAt;
  LocalPaperAccount._(
    this.id,
    this.openingLedgerId,
    this.openingCash,
    this.cashBalance,
    this.createdAt,
  );
}

class LocalPaperAccountState {
  final LocalPaperAccount? account;
  LocalPaperAccountState._(this.account);
  factory LocalPaperAccountState.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'paper_account_version',
      'simulation',
      'account',
    ]);
    _s3Version(value['paper_account_version'], 'paper_account.v1');
    if (value['simulation'] != true) invalidLocalResponse();
    if (value['account'] == null) return LocalPaperAccountState._(null);
    final account = s3Object(value['account'], [
      'account_id',
      'opening_ledger_id',
      'currency',
      'opening_cash',
      'cash_balance',
      'created_at',
    ], scoped: false);
    if (account['currency'] != 'USD' ||
        account['opening_cash'] != '10000.00' ||
        account['cash_balance'] != '10000.00') {
      invalidLocalResponse();
    }
    return LocalPaperAccountState._(
      LocalPaperAccount._(
        localUuid(account['account_id']),
        localUuid(account['opening_ledger_id']),
        account['opening_cash'] as String,
        account['cash_balance'] as String,
        localUtcTimestamp(account['created_at']),
      ),
    );
  }
}

class LocalOpeningEntry {
  final String id;
  final String accountId;
  final int sequence;
  final String cashDelta;
  final String cashAfter;
  final DateTime createdAt;
  LocalOpeningEntry._(
    this.id,
    this.accountId,
    this.sequence,
    this.cashDelta,
    this.cashAfter,
    this.createdAt,
  );
}

class LocalPaperLedger {
  final String accountId;
  final int limit;
  final int afterSequence;
  final List<LocalOpeningEntry> items;
  final int? nextCursor;
  LocalPaperLedger._(
    this.accountId,
    this.limit,
    this.afterSequence,
    this.items,
    this.nextCursor,
  );
  factory LocalPaperLedger.fromJson(Object? raw) {
    final value = s3Object(raw, [
      'paper_ledger_version',
      'simulation',
      'account_id',
      'limit',
      'after_sequence',
      'count',
      'items',
      'next_cursor',
    ]);
    _s3Version(value['paper_ledger_version'], 'paper_ledger.v1');
    if (value['simulation'] != true || value['next_cursor'] != null) {
      invalidLocalResponse();
    }
    final accountId = localUuid(value['account_id']);
    final limit = localS3Integer(value['limit'], maximum: 100);
    final after = localS3Integer(value['after_sequence']);
    if (limit == 0) invalidLocalResponse();
    final entries = _s3Array(value['items'], 1).map((raw) {
      final item = s3Object(raw, [
        'ledger_id',
        'account_id',
        'sequence',
        'entry_type',
        'cash_delta',
        'cash_after',
        'instrument_id',
        'quantity_delta',
        'position_after',
        'order_id',
        'trade_id',
        'corrects_ledger_id',
        'created_at',
      ], scoped: false);
      if (item['account_id'] != accountId ||
          localS3Integer(item['sequence']) != 1 ||
          item['entry_type'] != 'OPENING' ||
          item['cash_delta'] != '10000.00' ||
          item['cash_after'] != '10000.00' ||
          ![
            'instrument_id',
            'quantity_delta',
            'position_after',
            'order_id',
            'trade_id',
            'corrects_ledger_id',
          ].every((key) => item[key] == null) ||
          after >= 1) {
        invalidLocalResponse();
      }
      return LocalOpeningEntry._(
        localUuid(item['ledger_id']),
        accountId,
        1,
        item['cash_delta'] as String,
        item['cash_after'] as String,
        localUtcTimestamp(item['created_at']),
      );
    }).toList();
    if (localS3Integer(value['count'], maximum: limit) != entries.length ||
        (after == 0 && entries.length != 1)) {
      invalidLocalResponse();
    }
    return LocalPaperLedger._(
      accountId,
      limit,
      after,
      List.unmodifiable(entries),
      null,
    );
  }
}
