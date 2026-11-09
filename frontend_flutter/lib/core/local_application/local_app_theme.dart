import 'package:flutter/material.dart';

/// Scoped to the owned application; the already-tested pilot keeps its theme.
ThemeData localApplicationTheme(ThemeData base) {
  const primary = Color(0xff047857); // White text: 5.48:1.
  const focus = Color(0xfffbbf24);
  const helper = Color(0xff94a3b8); // On #0f172a: 6.96:1.
  final focusSide = WidgetStateProperty.resolveWith<BorderSide>(
    (states) => states.contains(WidgetState.focused)
        ? const BorderSide(color: focus, width: 2)
        : BorderSide.none,
  );
  final minimum = const WidgetStatePropertyAll(Size(48, 48));
  return base.copyWith(
    colorScheme: base.colorScheme.copyWith(
      primary: primary,
      onPrimary: Colors.white,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ButtonStyle(
        backgroundColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.disabled)
              ? const Color(0xff334155)
              : primary,
        ),
        foregroundColor: const WidgetStatePropertyAll(Colors.white),
        minimumSize: minimum,
        side: focusSide,
        padding: const WidgetStatePropertyAll(
          EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        foregroundColor: const WidgetStatePropertyAll(Colors.white),
        minimumSize: minimum,
        side: focusSide,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: ButtonStyle(
        foregroundColor: const WidgetStatePropertyAll(Colors.white),
        minimumSize: minimum,
        side: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.focused)
              ? const BorderSide(color: focus, width: 2)
              : const BorderSide(color: helper),
        ),
        padding: const WidgetStatePropertyAll(
          EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        ),
      ),
    ),
    inputDecorationTheme: base.inputDecorationTheme.copyWith(
      helperStyle: const TextStyle(color: helper),
      helperMaxLines: 3,
      hintStyle: const TextStyle(color: helper),
      focusedBorder: const OutlineInputBorder(
        borderSide: BorderSide(color: focus, width: 2),
      ),
    ),
    checkboxTheme: base.checkboxTheme.copyWith(
      fillColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected)
            ? primary
            : const Color(0xff334155),
      ),
      checkColor: const WidgetStatePropertyAll(Colors.white),
      overlayColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.focused)
            ? focus.withValues(alpha: .25)
            : null,
      ),
    ),
  );
}
