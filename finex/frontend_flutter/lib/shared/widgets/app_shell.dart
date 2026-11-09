import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  final Widget child;

  const AppShell({
    super.key,
    required this.child,
  });

  static const destinations = [
    _Destination(
      label: 'Dashboard',
      path: '/dashboard',
      icon: Icons.dashboard_outlined,
    ),
    _Destination(
      label: 'Portfolio',
      path: '/portfolio',
      icon: Icons.pie_chart_outline,
    ),
    _Destination(
      label: 'Market',
      path: '/market',
      icon: Icons.search_outlined,
    ),
    _Destination(
      label: 'Watchlist',
      path: '/watchlist',
      icon: Icons.star_outline,
    ),
    _Destination(
      label: 'AI Assistant',
      path: '/chat',
      icon: Icons.smart_toy_outlined,
    ),
    _Destination(
      label: 'Paper Trading',
      path: '/paper-trading',
      icon: Icons.trending_up,
    ),
    _Destination(
      label: 'Alerts',
      path: '/alerts',
      icon: Icons.notifications_none,
    ),
    _Destination(
      label: 'Goals',
      path: '/goals',
      icon: Icons.flag_outlined,
    ),
    _Destination(
      label: 'Spending',
      path: '/spending',
      icon: Icons.credit_card_outlined,
    ),
    _Destination(
      label: 'Onboarding',
      path: '/onboarding',
      icon: Icons.person_outline,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;

    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Icon(Icons.auto_awesome),
            SizedBox(width: 8),
            Text('FinEx'),
          ],
        ),
      ),
      drawer: Drawer(
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'FinEx',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text('Financial Excellence'),
                  ],
                ),
              ),
              const Divider(),
              Expanded(
                child: ListView(
                  children: destinations.map((destination) {
                    final selected = location == destination.path;

                    return ListTile(
                      leading: Icon(destination.icon),
                      title: Text(destination.label),
                      selected: selected,
                      onTap: () {
                        Navigator.of(context).pop();
                        context.go(destination.path);
                      },
                    );
                  }).toList(),
                ),
              ),
            ],
          ),
        ),
      ),
      body: child,
    );
  }
}

class _Destination {
  final String label;
  final String path;
  final IconData icon;

  const _Destination({
    required this.label,
    required this.path,
    required this.icon,
  });
}