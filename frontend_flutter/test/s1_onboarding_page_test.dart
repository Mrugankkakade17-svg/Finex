import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/features/onboarding/models/s1_onboarding_contract.dart';
import 'package:frontend_flutter/features/onboarding/presentation/s1_onboarding_page.dart';
import 'package:frontend_flutter/features/onboarding/services/s1_onboarding_contract_client.dart';
import 'package:frontend_flutter/features/onboarding/services/s1_onboarding_journey_store.dart';

void main() {
  Future<void> pumpPage(
    WidgetTester tester, {
    required S1OnboardingContractClient client,
    required InMemoryS1OnboardingJourneyStore store,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: S1OnboardingPage(
          config: S1OnboardingConfig(
            mode: S1IntegrationMode.fixture,
            apiBaseUri: Uri.parse('http://127.0.0.1:8000'),
          ),
          client: client,
          journeyStore: store,
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  Future<void> tapAppButton(WidgetTester tester, Key key) async {
    final button = find.descendant(
      of: find.byKey(key),
      matching: find.byType(ElevatedButton),
    );
    await tester.ensureVisible(button);
    await tester.tap(button);
  }

  testWidgets(
    'requires an explicit consent choice before profile submission is available',
    (tester) async {
      final store = InMemoryS1OnboardingJourneyStore();
      await pumpPage(tester, client: _FakeClient(), store: store);

      expect(find.text('Educational consent'), findsOneWidget);
      final consentButton = find.descendant(
        of: find.byKey(const Key('s1-consent-submit')),
        matching: find.byType(ElevatedButton),
      );
      final button = tester.widget<ElevatedButton>(consentButton);
      expect(button.onPressed, isNull);

      await tester.tap(find.byKey(const Key('s1-consent-checkbox')));
      await tester.pump();
      expect(tester.widget<ElevatedButton>(consentButton).onPressed, isNotNull);
    },
  );

  testWidgets('keeps an accessible loading label visible while consent saves', (
    tester,
  ) async {
    final completion = Completer<void>();
    await pumpPage(
      tester,
      client: _FakeClient(consentGate: completion),
      store: InMemoryS1OnboardingJourneyStore(),
    );

    await tester.tap(find.byKey(const Key('s1-consent-checkbox')));
    await tester.pump();
    await tapAppButton(tester, const Key('s1-consent-submit'));
    await tester.pump();

    expect(find.text('Recording consent…'), findsOneWidget);
    expect(
      find.bySemanticsLabel('Recording consent… in progress'),
      findsOneWidget,
    );
    final action = find.descendant(
      of: find.byKey(const Key('s1-consent-submit')),
      matching: find.byType(ElevatedButton),
    );
    expect(tester.widget<ElevatedButton>(action).onPressed, isNull);

    completion.complete();
    await tester.pumpAndSettle();
    expect(find.text('A small, useful profile'), findsOneWidget);
  });

  testWidgets(
    'handles fixture consent/profile/completion and persists completion',
    (tester) async {
      final store = InMemoryS1OnboardingJourneyStore();
      final client = _FakeClient();
      await pumpPage(tester, client: client, store: store);

      await tester.tap(find.byKey(const Key('s1-consent-checkbox')));
      await tester.pump();
      await tapAppButton(tester, const Key('s1-consent-submit'));
      await tester.pumpAndSettle();

      expect(find.text('A small, useful profile'), findsOneWidget);
      expect(find.textContaining('Fixture mode'), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('s1-display-name')),
        'Mobile Tester',
      );
      await tester.tap(find.byKey(const Key('s1-experience-level')));
      await tester.pumpAndSettle();
      await tester.tap(find.textContaining('Intermediate').last);
      await tester.pump();
      await tapAppButton(tester, const Key('s1-profile-submit'));
      await tester.pumpAndSettle();

      expect(find.text('Onboarding complete'), findsOneWidget);
      expect(client.consentCalls, 1);
      expect(client.profileCalls, 1);
      expect(client.completionCalls, 1);
      expect(store.current!.completed, isTrue);
      expect(store.current!.profileSubmitted, isTrue);
    },
  );

  testWidgets('shows a visible retry state after a contract failure', (
    tester,
  ) async {
    final store = InMemoryS1OnboardingJourneyStore()
      ..current = createS1Journey(S1IntegrationMode.fixture)
          .copyWith(consentRecorded: true);
    final client = _FakeClient(failProfile: true);
    await pumpPage(tester, client: client, store: store);

    await tester.enterText(
      find.byKey(const Key('s1-display-name')),
      'Mobile Tester',
    );
    await tester.tap(find.byKey(const Key('s1-experience-level')));
    await tester.pumpAndSettle();
    await tester.tap(find.textContaining('Beginner').last);
    await tester.pump();
    await tapAppButton(tester, const Key('s1-profile-submit'));
    await tester.pumpAndSettle();

    expect(find.text('API service unavailable'), findsOneWidget);
    expect(find.text('Retry submission'), findsOneWidget);
    final errorSemantics = tester.widget<Semantics>(
      find.byKey(const Key('s1-onboarding-error')),
    );
    expect(
      errorSemantics.properties.label,
      'Onboarding error: API service unavailable',
    );
    expect(errorSemantics.properties.liveRegion, isTrue);
    expect(find.byKey(const Key('s1-display-name')), findsOneWidget);
  });
}

class _FakeClient implements S1OnboardingContractClient {
  final bool failProfile;
  final Completer<void>? consentGate;
  int consentCalls = 0;
  int profileCalls = 0;
  int completionCalls = 0;

  _FakeClient({this.failProfile = false, this.consentGate});

  @override
  Future<S1ConsentResult> captureConsent(S1ConsentInput input) async {
    consentCalls += 1;
    if (consentGate != null) {
      await consentGate!.future;
    }
    return S1ConsentResult(
      consentVersion: input.consentVersion,
      consentStatus: 'accepted',
      recordedAt: DateTime.utc(2026, 10, 10),
    );
  }

  @override
  Future<S1CompletionResult> completeOnboarding(S1CompletionInput input) async {
    completionCalls += 1;
    return S1CompletionResult(
      onboardingCompleted: true,
      consentVersion: input.consentVersion,
      profileSchemaVersion: input.profileSchemaVersion,
      fixtureMode: 's1_dat_01',
      recordedAt: DateTime.utc(2026, 10, 10),
    );
  }

  @override
  Future<S1ProfileResult> submitProfile(S1ProfileInput input) async {
    profileCalls += 1;
    if (failProfile) {
      throw const S1OnboardingException(
        'API service unavailable',
        code: 'API_UNAVAILABLE',
      );
    }
    return S1ProfileResult(
      profileSchemaVersion: input.profileSchemaVersion,
      profileState: 'completed',
      displayName: input.displayName,
      experienceLevel: input.experienceLevel,
      recordedAt: DateTime.utc(2026, 10, 10),
    );
  }
}
