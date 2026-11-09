import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/theme/app_theme.dart';
import 'package:frontend_flutter/features/market/presentation/market_page.dart';

// Mock service futures resolve after 300-400ms; pump comfortably past
// that without using pumpAndSettle, which never completes while an
// indeterminate CircularProgressIndicator is on screen.
const _mockLatency = Duration(milliseconds: 500);

void main() {
  testWidgets('shows a validation error when searching with an empty query',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const MarketPage()),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pump();

    expect(
      find.text('Enter a symbol or company name to search.'),
      findsOneWidget,
    );
  });

  testWidgets('shows an empty state when no securities match',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const MarketPage()),
    );

    await tester.enterText(find.byType(TextField), 'ZZZUNKNOWN');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pump(_mockLatency);

    expect(find.text('No matches'), findsOneWidget);
  });

  testWidgets('loads a quote with freshness info after selecting a result',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const MarketPage()),
    );

    await tester.enterText(find.byType(TextField), 'AAPL');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pump(_mockLatency);

    await tester.tap(find.byKey(const Key('market-result-AAPL')));
    await tester.pump(_mockLatency);

    expect(find.byKey(const Key('quote-freshness')), findsOneWidget);
  });

  testWidgets('shows a price-unavailable state for the provider-outage symbol',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const MarketPage()),
    );

    await tester.enterText(find.byType(TextField), 'DOWN');
    await tester.tap(find.widgetWithText(FilledButton, 'Search'));
    await tester.pump(_mockLatency);

    await tester.tap(find.byKey(const Key('market-result-DOWN')));
    await tester.pump(_mockLatency);

    expect(find.byKey(const Key('quote-unavailable')), findsOneWidget);
  });
}
