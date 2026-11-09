import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart' hide testWidgets;
import 'package:flutter_test/flutter_test.dart' as ft;
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/local_application_fake.dart';

final _sessions = <LocalSession>[];
LocalSession trackedSession(FakeLocalApi api) {
  final session = LocalSession(api: api, clock: () => localTestTime);
  _sessions.add(session);
  return session;
}

void testWidgets(String description, Future<void> Function(WidgetTester) body) {
  ft.testWidgets(description, (tester) async {
    try {
      await body(tester);
    } finally {
      await tester.pumpWidget(const SizedBox.shrink());
      for (final session in _sessions) {
        session.dispose();
      }
      _sessions.clear();
    }
  });
}

Future<LocalSession> mount(
  WidgetTester tester,
  FakeLocalApi api, {
  bool signedIn = true,
  String path = '/onboarding',
}) async {
  final session = trackedSession(api);
  if (signedIn) await session.signIn('learner-a');
  await tester.pumpWidget(FinExApp(session: session, initialLocation: path));
  await tester.pumpAndSettle();
  return session;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

Future<void> setProfile(WidgetTester tester, String label) async {
  await tester.ensureVisible(find.byKey(const Key('local-display-label')));
  await tester.enterText(find.byKey(const Key('local-display-label')), label);
  await tapKey(tester, 'local-experience-none');
  await tester.tap(find.text('Beginner').last);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  for (final path in [
    '/onboarding',
    '/consent',
    '/dashboard',
    '/risk',
    '/portfolio',
    '/market',
    '/watchlist',
    '/account',
    '/paper-trading',
    '/goals',
  ]) {
    testWidgets('direct $path is guarded on a cold launch', (tester) async {
      final api = FakeLocalApi();
      await mount(tester, api, signedIn: false, path: path);
      expect(find.text('Choose a synthetic learner'), findsOneWidget);
      expect(api.calls, isEmpty);
    });
  }
  testWidgets('login checks server identity and opens saved onboarding', (
    tester,
  ) async {
    final api = FakeLocalApi();
    final session = await mount(tester, api, signedIn: false, path: '/login');
    await tapKey(tester, 'local-sign-in');
    expect(session.user!.alias, 'learner-a');
    expect(find.text('Saved onboarding'), findsOneWidget);
    expect(find.text('Current consent: not accepted'), findsOneWidget);
  });
  testWidgets('login failure is visible and does not navigate to demo state', (
    tester,
  ) async {
    final api = FakeLocalApi()
      ..onLogin = (_) async =>
          throw const LocalApiException('LOCAL_APPLICATION_ONLY', status: 403);
    await mount(tester, api, signedIn: false, path: '/login');
    await tapKey(tester, 'local-sign-in');
    expect(find.textContaining('LOCAL_APP_ENABLED=true'), findsOneWidget);
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(find.text('Saved onboarding'), findsNothing);
  });
  testWidgets('incomplete server onboarding cannot open a future feature', (
    tester,
  ) async {
    await mount(tester, FakeLocalApi(), path: '/portfolio');
    expect(find.text('Saved onboarding'), findsOneWidget);
    expect(find.text('Saved portfolios'), findsNothing);
  });
  testWidgets(
    'protected feature waits for fresh server state rather than stale completion',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = trackedSession(api);
      await session.signIn('learner-a');
      final pending = Completer<LocalOnboardingState>();
      api.onState = (_) => pending.future;
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: '/dashboard'),
      );
      await tester.pump();
      await tester.pump();
      expect(
        find.text('Checking saved consent and onboarding…'),
        findsOneWidget,
      );
      expect(find.text('Saved onboarding dashboard'), findsNothing);
      pending.complete(completedTestState());
      await tester.pumpAndSettle();
      expect(find.text('Saved onboarding dashboard'), findsOneWidget);
    },
  );
  testWidgets(
    'failed feature state check is visible, retryable and not completed',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = trackedSession(api);
      await session.signIn('learner-a');
      api.onState = (_) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: '/dashboard'),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Local storage is unavailable'),
        findsOneWidget,
      );
      expect(find.text('Saved onboarding dashboard'), findsNothing);
      api.onState = null;
      await tester.tap(find.text('Retry saved-state check'));
      await tester.pumpAndSettle();
      expect(find.text('Saved onboarding dashboard'), findsOneWidget);
    },
  );
  testWidgets(
    'fresh feature entry observes another client consent withdrawal',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = trackedSession(api);
      await session.signIn('learner-a');
      api.states['learner-a'] = testState(
        label: 'Synthetic A',
        level: 'beginner',
        accepted: false,
      );
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: '/dashboard'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Saved onboarding'), findsOneWidget);
      expect(find.text('Current consent: not accepted'), findsOneWidget);
      expect(find.text('Saved onboarding dashboard'), findsNothing);
    },
  );
  for (final route in ['/risk', '/portfolio']) {
    testWidgets(
      '$route uses the delivered S2 screen and fails safely without its owned adapter',
      (tester) async {
        final api = FakeLocalApi();
        api.states['learner-a'] = completedTestState();
        await mount(tester, api, path: route);
        expect(
          find.text(
            route == '/risk' ? 'Saved risk questionnaire' : 'Manual portfolios',
          ),
          findsOneWidget,
        );
        expect(find.textContaining('Pending Sprint 2 delivery'), findsNothing);
        expect(
          find.text(
            'The owned S2 API capability is unavailable. Configure the reviewed local backend; there is no demonstration fallback.',
          ),
          findsOneWidget,
        );
        expect(find.text('₹1,00,000'), findsNothing);
      },
    );
  }
  for (final route in {
    '/paper-trading': 4,
    '/goals': 4,
  }.entries) {
    testWidgets(
      '${route.key} is honest pending S${route.value}, not a hardcoded demo',
      (tester) async {
        final api = FakeLocalApi();
        api.states['learner-a'] = completedTestState();
        await mount(tester, api, path: route.key);
        expect(
          find.textContaining('Pending Sprint ${route.value} delivery'),
          findsOneWidget,
        );
        expect(find.textContaining('demonstration values'), findsOneWidget);
        expect(find.text('₹1,00,000'), findsNothing);
      },
    );
  }
  testWidgets(
    'partial draft can save and resume without granting feature access',
    (tester) async {
      final api = FakeLocalApi();
      final session = await mount(tester, api);
      await tester.ensureVisible(find.byKey(const Key('local-display-label')));
      await tester.enterText(
        find.byKey(const Key('local-display-label')),
        'Synthetic draft',
      );
      await tapKey(tester, 'local-save-draft');
      expect(session.onboarding!.displayName, 'Synthetic draft');
      expect(session.onboarding!.experienceLevel, isNull);
      expect(session.canAccessFeatures, isFalse);
      expect(find.textContaining('Draft confirmed saved'), findsOneWidget);
    },
  );
  testWidgets(
    'completion validates required label visibly and focuses its field',
    (tester) async {
      final api = FakeLocalApi();
      await mount(tester, api);
      await tapKey(tester, 'local-complete');
      expect(
        find.text('Enter a display label before completing onboarding.'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('local-display-label')))
            .focusNode!
            .hasFocus,
        isTrue,
      );
      expect(api.calls.where((call) => call.startsWith('complete')), isEmpty);
    },
  );
  testWidgets('completion validates experience before contacting the server', (
    tester,
  ) async {
    final api = FakeLocalApi();
    await mount(tester, api);
    await tester.ensureVisible(find.byKey(const Key('local-display-label')));
    await tester.enterText(
      find.byKey(const Key('local-display-label')),
      'Synthetic A',
    );
    await tapKey(tester, 'local-complete');
    expect(
      find.text('Select an experience level before completing onboarding.'),
      findsOneWidget,
    );
    expect(api.calls.where((call) => call.startsWith('complete')), isEmpty);
  });
  testWidgets('consent action requires explicit checkbox, not a silent flag', (
    tester,
  ) async {
    final api = FakeLocalApi();
    await mount(tester, api);
    await tapKey(tester, 'local-consent-save');
    expect(
      find.text('Select the educational consent checkbox before accepting.'),
      findsOneWidget,
    );
    expect(api.calls.where((call) => call.startsWith('consent')), isEmpty);
    await tapKey(tester, 'local-consent-choice');
    await tapKey(tester, 'local-consent-save');
    expect(find.text('Current consent: accepted'), findsOneWidget);
  });
  testWidgets('complete saves dirty profile then uses server completion only', (
    tester,
  ) async {
    final api = FakeLocalApi();
    final session = await mount(tester, api);
    await tapKey(tester, 'local-consent-choice');
    await tapKey(tester, 'local-consent-save');
    await setProfile(tester, 'Synthetic A');
    await tapKey(tester, 'local-complete');
    expect(session.canAccessFeatures, isTrue);
    expect(find.text('Onboarding confirmed complete'), findsOneWidget);
    expect(
      api.calls.indexOf('draft:learner-a'),
      lessThan(api.calls.indexOf('complete:learner-a')),
    );
    await tester.ensureVisible(find.text('Continue to saved dashboard'));
    await tester.tap(find.text('Continue to saved dashboard'));
    await tester.pumpAndSettle();
    expect(find.text('Saved onboarding dashboard'), findsOneWidget);
    expect(find.text('Display label: Synthetic A'), findsOneWidget);
  });
  testWidgets(
    'failed save preserves input, scrolls safe error into view and retries',
    (tester) async {
      final api = FakeLocalApi();
      api.onDraft = (_, _, _) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await mount(tester, api);
      await setProfile(tester, 'Keep my synthetic input');
      await tapKey(tester, 'local-save-draft');
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('local-display-label')))
            .controller!
            .text,
        'Keep my synthetic input',
      );
      final error = find.byKey(const Key('local-onboarding-error'));
      expect(error.hitTestable(), findsOneWidget);
      expect(
        find.textContaining('Local storage is unavailable'),
        findsOneWidget,
      );
      expect(find.textContaining('Draft confirmed saved'), findsNothing);
      api.onDraft = null;
      await tapKey(tester, 'local-save-draft');
      expect(find.textContaining('Draft confirmed saved'), findsOneWidget);
    },
  );
  testWidgets('failed consent preserves explicit checkbox choice for retry', (
    tester,
  ) async {
    final api = FakeLocalApi();
    api.onConsent = (_, _) async =>
        throw const LocalApiException('API_UNAVAILABLE');
    await mount(tester, api);
    await tapKey(tester, 'local-consent-choice');
    await tapKey(tester, 'local-consent-save');
    expect(
      tester
          .widget<CheckboxListTile>(
            find.byKey(const Key('local-consent-choice')),
          )
          .value,
      isTrue,
    );
    expect(find.text('Current consent: not accepted'), findsOneWidget);
    api.onConsent = null;
    await tapKey(tester, 'local-consent-save');
    expect(find.text('Current consent: accepted'), findsOneWidget);
  });
  testWidgets(
    'failed completion cannot claim success or navigate to dashboard',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = testState(
        label: 'Synthetic A',
        level: 'beginner',
        accepted: true,
      );
      api.onComplete = (_) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      final session = await mount(tester, api);
      await tapKey(tester, 'local-complete');
      expect(session.canAccessFeatures, isFalse);
      expect(find.text('Onboarding confirmed complete'), findsNothing);
      expect(
        find.textContaining('Local storage is unavailable'),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'withdrawal makes server completion disappear until recompleted',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = await mount(tester, api);
      await tapKey(tester, 'local-consent-withdraw');
      expect(session.canAccessFeatures, isFalse);
      expect(find.text('Onboarding confirmed complete'), findsNothing);
      expect(
        find.textContaining('Consent withdrawal confirmed'),
        findsOneWidget,
      );
    },
  );
  testWidgets('failed logout keeps learner, unsaved input and visible retry', (
    tester,
  ) async {
    final api = FakeLocalApi();
    api.onLogout = (_) async =>
        throw const LocalApiException('API_UNAVAILABLE');
    final session = await mount(tester, api);
    await tester.ensureVisible(find.byKey(const Key('local-display-label')));
    await tester.enterText(
      find.byKey(const Key('local-display-label')),
      'Unsaved synthetic input',
    );
    await tapKey(tester, 'local-sign-out');
    expect(session.user!.alias, 'learner-a');
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('local-display-label')))
          .controller!
          .text,
      'Unsaved synthetic input',
    );
    expect(find.textContaining('Sign-out is not confirmed'), findsOneWidget);
    expect(find.text('Retry confirmed sign-out'), findsOneWidget);
    api.onLogout = null;
    await tester.tap(find.text('Retry confirmed sign-out'));
    await tester.pumpAndSettle();
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(session.user, isNull);
  });
  testWidgets('client expiry returns to login and removes owned form', (
    tester,
  ) async {
    final api = FakeLocalApi()
      ..expiresAt = localTestTime.add(const Duration(seconds: 1));
    await mount(tester, api);
    await tester.pump(const Duration(seconds: 2));
    await tester.pumpAndSettle();
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(find.text('Saved onboarding'), findsNothing);
    expect(find.textContaining('local session ended'), findsOneWidget);
  });
  testWidgets(
    'pilot is separately labelled and cannot authorize full-app routes',
    (tester) async {
      final api = FakeLocalApi();
      await mount(tester, api, signedIn: false, path: '/pilot/onboarding');
      expect(
        find.textContaining('Nonpersistent compatibility pilot.'),
        findsOneWidget,
      );
      expect(find.text('Educational consent'), findsOneWidget);
      expect(api.calls, isEmpty);
    },
  );
  testWidgets('unimplemented excluded routes are not advertised as delivered', (
    tester,
  ) async {
    await mount(tester, FakeLocalApi(), signedIn: false, path: '/chat');
    expect(find.textContaining('Page not found.'), findsOneWidget);
    expect(find.text('Start Assistant'), findsNothing);
  });
  for (final signedIn in [false, true]) {
    testWidgets(
      '320px layout at 200percent text remains usable ${signedIn ? 'onboarding' : 'login'}',
      (tester) async {
        tester.view.physicalSize = const Size(320, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = FakeLocalApi();
        final session = trackedSession(api);
        if (signedIn) await session.signIn('learner-a');
        await tester.pumpWidget(
          MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(2)),
            child: FinExApp(
              session: session,
              initialLocation: signedIn ? '/onboarding' : '/login',
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        final target = find.byKey(
          Key(signedIn ? 'local-complete' : 'local-sign-in'),
        );
        await tester.ensureVisible(target);
        await tester.pumpAndSettle();
        expect(tester.getSize(target).height, greaterThanOrEqualTo(48));
        expect(tester.takeException(), isNull);
      },
    );
  }
  testWidgets(
    'scoped primary controls use measured contrast and visible focus style',
    (tester) async {
      await mount(tester, FakeLocalApi(), signedIn: false, path: '/login');
      final button = find.descendant(
        of: find.byKey(const Key('local-sign-in')),
        matching: find.byType(ElevatedButton),
      );
      final theme = Theme.of(tester.element(button));
      expect(
        theme.elevatedButtonTheme.style!.backgroundColor!.resolve({}),
        const Color(0xff047857),
      );
      expect(
        theme.elevatedButtonTheme.style!.foregroundColor!.resolve({}),
        Colors.white,
      );
      expect(
        theme.elevatedButtonTheme.style!.side!.resolve({
          WidgetState.focused,
        })!.width,
        2,
      );
    },
  );
}
