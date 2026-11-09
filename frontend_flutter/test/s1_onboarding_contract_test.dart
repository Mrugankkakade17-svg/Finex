import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend_flutter/features/onboarding/models/s1_onboarding_contract.dart';
import 'package:frontend_flutter/features/onboarding/services/s1_onboarding_contract_client.dart';
import 'package:frontend_flutter/features/onboarding/services/s1_onboarding_journey_store.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  group('FixtureS1OnboardingContractClient', () {
    test('requires consent, then completes the typed local journey', () async {
      final client = FixtureS1OnboardingContractClient();
      const correlationId = 'flutter-contract-test-1';

      expect(
        client.submitProfile(
          const S1ProfileInput(
            correlationId: correlationId,
            profileSchemaVersion: s1ProfileSchemaVersion,
            displayName: 'Local Tester',
            experienceLevel: S1ExperienceLevel.beginner,
          ),
        ),
        throwsA(
          isA<S1OnboardingException>().having(
            (error) => error.code,
            'code',
            'CONSENT_MISSING',
          ),
        ),
      );

      final consent = await client.captureConsent(
        const S1ConsentInput(
          correlationId: correlationId,
          consentVersion: s1ConsentVersion,
          consentGiven: true,
        ),
      );
      expect(consent.consentStatus, 'accepted');

      final profile = await client.submitProfile(
        const S1ProfileInput(
          correlationId: correlationId,
          profileSchemaVersion: s1ProfileSchemaVersion,
          displayName: '  Local Tester  ',
          experienceLevel: S1ExperienceLevel.intermediate,
        ),
      );
      expect(profile.displayName, 'Local Tester');
      expect(profile.experienceLevel, S1ExperienceLevel.intermediate);

      final completion = await client.completeOnboarding(
        const S1CompletionInput(
          correlationId: correlationId,
          consentVersion: s1ConsentVersion,
          profileSchemaVersion: s1ProfileSchemaVersion,
        ),
      );
      expect(completion.onboardingCompleted, isTrue);
      expect(completion.fixtureMode, 's1_dat_01');
    });

    test('returns a stable error for unsupported consent versions', () {
      final client = FixtureS1OnboardingContractClient();
      expect(
        client.captureConsent(
          const S1ConsentInput(
            correlationId: 'bad-version',
            consentVersion: 'consent.v999',
            consentGiven: true,
          ),
        ),
        throwsA(
          isA<S1OnboardingException>().having(
            (error) => error.code,
            'code',
            'UNSUPPORTED_CONSENT_VERSION',
          ),
        ),
      );
    });
  });

  test('API adapter returns a typed error for a malformed response', () {
    final client = HttpS1OnboardingContractClient(
      Uri.parse('http://127.0.0.1:8000'),
      client: MockClient((_) async => http.Response('not-json', 200)),
    );

    expect(
      client.captureConsent(
        const S1ConsentInput(
          correlationId: 'malformed-response',
          consentVersion: s1ConsentVersion,
          consentGiven: true,
        ),
      ),
      throwsA(
        isA<S1OnboardingException>().having(
          (error) => error.code,
          'code',
          'INVALID_API_RESPONSE',
        ),
      ),
    );
  });

  test(
    'API adapter preserves a safe server error code for the retry UI',
    () async {
      final client = HttpS1OnboardingContractClient(
        Uri.parse('http://127.0.0.1:8000'),
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'success': false,
              'message': 'The consent version is not supported.',
              'error_code': 'UNSUPPORTED_CONSENT_VERSION',
            }),
            400,
          ),
        ),
      );

      await expectLater(
        client.captureConsent(
          const S1ConsentInput(
            correlationId: 'flutter-safe-error',
            consentVersion: s1ConsentVersion,
            consentGiven: true,
          ),
        ),
        throwsA(
          isA<S1OnboardingException>()
              .having(
                (error) => error.code,
                'code',
                'UNSUPPORTED_CONSENT_VERSION',
              )
              .having(
                (error) => error.message,
                'message',
                'The consent version is not supported.',
              ),
        ),
      );
    },
  );

  test('API adapter maps the approved FastAPI consent contract', () async {
    final client = HttpS1OnboardingContractClient(
      Uri.parse('http://127.0.0.1:8000'),
      client: MockClient((request) async {
        expect(request.url.path, '/api/v1/onboarding-contract/consent');
        expect(request.headers['x-correlation-id'], 'flutter-api-contract-1');
        return http.Response(
          jsonEncode({
            'success': true,
            'message': 'Consent recorded',
            'data': {
              'consent_version': s1ConsentVersion,
              'consent_status': 'accepted',
              'recorded_at': '2026-10-10T00:00:00Z',
            },
          }),
          201,
        );
      }),
    );

    final result = await client.captureConsent(
      const S1ConsentInput(
        correlationId: 'flutter-api-contract-1',
        consentVersion: s1ConsentVersion,
        consentGiven: true,
      ),
    );

    expect(result.consentVersion, s1ConsentVersion);
    expect(result.consentStatus, 'accepted');
    expect(result.recordedAt, DateTime.utc(2026, 10, 10));
  });

  test(
    'API adapter rejects a successful envelope that drifts from the contract',
    () async {
      final client = HttpS1OnboardingContractClient(
        Uri.parse('http://127.0.0.1:8000'),
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'success': true,
              'message': 'Consent recorded',
              'data': {
                'consent_version': s1ConsentVersion,
                'consent_status': 'accepted',
              },
            }),
            201,
          ),
        ),
      );

      await expectLater(
        client.captureConsent(
          const S1ConsentInput(
            correlationId: 'flutter-contract-drift',
            consentVersion: s1ConsentVersion,
            consentGiven: true,
          ),
        ),
        throwsA(
          isA<S1OnboardingException>().having(
            (error) => error.code,
            'code',
            'INVALID_API_RESPONSE',
          ),
        ),
      );
    },
  );

  test(
    'in-memory journey store persists only journey state, not profile data',
    () async {
      final store = InMemoryS1OnboardingJourneyStore();
      final journey = createS1Journey(S1IntegrationMode.fixture).copyWith(
        consentRecorded: true,
        profileSubmitted: true,
        completed: true,
        completedAt: DateTime.utc(2026, 10, 10),
      );

      await store.save(journey);

      expect(await store.load(), journey);
      expect(store.current!.toJson().containsKey('displayName'), isFalse);
    },
  );
}
