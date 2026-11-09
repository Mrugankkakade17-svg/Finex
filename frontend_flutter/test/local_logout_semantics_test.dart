import 'dart:ui' show SemanticsAction, Tristate;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/local_application_fake.dart';

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  for (final compact in [false, true]) {
    testWidgets(
      'failed logout exposes safe live-region and enabled retry semantics ${compact ? 'compact' : 'desktop'}',
      (tester) async {
        final semantics = tester.ensureSemantics();
        LocalSession? session;
        try {
          tester.view.physicalSize = compact
              ? const Size(320, 360)
              : const Size(1280, 800);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final api = FakeLocalApi();
          api.onLogout = (_) async =>
              throw const LocalApiException('API_UNAVAILABLE');
          session = LocalSession(api: api, clock: () => localTestTime);
          await session.signIn('learner-a');
          await tester.pumpWidget(
            MediaQuery(
              data: MediaQueryData(
                textScaler: TextScaler.linear(compact ? 2 : 1),
              ),
              child: FinExApp(session: session, initialLocation: '/onboarding'),
            ),
          );
          await tester.pumpAndSettle();
          await tester.tap(find.byKey(const Key('local-sign-out')));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
          final error = find.byWidgetPredicate(
            (widget) =>
                widget is Semantics &&
                widget.properties.liveRegion == true &&
                widget.properties.label?.contains(
                      'Sign-out is not confirmed',
                    ) ==
                    true,
          );
          expect(error, findsOneWidget);
          await tester.ensureVisible(error);
          await tester.pumpAndSettle();
          final errorNode = tester.getSemantics(error);
          expect(errorNode.flagsCollection.isLiveRegion, isTrue);
          expect(errorNode.label, contains('form input have been retained'));
          final retry = find.widgetWithText(
            TextButton,
            'Retry confirmed sign-out',
          );
          await tester.ensureVisible(retry);
          await tester.pumpAndSettle();
          final retryNode = tester.getSemantics(retry);
          expect(retryNode.label, 'Retry confirmed sign-out');
          expect(retryNode.flagsCollection.isButton, isTrue);
          expect(retryNode.flagsCollection.isEnabled, Tristate.isTrue);
          expect(
            retryNode.getSemanticsData().hasAction(SemanticsAction.tap),
            isTrue,
          );
          expect(session.user!.alias, 'learner-a');
          api.onLogout = null;
          await tester.tap(retry);
          await tester.pumpAndSettle();
          expect(find.text('Choose a synthetic learner'), findsOneWidget);
        } finally {
          await tester.pumpWidget(const SizedBox.shrink());
          session?.dispose();
          semantics.dispose();
        }
      },
    );
  }
}
