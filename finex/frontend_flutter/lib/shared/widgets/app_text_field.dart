import 'package:flutter/material.dart';

class AppTextField extends StatelessWidget {
  final String label;
  final String? hint;
  final TextEditingController? controller;
  final String? errorText;
  final bool enabled;
  final bool loading;
  final TextInputType? keyboardType;
  final ValueChanged<String>? onChanged;

  const AppTextField({
    super.key,
    required this.label,
    this.hint,
    this.controller,
    this.errorText,
    this.enabled = true,
    this.loading = false,
    this.keyboardType,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final isEnabled = enabled && !loading;

    return TextField(
      controller: controller,
      enabled: isEnabled,
      keyboardType: keyboardType,
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        errorText: errorText,
        suffixIcon: loading
            ? const Padding(
                padding: EdgeInsets.all(12),
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                  ),
                ),
              )
            : null,
      ),
    );
  }
}