import 'package:flutter/foundation.dart';
import '../models/onboarding_state.dart';
import '../../auth/services/auth_service.dart';

class OnboardingService extends ChangeNotifier {
  static final OnboardingService _instance = OnboardingService._internal();
  factory OnboardingService() => _instance;
  OnboardingService._internal();

  OnboardingState _state = const OnboardingState();
  bool _isLoading = false;
  String? _errorMessage;

  OnboardingState get state => _state;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  /// Loads saved onboarding draft state (supporting resume behavior)
  Future<void> loadSavedProgress() async {
    // In production, syncs with GET /api/v1/users/me/profile draft
    notifyListeners();
  }

  /// Updates consent choices
  void updateConsent({
    bool? terms,
    bool? disclaimer,
    bool? profiling,
  }) {
    _state = _state.copyWith(
      termsConsent: terms ?? _state.termsConsent,
      disclaimerConsent: disclaimer ?? _state.disclaimerConsent,
      automatedProfilingConsent: profiling ?? _state.automatedProfilingConsent,
    );
    notifyListeners();
  }

  /// Submits consent and advances to profile setup
  Future<bool> submitConsent() async {
    if (!_state.hasAllConsents) {
      _errorMessage = 'All consents are required to proceed.';
      notifyListeners();
      return false;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await Future.delayed(const Duration(milliseconds: 400));
      _state = _state.copyWith(currentStep: OnboardingStep.profile);
      _isLoading = false;

      // Update auth user model
      final authService = AuthService();
      if (authService.currentUser != null) {
        authService.updateUser(
          authService.currentUser!.copyWith(
            hasConsent: true,
            onboardingStatus: 'IN_PROGRESS',
          ),
        );
      }

      notifyListeners();
      return true;
    } catch (e) {
      _isLoading = false;
      _errorMessage = 'Failed to submit consent. Please try again.';
      notifyListeners();
      return false;
    }
  }

  /// Saves profile information
  void updateProfile({
    String? fullName,
    String? preferredCurrency,
  }) {
    _state = _state.copyWith(
      fullName: fullName ?? _state.fullName,
      preferredCurrency: preferredCurrency ?? _state.preferredCurrency,
    );
    notifyListeners();
  }

  /// Saves investor preferences
  void updatePreferences({
    String? horizon,
    String? experience,
    String? primaryGoal,
  }) {
    _state = _state.copyWith(
      investmentHorizon: horizon ?? _state.investmentHorizon,
      investmentExperience: experience ?? _state.investmentExperience,
      primaryGoal: primaryGoal ?? _state.primaryGoal,
    );
    notifyListeners();
  }

  /// Advances to next onboarding step
  void advanceStep(OnboardingStep nextStep) {
    _state = _state.copyWith(currentStep: nextStep);
    notifyListeners();
  }

  /// Completes full onboarding flow
  Future<void> completeOnboarding({required String riskProfile}) async {
    _state = _state.copyWith(currentStep: OnboardingStep.completed);
    final authService = AuthService();
    if (authService.currentUser != null) {
      authService.updateUser(
        authService.currentUser!.copyWith(
          riskProfile: riskProfile,
          onboardingStatus: 'COMPLETED',
        ),
      );
    }
    notifyListeners();
  }
}
