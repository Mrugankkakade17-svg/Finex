import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../services/onboarding_service.dart';

class ConsentPage extends StatefulWidget {
  const ConsentPage({super.key});

  @override
  State<ConsentPage> createState() => _ConsentPageState();
}

class _ConsentPageState extends State<ConsentPage> {
  final _onboardingService = OnboardingService();

  @override
  Widget build(BuildContext context) {
    final state = _onboardingService.state;
    final allChecked = state.hasAllConsents;

    return Scaffold(
      appBar: AppBar(
        title: const Text('User Consent & Terms'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.go('/login'),
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
                  // Progress Step Indicator
                  Row(
                    children: [
                      _buildStepBadge('1', 'Consent', isActive: true),
                      const Expanded(child: Divider(color: AppTheme.border, thickness: 2)),
                      _buildStepBadge('2', 'Profile', isActive: false),
                      const Expanded(child: Divider(color: AppTheme.border, thickness: 2)),
                      _buildStepBadge('3', 'Risk Assessment', isActive: false),
                    ],
                  ),
                  const SizedBox(height: 28),

                  // Header
                  Text(
                    'Terms & Regulatory Acknowledgement',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Please review and accept the required disclosures to proceed with FinEx.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                  ),
                  const SizedBox(height: 24),

                  // Disclosures Card
                  AppCard(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      children: [
                        _buildConsentCheckbox(
                          title: 'Terms of Service & Privacy Policy',
                          description:
                              'I accept FinEx educational platform terms of service and agree to standard privacy and data handling practices.',
                          value: state.termsConsent,
                          onChanged: (val) {
                            setState(() {
                              _onboardingService.updateConsent(terms: val);
                            });
                          },
                        ),
                        const Divider(color: AppTheme.border, height: 28),
                        _buildConsentCheckbox(
                          title: 'Educational Prototype Disclaimer',
                          description:
                              'I acknowledge that FinEx is an educational research tool, does not provide regulated financial advice, and involves zero real-money trading.',
                          value: state.disclaimerConsent,
                          onChanged: (val) {
                            setState(() {
                              _onboardingService.updateConsent(disclaimer: val);
                            });
                          },
                        ),
                        const Divider(color: AppTheme.border, height: 28),
                        _buildConsentCheckbox(
                          title: 'Explainable Risk Profiling Consent',
                          description:
                              'I agree to complete the investor risk questionnaire and receive deterministic portfolio risk categorization and educational insights.',
                          value: state.automatedProfilingConsent,
                          onChanged: (val) {
                            setState(() {
                              _onboardingService.updateConsent(profiling: val);
                            });
                          },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // Submit Button
                  AppButton(
                    label: 'Accept & Continue',
                    enabled: allChecked && !_onboardingService.isLoading,
                    loading: _onboardingService.isLoading,
                    icon: Icons.check_circle_outline,
                    onPressed: () async {
                      final ok = await _onboardingService.submitConsent();
                      if (ok && context.mounted) {
                        context.go('/onboarding/profile');
                      }
                    },
                  ),
                  const SizedBox(height: 16),

                  if (!allChecked)
                    Text(
                      'All three acknowledgements are required to proceed.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.amber.shade300,
                            fontStyle: FontStyle.italic,
                          ),
                      textAlign: TextAlign.center,
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStepBadge(String number, String label, {required bool isActive}) {
    return Column(
      children: [
        CircleAvatar(
          radius: 14,
          backgroundColor: isActive ? AppTheme.primary : AppTheme.border,
          child: Text(
            number,
            style: TextStyle(
              color: isActive ? Colors.white : AppTheme.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            color: isActive ? AppTheme.textPrimary : AppTheme.textSecondary,
            fontSize: 11,
          ),
        ),
      ],
    );
  }

  Widget _buildConsentCheckbox({
    required String title,
    required String description,
    required bool value,
    required ValueChanged<bool?> onChanged,
  }) {
    return InkWell(
      onTap: () => onChanged(!value),
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Checkbox(
              value: value,
              onChanged: onChanged,
              activeColor: AppTheme.primary,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: const TextStyle(
                      color: AppTheme.textPrimary,
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: const TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 12,
                      height: 1.35,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
