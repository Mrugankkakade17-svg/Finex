import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../services/auth_service.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _authService = AuthService();

  String? _emailError;
  String? _passwordError;
  bool _isLoading = false;
  String? _formError;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _validateAndSubmit() async {
    setState(() {
      _emailError = null;
      _passwordError = null;
      _formError = null;
    });

    final email = _emailController.text.trim();
    final password = _passwordController.text;

    bool hasError = false;
    if (email.isEmpty) {
      _emailError = 'Email address is required.';
      hasError = true;
    } else if (!email.contains('@') || !email.contains('.')) {
      _emailError = 'Please enter a valid email address.';
      hasError = true;
    }

    if (password.isEmpty) {
      _passwordError = 'Password is required.';
      hasError = true;
    } else if (password.length < 6) {
      _passwordError = 'Password must be at least 6 characters.';
      hasError = true;
    }

    if (hasError) {
      setState(() {});
      return;
    }

    setState(() => _isLoading = true);

    final success = await _authService.signInWithEmailPassword(
      email: email,
      password: password,
    );

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (success) {
      _navigatePostAuth();
    } else {
      setState(() {
        _formError = _authService.errorMessage ?? 'Authentication failed.';
      });
    }
  }

  void _handleGoogleSignIn() async {
    setState(() {
      _isLoading = true;
      _formError = null;
    });

    final success = await _authService.signInWithGoogle();

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (success) {
      _navigatePostAuth();
    } else {
      setState(() {
        _formError = _authService.errorMessage ?? 'Google Sign-In failed.';
      });
    }
  }

  void _navigatePostAuth() {
    final user = _authService.currentUser;
    if (user != null && user.onboardingStatus == 'COMPLETED') {
      context.go('/dashboard');
    } else {
      context.go('/onboarding/consent');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Brand Header
                  const Icon(
                    Icons.account_balance_wallet_outlined,
                    size: 56,
                    color: AppTheme.primary,
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'Welcome to FinEx',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary,
                        ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Decision-support intelligence for modern investors',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppTheme.textSecondary,
                        ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),

                  // Login Form Card
                  AppCard(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // Error Banner
                        if (_formError != null) ...[
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.red.withAlpha(38),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.red.shade400),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    _formError!,
                                    style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                        ],

                        // Google OAuth Button
                        SizedBox(
                          height: 48,
                          child: OutlinedButton.icon(
                            icon: const Icon(Icons.g_mobiledata, size: 28, color: Colors.redAccent),
                            label: const Text(
                              'Sign in with Google',
                              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
                            ),
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: AppTheme.border),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                            ),
                            onPressed: _isLoading ? null : _handleGoogleSignIn,
                          ),
                        ),
                        const SizedBox(height: 20),

                        // Divider
                        Row(
                          children: [
                            const Expanded(child: Divider(color: AppTheme.border)),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              child: Text(
                                'or sign in with email',
                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: AppTheme.textSecondary,
                                    ),
                              ),
                            ),
                            const Expanded(child: Divider(color: AppTheme.border)),
                          ],
                        ),
                        const SizedBox(height: 20),

                        // Email Field
                        AppTextField(
                          label: 'Email address',
                          hint: 'name@example.com',
                          controller: _emailController,
                          keyboardType: TextInputType.emailAddress,
                          errorText: _emailError,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 16),

                        // Password Field
                        AppTextField(
                          label: 'Password',
                          hint: '••••••••',
                          controller: _passwordController,
                          keyboardType: TextInputType.visiblePassword,
                          errorText: _passwordError,
                          enabled: !_isLoading,
                        ),
                        const SizedBox(height: 24),

                        // Submit Button
                        AppButton(
                          label: 'Sign In',
                          loading: _isLoading,
                          onPressed: _isLoading ? null : _validateAndSubmit,
                          icon: Icons.login,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),
                  Text(
                    'Educational Prototype Edition • No Real Money Involved',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textSecondary.withAlpha(179),
                          fontSize: 11,
                        ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
