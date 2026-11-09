import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/local_application/local_app_widgets.dart';
import '../../core/local_application/local_app_theme.dart';
import '../../core/local_application/local_session.dart';

class AppShell extends StatelessWidget {
  final Widget child;
  final LocalSession session;
  final String location;
  const AppShell({
    super.key,
    required this.child,
    required this.session,
    required this.location,
  });

  static const _destinations = [
    ('Saved onboarding', '/onboarding', Icons.person_outline),
    ('S1 dashboard', '/dashboard', Icons.dashboard_outlined),
    ('Saved S2 risk', '/risk', Icons.shield_outlined),
    ('Manual S2 portfolios', '/portfolio', Icons.pie_chart_outline),
    ('S3 synthetic market', '/market', Icons.search_outlined),
    ('S3 owned watchlists', '/watchlist', Icons.star_outline),
    ('S3 simulated account', '/account', Icons.settings_outlined),
    ('S4 paper ledger (pending)', '/paper-trading', Icons.trending_up),
    ('S4 goals (pending)', '/goals', Icons.flag_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    final pilot = location.startsWith('/pilot/');
    return ListenableBuilder(
      listenable: session,
      builder: (context, _) => Theme(
        data: pilot
            ? Theme.of(context)
            : localApplicationTheme(Theme.of(context)),
        child: Scaffold(
          appBar: AppBar(
            title: const Text('FinEx'),
            actions: [
              if (!pilot && session.isAuthenticated)
                TextButton.icon(
                  key: const Key('local-sign-out'),
                  onPressed: session.authBusy ? null : session.signOut,
                  icon: const Icon(Icons.logout),
                  label: Text(session.authBusy ? 'Signing out…' : 'Sign out'),
                ),
            ],
          ),
          drawer: Drawer(
            child: SafeArea(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Text(
                      pilot
                          ? 'Compatibility pilot — nonpersistent'
                          : session.user == null
                          ? 'Local educational application — signed out'
                          : 'Synthetic learner: ${session.user!.alias}',
                    ),
                  ),
                  const Divider(),
                  Expanded(
                    child: ListView(
                      children: [
                        if (pilot) ...[
                          _tile(
                            context,
                            location,
                            'Pilot onboarding',
                            '/pilot/onboarding',
                            Icons.person_outline,
                          ),
                          _tile(
                            context,
                            location,
                            'Pilot risk questionnaire',
                            '/pilot/risk',
                            Icons.shield_outlined,
                          ),
                        ] else if (session.isAuthenticated)
                          for (final item in _destinations)
                            _tile(context, location, item.$1, item.$2, item.$3),
                        _tile(
                          context,
                          location,
                          pilot
                              ? 'Return to full application'
                              : 'Sign in / resume',
                          '/login',
                          Icons.login,
                        ),
                        if (!pilot)
                          _tile(
                            context,
                            location,
                            'Separate compatibility pilot',
                            '/pilot/onboarding',
                            Icons.science_outlined,
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          body: LayoutBuilder(
            builder: (context, constraints) => Column(
              children: [
                if (pilot)
                  const MaterialBanner(
                    content: Text(
                      'Nonpersistent compatibility pilot. Local device flow flags are not full-app identity, saved assessments or authorization.',
                    ),
                    actions: [SizedBox.shrink()],
                  ),
                if (!pilot &&
                    session.isAuthenticated &&
                    session.authError != null)
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxHeight: constraints.maxHeight / 2,
                    ),
                    child: SingleChildScrollView(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        child: Column(
                          children: [
                            LocalErrorNotice(
                              message:
                                  '${session.authError!.message} Sign-out is not confirmed; this learner and form input have been retained.',
                            ),
                            TextButton(
                              onPressed: session.authBusy
                                  ? null
                                  : session.signOut,
                              child: const Text('Retry confirmed sign-out'),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                // The nested route's BlockSemantics must not hide shell errors.
                Expanded(child: Semantics(container: true, child: child)),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tile(
    BuildContext context,
    String current,
    String label,
    String path,
    IconData icon,
  ) => ListTile(
    leading: Icon(icon),
    title: Text(label),
    selected: current == path,
    onTap: () {
      Navigator.of(context).pop();
      context.go(path);
    },
  );
}
