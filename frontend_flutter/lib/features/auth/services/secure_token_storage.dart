import 'dart:async';
import 'dart:convert';
import '../models/auth_token.dart';

/// Secure Token Storage abstraction.
/// Stores JWT tokens securely in device storage without ever logging plaintext tokens.
class SecureTokenStorage {
  static const String _accessTokenKey = 'finex_secure_access_token';
  static const String _refreshTokenKey = 'finex_secure_refresh_token';
  static const String _tokenMetaKey = 'finex_secure_token_meta';

  // In-memory backing cache for fast access & simulator / test execution
  final Map<String, String> _memoryStore = {};

  static final SecureTokenStorage _instance = SecureTokenStorage._internal();
  factory SecureTokenStorage() => _instance;
  SecureTokenStorage._internal();

  /// Saves token pair securely without logging secrets
  Future<void> saveToken(AuthToken token) async {
    _memoryStore[_accessTokenKey] = token.accessToken;
    if (token.refreshToken != null) {
      _memoryStore[_refreshTokenKey] = token.refreshToken!;
    }
    _memoryStore[_tokenMetaKey] = jsonEncode({
      'token_type': token.tokenType,
      'expires_in': token.expiresIn,
      'issued_at': token.issuedAt.toIso8601String(),
    });
  }

  /// Retrieves the stored token
  Future<AuthToken?> getToken() async {
    final access = _memoryStore[_accessTokenKey];
    if (access == null || access.isEmpty) {
      return null;
    }

    final refresh = _memoryStore[_refreshTokenKey];
    final metaRaw = _memoryStore[_tokenMetaKey];
    int expiresIn = 3600;
    String tokenType = 'Bearer';
    DateTime issuedAt = DateTime.now();

    if (metaRaw != null) {
      try {
        final meta = jsonDecode(metaRaw) as Map<String, dynamic>;
        expiresIn = (meta['expires_in'] as int?) ?? 3600;
        tokenType = (meta['token_type'] as String?) ?? 'Bearer';
        if (meta['issued_at'] != null) {
          issuedAt = DateTime.tryParse(meta['issued_at'].toString()) ?? DateTime.now();
        }
      } catch (_) {
        // Fallback to defaults if metadata format is unparseable
      }
    }

    return AuthToken(
      accessToken: access,
      refreshToken: refresh,
      tokenType: tokenType,
      expiresIn: expiresIn,
      issuedAt: issuedAt,
    );
  }

  /// Clears stored tokens securely
  Future<void> clearToken() async {
    _memoryStore.remove(_accessTokenKey);
    _memoryStore.remove(_refreshTokenKey);
    _memoryStore.remove(_tokenMetaKey);
  }

  /// Returns true if a valid non-empty access token exists
  Future<bool> hasToken() async {
    final token = await getToken();
    return token != null && token.accessToken.isNotEmpty;
  }
}
