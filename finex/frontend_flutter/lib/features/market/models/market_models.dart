/// Canonical prototype data status label.
/// Mirrors dataStatus in the FinEx standard response envelope.
enum DataStatus {
  live,
  delayed,
  endOfDay,
  cached,
  unavailable,
}

extension DataStatusLabel on DataStatus {
  String get label {
    switch (this) {
      case DataStatus.live:
        return 'Live';
      case DataStatus.delayed:
        return 'Delayed';
      case DataStatus.endOfDay:
        return 'End of day';
      case DataStatus.cached:
        return 'Cached';
      case DataStatus.unavailable:
        return 'Unavailable';
    }
  }
}

class MarketSecurity {
  final String securityId;
  final String symbol;
  final String name;
  final String assetType;
  final String exchange;
  final String currency;

  const MarketSecurity({
    required this.securityId,
    required this.symbol,
    required this.name,
    required this.assetType,
    required this.exchange,
    required this.currency,
  });
}

class MarketQuote {
  final String symbol;
  final double price;
  final String currency;
  final double changeValue;
  final double changePercent;
  final String source;
  final DateTime dataAsOf;
  final DataStatus dataStatus;

  const MarketQuote({
    required this.symbol,
    required this.price,
    required this.currency,
    required this.changeValue,
    required this.changePercent,
    required this.source,
    required this.dataAsOf,
    required this.dataStatus,
  });
}

class WatchlistItem {
  final String symbol;
  final String name;
  final DateTime addedAt;

  const WatchlistItem({
    required this.symbol,
    required this.name,
    required this.addedAt,
  });
}
