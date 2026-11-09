import 'package:flutter/material.dart';

class AppButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final bool enabled;
  final IconData? icon;

  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.enabled = true,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final isEnabled = enabled && !loading && onPressed != null;

    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 48),
      child: ElevatedButton(
        onPressed: isEnabled ? onPressed : null,
        child: loading
            ? Semantics(
                label: '$label in progress',
                liveRegion: true,
                child: ExcludeSemantics(
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      const SizedBox(width: 8),
                      Flexible(child: Text(label, textAlign: TextAlign.center)),
                    ],
                  ),
                ),
              )
            : Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (icon != null) ...[
                    Icon(icon, size: 18),
                    const SizedBox(width: 8),
                  ],
                  Flexible(child: Text(label, textAlign: TextAlign.center)),
                ],
              ),
      ),
    );
  }
}
