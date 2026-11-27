library;

/// Request and response models for authenticated paper trading.
/// Matches backend contracts in backend/app/schemas/paper.py.

class PaperOrderRequest {
  final String instrumentId;
  final String exchange;
  final String side;
  final int quantity;
  final String idempotencyKey;

  const PaperOrderRequest({
    required this.instrumentId,
    this.exchange = 'NASDAQ',
    required this.side,
    required this.quantity,
    required this.idempotencyKey,
  });

  Map<String, dynamic> toJson() => {
    'instrument_id': instrumentId,
    'exchange': exchange,
    'side': side,
    'quantity': quantity,
    'idempotency_key': idempotencyKey,
  };

  factory PaperOrderRequest.fromJson(Map<String, dynamic> json) {
    return PaperOrderRequest(
      instrumentId: json['instrument_id'] as String,
      exchange: (json['exchange'] as String?) ?? 'NASDAQ',
      side: json['side'] as String,
      quantity: (json['quantity'] as num).toInt(),
      idempotencyKey: json['idempotency_key'] as String,
    );
  }
}

class PaperOrder {
  final String orderId;
  final String instrumentId;
  final String exchange;
  final String side;
  final int quantity;
  final double executedPrice;
  final double notional;
  final double fee;
  final double cashDelta;
  final String status;
  final String quoteFreshness;
  final DateTime? quoteAsOf;
  final DateTime createdAt;
  final String simulationNotice;

  const PaperOrder({
    required this.orderId,
    required this.instrumentId,
    required this.exchange,
    required this.side,
    required this.quantity,
    required this.executedPrice,
    required this.notional,
    required this.fee,
    required this.cashDelta,
    required this.status,
    required this.quoteFreshness,
    this.quoteAsOf,
    required this.createdAt,
    this.simulationNotice =
        'SIMULATION ONLY: no real money or broker execution.',
  });

  factory PaperOrder.fromJson(Map<String, dynamic> json) {
    return PaperOrder(
      orderId: json['order_id'] as String,
      instrumentId: json['instrument_id'] as String,
      exchange: (json['exchange'] as String?) ?? 'NASDAQ',
      side: json['side'] as String,
      quantity: (json['quantity'] as num).toInt(),
      executedPrice: _toDouble(json['executed_price']),
      notional: _toDouble(json['notional']),
      fee: _toDouble(json['fee']),
      cashDelta: _toDouble(json['cash_delta']),
      status: (json['status'] as String?) ?? 'FILLED',
      quoteFreshness: (json['quote_freshness'] as String?) ?? 'LIVE',
      quoteAsOf: json['quote_as_of'] != null
          ? DateTime.tryParse(json['quote_as_of'] as String)?.toUtc()
          : null,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String).toUtc()
          : DateTime.now().toUtc(),
      simulationNotice:
          (json['simulation_notice'] as String?) ??
          'SIMULATION ONLY: no real money or broker execution.',
    );
  }

  Map<String, dynamic> toJson() => {
    'order_id': orderId,
    'instrument_id': instrumentId,
    'exchange': exchange,
    'side': side,
    'quantity': quantity,
    'executed_price': executedPrice.toStringAsFixed(2),
    'notional': notional.toStringAsFixed(2),
    'fee': fee.toStringAsFixed(2),
    'cash_delta': cashDelta.toStringAsFixed(2),
    'status': status,
    'quote_freshness': quoteFreshness,
    if (quoteAsOf != null) 'quote_as_of': quoteAsOf!.toIso8601String(),
    'created_at': createdAt.toIso8601String(),
    'simulation_notice': simulationNotice,
  };
}

class PaperPosition {
  final String instrumentId;
  final String exchange;
  final int quantity;
  final double averageCost;
  final double lastPrice;
  final double marketValue;
  final double unrealizedPnl;

  const PaperPosition({
    required this.instrumentId,
    this.exchange = 'NASDAQ',
    required this.quantity,
    required this.averageCost,
    required this.lastPrice,
    required this.marketValue,
    required this.unrealizedPnl,
  });

  factory PaperPosition.fromJson(Map<String, dynamic> json) {
    return PaperPosition(
      instrumentId: json['instrument_id'] as String,
      exchange: (json['exchange'] as String?) ?? 'NASDAQ',
      quantity: (json['quantity'] as num).toInt(),
      averageCost: _toDouble(json['average_cost']),
      lastPrice: _toDouble(json['last_price']),
      marketValue: _toDouble(json['market_value']),
      unrealizedPnl: _toDouble(json['unrealized_pnl']),
    );
  }

  Map<String, dynamic> toJson() => {
    'instrument_id': instrumentId,
    'exchange': exchange,
    'quantity': quantity,
    'average_cost': averageCost.toStringAsFixed(2),
    'last_price': lastPrice.toStringAsFixed(2),
    'market_value': marketValue.toStringAsFixed(2),
    'unrealized_pnl': unrealizedPnl.toStringAsFixed(2),
  };
}

class PaperAccount {
  final String accountId;
  final String currency;
  final double cashBalance;
  final double portfolioValue;
  final double totalEquity;
  final List<PaperPosition> positions;
  final List<PaperOrder> recentOrders;
  final bool isSimulated;

  const PaperAccount({
    required this.accountId,
    this.currency = 'USD',
    required this.cashBalance,
    required this.portfolioValue,
    required this.totalEquity,
    this.positions = const [],
    this.recentOrders = const [],
    this.isSimulated = true,
  });

  factory PaperAccount.fromJson(Map<String, dynamic> json) {
    return PaperAccount(
      accountId: json['account_id'] as String,
      currency: (json['currency'] as String?) ?? 'USD',
      cashBalance: _toDouble(json['cash_balance']),
      portfolioValue: _toDouble(json['portfolio_value']),
      totalEquity: _toDouble(json['total_equity']),
      positions:
          (json['positions'] as List<dynamic>?)
              ?.map((e) => PaperPosition.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      recentOrders:
          (json['recent_orders'] as List<dynamic>?)
              ?.map((e) => PaperOrder.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      isSimulated: (json['is_simulated'] as bool?) ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
    'account_id': accountId,
    'currency': currency,
    'cash_balance': cashBalance.toStringAsFixed(2),
    'portfolio_value': portfolioValue.toStringAsFixed(2),
    'total_equity': totalEquity.toStringAsFixed(2),
    'positions': positions.map((p) => p.toJson()).toList(),
    'recent_orders': recentOrders.map((o) => o.toJson()).toList(),
    'is_simulated': isSimulated,
  };
}

double _toDouble(dynamic value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? 0.0;
  return 0.0;
}
