class AuthToken {
  final String accessToken;
  final String? refreshToken;
  final String tokenType;
  final int expiresIn;
  final DateTime issuedAt;

  const AuthToken({
    required this.accessToken,
    this.refreshToken,
    this.tokenType = 'Bearer',
    this.expiresIn = 3600,
    required this.issuedAt,
  });

  bool get isExpired {
    final expiryTime = issuedAt.add(Duration(seconds: expiresIn));
    return DateTime.now().isAfter(expiryTime);
  }

  factory AuthToken.fromJson(Map<String, dynamic> json) {
    return AuthToken(
      accessToken: json['access_token']?.toString() ?? json['accessToken']?.toString() ?? '',
      refreshToken: json['refresh_token']?.toString() ?? json['refreshToken']?.toString(),
      tokenType: json['token_type']?.toString() ?? json['tokenType']?.toString() ?? 'Bearer',
      expiresIn: (json['expires_in'] ?? json['expiresIn'] ?? 3600) as int,
      issuedAt: json['issued_at'] != null
          ? DateTime.tryParse(json['issued_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'access_token': accessToken,
      'refresh_token': refreshToken,
      'token_type': tokenType,
      'expires_in': expiresIn,
      'issued_at': issuedAt.toIso8601String(),
    };
  }
}
