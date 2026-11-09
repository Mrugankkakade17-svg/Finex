import 'package:flutter/foundation.dart';

import '../models/market_models.dart';

/// Symbol explicitly wired to simulate a provider outage so the
/// PRICE_UNAVAILABLE / provider-unavailable UI state is testable.
const String kUnavailableSymbol = 'DOWN';

/// Mock market data service while the backend API (MKT-01..03, WAT-01)
/// is pending. Mirrors the shape of the future generated Dart client.
class MarketService extends ChangeNotifier {
  static final MarketService _instance = MarketService._internal();
  factory MarketService() => _instance;
  MarketService._internal();

  static final List<MarketSecurity> _catalog = [
    const MarketSecurity(
      securityId: 'sec_aapl',
      symbol: 'AAPL',
      name: 'Apple Inc.',
      assetType: 'EQUITY',
      exchange: 'NASDAQ',
      currency: 'USD',
    ),
    const MarketSecurity(
      securityId: 'sec_msft',
      symbol: 'MSFT',
      name: 'Microsoft Corporation',
      assetType: 'EQUITY',
      exchange: 'NASDAQ',
      currency: 'USD',
    ),
    const MarketSecurity(
      securityId: 'sec_nvda',
      symbol: 'NVDA',
      name: 'NVIDIA Corporation',
      assetType: 'EQUITY',
      exchange: 'NASDAQ',
      currency: 'USD',
    ),
    const MarketSecurity(
      securityId: 'sec_googl',
      symbol: 'GOOGL',
      name: 'Alphabet Inc.',
      assetType: 'EQUITY',
      exchange: 'NASDAQ',
      currency: 'USD',
    ),
    const MarketSecurity(
      securityId: 'sec_vti',
      symbol: 'VTI',
      name: 'Vanguard Total Stock Market ETF',
      assetType: 'ETF',
      exchange: 'NYSEARCA',
      currency: 'USD',
    ),
    const MarketSecurity(
      securityId: 'sec_down',
      symbol: kUnavailableSymbol,
      name: 'Provider Outage Demo Security',
      assetType: 'EQUITY',
      exchange: 'DEMO',
      currency: 'USD',
    ),
  ];

  static final Map<String, _CachedQuote> _quoteCache = {
    'AAPL': const _CachedQuote(227.52, 'USD', 1.84, 0.0082, DataStatus.cached),
    'MSFT': const _CachedQuote(421.10, 'USD', -2.35, -0.0055, DataStatus.cached),
    'NVDA': const _CachedQuote(138.07, 'USD', -1.12, -0.0080, DataStatus.delayed),
    'GOOGL': const _CachedQuote(176.40, 'USD', 0.65, 0.0037, DataStatus.cached),
    'VTI': const _CachedQuote(289.33, 'USD', 0.42, 0.0015, DataStatus.endOfDay),
  };

  final List<WatchlistItem> _watchlist = [
    WatchlistItem(symbol: 'AAPL', name: 'Apple Inc.', addedAt: DateTime.now()),
  ];

  /// MKT-01: search securities by symbol or name.
  Future<List<MarketSecurity>> search(String query) async {
    await Future.delayed(const Duration(milliseconds: 300));

    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      throw Exception('Enter at least one character to search.');
    }

    final lowered = trimmed.toLowerCase();
    return _catalog
        .where(
          (security) =>
              security.symbol.toLowerCase().contains(lowered) ||
              security.name.toLowerCase().contains(lowered),
        )
        .toList();
  }

  /// MKT-02: get the latest available quote for a symbol.
  /// Returns an explicit UNAVAILABLE status instead of throwing, so the
  /// client can render a PRICE_UNAVAILABLE state per the handbook.
  Future<MarketQuote> getQuote(String symbol) async {
    await Future.delayed(const Duration(milliseconds: 400));

    final normalized = symbol.trim().toUpperCase();

    if (normalized == kUnavailableSymbol) {
      return MarketQuote(
        symbol: normalized,
        price: 0,
        currency: 'USD',
        changeValue: 0,
        changePercent: 0,
        source: 'yfinance-prototype',
        dataAsOf: DateTime.now(),
        dataStatus: DataStatus.unavailable,
      );
    }

    final cached = _quoteCache[normalized];
    if (cached == null) {
      throw Exception('SYMBOL_NOT_SUPPORTED');
    }

    return MarketQuote(
      symbol: normalized,
      price: cached.price,
      currency: cached.currency,
      changeValue: cached.changeValue,
      changePercent: cached.changePercent,
      source: 'yfinance-prototype',
      dataAsOf: DateTime.now(),
      dataStatus: cached.status,
    );
  }

  /// WAT-01: fetch the current user's default watchlist.
  Future<List<WatchlistItem>> getWatchlist() async {
    await Future.delayed(const Duration(milliseconds: 250));
    return List.unmodifiable(_watchlist);
  }

  /// WAT-01: add a security to the default watchlist.
  /// Adding an already-present symbol is idempotent.
  Future<List<WatchlistItem>> addToWatchlist(MarketSecurity security) async {
    await Future.delayed(const Duration(milliseconds: 250));

    final exists = _watchlist.any((item) => item.symbol == security.symbol);
    if (!exists) {
      _watchlist.add(
        WatchlistItem(
          symbol: security.symbol,
          name: security.name,
          addedAt: DateTime.now(),
        ),
      );
    }

    notifyListeners();
    return List.unmodifiable(_watchlist);
  }

  /// WAT-01: remove a security from the default watchlist.
  /// Removing an absent symbol is idempotent.
  Future<List<WatchlistItem>> removeFromWatchlist(String symbol) async {
    await Future.delayed(const Duration(milliseconds: 250));

    _watchlist.removeWhere((item) => item.symbol == symbol);

    notifyListeners();
    return List.unmodifiable(_watchlist);
  }
}

class _CachedQuote {
  final double price;
  final String currency;
  final double changeValue;
  final double changePercent;
  final DataStatus status;

  const _CachedQuote(
    this.price,
    this.currency,
    this.changeValue,
    this.changePercent,
    this.status,
  );
}
