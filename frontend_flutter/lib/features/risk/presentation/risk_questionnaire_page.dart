import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../services/risk_service.dart';

class RiskQuestionnairePage extends StatefulWidget {
  const RiskQuestionnairePage({super.key});

  @override
  State<RiskQuestionnairePage> createState() => _RiskQuestionnairePageState();
}

class _RiskQuestionnairePageState extends State<RiskQuestionnairePage> {
  final _riskService = RiskService();
  int _currentIndex = 0;

  void _nextOrSubmit() async {
    final questions = _riskService.questions;
    final currentQ = questions[_currentIndex];

    if (!_riskService.selectedAnswers.containsKey(currentQ.id)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please select an option to continue.'),
          backgroundColor: Colors.amber,
        ),
      );
      return;
    }

    if (_currentIndex < questions.length - 1) {
      setState(() => _currentIndex++);
    } else {
      // Final submission
      await _riskService.submitAssessment();
      if (mounted) {
        context.go('/risk/result');
      }
    }
  }

  void _previous() {
    if (_currentIndex > 0) {
      setState(() => _currentIndex--);
    } else {
      context.go('/onboarding/profile');
    }
  }

  @override
  Widget build(BuildContext context) {
    final questions = _riskService.questions;
    final currentQ = questions[_currentIndex];
    final progress = (_currentIndex + 1) / questions.length;
    final selectedOption = _riskService.selectedAnswers[currentQ.id];
    final isLast = _currentIndex == questions.length - 1;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Risk Profile Assessment'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: _previous,
        ),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Progress Bar & Counter
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Question ${_currentIndex + 1} of ${questions.length}',
                        style: const TextStyle(
                          color: AppTheme.primary,
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        '${(progress * 100).toInt()}% Completed',
                        style: const TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: progress,
                      minHeight: 8,
                      backgroundColor: AppTheme.border,
                      valueColor: const AlwaysStoppedAnimation<Color>(
                        AppTheme.primary,
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),

                  // Question Card
                  AppCard(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AppTheme.secondary.withAlpha(51),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            currentQ.category.toUpperCase(),
                            style: const TextStyle(
                              color: AppTheme.secondary,
                              fontWeight: FontWeight.bold,
                              fontSize: 11,
                              letterSpacing: 0.8,
                            ),
                          ),
                        ),
                        const SizedBox(height: 14),
                        Text(
                          currentQ.questionText,
                          style: Theme.of(context).textTheme.titleMedium
                              ?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary,
                                fontSize: 16,
                                height: 1.35,
                              ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          currentQ.subtitle,
                          style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Options
                        RadioGroup<String>(
                          groupValue: selectedOption?.id,
                          onChanged: (answerId) {
                            if (answerId == null) {
                              return;
                            }
                            final answer = currentQ.options.firstWhere(
                              (option) => option.id == answerId,
                            );
                            setState(
                              () => _riskService.selectAnswer(
                                currentQ.id,
                                answer,
                              ),
                            );
                          },
                          child: Column(
                            children: currentQ.options.map((option) {
                              final isSelected =
                                  selectedOption?.id == option.id;
                              return Container(
                                margin: const EdgeInsets.only(bottom: 12),
                                decoration: BoxDecoration(
                                  color: isSelected
                                      ? AppTheme.primary.withAlpha(31)
                                      : AppTheme.surface,
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(
                                    color: isSelected
                                        ? AppTheme.primary
                                        : AppTheme.border,
                                    width: isSelected ? 2 : 1,
                                  ),
                                ),
                                child: InkWell(
                                  onTap: () {
                                    setState(() {
                                      _riskService.selectAnswer(
                                        currentQ.id,
                                        option,
                                      );
                                    });
                                  },
                                  borderRadius: BorderRadius.circular(10),
                                  child: Padding(
                                    padding: const EdgeInsets.all(14),
                                    child: Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.center,
                                      children: [
                                        Radio<String>(
                                          value: option.id,
                                          activeColor: AppTheme.primary,
                                        ),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Text(
                                            option.text,
                                            style: TextStyle(
                                              color: isSelected
                                                  ? AppTheme.textPrimary
                                                  : AppTheme.textSecondary,
                                              fontWeight: isSelected
                                                  ? FontWeight.w600
                                                  : FontWeight.normal,
                                              fontSize: 14,
                                            ),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            }).toList(),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Bottom Navigation Actions
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          icon: const Icon(Icons.arrow_back, size: 18),
                          label: Text(
                            _currentIndex == 0 ? 'Profile' : 'Previous',
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: AppTheme.border),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          onPressed: _riskService.isSubmitting
                              ? null
                              : _previous,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: AppButton(
                          label: isLast ? 'Calculate Risk' : 'Next Question',
                          icon: isLast
                              ? Icons.analytics_outlined
                              : Icons.arrow_forward,
                          loading: _riskService.isSubmitting,
                          enabled: selectedOption != null,
                          onPressed: _nextOrSubmit,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
