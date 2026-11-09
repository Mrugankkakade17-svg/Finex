import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/dashboard/dashboard_page.dart';
import '../../features/market/presentation/market_page.dart';
import '../../features/market/presentation/watchlist_page.dart';
import '../../shared/widgets/app_shell.dart';
import '../../shared/widgets/feature_placeholder.dart';

class AppRouter {
  static final GoRouter router = GoRouter(
    initialLocation: '/dashboard',
    routes: [
      ShellRoute(
        builder: (context, state, child) {
          return AppShell(child: child);
        },
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (context, state) => const DashboardPage(),
          ),
          GoRoute(
            path: '/portfolio',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Portfolio',
              description:
                  'View holdings, allocation and portfolio performance.',
              icon: Icons.pie_chart_outline,
              primaryAction: 'View Portfolio',
            ),
          ),
          GoRoute(
            path: '/market',
            builder: (context, state) => const MarketPage(),
          ),
          GoRoute(
            path: '/watchlist',
            builder: (context, state) => const WatchlistPage(),
          ),
          GoRoute(
            path: '/chat',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'AI Assistant',
              description:
                  'Your future AI-powered financial assistant.',
              icon: Icons.smart_toy_outlined,
              primaryAction: 'Start Assistant',
            ),
          ),
          GoRoute(
            path: '/paper-trading',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Paper Trading',
              description:
                  'Practice investment decisions without real money.',
              icon: Icons.trending_up,
              primaryAction: 'Open Paper Trading',
            ),
          ),
          GoRoute(
            path: '/alerts',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Smart Alerts',
              description:
                  'Monitor portfolio and market events.',
              icon: Icons.notifications_none,
              primaryAction: 'View Alerts',
            ),
          ),
          GoRoute(
            path: '/goals',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Financial Goals',
              description:
                  'Track and plan progress toward your financial goals.',
              icon: Icons.flag_outlined,
              primaryAction: 'Manage Goals',
            ),
          ),
          GoRoute(
            path: '/spending',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Spending',
              description:
                  'Understand spending patterns and financial trends.',
              icon: Icons.credit_card_outlined,
              primaryAction: 'View Spending',
            ),
          ),
          GoRoute(
            path: '/onboarding',
            builder: (context, state) => const FeaturePlaceholder(
              title: 'Onboarding',
              description:
                  'Set up your FinEx profile and financial preferences.',
              icon: Icons.person_outline,
              primaryAction: 'Continue Setup',
            ),
          ),
        ],
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => const _Page(title: 'Login'),
      ),
    ],
    errorBuilder: (context, state) => const _Page(
      title: 'Page Not Found',
    ),
  );
}

class _Page extends StatelessWidget {
  final String title;

  const _Page({
    required this.title,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        title,
        style: Theme.of(context).textTheme.headlineMedium,
      ),
    );
  }
}