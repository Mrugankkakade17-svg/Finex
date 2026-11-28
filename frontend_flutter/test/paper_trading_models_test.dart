import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/features/paper_trading/models/paper_trading_models.dart';

void main() {
  group('PaperOrderRequest', () {
    test('toJson serializes correctly', () {
      const request = PaperOrderRequest(
        instrumentId: 'AAPL',
        exchange: 'NASDAQ',
        side: 'BUY',
        quantity: 15,
        idempotencyKey: 'idem-01',
      );
      final json = request.toJson();
      expect(json['instrument_id'], 'AAPL');
      expect(json['exchange'], 'NASDAQ');
      expect(json['side'], 'BUY');
      expect(json['quantity'], 15);
      expect(json['idempotency_key'], 'idem-01');
    });

    test('fromJson deserializes correctly', () {
      final json = {
        'instrument_id': 'SPY',
        'exchange': 'NYSE',
        'side': 'SELL',
        'quantity': 10,
        'idempotency_key': 'idem-02',
      };
      final request = PaperOrderRequest.fromJson(json);
      expect(request.instrumentId, 'SPY');
      expect(request.exchange, 'NYSE');
      expect(request.side, 'SELL');
      expect(request.quantity, 10);
      expect(request.idempotencyKey, 'idem-02');
    });
  });

  group('PaperOrder', () {
    test('fromJson parses string numbers and timestamps', () {
      final json = {
        'order_id': 'ord-1001',
        'instrument_id': 'NVDA',
        'exchange': 'NASDAQ',
        'side': 'BUY',
        'quantity': 5,
        'executed_price': '138.50',
        'notional': '692.50',
        'fee': '1.00',
        'cash_delta': '-693.50',
        'status': 'FILLED',
        'quote_freshness': 'LIVE',
        'quote_as_of': '2026-11-27T10:00:00Z',
        'created_at': '2026-11-27T10:00:01Z',
        'simulation_notice': 'SIMULATION ONLY',
      };
      final order = PaperOrder.fromJson(json);
      expect(order.orderId, 'ord-1001');
      expect(order.instrumentId, 'NVDA');
      expect(order.executedPrice, 138.50);
      expect(order.notional, 692.50);
      expect(order.fee, 1.00);
      expect(order.cashDelta, -693.50);
      expect(order.status, 'FILLED');
      expect(order.quoteFreshness, 'LIVE');
      expect(order.quoteAsOf, DateTime.utc(2026, 11, 27, 10, 0, 0));
      expect(order.createdAt, DateTime.utc(2026, 11, 27, 10, 0, 1));
      expect(order.simulationNotice, 'SIMULATION ONLY');
    });
  });

  group('PaperPosition', () {
    test('fromJson and toJson round-trip', () {
      final json = {
        'instrument_id': 'MSFT',
        'exchange': 'NASDAQ',
        'quantity': 20,
        'average_cost': '410.25',
        'last_price': '420.50',
        'market_value': '8410.00',
        'unrealized_pnl': '205.00',
      };
      final pos = PaperPosition.fromJson(json);
      expect(pos.instrumentId, 'MSFT');
      expect(pos.quantity, 20);
      expect(pos.averageCost, 410.25);
      expect(pos.lastPrice, 420.50);
      expect(pos.marketValue, 8410.00);
      expect(pos.unrealizedPnl, 205.00);

      final out = pos.toJson();
      expect(out['instrument_id'], 'MSFT');
      expect(out['market_value'], '8410.00');
    });
  });

  group('PaperAccount', () {
    test('fromJson parses full account tree with positions and orders', () {
      final json = {
        'account_id': 'acc-test-99',
        'currency': 'USD',
        'cash_balance': '9500.00',
        'portfolio_value': '8410.00',
        'total_equity': '17910.00',
        'positions': [
          {
            'instrument_id': 'MSFT',
            'exchange': 'NASDAQ',
            'quantity': 20,
            'average_cost': '410.25',
            'last_price': '420.50',
            'market_value': '8410.00',
            'unrealized_pnl': '205.00',
          },
        ],
        'recent_orders': [
          {
            'order_id': 'ord-1',
            'instrument_id': 'MSFT',
            'exchange': 'NASDAQ',
            'side': 'BUY',
            'quantity': 20,
            'executed_price': '410.25',
            'notional': '8205.00',
            'fee': '1.00',
            'cash_delta': '-8206.00',
            'status': 'FILLED',
            'quote_freshness': 'LIVE',
            'created_at': '2026-11-27T09:30:00Z',
          },
        ],
        'is_simulated': true,
      };

      final acc = PaperAccount.fromJson(json);
      expect(acc.accountId, 'acc-test-99');
      expect(acc.currency, 'USD');
      expect(acc.cashBalance, 9500.00);
      expect(acc.portfolioValue, 8410.00);
      expect(acc.totalEquity, 17910.00);
      expect(acc.positions.length, 1);
      expect(acc.positions.first.instrumentId, 'MSFT');
      expect(acc.recentOrders.length, 1);
      expect(acc.recentOrders.first.orderId, 'ord-1');
      expect(acc.isSimulated, true);
    });
  });
}
