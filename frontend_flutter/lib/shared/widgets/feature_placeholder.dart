import 'package:flutter/material.dart';

import 'app_card.dart';
import 'empty_view.dart';

class FeaturePlaceholder extends StatelessWidget {
  final String title;
  final String description;
  final IconData icon;
  final String primaryAction;
  final VoidCallback? onPrimaryAction;

  const FeaturePlaceholder({
    super.key,
    required this.title,
    required this.description,
    required this.icon,
    required this.primaryAction,
    this.onPrimaryAction,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(
                  icon,
                  size: 30,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              description,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 24),
            AppCard(
              child: Row(
                children: [
                  Icon(
                    Icons.construction_outlined,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'FinEx platform module ready for integration.',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            AppCard(
              child: EmptyView(
                title: 'No live data yet',
                message:
                    'This Sprint 1 screen is connected and ready for the generated API/mock client.',
                icon: icon,
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onPrimaryAction,
              icon: const Icon(Icons.arrow_forward),
              label: Text(primaryAction),
            ),
          ],
        ),
      ),
    );
  }
}