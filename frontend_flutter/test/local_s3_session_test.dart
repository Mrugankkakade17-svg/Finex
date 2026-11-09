import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';

import 'support/local_application_fake.dart';
import 'support/local_s3_fake.dart';
import 'support/local_s3_data.dart';

void main() {
  late FakeLocalApi auth;
  late FakeLocalS3Api api;
  late LocalSession session;
  setUp(() async {
    auth = FakeLocalApi();
    auth.states['learner-a'] = completedTestState();
    auth.states['learner-b'] = completedTestState('Synthetic B');
    api = FakeLocalS3Api();
    session = LocalSession(api: auth, s3Api: api, clock: () => localTestTime);
    await session.signIn('learner-a');
  });
  tearDown(() => session.dispose());
  test(
    'typed owner scope dispatches without a public credential getter',
    () async {
      final scope = session.createS3Scope();
      expect((await scope.marketSearch(limit: 1)).value.items.length, 1);
      expect(api.calls, ['search:A']);
      scope.dispose();
      await expectLater(
        scope.watchlists(),
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'safe code',
            'SESSION_CHANGED',
          ),
        ),
      );
    },
  );
  test(
    'logout attempt invalidates late401 even when revocation fails',
    () async {
      final pending = Completer<LocalS3Reply<LocalWatchlistList>>();
      api.onLists = () => pending.future;
      final scope = session.createS3Scope();
      final future = scope.watchlists();
      final assertion = expectLater(
        future,
        throwsA(
          isA<LocalApiException>().having(
            (e) => e.code,
            'safe code',
            'SESSION_CHANGED',
          ),
        ),
      );
      auth.onLogout = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      await session.signOut();
      pending.completeError(
        const LocalApiException('SESSION_INVALID', status: 401),
      );
      await assertion;
      expect(session.user!.alias, 'learner-a');
    },
  );
  test('coalesced A to B cancels old success without clearing B', () async {
    final pending = Completer<LocalS3Reply<LocalMarketSearch>>();
    api.onSearch = () => pending.future;
    final old = session.createS3Scope();
    final future = old.marketSearch();
    final assertion = expectLater(
      future,
      throwsA(
        isA<LocalApiException>().having(
          (e) => e.code,
          'safe code',
          'SESSION_CHANGED',
        ),
      ),
    );
    await session.signOut();
    await session.signIn('learner-b');
    pending.complete(
      LocalS3Reply(
        LocalMarketSearch.fromJson(s3Search()),
        'CACHED',
        DateTime.parse(s3FixtureTime),
      ),
    );
    await assertion;
    expect(session.user!.alias, 'learner-b');
  });
  test('current401 clears owned session', () async {
    api.onLists = () async =>
        throw const LocalApiException('SESSION_INVALID', status: 401);
    await expectLater(
      session.createS3Scope().watchlists(),
      throwsA(isA<LocalApiException>()),
    );
    expect(session.isAuthenticated, isFalse);
  });
  test(
    'current onboarding409 removes feature authority but retains owner',
    () async {
      api.onLists = () async =>
          throw const LocalApiException('ONBOARDING_REQUIRED', status: 409);
      await expectLater(
        session.createS3Scope().watchlists(),
        throwsA(isA<LocalApiException>()),
      );
      expect(session.canAccessFeatures, isFalse);
      expect(session.user!.alias, 'learner-a');
    },
  );
}
