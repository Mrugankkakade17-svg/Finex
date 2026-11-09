import 'package:flutter/material.dart';

import 'app_button.dart';
import 'app_card.dart';
import 'app_text_field.dart';
import 'loading_view.dart';

class WidgetsDemoPage extends StatefulWidget {
  const WidgetsDemoPage({super.key});

  @override
  State<WidgetsDemoPage> createState() => _WidgetsDemoPageState();
}

class _WidgetsDemoPageState extends State<WidgetsDemoPage> {
  bool buttonLoading = false;
  bool buttonEnabled = true;

  bool textFieldLoading = false;
  bool textFieldEnabled = true;

  bool cardEnabled = true;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FinEx Shared Widgets'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ------------------------------------------------------------
            // AppButton
            // ------------------------------------------------------------
            Text(
              'AppButton',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),

            AppButton(
              label: 'Continue',
              icon: Icons.arrow_forward,
              enabled: buttonEnabled,
              loading: buttonLoading,
              onPressed: () {
                setState(() {
                  buttonLoading = true;
                });

                Future.delayed(const Duration(seconds: 1), () {
                  if (mounted) {
                    setState(() {
                      buttonLoading = false;
                    });
                  }
                });
              },
            ),

            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() {
                        buttonEnabled = !buttonEnabled;
                      });
                    },
                    child: const Text('Toggle Disabled'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() {
                        buttonLoading = !buttonLoading;
                      });
                    },
                    child: const Text('Toggle Loading'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 32),

            // ------------------------------------------------------------
            // AppTextField
            // ------------------------------------------------------------
            Text(
              'AppTextField',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),

            AppTextField(
              label: 'Email',
              hint: 'Enter your email',
              errorText: 'Example validation error',
              enabled: textFieldEnabled,
              loading: textFieldLoading,
            ),

            const SizedBox(height: 12),

            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() {
                        textFieldEnabled = !textFieldEnabled;
                      });
                    },
                    child: const Text('Toggle Disabled'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () {
                      setState(() {
                        textFieldLoading = !textFieldLoading;
                      });
                    },
                    child: const Text('Toggle Loading'),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 32),

            // ------------------------------------------------------------
            // AppCard
            // ------------------------------------------------------------
            Text(
              'AppCard',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),

            AppCard(
              onTap: cardEnabled
                  ? () {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('AppCard tapped successfully'),
                        ),
                      );
                    }
                  : null,
              child: Row(
                children: [
                  const Icon(Icons.account_balance_wallet_outlined),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      cardEnabled
                          ? 'Interactive FinEx card'
                          : 'Disabled FinEx card',
                      style: const TextStyle(fontSize: 18),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            OutlinedButton(
              onPressed: () {
                setState(() {
                  cardEnabled = !cardEnabled;
                });
              },
              child: const Text('Toggle Card Interaction'),
            ),

            const SizedBox(height: 32),

            // ------------------------------------------------------------
            // LoadingView
            // ------------------------------------------------------------
            Text(
              'LoadingView',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),

            const SizedBox(
              height: 160,
              child: LoadingView(
                message: 'Loading FinEx data...',
              ),
            ),

            const SizedBox(height: 32),

            // ------------------------------------------------------------
            // State coverage summary
            // ------------------------------------------------------------
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Shared Widget State Coverage',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  const Text('✓ AppButton: enabled, disabled, loading'),
                  const Text('✓ AppTextField: enabled, disabled, loading, error'),
                  const Text('✓ AppCard: enabled and non-interactive states'),
                  const Text('✓ LoadingView: loading state'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}