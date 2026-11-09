import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../models/s1_onboarding_contract.dart';
import '../services/s1_onboarding_contract_client.dart';
import '../services/s1_onboarding_journey_store.dart';

class S1OnboardingPage extends StatefulWidget {
  final S1OnboardingConfig? config;
  final S1OnboardingContractClient? client;
  final S1OnboardingJourneyStore? journeyStore;
  final String riskPath;

  const S1OnboardingPage({
    super.key,
    this.config,
    this.client,
    this.journeyStore,
    this.riskPath = '/risk',
  });

  @override
  State<S1OnboardingPage> createState() => _S1OnboardingPageState();
}

class _S1OnboardingPageState extends State<S1OnboardingPage> {
  late final S1OnboardingConfig _config;
  late final S1OnboardingContractClient _client;
  late final S1OnboardingJourneyStore _journeyStore;
  late final TextEditingController _displayNameController;

  S1OnboardingJourney? _journey;
  S1ExperienceLevel? _experienceLevel;
  bool _loadingJourney = true;
  bool _submitting = false;
  bool _consentChoice = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _config = widget.config ?? S1OnboardingConfig.fromEnvironment();
    _client = widget.client ?? createS1OnboardingClient(_config);
    _journeyStore =
        widget.journeyStore ??
        const SharedPreferencesS1OnboardingJourneyStore();
    _displayNameController = TextEditingController();
    _loadJourney();
  }

  @override
  void dispose() {
    _displayNameController.dispose();
    super.dispose();
  }

  Future<void> _loadJourney() async {
    final savedJourney = await _journeyStore.load();
    final journey =
        savedJourney != null && savedJourney.integrationMode == _config.mode
        ? savedJourney
        : createS1Journey(_config.mode);
    if (_client case final FixtureS1OnboardingContractClient fixtureClient) {
      fixtureClient.restoreProgress(
        correlationId: journey.correlationId,
        consentRecorded: journey.consentRecorded,
        profileSubmitted: journey.profileSubmitted,
      );
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _journey = journey;
      _loadingJourney = false;
    });
  }

  Future<void> _submitConsent() async {
    final journey = _journey;
    if (journey == null || !_consentChoice) {
      setState(
        () => _errorMessage = 'Select the consent checkbox before continuing.',
      );
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await _client.captureConsent(
        S1ConsentInput(
          correlationId: journey.correlationId,
          consentVersion: s1ConsentVersion,
          consentGiven: true,
        ),
      );
      final updatedJourney = journey.copyWith(consentRecorded: true);
      await _journeyStore.save(updatedJourney);
      if (!mounted) {
        return;
      }
      setState(() => _journey = updatedJourney);
    } on S1OnboardingException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Exception {
      if (mounted) {
        setState(
          () => _errorMessage = 'Consent could not be recorded. Please retry.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _submitProfile() async {
    final journey = _journey;
    final displayName = _displayNameController.text.trim();
    if (journey == null || displayName.isEmpty || _experienceLevel == null) {
      setState(() {
        _errorMessage = 'Enter a display label and select an experience level before continuing.';
      });
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await _client.submitProfile(
        S1ProfileInput(
          correlationId: journey.correlationId,
          profileSchemaVersion: s1ProfileSchemaVersion,
          displayName: displayName,
          experienceLevel: _experienceLevel!,
        ),
      );
      final profileJourney = journey.copyWith(profileSubmitted: true);
      await _journeyStore.save(profileJourney);
      final completion = await _client.completeOnboarding(
        S1CompletionInput(
          correlationId: profileJourney.correlationId,
          consentVersion: s1ConsentVersion,
          profileSchemaVersion: s1ProfileSchemaVersion,
        ),
      );
      final completedJourney = profileJourney.copyWith(
        completed: completion.onboardingCompleted,
        completedAt: completion.recordedAt,
      );
      await _journeyStore.save(completedJourney);
      if (!mounted) {
        return;
      }
      setState(() => _journey = completedJourney);
    } on S1OnboardingException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Exception {
      if (mounted) {
        setState(
          () => _errorMessage =
              'The profile could not be submitted. Please retry.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _startAgain() async {
    await _journeyStore.clear();
    final journey = createS1Journey(_config.mode);
    if (!mounted) {
      return;
    }
    setState(() {
      _journey = journey;
      _consentChoice = false;
      _displayNameController.clear();
      _experienceLevel = null;
      _errorMessage = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loadingJourney) {
      return Center(
        child: Semantics(
          label: 'Loading onboarding journey',
          child: CircularProgressIndicator(),
        ),
      );
    }

    final journey = _journey!;
    return SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: AppCard(
              padding: const EdgeInsets.all(24),
              child: journey.completed
                  ? _buildCompleted(journey)
                  : journey.consentRecorded
                  ? _buildProfile(journey)
                  : _buildConsent(),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildConsent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _StepIndicator(step: 1),
        const SizedBox(height: 24),
        Text(
          'Educational consent',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: AppTheme.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'FinEx is an educational pilot. This journey collects only a display label '
          'and a self-declared experience level; it does not collect account data or '
          'provide investment advice.',
          style: TextStyle(color: AppTheme.textSecondary, height: 1.45),
        ),
        const SizedBox(height: 16),
        _modeBanner(),
        const SizedBox(height: 16),
        const Text(
          'Consent version: $s1ConsentVersion',
          style: TextStyle(
            color: AppTheme.textPrimary,
            fontWeight: FontWeight.w600,
          ),
        ),
        CheckboxListTile(
          key: const Key('s1-consent-checkbox'),
          contentPadding: EdgeInsets.zero,
          value: _consentChoice,
          activeColor: AppTheme.primary,
          title: const Text(
            'I agree to continue with the educational onboarding pilot.',
          ),
          subtitle: const Text(
            'The completed state is stored locally on this device.',
            style: TextStyle(color: AppTheme.textSecondary),
          ),
          onChanged: _submitting
              ? null
              : (value) {
                  setState(() {
                    _consentChoice = value ?? false;
                    _errorMessage = null;
                  });
                },
        ),
        _errorBanner(),
        const SizedBox(height: 16),
        AppButton(
          key: const Key('s1-consent-submit'),
          label: _submitting
              ? 'Recording consent…'
              : _errorMessage != null
              ? 'Retry consent'
              : 'Accept & continue',
          icon: Icons.check_circle_outline,
          loading: _submitting,
          enabled: _consentChoice,
          onPressed: _submitConsent,
        ),
      ],
    );
  }

  Widget _buildProfile(S1OnboardingJourney journey) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _StepIndicator(step: 2),
        const SizedBox(height: 24),
        Text(
          'A small, useful profile',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: AppTheme.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Use a non-sensitive display label and your experience level. This is not a '
          'risk questionnaire and does not generate a recommendation.',
          style: TextStyle(color: AppTheme.textSecondary, height: 1.45),
        ),
        const SizedBox(height: 16),
        _modeBanner(),
        const SizedBox(height: 18),
        TextField(
          key: const Key('s1-display-name'),
          controller: _displayNameController,
          enabled: !_submitting,
          maxLength: 80,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(
            labelText: 'Display label',
            helperText: 'Use a non-sensitive label, not a legal name.',
          ),
          onChanged: (_) => setState(() => _errorMessage = null),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<S1ExperienceLevel>(
          key: const Key('s1-experience-level'),
          initialValue: _experienceLevel,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Experience level'),
          hint: const Text('Choose one'),
          items: S1ExperienceLevel.values
              .map(
                (level) =>
                    DropdownMenuItem(value: level, child: Text(level.label)),
              )
              .toList(),
          onChanged: _submitting
              ? null
              : (value) {
                  setState(() {
                    _experienceLevel = value;
                    _errorMessage = null;
                  });
                },
        ),
        _errorBanner(),
        const SizedBox(height: 24),
        AppButton(
          key: const Key('s1-profile-submit'),
          label: _submitting
              ? 'Saving profile…'
              : _errorMessage != null
              ? 'Retry submission'
              : 'Complete onboarding',
          icon: Icons.check_circle_outline,
          loading: _submitting,
          enabled:
              _displayNameController.text.trim().isNotEmpty &&
              _experienceLevel != null,
          onPressed: _submitProfile,
        ),
      ],
    );
  }

  Widget _buildCompleted(S1OnboardingJourney journey) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.check_circle, color: AppTheme.primary, size: 56),
        const SizedBox(height: 16),
        Text(
          'Onboarding complete',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: AppTheme.textPrimary,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'This local device remembers completion of the Sprint 1 journey. No '
          'financial-account data or credentials were saved by this flow.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppTheme.textSecondary, height: 1.45),
        ),
        if (journey.completedAt != null) ...[
          const SizedBox(height: 16),
          Text(
            'Completed locally: ${journey.completedAt!.toLocal()}',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppTheme.textSecondary),
          ),
        ],
        const SizedBox(height: 24),
        AppButton(
          label: 'Continue to educational risk profile',
          icon: Icons.shield_outlined,
          onPressed: () => context.go(widget.riskPath),
        ),
        const SizedBox(height: 12),
        AppButton(
          label: 'Start another local journey',
          icon: Icons.refresh,
          onPressed: _startAgain,
        ),
      ],
    );
  }

  Widget _modeBanner() {
    final text = _config.mode == S1IntegrationMode.fixture
        ? 'Fixture mode — local synthetic contract adapter'
        : 'API mode — versioned local FinEx API';
    return Semantics(
      label: text,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppTheme.secondary.withAlpha(38),
          border: Border.all(color: AppTheme.secondary.withAlpha(128)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Text(
            text,
            style: const TextStyle(color: AppTheme.textPrimary),
          ),
        ),
      ),
    );
  }

  Widget _errorBanner() {
    final message = _errorMessage;
    if (message == null) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Semantics(
        key: const Key('s1-onboarding-error'),
        liveRegion: true,
        excludeSemantics: true,
        label: 'Onboarding error: $message',
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: Colors.red.withAlpha(31),
            border: Border.all(color: Colors.redAccent.withAlpha(153)),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              message,
              style: const TextStyle(color: Colors.redAccent),
            ),
          ),
        ),
      ),
    );
  }
}

class _StepIndicator extends StatelessWidget {
  final int step;

  const _StepIndicator({required this.step});

  @override
  Widget build(BuildContext context) {
    const labels = ['Consent', 'Profile', 'Complete'];
    return Semantics(
      label: 'Onboarding step $step of 3',
      child: Row(
        children: List.generate(labels.length, (index) {
          final complete = index + 1 < step;
          final active = index + 1 == step;
          final color = complete || active ? AppTheme.primary : AppTheme.border;
          return Expanded(
            child: Column(
              children: [
                Container(height: 5, color: color),
                const SizedBox(height: 6),
                Text(
                  labels[index],
                  style: TextStyle(
                    color: active || complete
                        ? AppTheme.textPrimary
                        : AppTheme.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }
}
