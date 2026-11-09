class AuthUser {
  final String userId;
  final String email;
  final String name;
  final String role;
  final String? riskProfile;
  final bool hasConsent;
  final String onboardingStatus; // 'NOT_STARTED', 'IN_PROGRESS', 'COMPLETED'
  final DateTime createdAt;

  const AuthUser({
    required this.userId,
    required this.email,
    required this.name,
    this.role = 'user',
    this.riskProfile,
    this.hasConsent = false,
    this.onboardingStatus = 'NOT_STARTED',
    required this.createdAt,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      userId: json['userId']?.toString() ?? json['user_id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      role: json['role']?.toString() ?? 'user',
      riskProfile: json['riskProfile']?.toString() ?? json['risk_profile']?.toString(),
      hasConsent: json['hasConsent'] == true || json['has_consent'] == true,
      onboardingStatus: json['onboardingStatus']?.toString() ?? json['onboarding_status']?.toString() ?? 'NOT_STARTED',
      createdAt: json['createdAt'] != null
          ? DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now()
          : (json['created_at'] != null
              ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
              : DateTime.now()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'email': email,
      'name': name,
      'role': role,
      'riskProfile': riskProfile,
      'hasConsent': hasConsent,
      'onboardingStatus': onboardingStatus,
      'createdAt': createdAt.toIso8601String(),
    };
  }

  AuthUser copyWith({
    String? userId,
    String? email,
    String? name,
    String? role,
    String? riskProfile,
    bool? hasConsent,
    String? onboardingStatus,
    DateTime? createdAt,
  }) {
    return AuthUser(
      userId: userId ?? this.userId,
      email: email ?? this.email,
      name: name ?? this.name,
      role: role ?? this.role,
      riskProfile: riskProfile ?? this.riskProfile,
      hasConsent: hasConsent ?? this.hasConsent,
      onboardingStatus: onboardingStatus ?? this.onboardingStatus,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}
