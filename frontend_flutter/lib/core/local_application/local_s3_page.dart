import 'package:flutter/material.dart';

import '../../shared/widgets/app_button.dart';
import 'local_app_widgets.dart';
import 'local_models.dart';
import 'local_s3_api.dart';
import 'local_session.dart';

abstract class LocalS3Page extends StatefulWidget {
  final LocalSession session;
  const LocalS3Page({super.key, required this.session});
}

/// Page-owned logical cancellation supplements the session's private lease.
/// A transport may ignore cancellation; no result may outlive either guard.
abstract class LocalS3PageState<W extends LocalS3Page> extends State<W> {
  LocalSession get session => widget.session;
  LocalS3Scope? _scope;
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

  @override
  void didUpdateWidget(covariant W oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.session, session)) {
      oldWidget.session.removeListener(_sessionChanged);
      invalidateWork();
      onOwnerReplaced();
      session.addListener(_sessionChanged);
    }
  }

  void onOwnerReplaced();
  void onLeaseInvalidated() {}
  void afterFirstFrame(VoidCallback action) {
    final owner = session;
    final generation = owner.generation;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted &&
          identical(session, owner) &&
          owner.generation == generation) {
        action();
      }
    });
  }

  void _sessionChanged() {
    if (_scope != null && !_scope!.isCurrent) {
      invalidateWork();
      if (mounted) setState(() {});
    }
    onLeaseInvalidated();
  }

  void invalidateWork() {
    _sequence++;
    _scope?.dispose();
    _scope = null;
    busy = false;
  }

  void showError(LocalApiException value) {
    if (!mounted || value.code == 'SESSION_CHANGED') return;
    setState(() {
      error = value;
      message = null;
    });
    final owner = session;
    final generation = owner.generation;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted ||
          !identical(session, owner) ||
          owner.generation != generation ||
          !session.canAccessFeatures) {
        return;
      }
      errorFocus.requestFocus();
      final target = errorKey.currentContext;
      if (target != null) {
        Scrollable.ensureVisible(
          target,
          alignment: .1,
          duration: const Duration(milliseconds: 150),
        );
      }
    });
  }

  Future<bool> request<T>(
    Future<T> Function(LocalS3Scope) operation,
    void Function(T) accept,
  ) async {
    if (busy || !session.canAccessFeatures || session.isBusy) return false;
    _scope?.dispose();
    final current = session.createS3Scope();
    _scope = current;
    final sequence = ++_sequence;
    setState(() {
      busy = true;
      error = null;
      message = null;
    });
    try {
      final value = await operation(current);
      if (!mounted || sequence != _sequence || !current.isCurrent) return false;
      setState(() => accept(value));
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
              'Synthetic educational simulation only. No live market prices, real money or investment advice.',
            ),
            if (error != null)
              Focus(
                key: errorKey,
                focusNode: errorFocus,
                child: LocalErrorNotice(
                  message: error!.code == 'VALIDATION_ERROR'
                      ? 'Check the supported fields and versions. Your input was kept; nothing was confirmed saved.'
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
    String label,
    VoidCallback action, {
    Key? key,
    bool enabled = true,
  }) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: AppButton(
      key: key,
      label: label,
      enabled: enabled && !busy && session.canAccessFeatures,
      onPressed: action,
    ),
  );
  @override
  void dispose() {
    invalidateWork();
    session.removeListener(_sessionChanged);
    errorFocus.dispose();
    super.dispose();
  }
}
