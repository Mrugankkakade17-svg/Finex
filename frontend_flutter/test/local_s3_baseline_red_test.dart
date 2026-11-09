import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/local_application_fake.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  for (final route in {
    '/market': 'Supported synthetic instruments',
    '/watchlist': 'Owned watchlists',
    '/account': 'Simulated paper account',
  }.entries) {
    testWidgets('${route.key} is an owned S3 screen, not a pending pilot', (
      tester,
    ) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = LocalSession(api: api, clock: () => localTestTime);
      try {
        await session.signIn('learner-a');
        await tester.pumpWidget(
          FinExApp(session: session, initialLocation: route.key),
        );
        await tester.pumpAndSettle();
        expect(find.text(route.value), findsOneWidget);
        expect(find.textContaining('Pending Sprint 3 delivery'), findsNothing);
        expect(find.text('₹1,00,000'), findsNothing);
        expect(
          find.textContaining('owned S3 API capability is unavailable'),
          findsOneWidget,
        );
      } finally {
        await tester.pumpWidget(const SizedBox.shrink());
        session.dispose();
      }
    });
  }
}
