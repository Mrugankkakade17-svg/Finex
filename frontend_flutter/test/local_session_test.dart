import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';

import 'support/local_application_fake.dart';

void main() {
  late FakeLocalApi api;
  late LocalSession session;
  setUp(() {
    api = FakeLocalApi();
    session = LocalSession(api: api, clock: () => localTestTime);
  });
  tearDown(() {
    session.dispose();
  });
  Future<void> signInA() async {
    expect(await session.signIn('learner-a'), isTrue);
  }

  test('cold session has no authority and no transport calls', () {
    expect(session.isAuthenticated, isFalse);
    expect(session.canAccessFeatures, isFalse);
    expect(api.calls, isEmpty);
  });
  test('login validates identity then restores owned server state', () async {
    api.states['learner-a'] = completedTestState();
    await signInA();
    expect(api.calls, ['login:learner-a', 'me:learner-a', 'state:learner-a']);
    expect(session.canAccessFeatures, isTrue);
  });
  test('selected alias must match login identity', () async {
    api.onLogin = (_) async => LocalLogin(
      accessToken: testBearer('learner-b'),
      expiresAt: localTestTime.add(const Duration(hours: 1)),
      user: testUser('learner-b'),
    );
    expect(await session.signIn('learner-a'), isFalse);
    expect(session.authError!.code, 'INVALID_API_RESPONSE');
    expect(session.isAuthenticated, isFalse);
    expect(api.calls.length, 1);
  });
  test('me identity must match login id and alias', () async {
    api.onMe = (_) async => testUser('learner-b');
    expect(await session.signIn('learner-a'), isFalse);
    expect(session.authError!.code, 'INVALID_API_RESPONSE');
    expect(api.calls.where((call) => call.startsWith('state')), isEmpty);
  });
  test('expired returned login cannot acquire client authority', () async {
    api.expiresAt = localTestTime;
    expect(await session.signIn('learner-a'), isFalse);
    expect(session.isAuthenticated, isFalse);
  });
  test(
    'state failure is retryable but never completed feature access',
    () async {
      api.onState = (_) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      await signInA();
      expect(session.isAuthenticated, isTrue);
      expect(session.onboarding, isNull);
      expect(session.canAccessFeatures, isFalse);
      expect(session.loadError!.code, 'LOCAL_STORE_UNAVAILABLE');
      api.onState = null;
      await session.refreshOnboarding();
      expect(session.loadError, isNull);
      expect(session.onboarding, isNotNull);
    },
  );
  test('consent and drafts do not claim server completion', () async {
    await signInA();
    await session.recordConsent(true);
    await session.saveDraft(
      displayName: 'Synthetic A',
      experienceLevel: 'beginner',
    );
    expect(session.canAccessFeatures, isFalse);
    expect(await session.complete(), isTrue);
    expect(session.canAccessFeatures, isTrue);
  });
  test('saving changed completed profile regates until completion', () async {
    api.states['learner-a'] = completedTestState();
    await signInA();
    await session.saveDraft(
      displayName: 'Changed synthetic',
      experienceLevel: 'advanced',
    );
    expect(session.onboarding!.completed, isFalse);
    expect(session.canAccessFeatures, isFalse);
  });
  test(
    'consent withdrawal gates immediately; reaccept alone is not completion',
    () async {
      api.states['learner-a'] = completedTestState();
      await signInA();
      await session.recordConsent(false);
      expect(session.canAccessFeatures, isFalse);
      await session.recordConsent(true);
      expect(session.canAccessFeatures, isFalse);
      await session.complete();
      expect(session.canAccessFeatures, isTrue);
    },
  );
  test('state recheck observes another client withdrawal', () async {
    api.states['learner-a'] = completedTestState();
    await signInA();
    api.states['learner-a'] = testState(
      label: 'Synthetic A',
      level: 'beginner',
      accepted: false,
    );
    await session.refreshOnboarding();
    expect(session.canAccessFeatures, isFalse);
  });
  test(
    'failed draft retains known state and truthful error for retry',
    () async {
      await signInA();
      api.onDraft = (_, _, _) async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      expect(await session.saveDraft(displayName: 'Unsaved'), isFalse);
      expect(session.onboarding!.displayName, isNull);
      expect(session.operationError!.code, 'LOCAL_STORE_UNAVAILABLE');
      api.onDraft = null;
      expect(await session.saveDraft(displayName: 'Retry'), isTrue);
      expect(session.operationError, isNull);
    },
  );
  test(
    'confirmed logout clears all authority; re-login resumes server data',
    () async {
      api.states['learner-a'] = completedTestState();
      await signInA();
      expect(await session.signOut(), isTrue);
      expect(session.user, isNull);
      expect(session.onboarding, isNull);
      await signInA();
      expect(session.onboarding!.displayName, 'Synthetic A');
    },
  );
  test('failed non401 logout retains learner and state until retry', () async {
    api.states['learner-a'] = completedTestState();
    await signInA();
    api.onLogout = (_) async =>
        throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
    expect(await session.signOut(), isFalse);
    expect(session.isAuthenticated, isTrue);
    expect(session.user!.alias, 'learner-a');
    expect(session.onboarding!.displayName, 'Synthetic A');
    expect(session.authError!.code, 'LOCAL_STORE_UNAVAILABLE');
    api.onLogout = null;
    expect(await session.signOut(), isTrue);
  });
  test('even a forged non401 SESSION_INVALID cannot confirm logout', () async {
    await signInA();
    api.onLogout = (_) async =>
        throw const LocalApiException('SESSION_INVALID', status: 503);
    expect(await session.signOut(), isFalse);
    expect(session.isAuthenticated, isTrue);
  });
  test('actual current401 clears learner state', () async {
    await signInA();
    api.onState = (_) async =>
        throw const LocalApiException('SESSION_INVALID', status: 401);
    await session.refreshOnboarding();
    expect(session.isAuthenticated, isFalse);
    expect(session.onboarding, isNull);
  });
  test(
    'future ONBOARDING_REQUIRED clears feature authority but not identity',
    () async {
      api.states['learner-a'] = completedTestState();
      await signInA();
      api.onComplete = (_) async =>
          throw const LocalApiException('ONBOARDING_REQUIRED', status: 409);
      expect(await session.complete(), isFalse);
      expect(session.isAuthenticated, isTrue);
      expect(session.canAccessFeatures, isFalse);
      expect(session.onboarding, isNull);
    },
  );
  test('persona switch requires confirmed logout', () async {
    await signInA();
    final callCount = api.calls.length;
    expect(await session.signIn('learner-b'), isFalse);
    expect(session.user!.alias, 'learner-a');
    expect(api.calls.length, callCount);
  });
  test('late login A cannot overwrite newer B login', () async {
    final lateA = Completer<LocalLogin>();
    api.onLogin = (alias) async => alias == 'learner-a'
        ? lateA.future
        : LocalLogin(
            accessToken: testBearer(alias),
            expiresAt: localTestTime.add(const Duration(hours: 1)),
            user: testUser(alias),
          );
    final first = session.signIn('learner-a');
    await Future<void>.delayed(Duration.zero);
    expect(await session.signIn('learner-b'), isTrue);
    lateA.complete(
      LocalLogin(
        accessToken: testBearer('learner-a'),
        expiresAt: localTestTime.add(const Duration(hours: 1)),
        user: testUser('learner-a'),
      ),
    );
    expect(await first, isFalse);
    expect(session.user!.alias, 'learner-b');
  });
  test(
    'late me A cannot overwrite B identity or issue A state request',
    () async {
      final lateA = Completer<LocalUser>();
      api.onMe = (token) async => api.aliasFor(token) == 'learner-a'
          ? lateA.future
          : testUser('learner-b');
      final first = session.signIn('learner-a');
      await Future<void>.delayed(Duration.zero);
      expect(await session.signIn('learner-b'), isTrue);
      lateA.complete(testUser('learner-a'));
      expect(await first, isFalse);
      expect(session.user!.alias, 'learner-b');
      expect(api.calls.contains('state:learner-a'), isFalse);
    },
  );
  for (final fails401 in [false, true]) {
    test(
      'late A state ${fails401 ? '401' : 'success'} cannot affect B',
      () async {
        final lateA = Completer<LocalOnboardingState>();
        api.onState = (token) async => api.aliasFor(token) == 'learner-a'
            ? lateA.future
            : completedTestState('Synthetic B');
        final first = session.signIn('learner-a');
        await Future<void>.delayed(Duration.zero);
        expect(session.isAuthenticated, isTrue);
        await session.signOut();
        await session.signIn('learner-b');
        if (fails401) {
          lateA.completeError(
            const LocalApiException('SESSION_INVALID', status: 401),
          );
        } else {
          lateA.complete(completedTestState());
        }
        expect(await first, isFalse);
        expect(session.user!.alias, 'learner-b');
        expect(session.onboarding!.displayName, 'Synthetic B');
        expect(session.canAccessFeatures, isTrue);
      },
    );
    test(
      'late A mutation ${fails401 ? '401' : 'success'} cannot affect B',
      () async {
        await signInA();
        final lateA = Completer<LocalOnboardingState>();
        api.onDraft = (_, _, _) => lateA.future;
        final first = session.saveDraft(displayName: 'A pending');
        await session.signOut();
        api.states['learner-b'] = completedTestState('Synthetic B');
        await session.signIn('learner-b');
        if (fails401) {
          lateA.completeError(
            const LocalApiException('SESSION_INVALID', status: 401),
          );
        } else {
          lateA.complete(completedTestState());
        }
        expect(await first, isFalse);
        expect(session.user!.alias, 'learner-b');
        expect(session.onboarding!.displayName, 'Synthetic B');
        expect(session.canAccessFeatures, isTrue);
      },
    );
    test(
      'late A logout ${fails401 ? '401' : 'success'} cannot sign out B',
      () async {
        await signInA();
        final lateState = Completer<LocalOnboardingState>();
        final lateLogout = Completer<void>();
        api.onState = (_) => lateState.future;
        api.onLogout = (_) => lateLogout.future;
        final refresh = session.refreshOnboarding();
        final logout = session.signOut();
        lateState.completeError(
          const LocalApiException('SESSION_INVALID', status: 401),
        );
        await refresh;
        api.onState = null;
        await session.signIn('learner-b');
        if (fails401) {
          lateLogout.completeError(
            const LocalApiException('SESSION_INVALID', status: 401),
          );
        } else {
          lateLogout.complete();
        }
        expect(await logout, isFalse);
        expect(session.user!.alias, 'learner-b');
        expect(session.authError, isNull);
      },
    );
  }
}
