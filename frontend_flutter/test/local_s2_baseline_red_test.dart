import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_app_widgets.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';
import 'package:frontend_flutter/core/local_application/local_session.dart';
import 'package:frontend_flutter/main.dart';

import 'support/local_application_fake.dart';

class _DirtyForm extends StatefulWidget {
  final VoidCallback onDispose;
  const _DirtyForm({required this.onDispose});
  @override
  State<_DirtyForm> createState() => _DirtyFormState();
}

class _DirtyFormState extends State<_DirtyForm> {
  final controller = TextEditingController();
  @override
  void dispose() {
    widget.onDispose();
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      TextField(key: const Key('owned-dirty-form'), controller: controller);
}

void main() {
  for (final route in ['/risk', '/portfolio']) {
    testWidgets('owned $route no longer renders an S2 placeholder', (
      tester,
    ) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      final session = LocalSession(api: api, clock: () => localTestTime);
      await session.signIn('learner-a');
      await tester.pumpWidget(
        FinExApp(session: session, initialLocation: route),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Pending Sprint 2 delivery.'), findsNothing);
      expect(
        find.text(
          route == '/risk' ? 'Saved risk questionnaire' : 'Manual portfolios',
        ),
        findsOneWidget,
      );
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    });
  }

  testWidgets(
    'failed logout retains an already authorized owned form subtree',
    (tester) async {
      final api = FakeLocalApi();
      api.states['learner-a'] = completedTestState();
      api.onLogout = (_) async =>
          throw const LocalApiException('API_UNAVAILABLE');
      final session = LocalSession(api: api, clock: () => localTestTime);
      await session.signIn('learner-a');
      var disposals = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: LocalFeatureGate(
              session: session,
              child: _DirtyForm(onDispose: () => disposals++),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('owned-dirty-form')),
        'Keep this input',
      );
      expect(await session.signOut(), isFalse);
      await tester.pumpAndSettle();
      expect(disposals, 0);
      final retained = find.byKey(
        const Key('owned-dirty-form'),
        skipOffstage: false,
      );
      expect(
        tester.widget<TextField>(retained).controller!.text,
        'Keep this input',
      );
      await tester.pumpWidget(const SizedBox.shrink());
      session.dispose();
    },
  );
}
