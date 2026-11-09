import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend_flutter/main.dart';
import 'package:frontend_flutter/shared/widgets/app_button.dart';
import 'package:frontend_flutter/shared/widgets/app_card.dart';
import 'package:frontend_flutter/shared/widgets/app_text_field.dart';
import 'package:frontend_flutter/shared/widgets/empty_view.dart';
import 'package:frontend_flutter/shared/widgets/error_view.dart';
import 'package:frontend_flutter/shared/widgets/loading_view.dart';

void main() {
  testWidgets('FinEx app shell loads', (WidgetTester tester) async {
    await tester.pumpWidget(const FinExApp());
    await tester.pumpAndSettle();

    expect(find.byType(Scaffold), findsOneWidget);
    expect(find.text('FinEx'), findsOneWidget);
  });

  testWidgets('AppButton shows loading state', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AppButton(
            label: 'Continue',
            loading: true,
            onPressed: () {},
          ),
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('AppButton can be disabled', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: AppButton(
            label: 'Continue',
            enabled: false,
            onPressed: () {},
          ),
        ),
      ),
    );

    final button = tester.widget<ElevatedButton>(
      find.byType(ElevatedButton),
    );

    expect(button.onPressed, isNull);
  });

  testWidgets('AppTextField shows error state', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppTextField(
            label: 'Email',
            errorText: 'Invalid email',
          ),
        ),
      ),
    );

    expect(find.text('Invalid email'), findsOneWidget);
  });

  testWidgets('AppTextField can be disabled', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppTextField(
            label: 'Email',
            enabled: false,
          ),
        ),
      ),
    );

    final field = tester.widget<TextField>(
      find.byType(TextField),
    );

    expect(field.enabled, isFalse);
  });

  testWidgets('AppTextField shows loading indicator',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppTextField(
            label: 'Email',
            loading: true,
          ),
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('AppCard renders content', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppCard(
            child: Text('FinEx Card'),
          ),
        ),
      ),
    );

    expect(find.text('FinEx Card'), findsOneWidget);
  });

  testWidgets('EmptyView renders empty state', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: EmptyView(
            title: 'No data',
            message: 'There is no data available.',
          ),
        ),
      ),
    );

    expect(find.text('No data'), findsOneWidget);
    expect(find.text('There is no data available.'), findsOneWidget);
  });

  testWidgets('ErrorView renders error state', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ErrorView(
            message: 'Something failed.',
            onRetry: () {},
          ),
        ),
      ),
    );

    expect(find.text('Something failed.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
  });

  testWidgets('LoadingView renders loading state',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: LoadingView(
            message: 'Loading FinEx data...',
          ),
        ),
      ),
    );

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading FinEx data...'), findsOneWidget);
  });
}