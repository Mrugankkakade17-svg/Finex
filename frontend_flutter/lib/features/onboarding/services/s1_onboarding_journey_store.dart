import 'dart:convert';
import 'dart:math';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/s1_onboarding_contract.dart';

const _journeyStorageKey = 'finex_s1_onboarding_journey_v1';

class S1OnboardingJourney {
  final int schemaVersion;
  final String correlationId;
  final S1IntegrationMode integrationMode;
  final bool consentRecorded;
  final bool profileSubmitted;
  final bool completed;
  final DateTime? completedAt;

  const S1OnboardingJourney({
    this.schemaVersion = 1,
    required this.correlationId,
    required this.integrationMode,
    this.consentRecorded = false,
    this.profileSubmitted = false,
    this.completed = false,
    this.completedAt,
  });

  S1OnboardingJourney copyWith({
    bool? consentRecorded,
    bool? profileSubmitted,
    bool? completed,
    DateTime? completedAt,
  }) {
    return S1OnboardingJourney(
      schemaVersion: schemaVersion,
      correlationId: correlationId,
      integrationMode: integrationMode,
      consentRecorded: consentRecorded ?? this.consentRecorded,
      profileSubmitted: profileSubmitted ?? this.profileSubmitted,
      completed: completed ?? this.completed,
      completedAt: completedAt ?? this.completedAt,
    );
  }

  Map<String, Object?> toJson() => {
    'schemaVersion': schemaVersion,
    'correlationId': correlationId,
    'integrationMode': integrationMode.name,
    'consentRecorded': consentRecorded,
    'profileSubmitted': profileSubmitted,
    'completed': completed,
    'completedAt': completedAt?.toUtc().toIso8601String(),
  };

  factory S1OnboardingJourney.fromJson(Map<String, dynamic> json) {
    final completedAtValue = json['completedAt'] as String?;
    return S1OnboardingJourney(
      schemaVersion: json['schemaVersion'] as int? ?? 0,
      correlationId: json['correlationId'] as String? ?? '',
      integrationMode: S1IntegrationMode.values.byName(
        json['integrationMode'] as String? ?? S1IntegrationMode.fixture.name,
      ),
      consentRecorded: json['consentRecorded'] == true,
      profileSubmitted: json['profileSubmitted'] == true,
      completed: json['completed'] == true,
      completedAt: completedAtValue == null
          ? null
          : DateTime.tryParse(completedAtValue)?.toUtc(),
    );
  }
}

abstract interface class S1OnboardingJourneyStore {
  Future<S1OnboardingJourney?> load();

  Future<void> save(S1OnboardingJourney journey);

  Future<void> clear();
}

class SharedPreferencesS1OnboardingJourneyStore
    implements S1OnboardingJourneyStore {
  const SharedPreferencesS1OnboardingJourneyStore();

  @override
  Future<S1OnboardingJourney?> load() async {
    final preferences = await SharedPreferences.getInstance();
    final raw = preferences.getString(_journeyStorageKey);
    if (raw == null) {
      return null;
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Invalid stored journey');
      }
      final journey = S1OnboardingJourney.fromJson(decoded);
      if (journey.schemaVersion != 1 || journey.correlationId.isEmpty) {
        throw const FormatException('Unsupported stored journey');
      }
      return journey;
    } on FormatException {
      await preferences.remove(_journeyStorageKey);
      return null;
    } on ArgumentError {
      await preferences.remove(_journeyStorageKey);
      return null;
    }
  }

  @override
  Future<void> save(S1OnboardingJourney journey) async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
      _journeyStorageKey,
      jsonEncode(journey.toJson()),
    );
  }

  @override
  Future<void> clear() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.remove(_journeyStorageKey);
  }
}

class InMemoryS1OnboardingJourneyStore implements S1OnboardingJourneyStore {
  S1OnboardingJourney? current;

  @override
  Future<void> clear() async {
    current = null;
  }

  @override
  Future<S1OnboardingJourney?> load() async => current;

  @override
  Future<void> save(S1OnboardingJourney journey) async {
    current = journey;
  }
}

S1OnboardingJourney createS1Journey(S1IntegrationMode mode) {
  // Dart's JavaScript bitwise shifts are 32-bit: 1 << 32 compiles to zero.
  // A numeric literal retains the full 32-bit secure range on VM and web.
  final random = Random.secure().nextInt(0x100000000).toRadixString(16);
  return S1OnboardingJourney(
    correlationId: 'flutter-${DateTime.now().microsecondsSinceEpoch}-$random',
    integrationMode: mode,
  );
}
