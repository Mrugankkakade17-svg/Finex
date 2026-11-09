import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('cold launch requires an explicit synthetic learner sign-in', (
    tester,
  ) async {
    await tester.pumpWidget(const FinExApp());
    await tester.pumpAndSettle();

    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(find.text('Educational consent'), findsNothing);
    expect(find.byType(Scaffold), findsOneWidget);
  });

  testWidgets(
    'legacy device completion cannot authorize the full application',
    (tester) async {
      SharedPreferences.setMockInitialValues({
        'finex_is_authenticated': true,
        'finex_s1_onboarding_journey_v1':
            '{"schemaVersion":1,"correlationId":"old-pilot",'
            '"integrationMode":"fixture","consentRecorded":true,'
            '"profileSubmitted":true,"completed":true}',
      });
      await tester.pumpWidget(const FinExApp());
      await tester.pumpAndSettle();

      expect(find.text('Choose a synthetic learner'), findsOneWidget);
      expect(find.text('Onboarding complete'), findsNothing);
    },
  );
}
