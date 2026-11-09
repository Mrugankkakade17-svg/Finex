import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../models/onboarding_state.dart';
import '../services/onboarding_service.dart';

class OnboardingFlowPage extends StatefulWidget {
  const OnboardingFlowPage({super.key});

  @override
  State<OnboardingFlowPage> createState() => _OnboardingFlowPageState();
}

class _OnboardingFlowPageState extends State<OnboardingFlowPage> {
  final _onboardingService = OnboardingService();
  late final TextEditingController _nameController;

  String? _selectedHorizon;
  String? _selectedExperience;
  String? _selectedGoal;
  String _selectedCurrency = 'USD';
  String? _nameError;

  final List<String> _horizons = [
    '< 1 Year',
    '1-3 Years',
    '3-5 Years',
    '5+ Years',
  ];
  final List<String> _experiences = ['Beginner', 'Intermediate', 'Advanced'];
  final List<String> _goals = [
    'Capital Preservation',
    'Balanced Growth',
    'Aggressive Wealth Creation',
  ];
  final List<String> _currencies = ['USD', 'EUR', 'GBP', 'INR'];

  @override
  void initState() {
    super.initState();
    final state = _onboardingService.state;
    _nameController = TextEditingController(text: state.fullName ?? '');
    _selectedHorizon = state.investmentHorizon ?? _horizons[1];
    _selectedExperience = state.investmentExperience ?? _experiences[0];
    _selectedGoal = state.primaryGoal ?? _goals[1];
    _selectedCurrency = state.preferredCurrency ?? 'USD';
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  void _submitProfileAndProceed() {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      setState(() {
        _nameError = 'Please enter your full name.';
      });
      return;
    }

    _onboardingService.updateProfile(
      fullName: name,
      preferredCurrency: _selectedCurrency,
    );

    _onboardingService.updatePreferences(
      horizon: _selectedHorizon,
      experience: _selectedExperience,
      primaryGoal: _selectedGoal,
    );

    _onboardingService.advanceStep(OnboardingStep.risk);
    context.go('/risk/questionnaire');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Investor Profile Setup'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/onboarding/consent'),
        ),
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
                  // Step Indicator
                  Row(
                    children: [
                      _buildStepBadge('1', 'Consent', isDone: true),
                      const Expanded(
                        child: Divider(color: AppTheme.primary, thickness: 2),
                      ),
                      _buildStepBadge('2', 'Profile', isActive: true),
                      const Expanded(
                        child: Divider(color: AppTheme.border, thickness: 2),
                      ),
                      _buildStepBadge('3', 'Risk Assessment', isActive: false),
                    ],
                  ),
                  const SizedBox(height: 28),

                  Text(
                    'Customize Your Portfolio Preferences',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: AppTheme.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'These parameters customize your risk boundary and portfolio analytics.',
                    style: Theme.of(context).textTheme.bodyMedium
                        ?.copyWith(color: AppTheme.textSecondary),
                  ),
                  const SizedBox(height: 24),

                  // Form Card
                  AppCard(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        AppTextField(
                          label: 'Full Name',
                          hint: 'Alex Morgan',
                          controller: _nameController,
                          errorText: _nameError,
                          onChanged: (_) {
                            if (_nameError != null) {
                              setState(() => _nameError = null);
                            }
                          },
                        ),
                        const SizedBox(height: 20),

                        // Currency Selector
                        const Text(
                          'Base Currency',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          children: _currencies.map((curr) {
                            final isSel = _selectedCurrency == curr;
                            return ChoiceChip(
                              label: Text(curr),
                              selected: isSel,
                              selectedColor: AppTheme.primary.withAlpha(64),
                              side: BorderSide(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.border,
                              ),
                              labelStyle: TextStyle(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.textSecondary,
                                fontWeight: isSel
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                              ),
                              onSelected: (_) =>
                                  setState(() => _selectedCurrency = curr),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 20),

                        // Investment Horizon
                        const Text(
                          'Investment Horizon',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _horizons.map((h) {
                            final isSel = _selectedHorizon == h;
                            return ChoiceChip(
                              label: Text(h),
                              selected: isSel,
                              selectedColor: AppTheme.primary.withAlpha(64),
                              side: BorderSide(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.border,
                              ),
                              labelStyle: TextStyle(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.textSecondary,
                                fontWeight: isSel
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                              ),
                              onSelected: (_) =>
                                  setState(() => _selectedHorizon = h),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 20),

                        // Experience Level
                        const Text(
                          'Investing Experience',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          children: _experiences.map((exp) {
                            final isSel = _selectedExperience == exp;
                            return ChoiceChip(
                              label: Text(exp),
                              selected: isSel,
                              selectedColor: AppTheme.primary.withAlpha(64),
                              side: BorderSide(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.border,
                              ),
                              labelStyle: TextStyle(
                                color: isSel
                                    ? AppTheme.primary
                                    : AppTheme.textSecondary,
                                fontWeight: isSel
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                              ),
                              onSelected: (_) =>
                                  setState(() => _selectedExperience = exp),
                            );
                          }).toList(),
                        ),
                        const SizedBox(height: 20),

                        // Primary Goal
                        const Text(
                          'Primary Goal',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 8),
                        RadioGroup<String>(
                          groupValue: _selectedGoal,
                          onChanged: (goal) {
                            if (goal != null) {
                              setState(() => _selectedGoal = goal);
                            }
                          },
                          child: Column(
                            children: _goals.map((g) {
                              final isSel = _selectedGoal == g;
                              return InkWell(
                                onTap: () => setState(() => _selectedGoal = g),
                                borderRadius: BorderRadius.circular(8),
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 6,
                                  ),
                                  child: Row(
                                    children: [
                                      Radio<String>(
                                        value: g,
                                        activeColor: AppTheme.primary,
                                      ),
                                      const SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          g,
                                          style: TextStyle(
                                            fontSize: 14,
                                            color: isSel
                                                ? AppTheme.textPrimary
                                                : AppTheme.textSecondary,
                                            fontWeight: isSel
                                                ? FontWeight.w600
                                                : FontWeight.normal,
                                          ),
                                        ),
                                      ),
                                    ],
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

                  // Proceed Button
                  AppButton(
                    label: 'Proceed to Risk Questionnaire',
                    icon: Icons.arrow_forward,
                    onPressed: _submitProfileAndProceed,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStepBadge(
    String number,
    String label, {
    bool isActive = false,
    bool isDone = false,
  }) {
    final bgColor = isDone
        ? AppTheme.primary
        : (isActive ? AppTheme.secondary : AppTheme.border);
    return Column(
      children: [
        CircleAvatar(
          radius: 14,
          backgroundColor: bgColor,
          child: isDone
              ? const Icon(Icons.check, size: 14, color: Colors.white)
              : Text(
                  number,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: isActive || isDone
                ? AppTheme.textPrimary
                : AppTheme.textSecondary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}
