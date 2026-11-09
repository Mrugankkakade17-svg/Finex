import 'package:frontend_flutter/core/local_application/local_s3_api.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';

import 'local_s3_data.dart';

class FakeLocalS3Api implements LocalS3Api {
  final calls = <String>[];
  final saved = <String, Map<String, Map<String, dynamic>>>{'A': {}, 'B': {}};
  final opened = <String>{};
  Future<LocalS3Reply<LocalMarketSearch>> Function()? onSearch;
  Future<LocalS3Reply<LocalWatchlistList>> Function()? onLists;
  Future<LocalS3Reply<LocalWatchlist>> Function(String)? onCreate;
  Future<LocalS3Reply<LocalMarketQuote>> Function(String)? onQuote;
  Future<LocalS3Reply<LocalPaperAccountState>> Function()? onAccount;
  Future<LocalS3Reply<LocalPaperLedger>> Function()? onLedger;
  String owner(String bearer) => bearer.startsWith('A') ? 'A' : 'B';
  DateTime get time => DateTime.parse(s3Time);
  @override
  Future<LocalS3Reply<LocalMarketSearch>> marketSearch(
    String bearer, {
    String query = '',
    int limit = 20,
  }) async {
    calls.add('search:${owner(bearer)}');
    if (onSearch != null) return onSearch!();
    final raw = s3Search(query: query, limit: limit);
    return LocalS3Reply(
      LocalMarketSearch.fromJson(raw),
      'CACHED',
      DateTime.parse(s3FixtureTime),
    );
  }

  @override
  Future<LocalS3Reply<LocalMarketQuote>> marketQuote(
    String bearer,
    String instrument,
  ) async {
    calls.add('quote:${owner(bearer)}:$instrument');
    final raw = s3Quote(instrument: instrument);
    if (onQuote != null) return onQuote!(instrument);
    final value = LocalMarketQuote.fromJson(raw);
    return LocalS3Reply(value, value.dataStatus, value.quoteAsOf);
  }

  @override
  Future<LocalS3Reply<LocalWatchlistList>> watchlists(String bearer) async {
    calls.add('lists:${owner(bearer)}');
    if (onLists != null) return onLists!();
    final items =
        saved[owner(bearer)]!.values
            .map(
              (v) => {
                for (final k in [
                  'watchlist_id',
                  'name',
                  'created_at',
                  'updated_at',
                  'item_count',
                ])
                  k: v[k],
              },
            )
            .toList()
          ..sort(
            (a, b) => (a['watchlist_id'] as String).compareTo(
              b['watchlist_id'] as String,
            ),
          );
    return LocalS3Reply(
      LocalWatchlistList.fromJson(
        s3Watchlists()
          ..['items'] = items
          ..['count'] = items.length,
      ),
      'CACHED',
      null,
    );
  }

  @override
  Future<LocalS3Reply<LocalWatchlist>> watchlist(
    String bearer,
    String id,
  ) async {
    calls.add('detail:${owner(bearer)}');
    final raw = saved[owner(bearer)]![id];
    if (raw == null) {
      throw const LocalApiException('WATCHLIST_NOT_FOUND', status: 404);
    }
    return LocalS3Reply(LocalWatchlist.fromJson(raw), 'CACHED', time);
  }

  @override
  Future<LocalS3Reply<LocalWatchlist>> createWatchlist(
    String bearer,
    String name,
  ) async {
    calls.add('create:${owner(bearer)}');
    if (onCreate != null) return onCreate!(name);
    final id = saved[owner(bearer)]!.isEmpty ? s3Id : s3OtherId;
    final raw = s3Watchlist(id: id, name: name.trim());
    saved[owner(bearer)]![id] = raw;
    return LocalS3Reply(LocalWatchlist.fromJson(raw), 'CACHED', time);
  }

  @override
  Future<LocalS3Reply<LocalWatchlist>> updateWatchlist(
    String bearer,
    String id,
    String name,
  ) async {
    calls.add('rename:${owner(bearer)}');
    final raw = saved[owner(bearer)]![id];
    if (raw == null) {
      throw const LocalApiException('WATCHLIST_NOT_FOUND', status: 404);
    }
    raw['name'] = name.trim();
    return LocalS3Reply(LocalWatchlist.fromJson(raw), 'CACHED', time);
  }

  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> deleteWatchlist(
    String bearer,
    String id,
  ) async {
    calls.add('delete:${owner(bearer)}');
    if (!saved[owner(bearer)]!.containsKey(id)) {
      throw const LocalApiException('WATCHLIST_NOT_FOUND', status: 404);
    }
    saved[owner(bearer)]!.remove(id);
    return LocalS3Reply(
      LocalWatchlistConfirmation.fromJson({
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_id': id,
        'deleted': true,
      }),
      'CACHED',
      time,
    );
  }

  @override
  Future<LocalS3Reply<LocalWatchlistItemSaved>> putWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  ) async {
    calls.add('add:${owner(bearer)}');
    final raw = saved[owner(bearer)]![parent];
    if (raw == null) {
      throw const LocalApiException('WATCHLIST_NOT_FOUND', status: 404);
    }
    final candidate = s3Item(instrument);
    final items = List<Map<String, dynamic>>.from(raw['items'] as List);
    final existing = items
        .where((v) => v['instrument_id'] == instrument)
        .toList();
    final item = existing.isEmpty ? candidate : existing.single;
    if (existing.isEmpty) items.add(item);
    items.sort(
      (a, b) => (a['instrument_id'] as String).compareTo(
        b['instrument_id'] as String,
      ),
    );
    raw['items'] = items;
    raw['item_count'] = items.length;
    return LocalS3Reply(
      LocalWatchlistItemSaved.fromJson({
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_item_version': 'watchlist_item.v1',
        'watchlist_id': parent,
        'item': item,
      }),
      'CACHED',
      time,
    );
  }

  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> removeWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  ) async {
    calls.add('remove:${owner(bearer)}');
    final raw = saved[owner(bearer)]![parent];
    if (raw == null) {
      throw const LocalApiException('WATCHLIST_NOT_FOUND', status: 404);
    }
    s3Instrument(instrument);
    final items = List<Map<String, dynamic>>.from(raw['items'] as List)
      ..removeWhere((v) => v['instrument_id'] == instrument);
    raw['items'] = items;
    raw['item_count'] = items.length;
    return LocalS3Reply(
      LocalWatchlistConfirmation.fromJson({
        ...s3Root(),
        'watchlist_version': 'watchlist.v1',
        'watchlist_item_version': 'watchlist_item.v1',
        'watchlist_id': parent,
        'instrument_id': instrument,
        'removed': true,
      }, item: true),
      'CACHED',
      time,
    );
  }

  @override
  Future<LocalS3Reply<LocalPaperAccountState>> paperAccount(
    String bearer,
  ) async {
    if (onAccount != null) return onAccount!();
    calls.add('account:${owner(bearer)}');
    final exists = opened.contains(owner(bearer));
    return LocalS3Reply(
      LocalPaperAccountState.fromJson(s3Account(opened: exists)),
      'CACHED',
      exists ? time : null,
    );
  }

  @override
  Future<LocalS3Reply<LocalPaperAccountState>> openPaperAccount(
    String bearer,
  ) async {
    calls.add('open:${owner(bearer)}');
    opened.add(owner(bearer));
    return paperAccount(bearer);
  }

  @override
  Future<LocalS3Reply<LocalPaperLedger>> paperLedger(
    String bearer, {
    int after = 0,
    int limit = 100,
  }) async {
    if (onLedger != null) return onLedger!();
    calls.add('ledger:${owner(bearer)}');
    final raw = s3Ledger(after: after, limit: limit);
    return LocalS3Reply(
      LocalPaperLedger.fromJson(raw),
      'CACHED',
      after == 0 ? time : null,
    );
  }
}
