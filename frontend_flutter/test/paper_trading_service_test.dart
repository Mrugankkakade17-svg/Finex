import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:frontend_flutter/features/paper_trading/models/paper_trading_models.dart';
import 'package:frontend_flutter/features/paper_trading/services/paper_trading_service.dart';

void main() {
  group('PaperTradingService', () {
    test('getAccount parses successful backend response', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/paper/account');
        expect(request.headers['Authorization'], 'Bearer test-token-123');
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Paper account retrieved',
            'data': {
              'account_id': 'acc-1',
              'currency': 'USD',
              'cash_balance': '10000.00',
              'portfolio_value': '0.00',
              'total_equity': '10000.00',
              'positions': [],
              'recent_orders': [],
              'is_simulated': true,
            },
            'correlation_id': 'corr-123',
            'data_status': 'CACHED',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = PaperTradingService(
        client: mockClient,
        tokenProvider: () async => 'test-token-123',
      );

      final account = await service.getAccount();
      expect(account.accountId, 'acc-1');
      expect(account.cashBalance, 10000.00);
      expect(account.totalEquity, 10000.00);
      expect(account.isSimulated, true);
    });

    test('getPositions returns list of positions', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/paper/positions');
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Paper positions retrieved',
            'data': [
              {
                'instrument_id': 'AAPL',
                'exchange': 'NASDAQ',
                'quantity': 10,
                'average_cost': '150.00',
                'last_price': '155.00',
                'market_value': '1550.00',
                'unrealized_pnl': '50.00',
              },
            ],
            'correlation_id': 'corr-456',
            'data_status': 'CACHED',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = PaperTradingService(client: mockClient);
      final positions = await service.getPositions();
      expect(positions.length, 1);
      expect(positions.first.instrumentId, 'AAPL');
      expect(positions.first.marketValue, 1550.00);
    });

    test('getOrders queries with limit parameter', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/paper/orders');
        expect(request.url.queryParameters['limit'], '5');
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Paper orders retrieved',
            'data': [
              {
                'order_id': 'ord-1',
                'instrument_id': 'SPY',
                'exchange': 'NYSE',
                'side': 'BUY',
                'quantity': 2,
                'executed_price': '500.00',
                'notional': '1000.00',
                'fee': '1.00',
                'cash_delta': '-1001.00',
                'status': 'FILLED',
                'quote_freshness': 'LIVE',
                'created_at': '2026-11-27T10:00:00Z',
              },
            ],
            'correlation_id': 'corr-789',
            'data_status': 'CACHED',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = PaperTradingService(client: mockClient);
      final orders = await service.getOrders(limit: 5);
      expect(orders.length, 1);
      expect(orders.first.orderId, 'ord-1');
      expect(orders.first.side, 'BUY');
    });

    test('submitOrder handles 201 Created', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/v1/paper/orders');
        expect(request.method, 'POST');
        final body = jsonDecode(request.body);
        expect(body['instrument_id'], 'AAPL');
        expect(body['quantity'], 10);
        return http.Response(
          jsonEncode({
            'status': 'success',
            'message': 'Paper order filled',
            'data': {
              'order_id': 'ord-new-1',
              'instrument_id': 'AAPL',
              'exchange': 'NASDAQ',
              'side': 'BUY',
              'quantity': 10,
              'executed_price': '225.00',
              'notional': '2250.00',
              'fee': '1.00',
              'cash_delta': '-2251.00',
              'status': 'FILLED',
              'quote_freshness': 'LIVE',
              'created_at': '2026-11-27T10:05:00Z',
            },
            'correlation_id': 'corr-new',
            'data_status': 'LIVE',
          }),
          201,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = PaperTradingService(client: mockClient);
      const req = PaperOrderRequest(
        instrumentId: 'AAPL',
        exchange: 'NASDAQ',
        side: 'BUY',
        quantity: 10,
        idempotencyKey: 'idem-01',
      );
      final order = await service.submitOrder(req);
      expect(order.orderId, 'ord-new-1');
      expect(order.executedPrice, 225.00);
      expect(order.status, 'FILLED');
    });

    test('submitOrder throws PaperTradingException on backend error', () async {
      final mockClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'error_code': 'MARKET_CLOSED',
            'message':
                'Paper orders are accepted only during regular market hours.',
          }),
          409,
          headers: {'content-type': 'application/json'},
        );
      });

      final service = PaperTradingService(client: mockClient);
      const req = PaperOrderRequest(
        instrumentId: 'AAPL',
        side: 'BUY',
        quantity: 10,
        idempotencyKey: 'idem-02',
      );

      expect(
        () => service.submitOrder(req),
        throwsA(
          isA<PaperTradingException>()
              .having((e) => e.code, 'code', 'MARKET_CLOSED')
              .having((e) => e.statusCode, 'statusCode', 409),
        ),
      );
    });
  });
}
