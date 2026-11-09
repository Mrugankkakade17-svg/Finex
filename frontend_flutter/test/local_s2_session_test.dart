import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_s2_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';

import 'support/local_application_fake.dart';
import 'support/local_s2_fake.dart';
import 'support/local_s2_data.dart';

void main() {
  late FakeLocalApi api;
  late FakeLocalS2Api s2;
  late LocalSession session;
  setUp(() {
    api = FakeLocalApi();
    s2 = FakeLocalS2Api();
    api.states['learner-a'] = completedTestState();
    api.states['learner-b'] = completedTestState('Synthetic B');
    session = LocalSession(api: api, s2Api: s2, clock: () => localTestTime);
  });
  tearDown(() => session.dispose());
  final stale = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'safe code',
      'SESSION_CHANGED',
    ),
  );
  test(
    'optional S2 injection preserves old S1 API mocks without fallback',
    () async {
      final old = LocalSession(api: api, clock: () => localTestTime);
      addTearDown(old.dispose);
      await old.signIn('learner-a');
      await expectLater(
        old.createS2Scope().portfolios(),
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'code',
            'FEATURE_UNAVAILABLE',
          ),
        ),
      );
    },
  );
  for (final outcome in ['success', 'error', '401']) {
    test(
      'failed logout attempt permanently invalidates prior domain $outcome',
      () async {
        await session.signIn('learner-a');
        final generation = session.generation;
        final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
        s2.onPortfolios = () => delayed.future;
        final scope = session.createS2Scope();
        final result = scope.portfolios();
        final expectation = expectLater(result, stale);
        api.onLogout = (_) async =>
            throw const LocalApiException('API_UNAVAILABLE');
        expect(await session.signOut(), isFalse);
        expect(session.generation, generation);
        expect(session.user!.alias, 'learner-a');
        if (outcome == 'success') {
          delayed.complete(
            LocalS2Reply(
              LocalPortfolioList.fromJson(
                s2Scoped({
                  'portfolio_version': 'portfolio.v1',
                  'items': [],
                  'count': 0,
                }),
              ),
              'CACHED',
              null,
            ),
          );
        } else {
          delayed.completeError(
            LocalApiException(
              outcome == '401' ? 'SESSION_INVALID' : 'LOCAL_STORE_UNAVAILABLE',
              status: outcome == '401' ? 401 : 503,
            ),
          );
        }
        await expectation;
        expect(scope.isCurrent, isFalse);
        expect(session.user!.alias, 'learner-a');
        expect(session.authError!.code, 'API_UNAVAILABLE');
      },
    );
  }
  test(
    'disposed screen scope ignores response and 401 without clearing owner',
    () async {
      await session.signIn('learner-a');
      final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
      s2.onPortfolios = () => delayed.future;
      final scope = session.createS2Scope();
      final expectation = expectLater(scope.portfolios(), stale);
      scope.dispose();
      delayed.completeError(
        const LocalApiException('SESSION_INVALID', status: 401),
      );
      await expectation;
      expect(session.user!.alias, 'learner-a');
    },
  );
  for (final code in ['SESSION_INVALID', 'ONBOARDING_REQUIRED']) {
    test('current domain $code immediately removes authorization', () async {
      await session.signIn('learner-a');
      s2.onPortfolios = () async => throw LocalApiException(
        code,
        status: code == 'SESSION_INVALID' ? 401 : 409,
      );
      await expectLater(
        session.createS2Scope().portfolios(),
        throwsA(isA<LocalApiException>().having((e) => e.code, 'code', code)),
      );
      expect(session.canAccessFeatures, isFalse);
      expect(session.onboarding, isNull);
      if (code == 'SESSION_INVALID') expect(session.isAuthenticated, isFalse);
    });
  }
  test('old owner reply cannot clear newly selected learner', () async {
    await session.signIn('learner-a');
    final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
    s2.onPortfolios = () => delayed.future;
    final expectation = expectLater(
      session.createS2Scope().portfolios(),
      stale,
    );
    await session.signOut();
    await session.signIn('learner-b');
    delayed.completeError(
      const LocalApiException('SESSION_INVALID', status: 401),
    );
    await expectation;
    expect(session.user!.alias, 'learner-b');
    expect(session.canAccessFeatures, isTrue);
  });
  for (final operation in ['recheck', 'consent']) {
    for (final outcome in ['success', 'error', '401']) {
      test(
        '$operation invalidates in-flight domain $outcome even when adapter ignores cancellation',
        () async {
          await session.signIn('learner-a');
          final delayed = Completer<LocalS2Reply<LocalPortfolioList>>();
          s2.onPortfolios = () => delayed.future;
          final scope = session.createS2Scope();
          final expectation = expectLater(scope.portfolios(), stale);
          if (operation == 'recheck') {
            await session.refreshOnboarding();
          } else {
            await session.recordConsent(true);
          }
          if (outcome == 'success') {
            delayed.complete(
              s2.reply(
                LocalPortfolioList.fromJson(
                  s2Scoped({
                    'portfolio_version': 'portfolio.v1',
                    'items': [],
                    'count': 0,
                  }),
                ),
              ),
            );
          } else {
            delayed.completeError(
              LocalApiException(
                outcome == '401'
                    ? 'SESSION_INVALID'
                    : 'LOCAL_STORE_UNAVAILABLE',
                status: outcome == '401' ? 401 : 503,
              ),
            );
          }
          await expectation;
          expect(scope.isCurrent, isFalse);
          expect(session.user!.alias, 'learner-a');
          expect(session.canAccessFeatures, isTrue);
        },
      );
    }
  }
}
