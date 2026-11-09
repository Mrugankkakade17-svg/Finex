import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../shared/widgets/app_button.dart';
import '../../shared/widgets/app_card.dart';
import 'local_models.dart';
import 'local_session.dart';

class LocalErrorNotice extends StatelessWidget {
  final String message;
  const LocalErrorNotice({super.key, required this.message});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Semantics(
      container: true,
      liveRegion: true,
      label: message,
      excludeSemantics: true,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          border: Border.all(color: Colors.redAccent),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(message),
      ),
    ),
  );
}

class LocalLoginPage extends StatefulWidget {
  final LocalSession session;
  const LocalLoginPage({super.key, required this.session});

  @override
  State<LocalLoginPage> createState() => _LocalLoginPageState();
}

class _LocalLoginPageState extends State<LocalLoginPage> {
  String _alias = localAliases.first;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.session,
    builder: (context, _) => Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: AppCard(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'Choose a synthetic learner',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 12),
                const Text(
                  'This is a trusted, loopback-only educational simulation, not verified identity or Google OAuth. '
                  'Another local operator can select the same persona. Use synthetic labels only: no real personal or financial data.',
                ),
                const SizedBox(height: 20),
                DropdownButtonFormField<String>(
                  key: const Key('local-login-alias'),
                  initialValue: _alias,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Synthetic learner',
                  ),
                  items: localAliases
                      .map(
                        (alias) =>
                            DropdownMenuItem(value: alias, child: Text(alias)),
                      )
                      .toList(),
                  onChanged: widget.session.authBusy
                      ? null
                      : (alias) => setState(() => _alias = alias!),
                ),
                const SizedBox(height: 16),
                if (widget.session.authError case final error?)
                  LocalErrorNotice(message: error.message),
                AppButton(
                  key: const Key('local-sign-in'),
                  label: widget.session.authBusy
                      ? 'Validating local session…'
                      : 'Sign in to local application',
                  loading: widget.session.authBusy,
                  onPressed: () => widget.session.signIn(_alias),
                ),
                const SizedBox(height: 16),
                const Text(
                  'The opaque session stays in memory only. After closing or reloading, sign in again to resume server-saved data. '
                  'No real money, broker connection or investment advice.',
                ),
                TextButton(
                  onPressed: widget.session.authBusy
                      ? null
                      : () => context.go('/pilot/onboarding'),
                  child: const Text('Open nonpersistent compatibility pilot'),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

/// Every protected entry loads the server state, including another client's changes.
class LocalFeatureGate extends StatefulWidget {
  final LocalSession session;
  final Widget child;
  const LocalFeatureGate({
    super.key,
    required this.session,
    required this.child,
  });

  @override
  State<LocalFeatureGate> createState() => _LocalFeatureGateState();
}

class _LocalFeatureGateState extends State<LocalFeatureGate> {
  bool _checking = true;
  int _checkEpoch = 0;
  late int _observedGeneration;
  bool _needsFreshCheck = true;
  bool _checkScheduled = false;
  int? _authorizedGeneration;
  String? _authorizedOwner;

  @override
  void initState() {
    super.initState();
    _observedGeneration = widget.session.generation;
    widget.session.addListener(_sessionChanged);
    _scheduleCheck(widget.session);
  }

  void _scheduleCheck(LocalSession session) {
    if (_checkScheduled) return;
    _checkScheduled = true;
    final generation = session.generation;
    final epoch = _checkEpoch;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted ||
          !identical(widget.session, session) ||
          session.generation != generation ||
          _checkEpoch != epoch) {
        return;
      }
      _checkScheduled = false;
      if (session.isAuthenticated && !session.isBusy) _check();
    });
  }

  void _sessionChanged() {
    final session = widget.session;
    if (_observedGeneration != session.generation) {
      _observedGeneration = session.generation;
      _checkEpoch++;
      _checking = true;
      _needsFreshCheck = true;
      _checkScheduled = false;
      _authorizedGeneration = null;
      _authorizedOwner = null;
    }
    // A coalesced logout/relogin can retain this gate widget. Bind a fresh
    // check to the new generation rather than waiting for the old read, which
    // may ignore cancellation or never resolve. Failed logout keeps its owner.
    if (_needsFreshCheck && session.isAuthenticated && !session.isBusy) {
      _scheduleCheck(session);
    }
  }

  @override
  void didUpdateWidget(covariant LocalFeatureGate oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (identical(oldWidget.session, widget.session)) return;
    oldWidget.session.removeListener(_sessionChanged);
    widget.session.addListener(_sessionChanged);
    _observedGeneration = widget.session.generation;
    _checkEpoch++;
    _checking = true;
    _needsFreshCheck = true;
    _checkScheduled = false;
    _authorizedGeneration = null;
    _authorizedOwner = null;
    _scheduleCheck(widget.session);
  }

  Future<void> _check() async {
    final session = widget.session;
    if (!mounted || !session.isAuthenticated || session.isBusy) return;
    final generation = session.generation;
    final checkEpoch = ++_checkEpoch;
    _needsFreshCheck = false;
    _checkScheduled = false;
    if (mounted) setState(() => _checking = true);
    await session.refreshOnboarding();
    if (!mounted ||
        !identical(widget.session, session) ||
        session.generation != generation ||
        checkEpoch != _checkEpoch) {
      return;
    }
    if (session.onboarding != null && !session.onboarding!.canAccessFeatures) {
      context.go('/onboarding');
      return;
    }
    setState(() => _checking = false);
  }

  @override
  void dispose() {
    _checkEpoch++;
    widget.session.removeListener(_sessionChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.session,
    builder: (context, _) {
      final session = widget.session;
      if (!_checking && session.canAccessFeatures) {
        _authorizedGeneration = session.generation;
        _authorizedOwner = session.user!.id;
      }
      final sameOwner =
          _authorizedGeneration == session.generation &&
          _authorizedOwner == session.user?.id &&
          session.isAuthenticated;
      final revoked =
          session.onboarding?.canAccessFeatures == false ||
          session.operationError?.code == 'ONBOARDING_REQUIRED';
      final retain = sameOwner && !revoked;
      final visible = retain && !_checking && session.canAccessFeatures;
      Widget? notice;
      if (_checking ||
          session.loadingState ||
          session.authBusy ||
          session.saving) {
        notice = Center(
          child: Semantics(
            liveRegion: true,
            child: const Text('Checking saved consent and onboarding…'),
          ),
        );
      } else if (!visible) {
        notice = Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                LocalErrorNotice(
                  message:
                      session.loadError?.message ??
                      session.authError?.message ??
                      session.operationError?.message ??
                      'Completion could not be confirmed.',
                ),
                AppButton(label: 'Retry saved-state check', onPressed: _check),
                TextButton(
                  onPressed: () => context.go('/onboarding'),
                  child: const Text('Return to onboarding'),
                ),
              ],
            ),
          ),
        );
      }
      return Stack(
        fit: StackFit.expand,
        children: [
          if (retain)
            Offstage(
              offstage: !visible,
              child: ExcludeFocus(
                excluding: !visible,
                child: ExcludeSemantics(
                  excluding: !visible,
                  child: IgnorePointer(
                    ignoring: !visible,
                    // GoRouter can retain the same page widget across a rapid
                    // sign-out/sign-in without an intermediate rendered frame.
                    // The gate, not a route rebuild, owns controller isolation.
                    child: KeyedSubtree(
                      key: ValueKey((session.generation, session.user!.id)),
                      child: widget.child,
                    ),
                  ),
                ),
              ),
            ),
          ?notice,
        ],
      );
    },
  );
}

class LocalDashboardPage extends StatelessWidget {
  final LocalSession session;
  const LocalDashboardPage({super.key, required this.session});

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
    padding: const EdgeInsets.all(24),
    child: AppCard(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Saved onboarding dashboard',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 12),
          Text('Synthetic learner: ${session.user!.alias}'),
          Text('Display label: ${session.onboarding!.displayName}'),
          Text('Experience: ${session.onboarding!.experienceLevel}'),
          Text(
            'Completed (UTC): ${session.onboarding!.completedAt!.toIso8601String()}',
          ),
          const SizedBox(height: 16),
          const Text(
            'This confirms server-saved onboarding. Open Saved S2 risk or Manual S2 portfolios from navigation for the owned educational journeys. Use S3 synthetic market, owned watchlists and explicit simulated account opening. Simulated orders and goals remain pending S4. Only server-confirmed synthetic data is shown; no real money or live market prices are claimed.',
          ),
          const SizedBox(height: 16),
          AppButton(
            label: 'Review consent and saved profile',
            onPressed: () => context.go('/onboarding'),
          ),
        ],
      ),
    ),
  );
}

class LocalPendingPage extends StatelessWidget {
  final String title;
  final int sprint;
  const LocalPendingPage({
    super.key,
    required this.title,
    required this.sprint,
  });

  @override
  Widget build(BuildContext context) => Center(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: AppCard(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            Text(
              'Pending Sprint $sprint delivery. This full-application screen is not implemented or accepted yet; it does not display demonstration values or claim successful execution.',
            ),
          ],
        ),
      ),
    ),
  );
}
