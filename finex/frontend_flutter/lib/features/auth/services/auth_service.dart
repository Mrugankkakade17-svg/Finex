import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/auth_token.dart';
import '../models/auth_user.dart';
import 'secure_token_storage.dart';

enum AuthStatus { unauthenticated, authenticating, authenticated, error }

class AuthService extends ChangeNotifier {
  static final AuthService _instance = AuthService._internal();
  factory AuthService() => _instance;
  AuthService._internal();

  final SecureTokenStorage _tokenStorage = SecureTokenStorage();

  AuthStatus _status = AuthStatus.unauthenticated;
  AuthUser? _currentUser;
  String? _errorMessage;

  AuthStatus get status => _status;
  AuthUser? get currentUser => _currentUser;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _status == AuthStatus.authenticated && _currentUser != null;

  /// Initializes auth state on application startup
  Future<void> initialize() async {
    final token = await _tokenStorage.getToken();
    if (token != null && !token.isExpired) {
      // In production, validate token against GET /api/v1/users/me
      _currentUser = AuthUser(
        userId: 'user_001',
        email: 'investor@finex.dev',
        name: 'FinEx Investor',
        hasConsent: false,
        onboardingStatus: 'NOT_STARTED',
        createdAt: DateTime.now(),
      );
      _status = AuthStatus.authenticated;
    } else {
      _status = AuthStatus.unauthenticated;
      _currentUser = null;
    }
    notifyListeners();
  }

  /// Sign in with Google OAuth flow (handles callback token exchange)
  Future<bool> signInWithGoogle({String? mockIdToken}) async {
    _status = AuthStatus.authenticating;
    _errorMessage = null;
    notifyListeners();

    try {
      // Simulate network / OAuth exchange
      await Future.delayed(const Duration(milliseconds: 600));

      final token = AuthToken(
        accessToken: 'mock_jwt_access_${DateTime.now().millisecondsSinceEpoch}',
        refreshToken: 'mock_jwt_refresh_${DateTime.now().millisecondsSinceEpoch}',
        tokenType: 'Bearer',
        expiresIn: 3600,
        issuedAt: DateTime.now(),
      );

      await _tokenStorage.saveToken(token);

      _currentUser = AuthUser(
        userId: 'user_google_001',
        email: 'google.investor@finex.dev',
        name: 'Google Investor',
        hasConsent: false,
        onboardingStatus: 'NOT_STARTED',
        createdAt: DateTime.now(),
      );

      _status = AuthStatus.authenticated;
      notifyListeners();
      return true;
    } catch (e) {
      _status = AuthStatus.error;
      _errorMessage = 'Google authentication failed. Please try again.';
      notifyListeners();
      return false;
    }
  }

  /// Sign in with Email & Password
  Future<bool> signInWithEmailPassword({
    required String email,
    required String password,
  }) async {
    _status = AuthStatus.authenticating;
    _errorMessage = null;
    notifyListeners();

    // Field validations
    if (email.trim().isEmpty) {
      _status = AuthStatus.error;
      _errorMessage = 'Email address is required.';
      notifyListeners();
      return false;
    }

    if (!email.contains('@')) {
      _status = AuthStatus.error;
      _errorMessage = 'Please enter a valid email address.';
      notifyListeners();
      return false;
    }

    if (password.length < 6) {
      _status = AuthStatus.error;
      _errorMessage = 'Password must be at least 6 characters.';
      notifyListeners();
      return false;
    }

    try {
      await Future.delayed(const Duration(milliseconds: 600));

      final token = AuthToken(
        accessToken: 'mock_jwt_email_${DateTime.now().millisecondsSinceEpoch}',
        refreshToken: 'mock_jwt_refresh_${DateTime.now().millisecondsSinceEpoch}',
        tokenType: 'Bearer',
        expiresIn: 3600,
        issuedAt: DateTime.now(),
      );

      await _tokenStorage.saveToken(token);

      _currentUser = AuthUser(
        userId: 'user_email_001',
        email: email.trim(),
        name: email.split('@').first,
        hasConsent: false,
        onboardingStatus: 'NOT_STARTED',
        createdAt: DateTime.now(),
      );

      _status = AuthStatus.authenticated;
      notifyListeners();
      return true;
    } catch (e) {
      _status = AuthStatus.error;
      _errorMessage = 'Invalid credentials. Please verify your login details.';
      notifyListeners();
      return false;
    }
  }

  /// Updates local user state (e.g. after consent or onboarding progress)
  void updateUser(AuthUser updated) {
    _currentUser = updated;
    notifyListeners();
  }

  /// Sign out & invalidate stored tokens
  Future<void> signOut() async {
    await _tokenStorage.clearToken();
    _currentUser = null;
    _status = AuthStatus.unauthenticated;
    _errorMessage = null;
    notifyListeners();
  }
}
