import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../local_application/local_app_widgets.dart';
import '../local_application/local_session.dart';
import '../../features/onboarding/presentation/local_onboarding_page.dart';
import '../../features/onboarding/presentation/s1_onboarding_page.dart';
import '../../features/risk/presentation/s2_risk_page.dart';
import '../../features/risk/presentation/local_saved_risk_page.dart';
import '../../features/portfolio/presentation/local_manual_portfolio_page.dart';
import '../../features/market/presentation/local_market_page.dart';
import '../../features/market/presentation/local_watchlists_page.dart';
import '../../features/account/presentation/local_paper_account_page.dart';
import '../../shared/widgets/app_shell.dart';

class AppRouter {
  static const featureRoutes = {
    '/dashboard',
    '/risk',
    '/portfolio',
    '/market',
    '/watchlist',
    '/account',
    '/paper-trading',
    '/goals',
  };

  static GoRouter create(
    LocalSession session, {
    String initialLocation = '/',
  }) => GoRouter(
    initialLocation: initialLocation,
    overridePlatformDefaultLocation: initialLocation != '/',
    refreshListenable: session,
    redirect: (context, state) {
      final path = state.uri.path;
      if (path.startsWith('/pilot/')) return null;
      if (path == '/') return '/login';
      if (path == '/login') {
        return session.isAuthenticated ? '/onboarding' : null;
      }
      if (path == '/onboarding' ||
          path == '/consent' ||
          featureRoutes.contains(path)) {
        if (!session.isAuthenticated) return '/login';
        if (path == '/consent') return '/onboarding';
        if (featureRoutes.contains(path) &&
            session.onboarding != null &&
            !session.onboarding!.canAccessFeatures) {
          return '/onboarding';
        }
      }
      return null;
    },
    routes: [
      GoRoute(path: '/', redirect: (_, _) => '/login'),
      ShellRoute(
        builder: (context, state, child) =>
            AppShell(session: session, location: state.uri.path, child: child),
        routes: [
          GoRoute(
            path: '/login',
            builder: (_, _) => LocalLoginPage(session: session),
          ),
          GoRoute(path: '/consent', redirect: (_, _) => '/onboarding'),
          GoRoute(
            path: '/onboarding',
            builder: (_, _) => LocalOnboardingPage(session: session),
          ),
          GoRoute(
            path: '/dashboard',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/dashboard'),
              session: session,
              child: LocalDashboardPage(session: session),
            ),
          ),
          GoRoute(
            path: '/risk',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/risk'),
              session: session,
              child: LocalSavedRiskPage(
                key: ValueKey('risk-${session.generation}'),
                session: session,
              ),
            ),
          ),
          GoRoute(
            path: '/portfolio',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/portfolio'),
              session: session,
              child: LocalManualPortfolioPage(
                key: ValueKey('portfolio-${session.generation}'),
                session: session,
              ),
            ),
          ),
          GoRoute(
            path: '/market',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/market'),
              session: session,
              child: LocalMarketPage(
                key: ValueKey('market-${session.generation}'),
                session: session,
              ),
            ),
          ),
          GoRoute(
            path: '/watchlist',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/watchlist'),
              session: session,
              child: LocalWatchlistsPage(
                key: ValueKey('watchlist-${session.generation}'),
                session: session,
              ),
            ),
          ),
          GoRoute(
            path: '/account',
            builder: (_, _) => LocalFeatureGate(
              key: const ValueKey('/account'),
              session: session,
              child: LocalPaperAccountPage(
                key: ValueKey('account-${session.generation}'),
                session: session,
              ),
            ),
          ),
          for (final entry in const {
            '/paper-trading': ('Simulated paper ledger', 4),
            '/goals': ('Saved financial goals', 4),
          }.entries)
            GoRoute(
              path: entry.key,
              builder: (_, _) => LocalFeatureGate(
                key: ValueKey(entry.key),
                session: session,
                child: LocalPendingPage(
                  title: entry.value.$1,
                  sprint: entry.value.$2,
                ),
              ),
            ),
          GoRoute(
            path: '/pilot/consent',
            redirect: (_, _) => '/pilot/onboarding',
          ),
          GoRoute(
            path: '/pilot/onboarding',
            builder: (_, _) => const S1OnboardingPage(riskPath: '/pilot/risk'),
          ),
          GoRoute(
            path: '/pilot/risk',
            builder: (_, _) =>
                const S2RiskPage(onboardingPath: '/pilot/onboarding'),
          ),
        ],
      ),
    ],
    errorBuilder: (_, state) => AppShell(
      session: session,
      location: state.uri.path,
      child: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Page not found. Use the navigation to return to the local application.',
          ),
        ),
      ),
    ),
  );
}
