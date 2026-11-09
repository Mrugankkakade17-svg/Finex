import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../models/risk_question.dart';
import '../services/risk_service.dart';

class RiskResultPage extends StatelessWidget {
  const RiskResultPage({super.key});

  @override
  Widget build(BuildContext context) {
    final riskService = RiskService();
    final result = riskService.latestResult ??
        RiskAssessmentResult(
          totalScore: 10,
          willingnessScore: 6,
          capacityScore: 4,
          profileTier: 'Moderate',
          summaryExplanation:
              'You demonstrate a balanced profile, willing to accept moderate market fluctuations in exchange for steady multi-year capital growth.',
          topFactors: [
            'Horizon: 3 to 7 years',
            'Drawdown reaction: Wait for recovery',
            'Asset experience: Moderate',
          ],
          assessedAt: DateTime.now(),
        );

    final Color tierColor;
    final IconData tierIcon;

    switch (result.profileTier.toLowerCase()) {
      case 'conservative':
        tierColor = const Color(0xFF10B981);
        tierIcon = Icons.shield_outlined;
        break;
      case 'aggressive':
        tierColor = const Color(0xFFF59E0B);
        tierIcon = Icons.bolt_outlined;
        break;
      case 'moderate':
      default:
        tierColor = const Color(0xFF6366F1);
        tierIcon = Icons.balance_outlined;
        break;
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Risk Profile Result'),
        automaticallyImplyLeading: false,
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Result Badge Card
                  AppCard(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      children: [
                        CircleAvatar(
                          radius: 36,
                          backgroundColor: tierColor.withAlpha(38),
                          child: Icon(tierIcon, size: 40, color: tierColor),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Your Investor Profile',
                          style: TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 13,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          result.profileTier,
                          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: tierColor,
                              ),
                        ),
                        const SizedBox(height: 14),
                        Text(
                          result.summaryExplanation,
                          style: const TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 14,
                            height: 1.4,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 20),
                        const Divider(color: AppTheme.border),
                        const SizedBox(height: 12),

                        // Score Breakdown
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceAround,
                          children: [
                            _buildScoreMetric('Total Score', '${result.totalScore}/20'),
                            _buildScoreMetric('Willingness', '${result.willingnessScore}/12'),
                            _buildScoreMetric('Capacity', '${result.capacityScore}/8'),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Contributing Factors Card
                  AppCard(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Key Influencing Factors',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 12),
                        ...result.topFactors.map(
                          (factor) => Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Icon(Icons.check_circle, color: AppTheme.primary, size: 16),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    factor,
                                    style: const TextStyle(
                                      color: AppTheme.textSecondary,
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Mandatory Disclaimer Card
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.info_outline, color: AppTheme.textSecondary, size: 18),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Regulatory Note: Risk profiling is an educational decision-support tool. It does not constitute investment advice or guarantee portfolio returns.',
                            style: TextStyle(
                              color: AppTheme.textSecondary.withAlpha(217),
                              fontSize: 11,
                              height: 1.35,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Enter Dashboard Button
                  AppButton(
                    label: 'Complete Setup & Enter Dashboard',
                    icon: Icons.dashboard_outlined,
                    onPressed: () {
                      context.go('/dashboard');
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildScoreMetric(String label, String value) {
    return Column(
      children: [
        Text(
          value,
          style: const TextStyle(
            color: AppTheme.textPrimary,
            fontWeight: FontWeight.bold,
            fontSize: 16,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: TextStyle(
            color: AppTheme.textSecondary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}
