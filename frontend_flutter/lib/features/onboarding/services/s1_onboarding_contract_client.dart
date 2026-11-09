import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/s1_onboarding_contract.dart';

abstract interface class S1OnboardingContractClient {
  Future<S1ConsentResult> captureConsent(S1ConsentInput input);

  Future<S1ProfileResult> submitProfile(S1ProfileInput input);

  Future<S1CompletionResult> completeOnboarding(S1CompletionInput input);
}

S1OnboardingContractClient createS1OnboardingClient(S1OnboardingConfig config) {
  return switch (config.mode) {
    S1IntegrationMode.fixture => FixtureS1OnboardingContractClient(),
    S1IntegrationMode.api => HttpS1OnboardingContractClient(config.apiBaseUri),
  };
}

class _FixtureJourney {
  bool consentAccepted = false;
  bool profileSubmitted = false;
}

/// Deterministic local adapter for native development and widget tests.
class FixtureS1OnboardingContractClient implements S1OnboardingContractClient {
  final Map<String, _FixtureJourney> _journeys = {};

  _FixtureJourney _journeyFor(String correlationId) {
    return _journeys.putIfAbsent(correlationId, _FixtureJourney.new);
  }

  /// Rehydrate only flow flags persisted on the local device; no profile data is stored.
  void restoreProgress({
    required String correlationId,
    required bool consentRecorded,
    required bool profileSubmitted,
  }) {
    final journey = _journeyFor(correlationId);
    journey.consentAccepted = consentRecorded;
    journey.profileSubmitted = profileSubmitted;
  }

  @override
  Future<S1ConsentResult> captureConsent(S1ConsentInput input) async {
    _validateConsent(input);
    _journeyFor(input.correlationId).consentAccepted = true;
    return S1ConsentResult(
      consentVersion: input.consentVersion,
      consentStatus: 'accepted',
      recordedAt: DateTime.now().toUtc(),
    );
  }

  @override
  Future<S1ProfileResult> submitProfile(S1ProfileInput input) async {
    _validateProfile(input);
    final journey = _journeyFor(input.correlationId);
    if (!journey.consentAccepted) {
      throw const S1OnboardingException(
        'Educational consent is required before a profile can be submitted.',
        code: 'CONSENT_MISSING',
      );
    }
    journey.profileSubmitted = true;
    return S1ProfileResult(
      profileSchemaVersion: input.profileSchemaVersion,
      profileState: 'completed',
      displayName: input.displayName.trim(),
      experienceLevel: input.experienceLevel,
      recordedAt: DateTime.now().toUtc(),
    );
  }

  @override
  Future<S1CompletionResult> completeOnboarding(S1CompletionInput input) async {
    if (input.consentVersion != s1ConsentVersion) {
      throw const S1OnboardingException(
        'The consent version is not supported.',
        code: 'UNSUPPORTED_CONSENT_VERSION',
      );
    }
    if (input.profileSchemaVersion != s1ProfileSchemaVersion) {
      throw const S1OnboardingException(
        'The profile version is not supported.',
        code: 'UNSUPPORTED_PROFILE_VERSION',
      );
    }
    final journey = _journeyFor(input.correlationId);
    if (!journey.consentAccepted) {
      throw const S1OnboardingException(
        'Educational consent is required before completion.',
        code: 'CONSENT_MISSING',
      );
    }
    if (!journey.profileSubmitted) {
      throw const S1OnboardingException(
        'Submit a profile before completing onboarding.',
        code: 'PROFILE_MISSING',
      );
    }
    return S1CompletionResult(
      onboardingCompleted: true,
      consentVersion: input.consentVersion,
      profileSchemaVersion: input.profileSchemaVersion,
      fixtureMode: 's1_dat_01',
      recordedAt: DateTime.now().toUtc(),
    );
  }
}

class HttpS1OnboardingContractClient implements S1OnboardingContractClient {
  final Uri _baseUri;
  final http.Client _client;

  HttpS1OnboardingContractClient(Uri baseUri, {http.Client? client})
    : _baseUri = baseUri,
      _client = client ?? http.Client();

  Uri _uri(String path) => _baseUri.replace(
    path: '${_baseUri.path}$s1OnboardingApiPath$path'.replaceAll('//', '/'),
  );

  Future<Map<String, dynamic>> _post({
    required String path,
    required String correlationId,
    required Map<String, Object> body,
  }) async {
    http.Response response;
    try {
      response = await _client.post(
        _uri(path),
        headers: {
          'accept': 'application/json',
          'content-type': 'application/json',
          'x-correlation-id': correlationId,
        },
        body: jsonEncode(body),
      );
    } on Exception {
      throw const S1OnboardingException(
        'The local FinEx API is unavailable. Start the backend, then retry.',
        code: 'API_UNAVAILABLE',
      );
    }

    dynamic decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      throw const S1OnboardingException(
        'The FinEx API returned an invalid response.',
        code: 'INVALID_API_RESPONSE',
      );
    }
    if (decoded is! Map<String, dynamic>) {
      throw const S1OnboardingException(
        'The FinEx API returned an invalid response.',
        code: 'INVALID_API_RESPONSE',
      );
    }
    final data = decoded['data'];
    if (response.statusCode < 200 ||
        response.statusCode >= 300 ||
        decoded['success'] != true ||
        data is! Map<String, dynamic>) {
      final message = decoded['message'];
      final errorCode = decoded['error_code'];
      throw S1OnboardingException(
        message is String && message.trim().isNotEmpty
            ? message
            : 'The onboarding request could not be completed.',
        code: errorCode is String && errorCode.isNotEmpty
            ? errorCode
            : 'ONBOARDING_REQUEST_FAILED',
      );
    }
    return data;
  }

  Never _invalidApiResponse() {
    throw const S1OnboardingException(
      'The FinEx API returned an invalid response.',
      code: 'INVALID_API_RESPONSE',
    );
  }

  String _requiredString(Map<String, dynamic> data, String field) {
    final value = data[field];
    if (value is! String || value.trim().isEmpty) {
      _invalidApiResponse();
    }
    return value;
  }

  bool _requiredTrue(Map<String, dynamic> data, String field) {
    if (data[field] != true) {
      _invalidApiResponse();
    }
    return true;
  }

  String? _nullableString(Map<String, dynamic> data, String field) {
    final value = data[field];
    if (value != null && value is! String) {
      _invalidApiResponse();
    }
    return value as String?;
  }

  DateTime _requiredTimestamp(Map<String, dynamic> data, String field) {
    try {
      return DateTime.parse(_requiredString(data, field)).toUtc();
    } on FormatException {
      _invalidApiResponse();
    }
  }

  S1ExperienceLevel _experienceLevel(Map<String, dynamic> data) {
    return switch (_requiredString(data, 'experience_level')) {
      'beginner' => S1ExperienceLevel.beginner,
      'intermediate' => S1ExperienceLevel.intermediate,
      'advanced' => S1ExperienceLevel.advanced,
      _ => _invalidApiResponse(),
    };
  }

  @override
  Future<S1ConsentResult> captureConsent(S1ConsentInput input) async {
    final data = await _post(
      path: '/consent',
      correlationId: input.correlationId,
      body: {
        'consent_version': input.consentVersion,
        'consent_given': input.consentGiven,
      },
    );
    final consentVersion = _requiredString(data, 'consent_version');
    final consentStatus = _requiredString(data, 'consent_status');
    if (consentVersion != input.consentVersion || consentStatus != 'accepted') {
      _invalidApiResponse();
    }
    return S1ConsentResult(
      consentVersion: consentVersion,
      consentStatus: consentStatus,
      recordedAt: _requiredTimestamp(data, 'recorded_at'),
    );
  }

  @override
  Future<S1ProfileResult> submitProfile(S1ProfileInput input) async {
    final data = await _post(
      path: '/profile',
      correlationId: input.correlationId,
      body: {
        'profile_schema_version': input.profileSchemaVersion,
        'display_name': input.displayName,
        'experience_level': input.experienceLevel.wireValue,
      },
    );
    final profileSchemaVersion = _requiredString(
      data,
      'profile_schema_version',
    );
    final profileState = _requiredString(data, 'profile_state');
    if (profileSchemaVersion != input.profileSchemaVersion ||
        profileState != 'completed') {
      _invalidApiResponse();
    }
    return S1ProfileResult(
      profileSchemaVersion: profileSchemaVersion,
      profileState: profileState,
      displayName: _requiredString(data, 'display_name'),
      experienceLevel: _experienceLevel(data),
      recordedAt: _requiredTimestamp(data, 'recorded_at'),
    );
  }

  @override
  Future<S1CompletionResult> completeOnboarding(S1CompletionInput input) async {
    final data = await _post(
      path: '/complete',
      correlationId: input.correlationId,
      body: {
        'consent_version': input.consentVersion,
        'profile_schema_version': input.profileSchemaVersion,
      },
    );
    final consentVersion = _requiredString(data, 'consent_version');
    final profileSchemaVersion = _requiredString(
      data,
      'profile_schema_version',
    );
    if (consentVersion != input.consentVersion ||
        profileSchemaVersion != input.profileSchemaVersion) {
      _invalidApiResponse();
    }
    return S1CompletionResult(
      onboardingCompleted: _requiredTrue(data, 'onboarding_completed'),
      consentVersion: consentVersion,
      profileSchemaVersion: profileSchemaVersion,
      fixtureMode: _nullableString(data, 'fixture_mode'),
      recordedAt: _requiredTimestamp(data, 'recorded_at'),
    );
  }
}

void _validateConsent(S1ConsentInput input) {
  if (input.consentVersion != s1ConsentVersion) {
    throw const S1OnboardingException(
      'The consent version is not supported.',
      code: 'UNSUPPORTED_CONSENT_VERSION',
    );
  }
  if (!input.consentGiven) {
    throw const S1OnboardingException(
      'Consent must be accepted to continue.',
      code: 'CONSENT_NOT_GIVEN',
    );
  }
}

void _validateProfile(S1ProfileInput input) {
  if (input.profileSchemaVersion != s1ProfileSchemaVersion) {
    throw const S1OnboardingException(
      'The profile version is not supported.',
      code: 'UNSUPPORTED_PROFILE_VERSION',
    );
  }
  if (input.displayName.trim().isEmpty) {
    throw const S1OnboardingException(
      'Enter a display label before continuing.',
      code: 'DISPLAY_NAME_REQUIRED',
    );
  }
}
