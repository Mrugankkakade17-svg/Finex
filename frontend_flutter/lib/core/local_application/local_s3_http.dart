part of 'local_api_client.dart';

const _s3ErrorStatuses = {
  'LOCAL_APPLICATION_ONLY': 403,
  'ONBOARDING_REQUIRED': 409,
  'LOCAL_STORE_UNAVAILABLE': 503,
  'VALIDATION_ERROR': 422,
  'LOCAL_CATALOG_UNAVAILABLE': 503,
  'LOCAL_QUOTE_UNAVAILABLE': 503,
  'INSTRUMENT_NOT_FOUND': 404,
  'WATCHLIST_NOT_FOUND': 404,
  'WATCHLIST_LIMIT': 409,
  'WATCHLIST_ITEM_LIMIT': 409,
  'PAPER_ACCOUNT_NOT_OPEN': 404,
  'MARKET_FOUNDATION_VERSION_MISMATCH': 409,
};

Set<String> _s3AllowedErrors(String method, String requestPath) {
  final path = requestPath.split('?').first;
  final codes = {
    'LOCAL_APPLICATION_ONLY',
    'ONBOARDING_REQUIRED',
    'LOCAL_STORE_UNAVAILABLE',
    'VALIDATION_ERROR',
  };
  if (path == '/api/v1/local-market/instruments') {
    codes.add('LOCAL_CATALOG_UNAVAILABLE');
  } else if (path.startsWith('/api/v1/local-market/quotes/')) {
    codes.addAll([
      'LOCAL_CATALOG_UNAVAILABLE',
      'LOCAL_QUOTE_UNAVAILABLE',
      'INSTRUMENT_NOT_FOUND',
    ]);
  } else if (path == '/api/v1/local-watchlists') {
    if (method == 'POST') codes.add('WATCHLIST_LIMIT');
  } else if (path.startsWith('/api/v1/local-watchlists/')) {
    codes.add('WATCHLIST_NOT_FOUND');
    // Detail and item operations require the current supported catalogue.
    if (method == 'GET' || method == 'PUT' || path.contains('/items/')) {
      codes.add('LOCAL_CATALOG_UNAVAILABLE');
    }
    if (path.contains('/items/')) {
      codes.add('INSTRUMENT_NOT_FOUND');
      if (method == 'PUT') codes.add('WATCHLIST_ITEM_LIMIT');
    }
  } else if (path == '/api/v1/local-paper/account/open') {
    codes.add('MARKET_FOUNDATION_VERSION_MISMATCH');
  } else if (path == '/api/v1/local-paper/account/ledger') {
    codes.add('PAPER_ACCOUNT_NOT_OPEN');
  }
  return codes;
}

Map<String, dynamic> _decodeS3Response(
  http.Response response,
  int expectedStatus,
  String method,
  String path,
) => _decodeS2Response(
  response,
  expectedStatus,
  method,
  path,
  allowedErrors: _s3AllowedErrors(method, path),
  errorStatuses: _s3ErrorStatuses,
);

mixin _LocalS3HttpMethods implements LocalS3Api {
  Future<Map<String, dynamic>> _s3Request(
    String method,
    String path, {
    String? bearer,
    Map<String, Object?>? body,
    int expectedStatus = 200,
  });

  Future<LocalS3Reply<T>> _s3<T>(
    String method,
    String path,
    String bearer,
    T Function(Object?) decode, {
    Map<String, Object?>? body,
    int status = 200,
    DateTime? Function(T)? asOf,
    String Function(T)? dataStatus,
    bool anyConfirmedTime = false,
  }) async {
    final envelope = await _s3Request(
      method,
      path,
      bearer: bearer,
      body: body,
      expectedStatus: status,
    );
    final value = decode(envelope['data']);
    final meta = localObject(envelope['meta']);
    final actual = meta['dataAsOf'] == null
        ? null
        : localUtcTimestamp(meta['dataAsOf']);
    if ((anyConfirmedTime ? actual == null : actual != asOf?.call(value)) ||
        meta['dataStatus'] != (dataStatus?.call(value) ?? 'CACHED')) {
      invalidLocalResponse();
    }
    return LocalS3Reply(value, meta['dataStatus'] as String, actual);
  }

  @override
  Future<LocalS3Reply<LocalMarketSearch>> marketSearch(
    String bearer, {
    String query = '',
    int limit = 20,
  }) async {
    final normalized = localS3Query(query);
    localS3Integer(limit, maximum: 20);
    if (limit == 0) throw const LocalApiException('VALIDATION_ERROR');
    final params = Uri(
      queryParameters: {'query': normalized, 'limit': '$limit'},
    ).query;
    final reply = await _s3(
      'GET',
      '/api/v1/local-market/instruments?$params',
      bearer,
      LocalMarketSearch.fromJson,
      asOf: (_) => localUtcTimestamp(localS3FixtureTime),
    );
    if (reply.value.query != normalized || reply.value.limit != limit) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalMarketQuote>> marketQuote(
    String bearer,
    String instrument,
  ) async {
    localS3InstrumentId(instrument);
    final reply = await _s3(
      'GET',
      '/api/v1/local-market/quotes/${Uri.encodeComponent(instrument)}',
      bearer,
      LocalMarketQuote.fromJson,
      asOf: (v) => v.quoteAsOf,
      dataStatus: (v) => v.dataStatus,
    );
    if (reply.value.instrumentId != instrument) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlistList>> watchlists(String bearer) => _s3(
    'GET',
    '/api/v1/local-watchlists',
    bearer,
    LocalWatchlistList.fromJson,
  );
  @override
  Future<LocalS3Reply<LocalWatchlist>> watchlist(
    String bearer,
    String id,
  ) async {
    localUuid(id);
    final reply = await _s3(
      'GET',
      '/api/v1/local-watchlists/$id',
      bearer,
      LocalWatchlist.fromJson,
      asOf: (v) => v.summary.updatedAt,
    );
    if (reply.value.summary.id != id) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlist>> createWatchlist(
    String bearer,
    String name,
  ) async {
    final normalized = localS3Name(name);
    final reply = await _s3(
      'POST',
      '/api/v1/local-watchlists',
      bearer,
      LocalWatchlist.fromJson,
      body: {'name': normalized},
      status: 201,
      asOf: (v) => v.summary.updatedAt,
    );
    if (reply.value.summary.name != normalized ||
        reply.value.items.isNotEmpty ||
        reply.value.summary.createdAt != reply.value.summary.updatedAt) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlist>> updateWatchlist(
    String bearer,
    String id,
    String name,
  ) async {
    localUuid(id);
    final normalized = localS3Name(name);
    final reply = await _s3(
      'PUT',
      '/api/v1/local-watchlists/$id',
      bearer,
      LocalWatchlist.fromJson,
      body: {'name': normalized},
      asOf: (v) => v.summary.updatedAt,
    );
    if (reply.value.summary.id != id ||
        reply.value.summary.name != normalized) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> deleteWatchlist(
    String bearer,
    String id,
  ) async {
    localUuid(id);
    final reply = await _s3(
      'DELETE',
      '/api/v1/local-watchlists/$id',
      bearer,
      LocalWatchlistConfirmation.fromJson,
      anyConfirmedTime: true,
    );
    if (reply.value.watchlistId != id) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlistItemSaved>> putWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  ) async {
    localUuid(parent);
    localS3InstrumentId(instrument);
    final reply = await _s3(
      'PUT',
      '/api/v1/local-watchlists/$parent/items/${Uri.encodeComponent(instrument)}',
      bearer,
      LocalWatchlistItemSaved.fromJson,
      asOf: (v) => v.item.addedAt,
    );
    if (reply.value.watchlistId != parent ||
        reply.value.item.instrument.instrumentId != instrument) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalWatchlistConfirmation>> removeWatchlistItem(
    String bearer,
    String parent,
    String instrument,
  ) async {
    localUuid(parent);
    localS3InstrumentId(instrument);
    final reply = await _s3(
      'DELETE',
      '/api/v1/local-watchlists/$parent/items/${Uri.encodeComponent(instrument)}',
      bearer,
      (v) => LocalWatchlistConfirmation.fromJson(v, item: true),
      anyConfirmedTime: true,
    );
    if (reply.value.watchlistId != parent ||
        reply.value.instrumentId != instrument) {
      invalidLocalResponse();
    }
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalPaperAccountState>> paperAccount(String bearer) =>
      _s3(
        'GET',
        '/api/v1/local-paper/account',
        bearer,
        LocalPaperAccountState.fromJson,
        asOf: (v) => v.account?.createdAt,
      );
  @override
  Future<LocalS3Reply<LocalPaperAccountState>> openPaperAccount(
    String bearer,
  ) async {
    final reply = await _s3(
      'POST',
      '/api/v1/local-paper/account/open',
      bearer,
      LocalPaperAccountState.fromJson,
      body: {'foundation_version': localFoundationVersion, 'currency': 'USD'},
      asOf: (v) => v.account?.createdAt,
    );
    if (reply.value.account == null) invalidLocalResponse();
    return reply;
  }

  @override
  Future<LocalS3Reply<LocalPaperLedger>> paperLedger(
    String bearer, {
    int after = 0,
    int limit = 100,
  }) async {
    localS3Integer(after);
    localS3Integer(limit, maximum: 100);
    if (limit == 0) throw const LocalApiException('VALIDATION_ERROR');
    final query = Uri(
      queryParameters: {'limit': '$limit', 'after_sequence': '$after'},
    ).query;
    final reply = await _s3(
      'GET',
      '/api/v1/local-paper/account/ledger?$query',
      bearer,
      LocalPaperLedger.fromJson,
      asOf: (v) => v.items.isEmpty ? null : v.items.last.createdAt,
    );
    if (reply.value.limit != limit || reply.value.afterSequence != after) {
      invalidLocalResponse();
    }
    return reply;
  }
}
