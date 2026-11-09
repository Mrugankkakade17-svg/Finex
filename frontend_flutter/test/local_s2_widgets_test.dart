import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/main.dart';

import 'support/local_application_fake.dart';
import 'support/local_s2_data.dart';
import 'support/local_s2_fake.dart';

class CatalogFaultS2Api extends FakeLocalS2Api {
  bool catalogUnavailable = true;
  @override
  Future<LocalS2Reply<LocalInstrumentCatalog>> instruments(String bearer) {
    if (!catalogUnavailable) return super.instruments(bearer);
    calls.add('instruments');
    return Future.error(
      const LocalApiException('LOCAL_CATALOG_UNAVAILABLE', status: 503),
    );
  }
}

void main() {
  late FakeLocalApi api;
  late FakeLocalS2Api s2;
  late LocalSession session;
  setUp(() {
    api = FakeLocalApi();
    api.states['learner-a'] = completedTestState();
    api.states['learner-b'] = completedTestState('Synthetic B');
    s2 = FakeLocalS2Api();
    session = LocalSession(api: api, s2Api: s2, clock: () => localTestTime);
  });
  void ownedTest(String name, WidgetTesterCallback body) =>
      testWidgets(name, (tester) async {
        try {
          await body(tester);
        } finally {
          await tester.pumpWidget(const SizedBox.shrink());
          session.dispose();
        }
      });
  Future<void> launch(WidgetTester tester, String path) async {
    await session.signIn('learner-a');
    await tester.pumpWidget(FinExApp(session: session, initialLocation: path));
    await tester.pumpAndSettle();
  }

  Future<void> click(WidgetTester tester, Finder finder) async {
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  Future<void> type(WidgetTester tester, String key, String text) async {
    final finder = find.byKey(Key(key));
    await tester.ensureVisible(finder);
    await tester.enterText(finder, text);
    await tester.pumpAndSettle();
  }

  Future<void> choose(WidgetTester tester, String label, String option) async {
    final finder = find.byWidgetPredicate(
      (w) =>
          w is DropdownButtonFormField<String> &&
          w.decoration.labelText == label,
    );
    await click(tester, finder);
    await click(tester, find.text(option).last);
  }

  ownedTest(
    'risk restores approved ten-question draft and saves partial or clear without scoring',
    (tester) async {
      s2.draft = LocalRiskInput.fromJson(riskInput(partial: true));
      await launch(tester, '/risk');
      expect(find.byType(DropdownButtonFormField<String>), findsNWidgets(10));
      expect(find.textContaining('1 of 10 answered'), findsOneWidget);
      await click(tester, find.byKey(const Key('risk-save')));
      expect(s2.draft.answers.length, 1);
      expect(s2.calls.contains('assess'), isFalse);
      await click(tester, find.byKey(const Key('risk-clear')));
      expect(s2.draft.answers, isEmpty);
      expect(find.textContaining('0 of 10 answered'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'risk failed save preserves selected answers with visible focused safe feedback',
    (tester) async {
      await launch(tester, '/risk');
      await choose(tester, 'Answer W1', 'Synthetic option C');
      s2.onDraft = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      await click(tester, find.byKey(const Key('risk-save')));
      expect(find.textContaining('1 of 10 answered'), findsOneWidget);
      expect(find.textContaining('local API is unavailable'), findsOneWidget);
      expect(FocusManager.instance.primaryFocus?.context?.widget, isA<Focus>());
      expect(
        tester.getRect(find.textContaining('local API is unavailable')).top,
        lessThan(tester.view.physicalSize.height),
      );
      s2.onDraft = null;
      await click(tester, find.byKey(const Key('risk-save')));
      expect(s2.draft.answers.length, 1);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'assessment uncertainty keeps one complete immutable input and UUID until explicit retry',
    (tester) async {
      s2.draft = LocalRiskInput.fromJson(riskInput());
      final keys = <String>[];
      final inputs = <LocalRiskInput>[];
      s2.onAssess = (input, key) async {
        keys.add(key);
        inputs.add(input);
        if (keys.length == 1) throw const LocalApiException('REQUEST_TIMEOUT');
        return s2.reply(
          LocalSavedRiskAssessment.fromJson(savedRiskData()),
          s2.time,
        );
      };
      await launch(tester, '/risk');
      await click(tester, find.byKey(const Key('risk-assess')));
      expect(keys.length, 1);
      expect(find.text('Retry same frozen assessment'), findsOneWidget);
      expect(
        tester
            .widget<DropdownButtonFormField<String>>(
              find.byType(DropdownButtonFormField<String>).first,
            )
            .onChanged,
        isNull,
      );
      await click(tester, find.byKey(const Key('risk-assess')));
      expect(keys.length, 2);
      expect(keys[0] == keys[1], isTrue);
      expect(identical(inputs[0], inputs[1]), isTrue);
      expect(find.text('Saved result: Moderate'), findsOneWidget);
      expect(
        find.textContaining('server deterministic', findRichText: true),
        findsNothing,
      );
      expect(find.text(localRiskLimitation), findsOneWidget);
      expect(
        find.text('Original approved rules and assumptions'),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'portfolio create update and deliberate deletion use server acknowledgments',
    (tester) async {
      await launch(tester, '/portfolio');
      await type(tester, 'portfolio-name', 'Synthetic learning');
      await type(tester, 'portfolio-description', 'Practice allocation');
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.portfolioItems.single.name, 'Synthetic learning');
      expect(s2.portfolioItems.single.description, 'Practice allocation');
      await click(tester, find.text('Edit Synthetic learning'));
      await type(tester, 'portfolio-name', 'Synthetic revised');
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.portfolioItems.single.name, 'Synthetic revised');
      await click(tester, find.text('Delete Synthetic revised'));
      await click(tester, find.text('Delete saved item'));
      expect(s2.portfolioItems, isEmpty);
      expect(find.text('No saved portfolios yet.'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'catalogue failure retains confirmed portfolio CRUD with holding creation gated',
    (tester) async {
      session.dispose();
      final catalogApi = CatalogFaultS2Api();
      s2 = catalogApi;
      session = LocalSession(api: api, s2Api: s2, clock: () => localTestTime);
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      expect(find.text('Edit Synthetic portfolio'), findsOneWidget);
      expect(find.text('Delete Synthetic portfolio'), findsOneWidget);
      expect(
        find.text('Catalogue not confirmed. New holdings are unavailable.'),
        findsOneWidget,
      );
      await click(tester, find.text('Edit Synthetic portfolio'));
      await type(tester, 'portfolio-name', 'Revised without catalogue');
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.portfolioItems.single.name, 'Revised without catalogue');
      await click(tester, find.text('Open Revised without catalogue'));
      final save = find.descendant(
        of: find.byKey(const Key('holding-save')),
        matching: find.byType(ElevatedButton),
      );
      expect(tester.widget<ElevatedButton>(save).onPressed, isNull);
      expect(s2.calls.contains('createHolding'), isFalse);
      await click(tester, find.text('Delete Revised without catalogue'));
      await click(tester, find.text('Delete saved item'));
      expect(s2.portfolioItems, isEmpty);
      await type(tester, 'portfolio-name', 'New without catalogue');
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.portfolioItems.single.name, 'New without catalogue');
      expect(tester.widget<ElevatedButton>(save).onPressed, isNull);
      final mutations = s2.calls
          .where(
            (v) =>
                v == 'updatePortfolio' ||
                v == 'deletePortfolio' ||
                v == 'createPortfolio',
          )
          .length;
      catalogApi.catalogUnavailable = false;
      await click(tester, find.byKey(const Key('catalogue-retry')));
      expect(
        find.byWidgetPredicate(
          (w) =>
              w is DropdownButtonFormField<String> &&
              w.decoration.labelText == 'Supported synthetic instrument',
        ),
        findsOneWidget,
      );
      expect(
        s2.calls
            .where(
              (v) =>
                  v == 'updatePortfolio' ||
                  v == 'deletePortfolio' ||
                  v == 'createPortfolio',
            )
            .length,
        mutations,
      );
    },
  );
  ownedTest(
    'uncertain portfolio create retains input and requires reconciliation before deliberate new POST',
    (tester) async {
      s2.onCreate = (_) async =>
          throw const LocalApiException('REQUEST_TIMEOUT');
      await launch(tester, '/portfolio');
      await type(tester, 'portfolio-name', 'Keep create');
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('portfolio-name')))
            .controller!
            .text,
        'Keep create',
      );
      expect(s2.calls.where((v) => v == 'createPortfolio').length, 1);
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.calls.where((v) => v == 'createPortfolio').length, 1);
      await click(tester, find.byKey(const Key('portfolio-reload')));
      expect(s2.calls.where((v) => v == 'createPortfolio').length, 1);
      await click(
        tester,
        find.text('I checked the list; allow a new portfolio create'),
      );
      s2.onCreate = null;
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.calls.where((v) => v == 'createPortfolio').length, 2);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'holding CRUD validates exact units and shows backend-only empty and complete metrics',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      await click(tester, find.text('Open Synthetic portfolio'));
      expect(find.text('Valuation EMPTY • Data CACHED'), findsOneWidget);
      await choose(
        tester,
        'Supported synthetic instrument',
        'SYN:AAPL • Synthetic AAPL',
      );
      await type(tester, 'holding-quantity', '1e3');
      await type(tester, 'holding-cost', '0');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.holdingItems, isEmpty);
      expect(find.textContaining('no sign or exponent'), findsOneWidget);
      await type(tester, 'holding-quantity', '10.0');
      await type(tester, 'holding-cost', '150');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.holdingItems.single.quantity, '10.000000');
      expect(find.text('Valuation COMPLETE • Data CACHED'), findsOneWidget);
      expect(find.text('Market value: 2000.00 USD'), findsOneWidget);
      expect(
        find.textContaining('not refreshed market prices'),
        findsOneWidget,
      );
      await click(tester, find.text('Edit holding SYN:AAPL'));
      await type(tester, 'holding-quantity', '11');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.holdingItems.single.quantity, '11.000000');
      await click(tester, find.text('Delete holding SYN:AAPL'));
      await click(tester, find.text('Delete saved item'));
      expect(s2.holdingItems, isEmpty);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  ownedTest(
    'quote failure retains confirmed holding CRUD and deliberate valuation retry',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      s2.holdingItems = [LocalHolding.fromJson(holdingData())];
      s2.onMetrics = () async =>
          throw const LocalApiException('LOCAL_QUOTE_UNAVAILABLE', status: 503);
      await launch(tester, '/portfolio');
      await click(tester, find.text('Open Synthetic portfolio'));
      // Confirmed manual holdings are not a quote calculation. A quote failure
      // must not discard them or disable valid manual record operations.
      expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
      expect(find.text('Delete holding SYN:AAPL'), findsOneWidget);
      expect(find.textContaining('Quantity: 10.000000 units'), findsOneWidget);
      expect(find.text('Market value: 2000.00 USD'), findsNothing);
      expect(
        find.text(
          'Valuation not confirmed. Saved manual holdings remain available.',
        ),
        findsOneWidget,
      );
      await click(tester, find.text('Edit holding SYN:AAPL'));
      await type(tester, 'holding-quantity', '11');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.holdingItems.single.quantity, '11.000000');
      expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
      await click(tester, find.text('Delete holding SYN:AAPL'));
      await click(tester, find.text('Delete saved item'));
      expect(s2.holdingItems, isEmpty);
      expect(
        find.text('This portfolio has no saved holdings.'),
        findsOneWidget,
      );
      await choose(
        tester,
        'Supported synthetic instrument',
        'SYN:AAPL • Synthetic AAPL',
      );
      await type(tester, 'holding-quantity', '10');
      await type(tester, 'holding-cost', '150');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.holdingItems.length, 1);
      expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
      final mutations = s2.calls
          .where(
            (v) =>
                v == 'createHolding' ||
                v == 'updateHolding' ||
                v == 'deleteHolding',
          )
          .length;
      s2.onMetrics = null;
      await click(tester, find.byKey(const Key('metrics-retry')));
      expect(find.text('Market value: 2000.00 USD'), findsOneWidget);
      expect(
        s2.calls
            .where(
              (v) =>
                  v == 'createHolding' ||
                  v == 'updateHolding' ||
                  v == 'deleteHolding',
            )
            .length,
        mutations,
      );
      s2.onMetrics = () async =>
          throw const LocalApiException('LOCAL_QUOTE_UNAVAILABLE', status: 503);
      await click(tester, find.byKey(const Key('metrics-retry')));
      expect(find.text('Market value: 2000.00 USD'), findsNothing);
      expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
      expect(find.text('Delete holding SYN:AAPL'), findsOneWidget);
    },
  );
  for (final outcome in ['success', '401']) {
    ownedTest(
      'stale metrics $outcome after failed logout preserves confirmed holdings and dirty input',
      (tester) async {
        s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
        s2.holdingItems = [LocalHolding.fromJson(holdingData())];
        final pending = Completer<LocalS2Reply<LocalPortfolioMetrics>>();
        s2.onMetrics = () => pending.future;
        await launch(tester, '/portfolio');
        await click(tester, find.text('Open Synthetic portfolio'));
        expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
        api.onLogout = (_) async =>
            throw const LocalApiException('API_UNAVAILABLE');
        await session.signOut();
        await tester.pumpAndSettle();
        await session.refreshOnboarding();
        await tester.pumpAndSettle();
        await click(tester, find.text('Edit holding SYN:AAPL'));
        await type(tester, 'holding-quantity', '12.0');
        if (outcome == '401') {
          pending.completeError(
            const LocalApiException('SESSION_INVALID', status: 401),
          );
        } else {
          final value = LocalPortfolioMetrics.fromJson(metricsData());
          pending.complete(
            LocalS2Reply(value, value.dataStatus, value.dataAsOf),
          );
        }
        await tester.pumpAndSettle();
        expect(session.user!.alias, 'learner-a');
        expect(find.text('Market value: 2000.00 USD'), findsNothing);
        expect(find.text('Edit holding SYN:AAPL'), findsOneWidget);
        expect(
          tester
              .widget<TextFormField>(find.byKey(const Key('holding-quantity')))
              .controller!
              .text,
          '12.0',
        );
        expect(s2.calls.contains('updateHolding'), isFalse);
      },
    );
  }
  ownedTest(
    'unavailable backend metrics do not invent overall values or allocations',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      s2.onMetrics = () async => LocalS2Reply(
        LocalPortfolioMetrics.fromJson(metricsData(unavailable: true)),
        'UNAVAILABLE',
        null,
      );
      await launch(tester, '/portfolio');
      await click(tester, find.text('Open Synthetic portfolio'));
      expect(
        find.text('Valuation UNAVAILABLE • Data UNAVAILABLE'),
        findsOneWidget,
      );
      expect(find.text('Market value: Unavailable'), findsOneWidget);
      expect(find.textContaining('not renormalized'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
  for (final path in ['/risk', '/portfolio']) {
    ownedTest(
      'route $path retains dirty input through failed logout but removes it on confirmed logout',
      (tester) async {
        await launch(tester, path);
        if (path == '/risk') {
          await choose(tester, 'Answer W1', 'Synthetic option C');
        } else {
          await type(tester, 'portfolio-name', 'Private dirty label');
        }
        api.onLogout = (_) async =>
            throw const LocalApiException('API_UNAVAILABLE');
        await click(tester, find.byKey(const Key('local-sign-out')));
        final dirty = path == '/risk'
            ? find
                  .byType(DropdownButtonFormField<String>, skipOffstage: false)
                  .first
            : find.byKey(const Key('portfolio-name'), skipOffstage: false);
        expect(dirty, findsOneWidget);
        if (path == '/portfolio') {
          expect(
            tester.widget<TextFormField>(dirty).controller!.text,
            'Private dirty label',
          );
        }
        final exclusions = find.byWidgetPredicate(
          (w) => w is ExcludeFocus && w.excluding,
          skipOffstage: false,
        );
        expect(exclusions, findsWidgets);
        expect(
          find
              .byType(Offstage, skipOffstage: false)
              .evaluate()
              .any((e) => (e.widget as Offstage).offstage),
          isTrue,
        );
        await click(tester, find.text('Retry saved-state check'));
        if (path == '/risk') {
          expect(find.textContaining('1 of 10 answered'), findsOneWidget);
        } else {
          expect(
            tester
                .widget<TextFormField>(find.byKey(const Key('portfolio-name')))
                .controller!
                .text,
            'Private dirty label',
          );
        }
        api.onLogout = null;
        await click(tester, find.byKey(const Key('local-sign-out')));
        expect(find.text('Choose a synthetic learner'), findsOneWidget);
        expect(
          find.byKey(const Key('portfolio-name'), skipOffstage: false),
          findsNothing,
        );
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }
  ownedTest(
    'same-frame duplicate update callback cannot issue another mutation',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      await click(tester, find.text('Edit Synthetic portfolio'));
      final delayed = Completer<LocalS2Reply<LocalPortfolio>>();
      s2.onUpdate = (_) => delayed.future;
      final button = find.descendant(
        of: find.byKey(const Key('portfolio-save')),
        matching: find.byType(ElevatedButton),
      );
      final callback = tester.widget<ElevatedButton>(button).onPressed!;
      callback();
      callback();
      expect(s2.calls.where((v) => v == 'updatePortfolio').length, 1);
      delayed.complete(
        s2.reply(LocalPortfolio.fromJson(portfolioData()), s2.time),
      );
      await tester.pumpAndSettle();
    },
  );
  ownedTest(
    'delete dialog cannot revive its old intent after a failed logout attempt',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      await click(tester, find.text('Delete Synthetic portfolio'));
      final staleConfirm = tester
          .widget<TextButton>(
            find.widgetWithText(TextButton, 'Delete saved item'),
          )
          .onPressed!;
      api.onLogout = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      await session.signOut();
      await tester.pumpAndSettle();
      expect(find.text('Confirm deletion'), findsNothing);
      await session.refreshOnboarding();
      await tester.pumpAndSettle();
      staleConfirm();
      await tester.pumpAndSettle();
      expect(s2.calls.contains('deletePortfolio'), isFalse);
      expect(s2.portfolioItems.length, 1);
    },
  );
  ownedTest('disposed route late 401 cannot clear current learner', (
    tester,
  ) async {
    final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
    s2.onPortfolios = () => delayed.future;
    await session.signIn('learner-a');
    await tester.pumpWidget(
      FinExApp(session: session, initialLocation: '/portfolio'),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 20));
    await tester.pumpWidget(const SizedBox.shrink());
    delayed.completeError(
      const LocalApiException('SESSION_INVALID', status: 401),
    );
    await tester.pump();
    expect(session.user!.alias, 'learner-a');
    expect(tester.takeException(), isNull);
  });
  ownedTest('disposing a portfolio route closes its root deletion dialog', (
    tester,
  ) async {
    s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
    await launch(tester, '/portfolio');
    final router = GoRouter.of(
      tester.element(find.byKey(const Key('portfolio-name'))),
    );
    await click(tester, find.text('Delete Synthetic portfolio'));
    router.go('/risk');
    await tester.pumpAndSettle();
    expect(find.text('Confirm deletion'), findsNothing);
    expect(s2.calls.contains('deletePortfolio'), isFalse);
    expect(find.text('Saved risk questionnaire'), findsOneWidget);
  });
  ownedTest(
    'logout attempt closes owned risk option popup without allowing old choice',
    (tester) async {
      await launch(tester, '/risk');
      final choice = find.byWidgetPredicate(
        (w) =>
            w is DropdownButtonFormField<String> &&
            w.decoration.labelText == 'Answer W1',
      );
      await click(tester, choice);
      expect(find.text('Synthetic option E'), findsWidgets);
      api.onLogout = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      await session.signOut();
      await tester.pumpAndSettle();
      expect(find.text('Synthetic option E'), findsNothing);
      expect(session.user!.alias, 'learner-a');
      await session.refreshOnboarding();
      await tester.pumpAndSettle();
      expect(find.textContaining('0 of 10 answered'), findsOneWidget);
    },
  );
  ownedTest(
    'initial protected check never mounts a domain child before fresh authorization',
    (tester) async {
      await session.signIn('learner-a');
      final checked = Completer<LocalOnboardingState>();
      api.onState = (_) => checked.future;
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: '/portfolio'),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));
      expect(
        find.byKey(const Key('portfolio-name'), skipOffstage: false),
        findsNothing,
      );
      expect(s2.calls, isEmpty);
      checked.complete(completedTestState());
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('portfolio-name')), findsOneWidget);
    },
  );
  ownedTest('fresh incomplete onboarding prevents any S2 request', (
    tester,
  ) async {
    await session.signIn('learner-a');
    api.states['learner-a'] = testState(accepted: true);
    await tester.pumpWidget(
      FinExApp(session: session, initialLocation: '/risk'),
    );
    await tester.pumpAndSettle();
    expect(s2.calls, isEmpty);
    expect(find.text('Saved risk questionnaire'), findsNothing);
    expect(find.text('Complete onboarding'), findsOneWidget);
  });
  for (final code in ['SESSION_INVALID', 'ONBOARDING_REQUIRED']) {
    ownedTest(
      'current $code discards owned dirty portfolio rather than hiding reusable data',
      (tester) async {
        await launch(tester, '/portfolio');
        await type(tester, 'portfolio-name', 'Private revoked label');
        s2.onCreate = (_) async => throw LocalApiException(
          code,
          status: code == 'SESSION_INVALID' ? 401 : 409,
        );
        await click(tester, find.byKey(const Key('portfolio-save')));
        expect(
          find.byKey(const Key('portfolio-name'), skipOffstage: false),
          findsNothing,
        );
        expect(
          find.text('Private revoked label', skipOffstage: false),
          findsNothing,
        );
        expect(session.canAccessFeatures, isFalse);
        if (code == 'SESSION_INVALID') {
          expect(find.text('Choose a synthetic learner'), findsOneWidget);
        }
      },
    );
  }
  ownedTest(
    'rechecking after failed logout never revives a pending old draft success',
    (tester) async {
      await launch(tester, '/risk');
      await choose(tester, 'Answer W1', 'Synthetic option C');
      final delayed = Completer<LocalS2Reply<LocalRiskDraft>>();
      s2.onDraft = (_) => delayed.future;
      await tester.ensureVisible(find.byKey(const Key('risk-save')));
      await tester.tap(find.byKey(const Key('risk-save')));
      await tester.pump();
      api.onLogout = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      await session.signOut();
      await tester.pumpAndSettle();
      await session.refreshOnboarding();
      await tester.pumpAndSettle();
      delayed.complete(
        s2.reply(LocalRiskDraft.fromJson(riskDraftData(saved: true)), s2.time),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('1 of 10 answered'), findsOneWidget);
      expect(
        find.text('Draft saved on the server. Sign in again to resume it.'),
        findsNothing,
      );
      expect(session.user!.alias, 'learner-a');
    },
  );
  ownedTest(
    'new learner never inherits old dirty inputs or ignored-cancellation portfolio reply',
    (tester) async {
      await launch(tester, '/portfolio');
      await type(tester, 'portfolio-name', 'Private A label');
      final router = GoRouter.of(
        tester.element(find.byKey(const Key('portfolio-name'))),
      );
      final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
      s2.onPortfolios = () => delayed.future;
      await tester.tap(find.byKey(const Key('portfolio-reload')));
      await tester.pump();
      await session.signOut();
      await session.signIn('learner-b');
      s2.onPortfolios = null;
      router.go('/portfolio');
      await tester.pumpAndSettle();
      delayed.complete(
        s2.reply(
          LocalPortfolioList.fromJson(
            s2Scoped({
              'portfolio_version': 'portfolio.v1',
              'items': [portfolioData()..['name'] = 'Old A saved receipt'],
              'count': 1,
            }),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(session.user!.alias, 'learner-b');
      expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('portfolio-name')))
            .controller!
            .text,
        isEmpty,
      );
      expect(find.textContaining('Old A saved receipt'), findsNothing);
      expect(find.text('Private A label', skipOffstage: false), findsNothing);
    },
  );
  ownedTest(
    'same persona new session never inherits prior-session dirty input or late portfolio reply',
    (tester) async {
      await launch(tester, '/portfolio');
      await type(tester, 'portfolio-name', 'Private earlier session label');
      final router = GoRouter.of(
        tester.element(find.byKey(const Key('portfolio-name'))),
      );
      final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
      s2.onPortfolios = () => delayed.future;
      await tester.tap(find.byKey(const Key('portfolio-reload')));
      await tester.pump();
      await session.signOut();
      await session.signIn('learner-a');
      s2.onPortfolios = null;
      router.go('/portfolio');
      await tester.pumpAndSettle();
      delayed.complete(
        s2.reply(
          LocalPortfolioList.fromJson(
            s2Scoped({
              'portfolio_version': 'portfolio.v1',
              'items': [portfolioData()..['name'] = 'Prior session receipt'],
              'count': 1,
            }),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(session.user!.alias, 'learner-a');
      expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('portfolio-name')))
            .controller!
            .text,
        isEmpty,
      );
      expect(find.textContaining('Prior session receipt'), findsNothing);
      expect(
        find.text('Private earlier session label', skipOffstage: false),
        findsNothing,
      );
    },
  );
  for (final nextAlias in ['learner-a', 'learner-b']) {
    ownedTest(
      'delayed old gate check cannot strand coalesced new $nextAlias session',
      (tester) async {
        await session.signIn('learner-a');
        final oldCheck = Completer<LocalOnboardingState>();
        api.onState = (_) => oldCheck.future;
        await tester.pumpWidget(
          FinExApp(session: session, initialLocation: '/portfolio'),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 20));
        expect(session.loadingState, isTrue);
        expect(s2.calls, isEmpty);
        await session.signOut();
        api.onState = null;
        await session.signIn(nextAlias);
        // No intervening frame: the same routed gate/session widget survives.
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('portfolio-name')), findsOneWidget);
        oldCheck.complete(completedTestState('Old gate state'));
        await tester.pumpAndSettle();
        expect(session.user!.alias, nextAlias);
        expect(find.byKey(const Key('portfolio-name')), findsOneWidget);
        expect(
          find.text('Checking saved consent and onboarding…'),
          findsNothing,
        );
        expect(
          session.onboarding!.displayName,
          nextAlias == 'learner-a' ? 'Synthetic A' : 'Synthetic B',
        );
      },
    );
  }
  ownedTest(
    'stale guard 401 cannot finish or clear a newer pending gate check',
    (tester) async {
      await session.signIn('learner-a');
      final oldCheck = Completer<LocalOnboardingState>();
      api.onState = (_) => oldCheck.future;
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: '/portfolio'),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 20));
      expect(session.loadingState, isTrue);
      await session.signOut();
      api.onState = null;
      await session.signIn('learner-b');
      final newCheck = Completer<LocalOnboardingState>();
      api.onState = (_) => newCheck.future;
      await tester.pumpAndSettle();
      expect(session.loadingState, isTrue);
      oldCheck.completeError(
        const LocalApiException('SESSION_INVALID', status: 401),
      );
      await tester.pumpAndSettle();
      expect(session.user!.alias, 'learner-b');
      expect(session.loadingState, isTrue);
      expect(
        find.byKey(const Key('portfolio-name'), skipOffstage: false),
        findsNothing,
      );
      expect(s2.calls, isEmpty);
      newCheck.complete(completedTestState('Synthetic B'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('portfolio-name')), findsOneWidget);
      expect(session.onboarding!.displayName, 'Synthetic B');
    },
  );
  ownedTest(
    'failed portfolio PUT keeps typed purpose and focused safe feedback for retry',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      await click(tester, find.text('Edit Synthetic portfolio'));
      await type(tester, 'portfolio-name', 'Keep revised');
      await type(tester, 'portfolio-description', 'Keep purpose');
      s2.onUpdate = (_) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('portfolio-name')))
            .controller!
            .text,
        'Keep revised',
      );
      expect(
        tester
            .widget<TextFormField>(
              find.byKey(const Key('portfolio-description')),
            )
            .controller!
            .text,
        'Keep purpose',
      );
      expect(FocusManager.instance.primaryFocus?.context?.widget, isA<Focus>());
      s2.onUpdate = null;
      await click(tester, find.byKey(const Key('portfolio-save')));
      expect(s2.portfolioItems.single.name, 'Keep revised');
    },
  );
  ownedTest(
    'uncertain holding create reconciles list without autoPOST and preserves exact input',
    (tester) async {
      s2.portfolioItems = [LocalPortfolio.fromJson(portfolioData())];
      await launch(tester, '/portfolio');
      await click(tester, find.text('Open Synthetic portfolio'));
      await choose(
        tester,
        'Supported synthetic instrument',
        'SYN:AAPL • Synthetic AAPL',
      );
      await type(tester, 'holding-quantity', '10.0');
      await type(tester, 'holding-cost', '150.0');
      s2.onCreateHolding = (_) async =>
          throw const LocalApiException('REQUEST_TIMEOUT');
      await click(tester, find.byKey(const Key('holding-save')));
      expect(
        tester
            .widget<TextFormField>(find.byKey(const Key('holding-quantity')))
            .controller!
            .text,
        '10.0',
      );
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.calls.where((v) => v == 'createHolding').length, 1);
      await click(tester, find.byKey(const Key('portfolio-reload')));
      expect(s2.calls.where((v) => v == 'createHolding').length, 1);
      await click(
        tester,
        find.text('I checked holdings; allow a new holding create'),
      );
      s2.onCreateHolding = null;
      await click(tester, find.byKey(const Key('holding-save')));
      expect(s2.calls.where((v) => v == 'createHolding').length, 2);
      expect(s2.holdingItems.single.averageCost, '150.0000');
    },
  );
  ownedTest(
    'saved history stays in server sequence and detail uses immutable receipt',
    (tester) async {
      final newer = savedRiskData()
        ..['assessment_id'] = '33333333-3333-4333-8333-333333333333';
      s2.onHistory = (cursor) async => s2.reply(
        LocalRiskHistory.fromJson(
          s2Scoped({
            'items': cursor == null
                ? [newer, savedRiskData()]
                : [savedRiskData()],
            'next_cursor': cursor == null ? '2' : null,
          }),
        ),
      );
      await launch(tester, '/risk');
      expect(
        find.byKey(
          const ValueKey('risk-history-33333333-3333-4333-8333-333333333333'),
        ),
        findsOneWidget,
      );
      expect(
        tester
            .getTopLeft(
              find.byKey(
                const ValueKey(
                  'risk-history-33333333-3333-4333-8333-333333333333',
                ),
              ),
            )
            .dy,
        lessThan(
          tester
              .getTopLeft(find.byKey(ValueKey('risk-history-$assessmentA')))
              .dy,
        ),
      );
      await click(tester, find.text('Older assessments'));
      expect(s2.calls.contains('history:2'), isTrue);
      await click(tester, find.textContaining('open saved assessment').last);
      expect(find.text('Saved result: Moderate'), findsOneWidget);
      expect(find.text(localRiskLimitation), findsOneWidget);
    },
  );
  for (final path in ['/risk', '/portfolio']) {
    ownedTest(
      '$path compact 320px 200percent text supports keyboard and safe error semantics',
      (tester) async {
        final semantics = tester.ensureSemantics();
        tester.view.physicalSize = const Size(320, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        try {
          await session.signIn('learner-a');
          await tester.pumpWidget(
            MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(2)),
              child: FinExApp(session: session, initialLocation: path),
            ),
          );
          await tester.pumpAndSettle();
          await tester.sendKeyEvent(LogicalKeyboardKey.tab);
          await tester.pump();
          expect(FocusManager.instance.primaryFocus, isNotNull);
          if (path == '/risk') {
            await click(tester, find.byKey(const Key('risk-assess')));
            expect(
              find.textContaining('Answer all ten questions'),
              findsOneWidget,
            );
          } else {
            await click(tester, find.byKey(const Key('portfolio-save')));
            expect(
              find.text('Enter a synthetic name of 1–100 characters.'),
              findsOneWidget,
            );
            final editor = find.descendant(
              of: find.byKey(const Key('portfolio-name')),
              matching: find.byType(EditableText),
            );
            expect(
              tester.widget<EditableText>(editor).focusNode.hasFocus,
              isTrue,
            );
            expect(
              tester
                  .getRect(
                    find.text('Enter a synthetic name of 1–100 characters.'),
                  )
                  .top,
              lessThan(800),
            );
          }
          expect(tester.takeException(), isNull);
        } finally {
          await tester.pumpWidget(const SizedBox.shrink());
          semantics.dispose();
        }
      },
    );
  }
}
