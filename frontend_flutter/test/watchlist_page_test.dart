import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/theme/app_theme.dart';
import 'package:frontend_flutter/features/market/presentation/watchlist_page.dart';
import 'package:frontend_flutter/features/market/services/market_service.dart';

// Mock service futures resolve after 250ms; pump comfortably past that
// without using pumpAndSettle, which never completes while an
// indeterminate CircularProgressIndicator is on screen.
const _mockLatency = Duration(milliseconds: 400);

void main() {
  testWidgets('shows a loading state before the watchlist resolves',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const WatchlistPage()),
    );

    expect(find.byKey(const Key('watchlist-loading')), findsOneWidget);

    // Let the pending mock-service timer resolve before the test ends.
    await tester.pump(_mockLatency);
  });

  testWidgets('renders the seeded watchlist item once loaded',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const WatchlistPage()),
    );

    await tester.pump(_mockLatency);

    expect(find.text('AAPL'), findsOneWidget);
  });

  testWidgets('removes an item from the watchlist when the remove control is used',
      (WidgetTester tester) async {
    // Ensure watchlist starts with exactly the AAPL seed for this test.
    // Runs outside the fake-async test zone so the mock service's real
    // Future.delayed calls actually complete.
    await tester.runAsync(() async {
      final service = MarketService();
      final current = await service.getWatchlist();
      for (final item in current) {
        if (item.symbol != 'AAPL') {
          await service.removeFromWatchlist(item.symbol);
        }
      }
    });

    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const WatchlistPage()),
    );
    await tester.pump(_mockLatency);

    await tester.tap(find.byIcon(Icons.delete_outline).first);
    await tester.pump(_mockLatency);

    expect(find.byKey(const Key('watchlist-empty')), findsOneWidget);
  });
}
