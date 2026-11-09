enum OnboardingStep {
  consent,
  profile,
  preferences,
  risk,
  completed,
}

class OnboardingState {
  final OnboardingStep currentStep;
  final bool termsConsent;
  final bool disclaimerConsent;
  final bool automatedProfilingConsent;
  final String? fullName;
  final String? investmentHorizon; // e.g. '< 1 Year', '1-3 Years', '3-5 Years', '5+ Years'
  final String? investmentExperience; // 'Beginner', 'Intermediate', 'Advanced'
  final String? primaryGoal; // 'Capital Preservation', 'Balanced Growth', 'Aggressive Growth'
  final String? preferredCurrency; // 'USD', 'EUR', 'GBP', 'INR'

  const OnboardingState({
    this.currentStep = OnboardingStep.consent,
    this.termsConsent = false,
    this.disclaimerConsent = false,
    this.automatedProfilingConsent = false,
    this.fullName,
    this.investmentHorizon,
    this.investmentExperience,
    this.primaryGoal,
    this.preferredCurrency = 'USD',
  });

  bool get hasAllConsents => termsConsent && disclaimerConsent && automatedProfilingConsent;

  factory OnboardingState.fromJson(Map<String, dynamic> json) {
    return OnboardingState(
      currentStep: OnboardingStep.values.firstWhere(
        (e) => e.name == json['currentStep'],
        orElse: () => OnboardingStep.consent,
      ),
      termsConsent: json['termsConsent'] == true,
      disclaimerConsent: json['disclaimerConsent'] == true,
      automatedProfilingConsent: json['automatedProfilingConsent'] == true,
      fullName: json['fullName'] as String?,
      investmentHorizon: json['investmentHorizon'] as String?,
      investmentExperience: json['investmentExperience'] as String?,
      primaryGoal: json['primaryGoal'] as String?,
      preferredCurrency: json['preferredCurrency'] as String? ?? 'USD',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'currentStep': currentStep.name,
      'termsConsent': termsConsent,
      'disclaimerConsent': disclaimerConsent,
      'automatedProfilingConsent': automatedProfilingConsent,
      'fullName': fullName,
      'investmentHorizon': investmentHorizon,
      'investmentExperience': investmentExperience,
      'primaryGoal': primaryGoal,
      'preferredCurrency': preferredCurrency,
    };
  }

  OnboardingState copyWith({
    OnboardingStep? currentStep,
    bool? termsConsent,
    bool? disclaimerConsent,
    bool? automatedProfilingConsent,
    String? fullName,
    String? investmentHorizon,
    String? investmentExperience,
    String? primaryGoal,
    String? preferredCurrency,
  }) {
    return OnboardingState(
      currentStep: currentStep ?? this.currentStep,
      termsConsent: termsConsent ?? this.termsConsent,
      disclaimerConsent: disclaimerConsent ?? this.disclaimerConsent,
      automatedProfilingConsent: automatedProfilingConsent ?? this.automatedProfilingConsent,
      fullName: fullName ?? this.fullName,
      investmentHorizon: investmentHorizon ?? this.investmentHorizon,
      investmentExperience: investmentExperience ?? this.investmentExperience,
      primaryGoal: primaryGoal ?? this.primaryGoal,
      preferredCurrency: preferredCurrency ?? this.preferredCurrency,
    );
  }
}
