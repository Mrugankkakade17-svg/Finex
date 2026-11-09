import 'package:flutter/material.dart';

import '../../shared/widgets/app_button.dart';
import 'local_app_widgets.dart';
import 'local_models.dart';
import 'local_s2_api.dart';
import 'local_session.dart';

/// Page-local work lifetime. Cancellation is a logical guard even when an
/// injected adapter ignores cancellation; session scopes separately guard 401.
abstract class LocalS2PageState<W extends StatefulWidget> extends State<W> {
  LocalSession get session;
  LocalS2Scope? _scope;
  LocalS2Scope? _popupIntent;
  NavigatorState? _popupNavigator;
  int _sequence = 0;
  bool busy = false;
  String? message;
  LocalApiException? error;
  final errorKey = GlobalKey();
  final errorFocus = FocusNode();

  @override
  void initState() {
    super.initState();
    session.addListener(_sessionChanged);
  }

  void _sessionChanged() {
    if (_popupIntent != null && !_popupIntent!.isCurrent) {
      _popupIntent!.dispose();
      _popupIntent = null;
      final navigator = _popupNavigator;
      _popupNavigator = null;
      if (navigator != null && navigator.mounted) {
        navigator.popUntil((route) => route is! PopupRoute);
      }
    }
    if (_scope != null && !_scope!.isCurrent) {
      _sequence++;
      _scope!.dispose();
      _scope = null;
      if (mounted) setState(() => busy = false);
    }
  }

  void watchOwnedPopup() {
    _popupIntent?.dispose();
    _popupIntent = session.createS2Scope();
    // Dropdown routes use the closest navigator (the owned shell), unlike
    // root dialogs. Closing a root navigator would leave this overlay visible.
    _popupNavigator = Navigator.maybeOf(context);
  }

  bool get currentPopupIntent =>
      _popupIntent?.isCurrent == true && session.canAccessFeatures;
  void endOwnedPopup() {
    _popupIntent?.dispose();
    _popupIntent = null;
    _popupNavigator = null;
  }

  void showError(LocalApiException value) {
    if (!mounted || value.code == 'SESSION_CHANGED') return;
    setState(() {
      error = value;
      message = null;
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      errorFocus.requestFocus();
      final context = errorKey.currentContext;
      if (context != null) {
        Scrollable.ensureVisible(
          context,
          duration: const Duration(milliseconds: 150),
          alignment: .1,
        );
      }
    });
  }

  Future<bool> request<T>(
    Future<T> Function(LocalS2Scope) operation,
    void Function(T) accept,
  ) async {
    if (busy || session.isBusy || !session.canAccessFeatures) return false;
    _scope?.dispose();
    endOwnedPopup();
    final current = session.createS2Scope();
    _scope = current;
    final sequence = ++_sequence;
    setState(() {
      busy = true;
      error = null;
      message = null;
    });
    try {
      final result = await operation(current);
      if (!mounted || sequence != _sequence || !current.isCurrent) return false;
      setState(() => accept(result));
      return true;
    } on LocalApiException catch (value) {
      if (mounted && sequence == _sequence && current.isCurrent) {
        showError(value);
      }
      return false;
    } on Exception {
      if (mounted && sequence == _sequence && current.isCurrent) {
        showError(const LocalApiException('API_UNAVAILABLE'));
      }
      return false;
    } finally {
      if (mounted && sequence == _sequence) setState(() => busy = false);
    }
  }

  Widget page(String title, List<Widget> children) => SingleChildScrollView(
    padding: const EdgeInsets.all(20),
    child: Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            const Text(
              'Synthetic educational data only. No real money, broker positions or investment advice.',
            ),
            if (error != null)
              Focus(
                key: errorKey,
                focusNode: errorFocus,
                child: LocalErrorNotice(
                  message: error!.code == 'VALIDATION_ERROR'
                      ? 'Check the required fields, exact units and supported versions. Your input was kept; nothing was confirmed saved.'
                      : error!.message,
                ),
              ),
            if (message != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Semantics(liveRegion: true, child: Text(message!)),
              ),
            if (busy)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Semantics(
                  liveRegion: true,
                  child: const Text('Waiting for server confirmation…'),
                ),
              ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    ),
  );
  Widget button(
    String text,
    VoidCallback action, {
    Key? key,
    bool enabled = true,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: AppButton(
      key: key,
      label: text,
      enabled: enabled && !busy,
      onPressed: action,
    ),
  );
  @override
  void dispose() {
    _sequence++;
    _scope?.dispose();
    endOwnedPopup();
    session.removeListener(_sessionChanged);
    errorFocus.dispose();
    super.dispose();
  }
}
