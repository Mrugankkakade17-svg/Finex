import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/local_application/local_app_widgets.dart';
import '../../../core/local_application/local_models.dart';
import '../../../core/local_application/local_session.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';

class LocalOnboardingPage extends StatefulWidget {
  final LocalSession session;
  const LocalOnboardingPage({super.key, required this.session});

  @override
  State<LocalOnboardingPage> createState() => _LocalOnboardingPageState();
}

class _LocalOnboardingPageState extends State<LocalOnboardingPage> {
  final _label = TextEditingController();
  final _labelFocus = FocusNode();
  final _experienceFocus = FocusNode();
  final _errorFocus = FocusNode();
  final _errorAnchor = GlobalKey();
  String? _level;
  String? _owner;
  String? _validation;
  String? _notice;
  bool _dirty = false;
  bool _consentChoice = false;
  bool _consentEdited = false;
  bool _hydrated = false;

  @override
  void initState() {
    super.initState();
    widget.session.addListener(_changed);
    _hydrate();
    _scheduleRefresh(widget.session);
  }

  void _scheduleRefresh(LocalSession session) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && identical(widget.session, session)) {
        session.refreshOnboarding();
      }
    });
  }

  @override
  void didUpdateWidget(covariant LocalOnboardingPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (identical(oldWidget.session, widget.session)) return;
    oldWidget.session.removeListener(_changed);
    widget.session.addListener(_changed);
    _owner = null;
    _dirty = false;
    _hydrated = false;
    _label.clear();
    _level = null;
    _validation = null;
    _notice = null;
    _consentChoice = false;
    _consentEdited = false;
    _hydrate();
    _scheduleRefresh(widget.session);
  }

  bool _isCurrent(LocalSession session, int generation) =>
      mounted &&
      identical(widget.session, session) &&
      session.generation == generation;

  void _hydrate() {
    if (_owner != widget.session.user?.id) {
      _owner = widget.session.user?.id;
      _dirty = false;
      _hydrated = false;
      _label.clear();
      _level = null;
      _validation = null;
      _notice = null;
      _consentChoice = false;
      _consentEdited = false;
    }
    final state = widget.session.onboarding;
    if (state != null && (!_hydrated || !_dirty)) {
      _label.text = state.displayName ?? '';
      _level = state.experienceLevel;
      if (!_consentEdited) _consentChoice = state.hasCurrentConsent;
      _hydrated = true;
    }
  }

  void _changed() {
    if (!mounted) return;
    _hydrate();
    setState(() {});
  }

  @override
  void dispose() {
    widget.session.removeListener(_changed);
    _label.dispose();
    _labelFocus.dispose();
    _experienceFocus.dispose();
    _errorFocus.dispose();
    super.dispose();
  }

  void _showValidation(String message, FocusNode focus) {
    setState(() {
      _validation = message;
      _notice = null;
    });
    if (focus == _errorFocus) {
      _focusError();
    } else {
      focus.requestFocus();
    }
  }

  void _focusError() {
    final session = widget.session;
    final generation = session.generation;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_isCurrent(session, generation)) return;
      _errorFocus.requestFocus();
      final errorContext = _errorAnchor.currentContext;
      if (errorContext != null) Scrollable.ensureVisible(errorContext);
    });
  }

  Future<void> _reloadSavedState() {
    // A historical action receipt is not a claim about newly loaded state.
    setState(() => _notice = null);
    return widget.session.refreshOnboarding();
  }

  Future<bool> _save() async {
    if (_label.text.trim().runes.length > 80) {
      _showValidation(
        'Use a display label of at most 80 characters.',
        _labelFocus,
      );
      return false;
    }
    final session = widget.session;
    final generation = session.generation;
    final saved = await session.saveDraft(
      displayName: _label.text.trim().isEmpty ? null : _label.text.trim(),
      experienceLevel: _level,
    );
    if (!_isCurrent(session, generation)) return false;
    if (saved) {
      setState(() {
        _dirty = false;
        _validation = null;
        _notice = 'Draft confirmed saved by the server. Incomplete drafts are not completed onboarding.';
        _hydrate();
      });
    } else {
      _focusError();
    }
    return saved;
  }

  Future<void> _complete() async {
    if (_label.text.trim().isEmpty) {
      _showValidation(
        'Enter a display label before completing onboarding.',
        _labelFocus,
      );
      return;
    }
    if (_level == null) {
      _showValidation(
        'Select an experience level before completing onboarding.',
        _experienceFocus,
      );
      return;
    }
    if (widget.session.onboarding?.hasCurrentConsent != true) {
      _showValidation(
        'Record the current educational consent notice before completion.',
        _errorFocus,
      );
      return;
    }
    final session = widget.session;
    final generation = session.generation;
    if (_dirty ||
        widget.session.onboarding?.displayName != _label.text.trim() ||
        widget.session.onboarding?.experienceLevel != _level) {
      if (!await _save()) return;
    }
    if (!_isCurrent(session, generation)) return;
    final completed = await session.complete();
    if (!_isCurrent(session, generation)) return;
    setState(() {
      _validation = null;
      _notice = completed
          ? 'Onboarding confirmed complete by the server.'
          : null;
    });
    if (!completed) _focusError();
  }

  Future<void> _consent(bool accepted) async {
    if (accepted && !_consentChoice) {
      _showValidation(
        'Select the educational consent checkbox before accepting.',
        _errorFocus,
      );
      return;
    }
    final session = widget.session;
    final generation = session.generation;
    final saved = await session.recordConsent(accepted);
    if (!_isCurrent(session, generation)) return;
    setState(() {
      _validation = null;
      _notice = saved
          ? accepted
                ? 'Current consent confirmed recorded. Completion must still be confirmed.'
                : 'Consent withdrawal confirmed. Later features are gated until valid recompletion.'
          : null;
      if (saved) {
        _consentChoice = accepted;
        _consentEdited = false;
      }
    });
    if (!saved) _focusError();
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    final state = session.onboarding;
    final busy = session.isBusy;
    final message =
        _validation ??
        session.operationError?.message ??
        session.loadError?.message;
    if (session.loadingState || state == null) {
      return Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              if (session.loadingState)
                Semantics(
                  liveRegion: true,
                  child: const Text(
                    'Loading owned onboarding from the server…',
                  ),
                )
              else ...[
                LocalErrorNotice(
                  message:
                      session.loadError?.message ??
                      session.operationError?.message ??
                      'Saved onboarding could not be confirmed.',
                ),
                AppButton(
                  label: 'Retry loading saved onboarding',
                  onPressed: _reloadSavedState,
                ),
              ],
            ],
          ),
        ),
      );
    }
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 680),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Saved onboarding',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text(
                'Synthetic learner: ${session.user!.alias} · $localContractVersion',
              ),
              const SizedBox(height: 12),
              const Text(
                'This application saves synthetic profile and consent decisions on your local API. A cold launch signs out; signing into the same learner resumes server data. No real personal/account data or investment advice.',
              ),
              const SizedBox(height: 16),
              if (message != null)
                Focus(
                  key: _errorAnchor,
                  focusNode: _errorFocus,
                  child: LocalErrorNotice(
                    key: const Key('local-onboarding-error'),
                    message: message,
                  ),
                ),
              if (_notice != null)
                Semantics(
                  liveRegion: true,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_notice!),
                  ),
                ),
              AppCard(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Educational consent',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Notice $localConsentVersion: FinEx is an educational, synthetic simulation. It does not verify suitability, guarantee returns, handle real money or connect to a brokerage. Consent and draft/profile decisions are saved locally with UTC timestamps; session secrets stay in memory only.',
                    ),
                    const SizedBox(height: 8),
                    Text(
                      state.hasCurrentConsent
                          ? 'Current consent: accepted'
                          : 'Current consent: not accepted',
                    ),
                    if (state.consent != null)
                      Text(
                        'Latest decision (UTC): ${state.consent!.recordedAt.toIso8601String()}',
                      ),
                    CheckboxListTile(
                      key: const Key('local-consent-choice'),
                      contentPadding: EdgeInsets.zero,
                      title: const Text(
                        'I understand and accept this educational synthetic notice.',
                      ),
                      value: _consentChoice,
                      onChanged: busy
                          ? null
                          : (value) => setState(() {
                              _consentChoice = value ?? false;
                              _consentEdited = true;
                              _validation = null;
                            }),
                    ),
                    AppButton(
                      key: const Key('local-consent-save'),
                      label: 'Record current consent',
                      enabled: !busy,
                      onPressed: () => _consent(true),
                    ),
                    if (state.hasCurrentConsent) ...[
                      const SizedBox(height: 8),
                      OutlinedButton(
                        key: const Key('local-consent-withdraw'),
                        onPressed: busy ? null : () => _consent(false),
                        child: const Text(
                          'Withdraw consent and gate later features',
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 16),
              AppCard(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Resumable profile draft',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Partial drafts are allowed. Completion requires a nonblank display label, experience level and current consent. Saving a changed completed profile requires reconfirmation.',
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      key: const Key('local-display-label'),
                      controller: _label,
                      focusNode: _labelFocus,
                      enabled: !busy,
                      maxLength: 80,
                      textInputAction: TextInputAction.next,
                      decoration: const InputDecoration(
                        labelText: 'Display label',
                        helperText: 'Use a synthetic, non-sensitive label; not a legal name.',
                      ),
                      onChanged: (_) => setState(() {
                        _dirty = true;
                        _validation = null;
                        _notice = null;
                      }),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      key: ValueKey('local-experience-${_level ?? 'none'}'),
                      focusNode: _experienceFocus,
                      initialValue: _level,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Experience level',
                      ),
                      hint: const Text('Choose one for completion'),
                      items: const [
                        DropdownMenuItem(
                          value: 'beginner',
                          child: Text('Beginner'),
                        ),
                        DropdownMenuItem(
                          value: 'intermediate',
                          child: Text('Intermediate'),
                        ),
                        DropdownMenuItem(
                          value: 'advanced',
                          child: Text('Advanced'),
                        ),
                      ],
                      onChanged: busy
                          ? null
                          : (value) => setState(() {
                              _level = value;
                              _dirty = true;
                              _validation = null;
                              _notice = null;
                            }),
                    ),
                    const SizedBox(height: 16),
                    AppButton(
                      key: const Key('local-save-draft'),
                      label: 'Save draft (partial values allowed)',
                      enabled: !busy,
                      onPressed: _save,
                    ),
                    const SizedBox(height: 12),
                    AppButton(
                      key: const Key('local-complete'),
                      label: 'Complete onboarding',
                      enabled: !busy,
                      onPressed: _complete,
                    ),
                    if (state.draftUpdatedAt != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        'Draft saved (UTC): ${state.draftUpdatedAt!.toIso8601String()}',
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (busy)
                Semantics(
                  liveRegion: true,
                  child: const Text('Confirming the server action…'),
                ),
              if (state.completed) ...[
                Text(
                  'Onboarding confirmed complete',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(
                  'Completed (UTC): ${state.completedAt!.toIso8601String()}',
                ),
                const SizedBox(height: 12),
                AppButton(
                  label: 'Continue to saved dashboard',
                  enabled: session.canAccessFeatures,
                  onPressed: () => context.go('/dashboard'),
                ),
              ] else
                const Text(
                  'Onboarding is incomplete. A saved draft or accepted consent alone does not grant feature access.',
                ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: busy ? null : _reloadSavedState,
                child: const Text(
                  'Reload saved state (unsaved edits remain in this form)',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
