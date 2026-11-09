import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_app_widgets.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/features/onboarding/presentation/local_onboarding_page.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/local_application_fake.dart';

class TrackedSession extends LocalSession {
  int disposals = 0;
  TrackedSession(FakeLocalApi api)
    : super(api: api, clock: () => localTestTime);

  bool get hasAttachedListeners => hasListeners;

  @override
  void dispose() {
    disposals++;
    super.dispose();
  }
}

Future<void> tapKey(WidgetTester tester, String key) async {
  final target = find.byKey(Key(key));
  await tester.ensureVisible(target);
  await tester.pumpAndSettle();
  await tester.tap(target);
  await tester.pumpAndSettle();
}

TextField labelField(WidgetTester tester) =>
    tester.widget<TextField>(find.byKey(const Key('local-display-label')));

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('same-key app session replacement cannot retain learner A', (
    tester,
  ) async {
    final apiA = FakeLocalApi();
    apiA.states['learner-a'] = completedTestState('Only learner A');
    final a = TrackedSession(apiA);
    final b = TrackedSession(FakeLocalApi());
    await a.signIn('learner-a');
    await tester.pumpWidget(
      FinExApp(session: a, initialLocation: '/dashboard'),
    );
    await tester.pumpAndSettle();
    expect(find.text('Display label: Only learner A'), findsOneWidget);
    await tester.pumpWidget(
      FinExApp(session: b, initialLocation: '/dashboard'),
    );
    await tester.pumpAndSettle();
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(find.text('Display label: Only learner A'), findsNothing);
    await tester.pumpWidget(const SizedBox.shrink());
    expect(a.disposals, 0);
    expect(b.disposals, 0);
    a.dispose();
    b.dispose();
  });

  testWidgets('same-key API replacement resets owned identity and transport', (
    tester,
  ) async {
    final a = FakeLocalApi();
    final b = FakeLocalApi();
    await tester.pumpWidget(FinExApp(api: a, initialLocation: '/login'));
    await tester.pumpAndSettle();
    final old = tester
        .widget<LocalLoginPage>(find.byType(LocalLoginPage))
        .session;
    await tapKey(tester, 'local-sign-in');
    expect(old.isAuthenticated, isTrue);
    final previousCalls = List<String>.of(a.calls);
    await tester.pumpWidget(FinExApp(api: b, initialLocation: '/login'));
    await tester.pumpAndSettle();
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(old.isAuthenticated, isFalse);
    expect(await old.signIn('learner-a'), isFalse);
    await tapKey(tester, 'local-sign-in');
    expect(b.calls, contains('login:learner-a'));
    expect(a.calls, previousCalls);
    await tester.pumpWidget(const SizedBox.shrink());
    expect(a.closed, isFalse);
    expect(b.closed, isFalse);
  });

  testWidgets('external to owned replacement never disposes external session', (
    tester,
  ) async {
    final external = TrackedSession(FakeLocalApi());
    final replacement = FakeLocalApi();
    await tester.pumpWidget(
      FinExApp(session: external, initialLocation: '/login'),
    );
    await tester.pumpAndSettle();
    await tester.pumpWidget(
      FinExApp(api: replacement, initialLocation: '/login'),
    );
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox.shrink());
    expect(external.disposals, 0);
    expect(await external.signIn('learner-a'), isTrue);
    external.dispose();
    expect(replacement.closed, isFalse);
  });

  testWidgets('owned to external replacement clears owned session and timer', (
    tester,
  ) async {
    final api = FakeLocalApi();
    final external = TrackedSession(FakeLocalApi());
    await tester.pumpWidget(FinExApp(api: api, initialLocation: '/login'));
    await tester.pumpAndSettle();
    final owned = tester
        .widget<LocalLoginPage>(find.byType(LocalLoginPage))
        .session;
    await tapKey(tester, 'local-sign-in');
    await tester.pumpWidget(
      FinExApp(session: external, initialLocation: '/login'),
    );
    await tester.pumpAndSettle();
    expect(owned.isAuthenticated, isFalse);
    expect(await owned.signIn('learner-a'), isFalse);
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    expect(external.disposals, 0);
    external.dispose();
  });

  testWidgets('late replaced owned login cannot install a prior persona', (
    tester,
  ) async {
    final a = FakeLocalApi();
    final b = FakeLocalApi();
    final pending = Completer<LocalLogin>();
    a.onLogin = (_) => pending.future;
    await tester.pumpWidget(FinExApp(api: a, initialLocation: '/login'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-sign-in')));
    await tester.pump();
    await tester.pumpWidget(FinExApp(api: b, initialLocation: '/login'));
    await tester.pump();
    pending.complete(
      LocalLogin(
        accessToken: testBearer('learner-a'),
        expiresAt: localTestTime.add(const Duration(minutes: 30)),
        user: testUser('learner-a'),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Choose a synthetic learner'), findsOneWidget);
    expect(a.calls, ['login:learner-a']);
    expect(b.calls, isEmpty);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('same-page onboarding replacement detaches and rehydrates', (
    tester,
  ) async {
    final apiA = FakeLocalApi();
    final apiB = FakeLocalApi();
    apiA.states['learner-a'] = testState(label: 'Saved A', level: 'beginner');
    apiB.states['learner-b'] = testState(label: 'Saved B', level: 'advanced');
    final a = TrackedSession(apiA);
    final b = TrackedSession(apiB);
    await a.signIn('learner-a');
    await b.signIn('learner-b');
    await tester.pumpWidget(MaterialApp(home: LocalOnboardingPage(session: a)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('local-display-label')));
    await tester.enterText(
      find.byKey(const Key('local-display-label')),
      'Unsaved A',
    );
    await tester.pumpWidget(MaterialApp(home: LocalOnboardingPage(session: b)));
    await tester.pumpAndSettle();
    expect(labelField(tester).controller!.text, 'Saved B');
    expect(a.hasAttachedListeners, isFalse);
    expect(b.hasAttachedListeners, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    expect(b.hasAttachedListeners, isFalse);
    a.dispose();
    b.dispose();
  });

  testWidgets('same-generation late A draft cannot change B input or notice', (
    tester,
  ) async {
    final apiA = FakeLocalApi();
    final apiB = FakeLocalApi();
    apiA.states['learner-a'] = testState(label: 'Saved A', level: 'beginner');
    apiB.states['learner-b'] = testState(label: 'Saved B', level: 'advanced');
    final pending = Completer<LocalOnboardingState>();
    apiA.onDraft = (_, _, _) => pending.future;
    final a = TrackedSession(apiA);
    final b = TrackedSession(apiB);
    await a.signIn('learner-a');
    await b.signIn('learner-b');
    expect(a.generation, b.generation);
    await tester.pumpWidget(MaterialApp(home: LocalOnboardingPage(session: a)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('local-display-label')));
    await tester.enterText(
      find.byKey(const Key('local-display-label')),
      'Request A',
    );
    await tapKey(tester, 'local-save-draft');
    await tester.pumpWidget(MaterialApp(home: LocalOnboardingPage(session: b)));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const Key('local-display-label')));
    await tester.enterText(
      find.byKey(const Key('local-display-label')),
      'Unsaved B',
    );
    pending.complete(testState(label: 'Request A', level: 'beginner'));
    await tester.pumpAndSettle();
    expect(labelField(tester).controller!.text, 'Unsaved B');
    expect(find.textContaining('Draft confirmed saved'), findsNothing);
    expect(b.onboarding!.displayName, 'Saved B');
    await tester.pumpWidget(const SizedBox.shrink());
    a.dispose();
    b.dispose();
  });

  testWidgets('same-key feature gate replacement freshly checks new session', (
    tester,
  ) async {
    final apiA = FakeLocalApi();
    final apiB = FakeLocalApi();
    apiA.states['learner-a'] = completedTestState('Saved A');
    apiB.states['learner-b'] = completedTestState('Saved B');
    final a = TrackedSession(apiA);
    final b = TrackedSession(apiB);
    await a.signIn('learner-a');
    await b.signIn('learner-b');
    await tester.pumpWidget(
      MaterialApp(
        home: LocalFeatureGate(session: a, child: const Text('Owned feature')),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Owned feature'), findsOneWidget);
    final calls = apiB.calls.where((call) => call.startsWith('state:')).length;
    apiB.onState = (_) async =>
        throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
    await tester.pumpWidget(
      MaterialApp(
        home: LocalFeatureGate(session: b, child: const Text('Owned feature')),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      apiB.calls.where((call) => call.startsWith('state:')).length,
      calls + 1,
    );
    expect(find.text('Owned feature'), findsNothing);
    expect(find.textContaining('Local storage is unavailable'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    a.dispose();
    b.dispose();
  });

  testWidgets('failed logout remains usable in a short large-text viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 360);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = FakeLocalApi();
    api.onLogout = (_) async =>
        throw const LocalApiException('API_UNAVAILABLE');
    final session = TrackedSession(api);
    await session.signIn('learner-a');
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2)),
        child: FinExApp(session: session, initialLocation: '/onboarding'),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('local-sign-out')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.text('Retry confirmed sign-out'));
    await tester.pumpAndSettle();
    expect(find.text('Retry confirmed sign-out').hitTestable(), findsOneWidget);
    expect(session.isAuthenticated, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
  });
}
