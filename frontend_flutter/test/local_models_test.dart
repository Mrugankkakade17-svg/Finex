import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/core/local_application/local_models.dart';

import 'support/local_application_fake.dart';

void main() {
  final invalid = throwsA(
    isA<LocalApiException>().having(
      (e) => e.code,
      'code',
      'INVALID_API_RESPONSE',
    ),
  );
  test('initial nullable draft is incomplete, never authorized', () {
    final state = testState();
    expect(state.displayName, isNull);
    expect(state.consent, isNull);
    expect(state.canAccessFeatures, isFalse);
  });
  test('partial profile and consent are not server completion', () {
    expect(
      testState(label: 'Synthetic', accepted: true).canAccessFeatures,
      isFalse,
    );
  });
  test('valid UTC completion authorizes only current accepted consent', () {
    expect(completedTestState().canAccessFeatures, isTrue);
    expect(completedTestState().completedAt!.isUtc, isTrue);
  });
  for (final field in [
    'scope',
    'contract_version',
    'profile_schema_version',
    'consent_version',
  ]) {
    test('reject wrong $field', () {
      final raw = localStateJson()..[field] = 'wrong';
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  for (final field in ['display_name', 'experience_level', 'updated_at']) {
    test('reject omitted nullable draft $field', () {
      final raw = localStateJson();
      (raw['draft'] as Map).remove(field);
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  for (final field in ['consent', 'onboarding_completed', 'completed_at']) {
    test('reject omitted state $field', () {
      final raw = localStateJson()..remove(field);
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  for (final label in [12, ' x ', List.filled(81, 'x').join()]) {
    test('reject malformed display label $label', () {
      final raw = localStateJson(label: 'ok');
      (raw['draft'] as Map)['display_name'] = label;
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  test('80 Unicode code points are accepted, not UTF16 unit count', () {
    final label = List.filled(80, '🧪').join();
    expect(testState(label: label).displayName, label);
  });
  for (final level in ['expert', '', false]) {
    test('reject unsupported experience $level', () {
      final raw = localStateJson();
      (raw['draft'] as Map)['experience_level'] = level;
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  for (final timestamp in [
    '2030-01-01',
    '2030-01-01T00:00:00',
    '2030-01-01T00:00:00+05:30',
    '2030-02-30T00:00:00Z',
    '2030-01-01T25:00:00Z',
    'not-a-time',
  ]) {
    test('reject nonUTC or invalid calendar timestamp $timestamp', () {
      expect(() => localUtcTimestamp(timestamp), invalid);
    });
  }
  test('zero-offset API timestamps and fractional seconds decode as UTC', () {
    expect(
      localUtcTimestamp('2030-01-01T00:00:00.123456+00:00').microsecond,
      456,
    );
  });
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'completion without consent': (raw) => raw['consent'] = null,
    'completion with withdrawn consent': (raw) =>
        (raw['consent'] as Map)['accepted'] = false,
    'completion without label': (raw) =>
        (raw['draft'] as Map)['display_name'] = null,
    'completion with empty label': (raw) =>
        (raw['draft'] as Map)['display_name'] = '',
    'completion without experience': (raw) =>
        (raw['draft'] as Map)['experience_level'] = null,
    'completion without time': (raw) => raw['completed_at'] = null,
    'incomplete with completed time': (raw) =>
        raw['onboarding_completed'] = false,
    'saved profile without update time': (raw) =>
        (raw['draft'] as Map)['updated_at'] = null,
    'stale consent version': (raw) =>
        (raw['consent'] as Map)['version'] = 'consent.v0',
    'nonboolean accepted consent': (raw) =>
        (raw['consent'] as Map)['accepted'] = 'true',
  }.entries) {
    test('reject contradictory ${mutation.key}', () {
      final raw = localStateJson(
        label: 'Synthetic A',
        level: 'beginner',
        accepted: true,
        completed: true,
      );
      mutation.value(raw);
      expect(() => LocalOnboardingState.fromJson(raw), invalid);
    });
  }
  Map<String, dynamic> login() => {
    'scope': localApplicationScope,
    'contract_version': localContractVersion,
    'access_token': testBearer('learner-a'),
    'token_type': 'Bearer',
    'expires_at': localTestTime.toIso8601String(),
    'user': {'id': 'synthetic-learner-a', 'alias': 'learner-a'},
  };
  test('opaque login has exact local scope and allowed identity', () {
    expect(LocalLogin.fromJson(login()).user.alias, 'learner-a');
  });
  for (final mutation in <String, void Function(Map<String, dynamic>)>{
    'token type': (raw) => raw['token_type'] = 'cookie',
    'JWT/token format': (raw) => raw['access_token'] = 'fake.jwt.token',
    'alias': (raw) => (raw['user'] as Map)['alias'] = 'real-person',
    'empty id': (raw) => (raw['user'] as Map)['id'] = '',
  }.entries) {
    test('reject login ${mutation.key}', () {
      final raw = login();
      mutation.value(raw);
      expect(() => LocalLogin.fromJson(raw), invalid);
    });
  }
}
