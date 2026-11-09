/// Strict DTOs for the owned local application, never the compatibility pilot.
library;

const localApplicationScope = 'local_educational_application';
const localContractVersion = 'local.v1';
const localProfileVersion = 'profile.v1';
const localConsentVersion = 'consent.v1';
const localAliases = ['learner-a', 'learner-b'];

class LocalApiException implements Exception {
  final String code;
  final int? status;
  final Set<String> fields;

  const LocalApiException(this.code, {this.status, this.fields = const {}});

  String get message => switch (code) {
    'SESSION_INVALID' =>
      'Your local session ended. Sign in again to resume saved data.',
    'SESSION_CHANGED' =>
      'The session changed. The previous response was ignored.',
    'LOCAL_APPLICATION_ONLY' => 'The local application is disabled. Run the backend on loopback with APP_ENV=local and LOCAL_APP_ENABLED=true.',
    'API_UNAVAILABLE' =>
      'The local API is unavailable. Check the backend, then retry.',
    'REQUEST_TIMEOUT' =>
      'The local API did not respond in time. Nothing was confirmed; retry.',
    'LOCAL_STORE_UNAVAILABLE' =>
      'Local storage is unavailable. Nothing was confirmed saved; retry.',
    'INVALID_API_RESPONSE' => 'The API response does not match local.v1. Do not assume the action succeeded.',
    'INVALID_API_ORIGIN' => 'The local API address must be an HTTP(S) loopback origin with no credentials or extra path.',
    'UNKNOWN_LOCAL_ALIAS' =>
      'Choose learner-a or learner-b, the approved synthetic personas.',
    'CONSENT_VERSION_MISMATCH' =>
      'The consent notice version changed. Reload before accepting it.',
    'PROFILE_VERSION_MISMATCH' =>
      'The profile version changed. Reload before saving.',
    'CONSENT_REQUIRED' =>
      'Accept the current educational consent notice before completion.',
    'PROFILE_INCOMPLETE' =>
      'Save a display label and experience level before completion.',
    'ONBOARDING_REQUIRED' =>
      'Reconfirm current consent and complete onboarding before continuing.',
    'VALIDATION_ERROR' => 'Check the display label, experience and supported versions. Nothing was confirmed saved.',
    'SIGN_OUT_FIRST' =>
      'Sign out of the current learner before switching personas.',
    'FEATURE_UNAVAILABLE' => 'The owned S2 API capability is unavailable. Configure the reviewed local backend; there is no demonstration fallback.',
    'S3_FEATURE_UNAVAILABLE' => 'The owned S3 API capability is unavailable. Configure the reviewed local backend; there is no demonstration fallback.',
    'WATCHLIST_NOT_FOUND' =>
      'This watchlist is not available to this learner. Reload the owned list.',
    'WATCHLIST_LIMIT' => 'This learner has reached the ten-watchlist limit.',
    'WATCHLIST_ITEM_LIMIT' =>
      'This watchlist has reached the one-hundred-instrument limit.',
    'INSTRUMENT_NOT_FOUND' =>
      'That instrument is not supported by the current synthetic catalogue.',
    'LOCAL_CATALOG_UNAVAILABLE' => 'The supported synthetic catalogue is unavailable. Saved data was not replaced; retry.',
    'LOCAL_QUOTE_UNAVAILABLE' =>
      'The synthetic quote could not be read. No price was assumed; retry.',
    'PAPER_ACCOUNT_NOT_OPEN' => 'Explicitly open the simulated account before reading its opening ledger.',
    'MARKET_FOUNDATION_VERSION_MISMATCH' =>
      'The simulated opening contract changed. Reload before opening.',
    'RISK_INCOMPLETE' => 'Answer all ten questions before saving an assessment. Partial answers can still be saved as a draft.',
    'CREATE_RECONCILE_REQUIRED' => 'A previous create was not confirmed. Reload and review the saved list before deliberately creating another item.',
    'INSTRUMENT_REQUIRED' => 'Choose a supported synthetic instrument.',
    'HOLDING_ALREADY_EXISTS' => 'This instrument already has a saved holding. Reload holdings and edit that item.',
    'PORTFOLIO_LIMIT_REACHED' =>
      'This learner has reached the twenty-portfolio limit.',
    'HOLDING_LIMIT_REACHED' =>
      'This portfolio has reached the one-hundred-holding limit.',
    'LOCAL_PORTFOLIO_NOT_FOUND' =>
      'This portfolio is not available to this learner. Reload the saved list.',
    'LOCAL_HOLDING_NOT_FOUND' =>
      'This holding is not available to this learner. Reload saved holdings.',
    'RISK_ASSESSMENT_NOT_FOUND' =>
      'This assessment is not available to this learner. Reload saved history.',
    'IDEMPOTENCY_CONFLICT' => 'That retry key belongs to different answers. Reload history before a new deliberate submission.',
    _ => 'The request could not be confirmed. Keep your input and retry.',
  };

  @override
  String toString() => 'LocalApiException($code)';
}

Never invalidLocalResponse() =>
    throw const LocalApiException('INVALID_API_RESPONSE');

Map<String, dynamic> localObject(Object? value) {
  if (value is! Map<String, dynamic>) invalidLocalResponse();
  return value;
}

String localString(Map<String, dynamic> value, String field) {
  final item = value[field];
  if (item is! String || item.trim().isEmpty) invalidLocalResponse();
  return item;
}

void requireLocalVersion(Map<String, dynamic> value) {
  if (value['scope'] != localApplicationScope ||
      value['contract_version'] != localContractVersion) {
    invalidLocalResponse();
  }
}

DateTime localUtcTimestamp(Object? value) {
  if (value is! String) invalidLocalResponse();
  final match = RegExp(
    r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|\+00:00)$',
  ).firstMatch(value);
  final parsed = DateTime.tryParse(value);
  if (match == null || parsed == null || !parsed.isUtc) invalidLocalResponse();
  final parts = [for (var i = 1; i <= 6; i++) int.parse(match.group(i)!)];
  if (parsed.year != parts[0] ||
      parsed.month != parts[1] ||
      parsed.day != parts[2] ||
      parsed.hour != parts[3] ||
      parsed.minute != parts[4] ||
      parsed.second != parts[5]) {
    invalidLocalResponse();
  }
  return parsed;
}

DateTime? _nullableTime(Map<String, dynamic> value, String field) {
  if (!value.containsKey(field)) invalidLocalResponse();
  return value[field] == null ? null : localUtcTimestamp(value[field]);
}

class LocalUser {
  final String id;
  final String alias;

  const LocalUser({required this.id, required this.alias});

  factory LocalUser.fromJson(Object? raw) {
    final value = localObject(raw);
    final id = localString(value, 'id');
    final alias = localString(value, 'alias');
    if (id.length > 128 || !localAliases.contains(alias)) {
      invalidLocalResponse();
    }
    return LocalUser(id: id, alias: alias);
  }
}

class LocalLogin {
  final String accessToken;
  final DateTime expiresAt;
  final LocalUser user;

  const LocalLogin({
    required this.accessToken,
    required this.expiresAt,
    required this.user,
  });

  factory LocalLogin.fromJson(Object? raw) {
    final value = localObject(raw);
    requireLocalVersion(value);
    final token = localString(value, 'access_token');
    if (value['token_type'] != 'Bearer' ||
        !RegExp(r'^[A-Za-z0-9_-]{43}$').hasMatch(token)) {
      invalidLocalResponse();
    }
    return LocalLogin(
      accessToken: token,
      expiresAt: localUtcTimestamp(value['expires_at']),
      user: LocalUser.fromJson(value['user']),
    );
  }
}

class LocalConsent {
  final bool accepted;
  final String version;
  final DateTime recordedAt;

  const LocalConsent({
    required this.accepted,
    required this.version,
    required this.recordedAt,
  });

  factory LocalConsent.fromJson(Object? raw) {
    final value = localObject(raw);
    if (value['accepted'] is! bool || value['version'] != localConsentVersion) {
      invalidLocalResponse();
    }
    return LocalConsent(
      accepted: value['accepted'] as bool,
      version: value['version'] as String,
      recordedAt: localUtcTimestamp(value['recorded_at']),
    );
  }
}

class LocalOnboardingState {
  final LocalConsent? consent;
  final String? displayName;
  final String? experienceLevel;
  final DateTime? draftUpdatedAt;
  final bool completed;
  final DateTime? completedAt;

  const LocalOnboardingState({
    this.consent,
    this.displayName,
    this.experienceLevel,
    this.draftUpdatedAt,
    required this.completed,
    this.completedAt,
  });

  bool get hasCurrentConsent =>
      consent?.accepted == true && consent?.version == localConsentVersion;
  bool get canAccessFeatures => completed && hasCurrentConsent;

  factory LocalOnboardingState.fromJson(Object? raw) {
    final value = localObject(raw);
    requireLocalVersion(value);
    if (value['profile_schema_version'] != localProfileVersion ||
        value['consent_version'] != localConsentVersion ||
        !value.containsKey('consent') ||
        value['onboarding_completed'] is! bool) {
      invalidLocalResponse();
    }
    final draft = localObject(value['draft']);
    if (!draft.containsKey('display_name') ||
        !draft.containsKey('experience_level')) {
      invalidLocalResponse();
    }
    final name = draft['display_name'];
    final level = draft['experience_level'];
    if ((name != null &&
            (name is! String ||
                name.runes.length > 80 ||
                name != name.trim())) ||
        (level != null &&
            !['beginner', 'intermediate', 'advanced'].contains(level))) {
      invalidLocalResponse();
    }
    final result = LocalOnboardingState(
      consent: value['consent'] == null
          ? null
          : LocalConsent.fromJson(value['consent']),
      displayName: name as String?,
      experienceLevel: level as String?,
      draftUpdatedAt: _nullableTime(draft, 'updated_at'),
      completed: value['onboarding_completed'] as bool,
      completedAt: _nullableTime(value, 'completed_at'),
    );
    if ((result.draftUpdatedAt == null && (name != null || level != null)) ||
        (result.completed &&
            (!result.hasCurrentConsent ||
                name == null ||
                name.trim().isEmpty ||
                level == null ||
                result.completedAt == null)) ||
        (!result.completed && result.completedAt != null)) {
      invalidLocalResponse();
    }
    return result;
  }
}
