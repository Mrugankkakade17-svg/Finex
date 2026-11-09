import 'package:frontend_flutter/core/local_application/local_api_client.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';

final localTestTime = DateTime.utc(2030, 1, 1);
String testBearer(String alias) =>
    List.filled(43, alias == 'learner-a' ? 'A' : 'B').join();
LocalUser testUser(String alias) =>
    LocalUser(id: 'synthetic-$alias', alias: alias);

Map<String, dynamic> localStateJson({
  String? label,
  String? level,
  bool? accepted,
  bool completed = false,
}) => {
  'scope': localApplicationScope,
  'contract_version': localContractVersion,
  'profile_schema_version': localProfileVersion,
  'consent_version': localConsentVersion,
  'consent': accepted == null
      ? null
      : {
          'accepted': accepted,
          'version': localConsentVersion,
          'recorded_at': localTestTime.toIso8601String(),
        },
  'draft': <String, dynamic>{
    'display_name': label,
    'experience_level': level,
    'updated_at': label == null && level == null
        ? null
        : localTestTime.toIso8601String(),
  },
  'onboarding_completed': completed,
  'completed_at': completed ? localTestTime.toIso8601String() : null,
};
LocalOnboardingState testState({
  String? label,
  String? level,
  bool? accepted,
  bool completed = false,
}) => LocalOnboardingState.fromJson(
  localStateJson(
    label: label,
    level: level,
    accepted: accepted,
    completed: completed,
  ),
);
LocalOnboardingState completedTestState([String label = 'Synthetic A']) =>
    testState(label: label, level: 'beginner', accepted: true, completed: true);

class FakeLocalApi implements LocalApplicationApi {
  final states = {'learner-a': testState(), 'learner-b': testState()};
  final calls = <String>[];
  Future<LocalLogin> Function(String)? onLogin;
  Future<LocalUser> Function(String)? onMe;
  Future<LocalOnboardingState> Function(String)? onState;
  Future<LocalOnboardingState> Function(String, String?, String?)? onDraft;
  Future<LocalOnboardingState> Function(String, bool)? onConsent;
  Future<LocalOnboardingState> Function(String)? onComplete;
  Future<void> Function(String)? onLogout;
  DateTime? expiresAt;
  bool closed = false;

  String aliasFor(String token) =>
      token == testBearer('learner-a') ? 'learner-a' : 'learner-b';

  @override
  Future<LocalLogin> login(String alias) async {
    calls.add('login:$alias');
    if (onLogin != null) return onLogin!(alias);
    return LocalLogin(
      accessToken: testBearer(alias),
      expiresAt: expiresAt ?? localTestTime.add(const Duration(hours: 1)),
      user: testUser(alias),
    );
  }

  @override
  Future<LocalUser> me(String bearer) async {
    calls.add('me:${aliasFor(bearer)}');
    return onMe == null ? testUser(aliasFor(bearer)) : onMe!(bearer);
  }

  @override
  Future<LocalOnboardingState> state(String bearer) async {
    calls.add('state:${aliasFor(bearer)}');
    return onState == null ? states[aliasFor(bearer)]! : onState!(bearer);
  }

  @override
  Future<LocalOnboardingState> saveDraft(
    String bearer, {
    String? displayName,
    String? experienceLevel,
  }) async {
    calls.add('draft:${aliasFor(bearer)}');
    if (onDraft != null) return onDraft!(bearer, displayName, experienceLevel);
    final alias = aliasFor(bearer);
    final before = states[alias]!;
    final same =
        displayName == before.displayName &&
        experienceLevel == before.experienceLevel;
    return states[alias] = testState(
      label: displayName,
      level: experienceLevel,
      accepted: before.consent?.accepted,
      completed: before.completed && same,
    );
  }

  @override
  Future<LocalOnboardingState> consent(String bearer, bool accepted) async {
    calls.add('consent:$accepted:${aliasFor(bearer)}');
    if (onConsent != null) return onConsent!(bearer, accepted);
    final alias = aliasFor(bearer);
    final before = states[alias]!;
    return states[alias] = testState(
      label: before.displayName,
      level: before.experienceLevel,
      accepted: accepted,
      completed: before.completed && accepted,
    );
  }

  @override
  Future<LocalOnboardingState> complete(String bearer) async {
    calls.add('complete:${aliasFor(bearer)}');
    if (onComplete != null) return onComplete!(bearer);
    final alias = aliasFor(bearer);
    final before = states[alias]!;
    if (!before.hasCurrentConsent) {
      throw const LocalApiException('CONSENT_REQUIRED', status: 409);
    }
    if (before.displayName == null || before.experienceLevel == null) {
      throw const LocalApiException('PROFILE_INCOMPLETE', status: 409);
    }
    return states[alias] = testState(
      label: before.displayName,
      level: before.experienceLevel,
      accepted: true,
      completed: true,
    );
  }

  @override
  Future<void> logout(String bearer) async {
    calls.add('logout:${aliasFor(bearer)}');
    if (onLogout != null) await onLogout!(bearer);
  }

  @override
  void close() {
    closed = true;
  }
}
