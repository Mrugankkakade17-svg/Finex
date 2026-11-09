import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart' hide testWidgets;
import 'package:frontend_flutter/core/local_application/local_models.dart';

import 'local_app_widgets_test.dart' show mount, tapKey, testWidgets;
import 'support/local_application_fake.dart';

Future<void> reloadSavedState(WidgetTester tester) async {
  final reload = find.text(
    'Reload saved state (unsaved edits remain in this form)',
  );
  await tester.ensureVisible(reload);
  await tester.pumpAndSettle();
  await tester.tap(reload);
  await tester.pumpAndSettle();
}

String displayLabel(WidgetTester tester) => tester
    .widget<TextField>(find.byKey(const Key('local-display-label')))
    .controller!
    .text;

void main() {
  testWidgets(
    'explicit reload removes old withdrawal claim after other-client recompletion and retains edits',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState('Previously saved');
      await mount(tester, api);
      await tester.ensureVisible(find.byKey(const Key('local-display-label')));
      await tester.enterText(
        find.byKey(const Key('local-display-label')),
        'Keep my unsaved edit',
      );
      await tapKey(tester, 'local-consent-withdraw');
      expect(
        find.textContaining('Consent withdrawal confirmed'),
        findsOneWidget,
      );
      api.states['learner-a'] = completedTestState('Saved by another client');
      await reloadSavedState(tester);
      expect(find.text('Current consent: accepted'), findsOneWidget);
      expect(find.text('Onboarding confirmed complete'), findsOneWidget);
      expect(find.textContaining('Consent withdrawal confirmed'), findsNothing);
      expect(displayLabel(tester), 'Keep my unsaved edit');
    },
  );

  testWidgets(
    'explicit reload removes old completion claim after other-client withdrawal',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      await mount(tester, api);
      await tapKey(tester, 'local-complete');
      expect(
        find.text('Onboarding confirmed complete by the server.'),
        findsOneWidget,
      );
      api.states['learner-a'] = testState(
        label: 'Synthetic A',
        level: 'beginner',
        accepted: false,
      );
      await reloadSavedState(tester);
      expect(find.text('Current consent: not accepted'), findsOneWidget);
      expect(
        find.text('Onboarding confirmed complete by the server.'),
        findsNothing,
      );
      expect(find.text('Onboarding confirmed complete'), findsNothing);
    },
  );

  testWidgets(
    'failed reload retains safe error and edits but retry cannot revive an old success notice',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      await mount(tester, api);
      await tester.ensureVisible(find.byKey(const Key('local-display-label')));
      await tester.enterText(
        find.byKey(const Key('local-display-label')),
        'Keep through load failure',
      );
      await tapKey(tester, 'local-consent-withdraw');
      api.onState = (_) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await reloadSavedState(tester);
      expect(
        find.textContaining('Local storage is unavailable'),
        findsOneWidget,
      );
      expect(find.textContaining('Consent withdrawal confirmed'), findsNothing);
      api.onState = null;
      api.states['learner-a'] = completedTestState('Other client');
      await tester.tap(find.text('Retry loading saved onboarding'));
      await tester.pumpAndSettle();
      expect(find.text('Current consent: accepted'), findsOneWidget);
      expect(find.textContaining('Consent withdrawal confirmed'), findsNothing);
      expect(displayLabel(tester), 'Keep through load failure');
    },
  );

  testWidgets(
    'a failed new consent action must not retain old success feedback',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      await mount(tester, api);
      await tapKey(tester, 'local-consent-withdraw');
      expect(
        find.textContaining('Consent withdrawal confirmed'),
        findsOneWidget,
      );
      api.onConsent = (_, _) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await tapKey(tester, 'local-consent-choice');
      await tapKey(tester, 'local-consent-save');
      expect(
        find.textContaining('Local storage is unavailable'),
        findsOneWidget,
      );
      expect(find.textContaining('Consent withdrawal confirmed'), findsNothing);
      expect(
        tester
            .widget<CheckboxListTile>(
              find.byKey(const Key('local-consent-choice')),
            )
            .value,
        isTrue,
      );
      expect(find.text('Current consent: not accepted'), findsOneWidget);
    },
  );
}
