import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/theme/app_theme.dart';
import 'package:frontend_flutter/shared/widgets/app_button.dart';
import 'package:frontend_flutter/features/onboarding/models/s1_onboarding_contract.dart';
import 'package:frontend_flutter/features/onboarding/services/s1_onboarding_journey_store.dart';
import 'package:frontend_flutter/features/risk/presentation/s2_risk_page.dart';
import 'package:frontend_flutter/features/risk/services/s2_risk_contract_client.dart';

FixtureS2RiskClient baseClient() => FixtureS2RiskClient(
  loader: () async =>
      File('assets/s2_risk_fixtures.v1.json').readAsStringSync(),
);

class DelayedClient extends S2RiskClient {
  final base = baseClient();
  final Completer<void>? gate;
  bool failLoad;
  bool failSubmit;
  int calls = 0;
  DelayedClient({this.gate, this.failLoad = false, this.failSubmit = false});
  @override
  List<Map<String, dynamic>> get profiles => base.profiles;
  @override
  Future<S2Questionnaire> loadQuestionnaire() async {
    if (failLoad) {
      failLoad = false;
      throw const S2RiskException('RISK_ASSESSMENT_UNAVAILABLE');
    }
    return base.loadQuestionnaire();
  }

  @override
  Future<S2RiskResult> submit(
    Map<String, dynamic> request, {
    String? correlationId,
  }) async {
    calls += 1;
    if (failSubmit) {
      failSubmit = false;
      throw const S2RiskException('RISK_ASSESSMENT_UNAVAILABLE');
    }
    await gate?.future;
    return base.submit(request);
  }
}

Future<void> pumpRisk(
  WidgetTester tester, {
  S2RiskClient? client,
  bool complete = true,
}) async {
  final store = InMemoryS1OnboardingJourneyStore();
  if (complete) {
    store.current = const S1OnboardingJourney(
      correlationId: 'flutter-s2-proof',
      integrationMode: S1IntegrationMode.fixture,
      consentRecorded: true,
      completed: true,
    );
  }
  await tester.pumpWidget(
    MaterialApp(
      theme: AppTheme.darkTheme,
      home: Scaffold(
        body: S2RiskPage(client: client ?? baseClient(), journeyStore: store),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> tap(WidgetTester tester, Key key) async {
  final target = find.byKey(key);
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pump();
}

Future<void> submitPreset(WidgetTester tester) async {
  await tap(tester, const Key('s2-preset'));
  await tester.pumpAndSettle();
  await tester.tap(find.text('All midpoint answers map to Moderate').last);
  await tester.pumpAndSettle();
  for (var i = 0; i < 9; i++) {
    await tap(tester, const Key('s2-next'));
  }
  await tap(tester, const Key('s2-next'));
}

void main() {
  test('fresh local journey IDs are unique and contain no profile data', () {
    final ids = List.generate(
      100,
      (_) => createS1Journey(S1IntegrationMode.fixture).correlationId,
    );
    expect(ids.toSet().length, 100);
    expect(
      ids.every((id) => RegExp(r'^flutter-\d+-[0-9a-f]{1,8}$').hasMatch(id)),
      isTrue,
    );
  });
  testWidgets('requires completion before exposing questions', (tester) async {
    await pumpRisk(tester, complete: false);
    expect(find.text('Complete onboarding first'), findsOneWidget);
    expect(find.byKey(const Key('s2-next')), findsNothing);
  });
  testWidgets('selection is required and survives back navigation', (
    tester,
  ) async {
    await pumpRisk(tester);
    await tap(tester, const Key('s2-next'));
    expect(find.text('Please select an option to continue.'), findsOneWidget);
    await tap(tester, const Key('s2-option-W1_C'));
    await tap(tester, const Key('s2-next'));
    await tap(tester, const Key('s2-previous'));
    expect(
      tester
          .widget<RadioListTile<String>>(
            find.byKey(const Key('s2-option-W1_C')),
          )
          .value,
      'W1_C',
    );
    expect(find.text('Question 1 of 10'), findsOneWidget);
    expect(
      tester
          .widget<RadioGroup<String>>(find.byType(RadioGroup<String>))
          .groupValue,
      'W1_C',
    );
  });
  testWidgets(
    'result discloses versions/method/time/limitations and restart clears answers',
    (tester) async {
      await pumpRisk(tester);
      await submitPreset(tester);
      await tester.pumpAndSettle();
      expect(find.text('Moderate'), findsOneWidget);
      expect(find.text('Composite: 50/100'), findsOneWidget);
      expect(find.textContaining('deterministic_v1.0.0'), findsOneWidget);
      expect(find.textContaining('2026-10-10T00:00:00Z'), findsOneWidget);
      expect(find.text(s2RiskLimitation), findsOneWidget);
      await tap(tester, const Key('s2-restart'));
      await tester.pumpAndSettle();
      expect(find.text('Question 1 of 10'), findsOneWidget);
      expect(find.text('Moderate'), findsNothing);
      await tap(tester, const Key('s2-next'));
      expect(find.text('Please select an option to continue.'), findsOneWidget);
    },
  );
  testWidgets(
    'failure retains answers and retries without duplicate submission',
    (tester) async {
      final client = DelayedClient(failSubmit: true);
      await pumpRisk(tester, client: client);
      await submitPreset(tester);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('s2-error')), findsOneWidget);
      await tap(tester, const Key('s2-next'));
      await tester.pumpAndSettle();
      expect(find.text('Moderate'), findsOneWidget);
      expect(client.calls, 2);
    },
  );
  testWidgets('pending calculation disables actions with a live status', (
    tester,
  ) async {
    final gate = Completer<void>();
    final client = DelayedClient(gate: gate);
    await pumpRisk(tester, client: client);
    await submitPreset(tester);
    expect(find.text('Calculating educational profile…'), findsOneWidget);
    expect(
      tester.widget<ElevatedButton>(find.byKey(const Key('s2-next'))).onPressed,
      isNull,
    );
    gate.complete();
    await tester.pumpAndSettle();
    expect(find.text('Moderate'), findsOneWidget);
    expect(client.calls, 1);
  });
  testWidgets('load error is retried and a 390px view has no overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await pumpRisk(tester, client: DelayedClient(failLoad: true));
    await tap(tester, const Key('s2-retry-load'));
    await tester.pumpAndSettle();
    expect(find.text('Question 1 of 10'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('long onboarding-to-risk button remains usable with large text', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 260,
              child: MediaQuery(
                data: const MediaQueryData(textScaler: TextScaler.linear(1.5)),
                child: AppButton(
                  label: 'Continue to educational risk profile',
                  icon: Icons.shield_outlined,
                  onPressed: () {},
                ),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Continue to educational risk profile'), findsOneWidget);
  });
}
