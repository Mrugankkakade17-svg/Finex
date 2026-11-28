import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend_flutter/features/paper_trading/models/paper_trading_models.dart';
import 'package:frontend_flutter/features/paper_trading/presentation/paper_trading_page.dart';
import 'package:frontend_flutter/features/paper_trading/services/paper_trading_service.dart';

class FakePaperTradingService extends PaperTradingService {
  PaperAccount? accountToReturn;
  PaperOrder? orderToReturn;
  Exception? errorToThrow;
  int getAccountCalls = 0;
  PaperOrderRequest? lastSubmittedOrder;

  @override
  Future<PaperAccount> getAccount() async {
    getAccountCalls++;
    if (errorToThrow != null) throw errorToThrow!;
    return accountToReturn ??
        const PaperAccount(
          accountId: 'acc-fake-1',
          currency: 'USD',
          cashBalance: 10000.00,
          portfolioValue: 0.00,
          totalEquity: 10000.00,
        );
  }

  @override
  Future<PaperOrder> submitOrder(PaperOrderRequest request) async {
    lastSubmittedOrder = request;
    if (errorToThrow != null) throw errorToThrow!;
    return orderToReturn ??
        PaperOrder(
          orderId: 'ord-fake-101',
          instrumentId: request.instrumentId,
          exchange: request.exchange,
          side: request.side,
          quantity: request.quantity,
          executedPrice: 150.00,
          notional: request.quantity * 150.00,
          fee: 1.00,
          cashDelta: -(request.quantity * 150.00 + 1.00),
          status: 'FILLED',
          quoteFreshness: 'LIVE',
          createdAt: DateTime.now().toUtc(),
        );
  }
}

void main() {
  Widget createTestWidget(WidgetTester tester, PaperTradingService service) {
    tester.view.physicalSize = const Size(1000, 1600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    return MaterialApp(home: PaperTradingPage(service: service));
  }

  group('PaperTradingPage Widget Tests', () {
    testWidgets('renders account overview, balances, and empty states', (
      tester,
    ) async {
      final service = FakePaperTradingService();
      service.accountToReturn = const PaperAccount(
        accountId: 'acc-1',
        currency: 'USD',
        cashBalance: 10000.00,
        portfolioValue: 0.00,
        totalEquity: 10000.00,
        positions: [],
        recentOrders: [],
      );

      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(find.text('Simulated Paper Trading'), findsOneWidget);
      expect(find.text('Educational Simulation Only'), findsOneWidget);
      expect(
        find.text('\$10000.00'),
        findsNWidgets(2),
      ); // cash balance and total equity
      expect(find.text('\$0.00'), findsOneWidget); // portfolio value
      expect(find.text('No Open Positions'), findsOneWidget);
      expect(find.text('No Orders Yet'), findsOneWidget);
    });

    testWidgets('renders open positions and recent orders when present', (
      tester,
    ) async {
      final service = FakePaperTradingService();
      service.accountToReturn = PaperAccount(
        accountId: 'acc-2',
        cashBalance: 8500.00,
        portfolioValue: 3000.00,
        totalEquity: 11500.00,
        positions: const [
          PaperPosition(
            instrumentId: 'AAPL',
            exchange: 'NASDAQ',
            quantity: 10,
            averageCost: 150.00,
            lastPrice: 155.00,
            marketValue: 1550.00,
            unrealizedPnl: 50.00,
          ),
        ],
        recentOrders: [
          PaperOrder(
            orderId: 'ord-1',
            instrumentId: 'AAPL',
            exchange: 'NASDAQ',
            side: 'BUY',
            quantity: 10,
            executedPrice: 150.00,
            notional: 1500.00,
            fee: 1.00,
            cashDelta: -1501.00,
            status: 'FILLED',
            quoteFreshness: 'LIVE',
            createdAt: DateTime.now().toUtc(),
          ),
        ],
      );

      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(find.text('AAPL (NASDAQ)'), findsOneWidget);
      expect(find.text('10 shares @ avg \$150.00'), findsOneWidget);
      expect(find.text('\$1550.00'), findsOneWidget);
      expect(find.text('+\$50.00'), findsOneWidget);
      expect(find.text('10x AAPL'), findsOneWidget);
      expect(find.text('LIVE'), findsOneWidget);
    });

    testWidgets('validates empty symbol and invalid quantity inputs', (
      tester,
    ) async {
      final service = FakePaperTradingService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      // Clear symbol input
      await tester.enterText(find.byKey(const Key('paper-symbol-input')), '');
      await tester.tap(find.byKey(const Key('paper-submit-order-btn')));
      await tester.pump();

      expect(find.text('Please enter an instrument symbol.'), findsOneWidget);

      // Enter valid symbol but negative quantity
      await tester.enterText(
        find.byKey(const Key('paper-symbol-input')),
        'MSFT',
      );
      await tester.enterText(
        find.byKey(const Key('paper-quantity-input')),
        '0',
      );
      await tester.tap(find.byKey(const Key('paper-submit-order-btn')));
      await tester.pump();

      expect(find.text('Quantity must be a positive integer.'), findsOneWidget);
    });

    testWidgets('submits order and displays server-confirmed success message', (
      tester,
    ) async {
      final service = FakePaperTradingService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('paper-symbol-input')),
        'SPY',
      );
      await tester.enterText(
        find.byKey(const Key('paper-quantity-input')),
        '5',
      );
      await tester.tap(find.byKey(const Key('paper-submit-order-btn')));
      await tester.pumpAndSettle();

      expect(service.lastSubmittedOrder?.instrumentId, 'SPY');
      expect(service.lastSubmittedOrder?.quantity, 5);
      expect(service.lastSubmittedOrder?.idempotencyKey, isNotEmpty);
      expect(find.byKey(const Key('paper-order-success')), findsOneWidget);
      expect(find.textContaining('Order Confirmed: BUY 5 SPY'), findsOneWidget);
    });

    testWidgets(
      'handles order rejection and provides safe retry with same idempotency key',
      (tester) async {
        final service = FakePaperTradingService();
        await tester.pumpWidget(createTestWidget(tester, service));
        await tester.pumpAndSettle();

        // Set error on order submission
        service.errorToThrow = const PaperTradingException(
          code: 'MARKET_CLOSED',
          message: 'Market is closed.',
          statusCode: 409,
        );

        await tester.tap(find.byKey(const Key('paper-submit-order-btn')));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('paper-order-error')), findsOneWidget);
        expect(
          find.textContaining('MARKET_CLOSED: Market is closed.'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('paper-retry-order-btn')), findsOneWidget);

        final firstIdempotencyKey = service.lastSubmittedOrder?.idempotencyKey;
        expect(firstIdempotencyKey, isNotNull);

        // Now clear error and retry
        service.errorToThrow = null;
        await tester.tap(find.byKey(const Key('paper-retry-order-btn')));
        await tester.pumpAndSettle();

        // Verify same idempotency key was reused on retry
        expect(service.lastSubmittedOrder?.idempotencyKey, firstIdempotencyKey);
        expect(find.byKey(const Key('paper-order-success')), findsOneWidget);
      },
    );

    testWidgets('refresh button triggers account reload', (tester) async {
      final service = FakePaperTradingService();
      await tester.pumpWidget(createTestWidget(tester, service));
      await tester.pumpAndSettle();

      expect(service.getAccountCalls, 1);
      await tester.tap(find.byKey(const Key('paper-refresh-btn')));
      await tester.pumpAndSettle();
      expect(service.getAccountCalls, 2);
    });
  });
}
