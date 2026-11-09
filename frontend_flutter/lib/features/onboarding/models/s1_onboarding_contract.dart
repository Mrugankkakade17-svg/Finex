/// Typed client contract for the Sprint 1 consent and profile journey.
///
/// The values here match the FastAPI `/api/v1/onboarding-contract` contract.
/// They intentionally exclude risk answers, recommendations, account data, and
/// credentials.
library;

const s1ConsentVersion = 'consent.v1';
const s1ProfileSchemaVersion = 'profile.v1';
const s1OnboardingApiPath = '/api/v1/onboarding-contract';

enum S1IntegrationMode { fixture, api }

enum S1ExperienceLevel { beginner, intermediate, advanced }

extension S1ExperienceLevelWireValue on S1ExperienceLevel {
  String get wireValue => name;

  String get label => switch (this) {
    S1ExperienceLevel.beginner => 'Beginner — I am new to investing concepts',
    S1ExperienceLevel.intermediate => 'Intermediate — I know the fundamentals',
    S1ExperienceLevel.advanced =>
      'Advanced — I am comfortable with the terminology',
  };
}

class S1OnboardingConfig {
  final S1IntegrationMode mode;
  final Uri apiBaseUri;

  const S1OnboardingConfig({required this.mode, required this.apiBaseUri});

  factory S1OnboardingConfig.fromEnvironment() {
    const configuredMode = String.fromEnvironment(
      'FINEX_ONBOARDING_MODE',
      defaultValue: 'fixture',
    );
    const configuredApiBaseUrl = String.fromEnvironment(
      'FINEX_API_BASE_URL',
      defaultValue: 'http://127.0.0.1:8000',
    );
    return S1OnboardingConfig(
      mode: configuredMode.toLowerCase() == 'api'
          ? S1IntegrationMode.api
          : S1IntegrationMode.fixture,
      apiBaseUri: Uri.parse(configuredApiBaseUrl),
    );
  }
}

class S1ConsentInput {
  final String correlationId;
  final String consentVersion;
  final bool consentGiven;

  const S1ConsentInput({
    required this.correlationId,
    required this.consentVersion,
    required this.consentGiven,
  });
}

class S1ProfileInput {
  final String correlationId;
  final String profileSchemaVersion;
  final String displayName;
  final S1ExperienceLevel experienceLevel;

  const S1ProfileInput({
    required this.correlationId,
    required this.profileSchemaVersion,
    required this.displayName,
    required this.experienceLevel,
  });
}

class S1CompletionInput {
  final String correlationId;
  final String consentVersion;
  final String profileSchemaVersion;

  const S1CompletionInput({
    required this.correlationId,
    required this.consentVersion,
    required this.profileSchemaVersion,
  });
}

class S1ConsentResult {
  final String consentVersion;
  final String consentStatus;
  final DateTime recordedAt;

  const S1ConsentResult({
    required this.consentVersion,
    required this.consentStatus,
    required this.recordedAt,
  });
}

class S1ProfileResult {
  final String profileSchemaVersion;
  final String profileState;
  final String displayName;
  final S1ExperienceLevel experienceLevel;
  final DateTime recordedAt;

  const S1ProfileResult({
    required this.profileSchemaVersion,
    required this.profileState,
    required this.displayName,
    required this.experienceLevel,
    required this.recordedAt,
  });
}

class S1CompletionResult {
  final bool onboardingCompleted;
  final String consentVersion;
  final String profileSchemaVersion;
  final String? fixtureMode;
  final DateTime recordedAt;

  const S1CompletionResult({
    required this.onboardingCompleted,
    required this.consentVersion,
    required this.profileSchemaVersion,
    required this.fixtureMode,
    required this.recordedAt,
  });
}

class S1OnboardingException implements Exception {
  final String message;
  final String code;

  const S1OnboardingException(
    this.message, {
    this.code = 'ONBOARDING_REQUEST_FAILED',
  });

  @override
  String toString() => message;
}
