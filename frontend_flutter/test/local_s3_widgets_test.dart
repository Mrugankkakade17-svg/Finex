import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/core/local_application/local_s3_models.dart';
import 'package:frontend_flutter/main.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'support/local_application_fake.dart';
import 'support/local_s3_fake.dart';
import 'support/local_s3_data.dart';

void main() {
  late FakeLocalApi auth;
  late FakeLocalS3Api api;
  late LocalSession session;
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    auth = FakeLocalApi();
    auth.states['learner-a'] = completedTestState();
    auth.states['learner-b'] = completedTestState('Synthetic B');
    api = FakeLocalS3Api();
    session = LocalSession(api: auth, s3Api: api, clock: () => localTestTime);
    await session.signIn('learner-a');
  });
  Future<void> mount(WidgetTester tester, String path) async {
    await tester.pumpWidget(FinExApp(session: session, initialLocation: path));
    await tester.pumpAndSettle();
  }

  Future<void> tap(WidgetTester tester, String key) async {
    final target = find.byKey(Key(key));
    expect(target, findsOneWidget);
    await tester.ensureVisible(target);
    await tester.pumpAndSettle();
    await tester.tap(target);
    await tester.pumpAndSettle();
  }

  Future<void> clean(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox.shrink());
    session.dispose();
  }

  testWidgets(
    'dashboard describes available S3 foundation but not S4 delivery',
    (tester) async {
      try {
        await mount(tester, '/dashboard');
        expect(
          find.textContaining(
            'S3 synthetic market, owned watchlists and explicit simulated account opening',
          ),
          findsOneWidget,
        );
        expect(
          find.textContaining('Simulated orders and goals remain pending S4'),
          findsOneWidget,
        );
        expect(
          find.textContaining(
            'Market, simulated execution and goals remain pending S3/S4',
          ),
          findsNothing,
        );
      } finally {
        await clean(tester);
      }
    },
  );

  testWidgets(
    'search supports actual empty results and exact synthetic quote',
    (tester) async {
      try {
        await mount(tester, '/market');
        expect(find.text('Supported synthetic instruments'), findsOneWidget);
        await tap(tester, 's3-quote-SYN:AAPL');
        expect(find.text('USD 200.0000'), findsOneWidget);
        expect(
          find.textContaining('finex.synthetic.portfolio'),
          findsOneWidget,
        );
        await tester.enterText(
          find.byKey(const Key('s3-search-query')),
          'no match',
        );
        await tap(tester, 's3-search');
        expect(
          find.text('No supported instruments match this search.'),
          findsOneWidget,
        );
        expect(find.text('USD 200.0000'), findsNothing);
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets('watchlist owned CRUD confirms names and item persistence', (
    tester,
  ) async {
    try {
      await mount(tester, '/watchlist');
      expect(find.text('Owned watchlists'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('s3-create-name')),
        'Teaching list',
      );
      await tap(tester, 's3-create');
      expect(find.text('Teaching list'), findsWidgets);
      await tap(tester, 's3-add-SYN:AAPL');
      expect(find.text('Saved supported instruments: 1'), findsOneWidget);
      await tap(tester, 's3-remove-SYN:AAPL');
      expect(find.text('Saved supported instruments: 0'), findsOneWidget);
      await tester.enterText(
        find.byKey(const Key('s3-edit-name')),
        'Renamed list',
      );
      await tap(tester, 's3-rename');
      expect(find.text('Renamed list'), findsWidgets);
      await tap(tester, 's3-delete');
      await tap(tester, 's3-confirm-delete');
      expect(find.text('No owned watchlists saved yet.'), findsOneWidget);
    } finally {
      await clean(tester);
    }
  });
  testWidgets('unopened GET does not fund; explicit opening shows one ledger', (
    tester,
  ) async {
    try {
      await mount(tester, '/account');
      expect(find.text('Simulated paper account'), findsOneWidget);
      expect(
        find.text('No simulated account has been opened.'),
        findsOneWidget,
      );
      expect(api.calls.where((c) => c.startsWith('open:')), isEmpty);
      await tap(tester, 's3-open-account');
      expect(find.text('Simulated cash balance: USD 10000.00'), findsOneWidget);
      expect(find.textContaining('OPENING · sequence 1'), findsOneWidget);
      await tap(tester, 's3-account-reload');
      expect(api.calls.where((c) => c.startsWith('open:')).length, 1);
    } finally {
      await clean(tester);
    }
  });
  testWidgets(
    'uncertain create requires successful list reload and deliberate reconciliation',
    (tester) async {
      api.onCreate = (name) async {
        api.saved['A']![s3Id] = s3Watchlist(name: name);
        throw const LocalApiException('REQUEST_TIMEOUT');
      };
      try {
        await mount(tester, '/watchlist');
        expect(find.text('Owned watchlists'), findsOneWidget);
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Kept uncertain name',
        );
        await tap(tester, 's3-create');
        expect(api.calls.where((c) => c.startsWith('create:')).length, 1);
        expect(
          find.textContaining('previous create was not confirmed'),
          findsOneWidget,
        );
        api.onLists = () async =>
            throw const LocalApiException('API_UNAVAILABLE');
        await tap(tester, 's3-watchlists-reload');
        expect(find.byKey(const Key('s3-reconcile-create')), findsNothing);
        api.onLists = null;
        await tap(tester, 's3-watchlists-reload');
        await tap(tester, 's3-reconcile-create');
        expect(api.calls.where((c) => c.startsWith('create:')).length, 1);
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'peer deletion reload clears selection but preserves independent create input',
    (tester) async {
      api.saved['A']![s3Id] = s3Watchlist(item: true);
      try {
        await mount(tester, '/watchlist');
        expect(find.text('Owned watchlists'), findsOneWidget);
        await tap(tester, 's3-select-$s3Id');
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Independent dirty create',
        );
        api.saved['A']!.clear();
        await tap(tester, 's3-watchlists-reload');
        expect(find.byKey(const Key('s3-edit-name')), findsNothing);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-create-name')))
              .controller!
              .text,
          'Independent dirty create',
        );
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'peer removal after collection read reconciles the typed404 missing selection',
    (tester) async {
      api.saved['A']![s3Id] = s3Watchlist(item: true);
      try {
        await mount(tester, '/watchlist');
        await tap(tester, 's3-select-$s3Id');
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Independent retained create',
        );
        await tester.enterText(
          find.byKey(const Key('s3-edit-name')),
          'Old selected dirty edit',
        );
        api.onLists = () async {
          final reply = LocalWatchlistList.fromJson(
            s3Watchlists()..['items'] = [s3Summary(count: 1)],
          );
          api.saved['A']!.clear();
          api.onLists = null;
          return LocalS3Reply(reply, 'CACHED', null);
        };
        await tap(tester, 's3-watchlists-reload');
        expect(tester.takeException(), isNull);
        expect(find.byKey(const Key('s3-edit-name')), findsNothing);
        expect(find.byKey(Key('s3-select-$s3Id')), findsNothing);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-create-name')))
              .controller!
              .text,
          'Independent retained create',
        );
        expect(find.textContaining('deletion confirmed'), findsNothing);
      } finally {
        await clean(tester);
      }
    },
  );
  for (final status in ['STALE', 'UNAVAILABLE']) {
    testWidgets(
      'quote $status remains labelled, not a zero or LIVE substitute',
      (tester) async {
        api.onQuote = (_) async => LocalS3Reply(
          LocalMarketQuote.fromJson(s3Quote(status: status)),
          status == 'UNAVAILABLE' ? 'UNAVAILABLE' : 'CACHED',
          status == 'UNAVAILABLE' ? null : DateTime.parse(s3FixtureTime),
        );
        try {
          await mount(tester, '/market');
          await tap(tester, 's3-quote-SYN:AAPL');
          expect(find.text('Status: $status'), findsOneWidget);
          if (status == 'UNAVAILABLE') {
            expect(
              find.textContaining('no zero price assumed'),
              findsOneWidget,
            );
          }
          expect(find.text('USD 0.0000'), findsNothing);
          expect(find.text('Status: LIVE'), findsNothing);
        } finally {
          await clean(tester);
        }
      },
    );
  }
  testWidgets(
    'quote failure removes an old selected price and offers explicit read retry',
    (tester) async {
      try {
        await mount(tester, '/market');
        await tap(tester, 's3-quote-SYN:AAPL');
        api.onQuote = (_) async => throw const LocalApiException(
          'LOCAL_QUOTE_UNAVAILABLE',
          status: 503,
        );
        await tap(tester, 's3-quote-SYN:AAPL');
        expect(find.text('USD 200.0000'), findsNothing);
        expect(find.textContaining('No price was assumed'), findsOneWidget);
        api.onQuote = null;
        await tap(tester, 's3-quote-retry');
        expect(find.text('USD 200.0000'), findsOneWidget);
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'catalogue503 does not erase or block owned watchlist management',
    (tester) async {
      api.saved['A']![s3Id] = s3Watchlist();
      api.onSearch = () async => throw const LocalApiException(
        'LOCAL_CATALOG_UNAVAILABLE',
        status: 503,
      );
      try {
        await mount(tester, '/watchlist');
        await tap(tester, 's3-select-$s3Id');
        expect(find.byKey(const Key('s3-rename')), findsOneWidget);
        expect(
          find.textContaining('Owned list management remains available'),
          findsOneWidget,
        );
        await tester.enterText(
          find.byKey(const Key('s3-edit-name')),
          'Catalogue independent rename',
        );
        await tap(tester, 's3-rename');
        expect(
          find.textContaining(
            'Selected watchlist: Catalogue independent rename',
          ),
          findsOneWidget,
        );
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'failed collection read keeps confirmed detail and dirty create input',
    (tester) async {
      api.saved['A']![s3Id] = s3Watchlist(item: true);
      try {
        await mount(tester, '/watchlist');
        await tap(tester, 's3-select-$s3Id');
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Keep dirty create',
        );
        api.onLists = () async => throw const LocalApiException(
          'LOCAL_STORE_UNAVAILABLE',
          status: 503,
        );
        await tap(tester, 's3-watchlists-reload');
        expect(find.text('Saved supported instruments: 1'), findsOneWidget);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-create-name')))
              .controller!
              .text,
          'Keep dirty create',
        );
        expect(
          find.textContaining('Nothing was confirmed saved'),
          findsOneWidget,
        );
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'initial list failure remains visible after a healthy catalogue read',
    (tester) async {
      api.onLists = () async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      try {
        await mount(tester, '/watchlist');
        expect(
          find.textContaining('Local storage is unavailable'),
          findsOneWidget,
        );
        expect(find.text('No owned watchlists saved yet.'), findsNothing);
        expect(find.byKey(const Key('s3-watchlists-reload')), findsOneWidget);
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'peer rename updates current metadata but never overwrites a dirty editor',
    (tester) async {
      api.saved['A']![s3Id] = s3Watchlist();
      try {
        await mount(tester, '/watchlist');
        await tap(tester, 's3-select-$s3Id');
        await tester.enterText(
          find.byKey(const Key('s3-edit-name')),
          'Unsaved own edit',
        );
        api.saved['A']![s3Id]!['name'] = 'Other client rename';
        await tap(tester, 's3-watchlists-reload');
        expect(
          find.text('Selected watchlist: Other client rename'),
          findsOneWidget,
        );
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-edit-name')))
              .controller!
              .text,
          'Unsaved own edit',
        );
        expect(api.calls.where((c) => c.startsWith('rename:')), isEmpty);
      } finally {
        await clean(tester);
      }
    },
  );
  testWidgets(
    'failed ledger read preserves confirmed account cash and offers a read-only retry',
    (tester) async {
      api.opened.add('A');
      api.onLedger = () async =>
          throw const LocalApiException('LOCAL_STORE_UNAVAILABLE', status: 503);
      try {
        await mount(tester, '/account');
        expect(
          find.text('Simulated cash balance: USD 10000.00'),
          findsOneWidget,
        );
        expect(
          find.textContaining('Opening ledger unavailable'),
          findsOneWidget,
        );
        api.onLedger = null;
        await tap(tester, 's3-ledger-reload');
        expect(find.textContaining('OPENING · sequence 1'), findsOneWidget);
        expect(api.calls.where((c) => c.startsWith('open:')), isEmpty);
      } finally {
        await clean(tester);
      }
    },
  );
  for (final alias in ['learner-b', 'learner-a']) {
    testWidgets('coalesced A to $alias clears old form and ignores stale401', (
      tester,
    ) async {
      try {
        await mount(tester, '/watchlist');
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Private A controller',
        );
        final pending = Completer<LocalS3Reply<LocalWatchlistList>>();
        api.onLists = () => pending.future;
        await tester.ensureVisible(
          find.byKey(const Key('s3-watchlists-reload')),
        );
        await tester.tap(find.byKey(const Key('s3-watchlists-reload')));
        await tester.pump();
        api.onLists = null;
        await session.signOut();
        await session.signIn(alias);
        await tester.pumpAndSettle();
        pending.completeError(
          const LocalApiException('SESSION_INVALID', status: 401),
        );
        await tester.pumpAndSettle();
        expect(session.user!.alias, alias);
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-create-name')))
              .controller!
              .text,
          isEmpty,
        );
      } finally {
        await clean(tester);
      }
    });
  }
  testWidgets(
    'failed logout hides and retains dirty form; old401 cannot revoke it',
    (tester) async {
      final semantics = tester.ensureSemantics();
      try {
        await mount(tester, '/watchlist');
        await tester.enterText(
          find.byKey(const Key('s3-create-name')),
          'Private retained input',
        );
        final pending = Completer<LocalS3Reply<LocalWatchlistList>>();
        api.onLists = () => pending.future;
        await tester.ensureVisible(
          find.byKey(const Key('s3-watchlists-reload')),
        );
        await tester.tap(find.byKey(const Key('s3-watchlists-reload')));
        await tester.pump();
        auth.onLogout = (_) async =>
            throw const LocalApiException('API_UNAVAILABLE');
        await session.signOut();
        await tester.pumpAndSettle();
        pending.completeError(
          const LocalApiException('SESSION_INVALID', status: 401),
        );
        await tester.pumpAndSettle();
        expect(session.user!.alias, 'learner-a');
        expect(find.byKey(const Key('s3-create-name')), findsNothing);
        expect(find.bySemanticsLabel('Private retained input'), findsNothing);
        final retained = find.byKey(
          const Key('s3-create-name'),
          skipOffstage: false,
        );
        expect(
          tester.widget<TextField>(retained).controller!.text,
          'Private retained input',
        );
        api.onLists = null;
        await tester.tap(find.text('Retry saved-state check'));
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<TextField>(find.byKey(const Key('s3-create-name')))
              .controller!
              .text,
          'Private retained input',
        );
      } finally {
        semantics.dispose();
        await clean(tester);
      }
    },
  );
  for (final path in ['/market', '/watchlist', '/account']) {
    testWidgets(
      '$path at320px/200percent has labelled accessible48px controls',
      (tester) async {
        tester.view.physicalSize = const Size(320, 844);
        tester.view.devicePixelRatio = 1;
        final semantics = tester.ensureSemantics();
        try {
          await tester.pumpWidget(
            MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(2)),
              child: FinExApp(session: session, initialLocation: path),
            ),
          );
          await tester.pumpAndSettle();
          final key = path == '/market'
              ? 's3-search'
              : path == '/watchlist'
              ? 's3-create'
              : 's3-open-account';
          final target = find.byKey(Key(key));
          await tester.ensureVisible(target);
          await tester.pumpAndSettle();
          expect(tester.getSize(target).height, greaterThanOrEqualTo(48));
          final button = find.descendant(
            of: target,
            matching: find.byType(ElevatedButton),
          );
          final label = path == '/market'
              ? 'Search supported catalogue'
              : path == '/watchlist'
              ? 'Create owned watchlist'
              : 'Open simulated account once';
          expect(tester.getSemantics(button).getSemanticsData().label, label);
          expect(tester.takeException(), isNull);
        } finally {
          semantics.dispose();
          await clean(tester);
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        }
      },
    );
  }
}
