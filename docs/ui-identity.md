# UI identity to preserve

This is the S0-NI01 visual baseline for the existing React web app and Flutter app. Preserve these established colors, type choices, component shapes, and accessibility cues when extending screens. This is a reference record; it does not introduce a new design system or change existing styles.

## React web

Primary source: `frontend-react/src/index.css`.

| Token | Current value | Use |
| --- | --- | --- |
| `--bg-dark` | `#0b0f19` | Global page background. |
| `--bg-card` | `rgba(15, 23, 42, 0.75)` | Glass card surface. |
| `--bg-card-hover` | `rgba(30, 41, 59, 0.85)` | Hovered card surface. |
| `--bg-sidebar` | `rgba(15, 23, 42, 0.95)` | Sidebar surface. |
| `--bg-input` | `rgba(30, 41, 59, 0.6)` | Input surface. |
| `--primary-emerald` | `#10b981` | Primary action and positive/success accent. |
| `--primary-emerald-glow` | `rgba(16, 185, 129, 0.25)` | Primary action glow. |
| `--accent-indigo` | `#6366f1` | Secondary accent. |
| `--accent-cyan` | `#06b6d4` | Tertiary accent. |
| `--accent-purple` | `#a855f7` | Tertiary accent. |
| `--text-primary` | `#f8fafc` | Primary text. |
| `--text-secondary` | `#94a3b8` | Secondary text. |
| `--text-muted` | `#64748b` | Muted text. |
| `--status-success` | `#10b981` | Success status. |
| `--status-warning` | `#f59e0b` | Warning status. |
| `--status-error` | `#ef4444` | Error status. |
| `--status-info` | `#3b82f6` | Informational status. |
| `--border-glass` | `rgba(255, 255, 255, 0.08)` | Default glass border. |
| `--border-glass-hover` | `rgba(255, 255, 255, 0.18)` | Hover glass border. |
| `--shadow-glass` | `0 8px 32px 0 rgba(0, 0, 0, 0.37)` | Glass card shadow. |
| `--shadow-glow` | `0 0 20px rgba(16, 185, 129, 0.15)` | Emerald ambient glow. |
| `--radius-sm` / `--radius-md` / `--radius-lg` / `--radius-full` | `6px` / `12px` / `20px` / `9999px` | Small, standard, large, and pill corners. |
| `--transition-fast` / `--transition-normal` | `0.15s ease` / `0.3s ease` | Interaction timing. |

Typography is `Inter`, then system sans-serif for body text. Headings use `Outfit`, then `Inter`, sans-serif; they are bold with `-0.02em` letter spacing. Primary and secondary buttons use the same emerald-led dark theme, and shared cards use a translucent glass surface, blur, border, and shadow. The global body uses a dark background with indigo, emerald, and cyan radial accents.

## Flutter

The repository has a general app theme at `frontend_flutter/lib/core/theme/app_theme.dart` and a separate owned local-application theme at `frontend_flutter/lib/core/local_application/local_app_theme.dart`. Keep their scope distinct: the local application theme explicitly layers accessibility-focused styling on its owned flow while preserving the existing pilot theme.

| Token or behavior | Current value | Source |
| --- | --- | --- |
| Primary | `#10B981` | `AppTheme.primary` |
| Secondary | `#6366F1` | `AppTheme.secondary` |
| Background | `#0F172A` | `AppTheme.background` |
| Surface | `#111827` | `AppTheme.surface` |
| Primary text | `#FFFFFF` | `AppTheme.textPrimary` |
| Secondary text | `#94A3B8` | `AppTheme.textSecondary` |
| Border | `#334155` | `AppTheme.border` |
| General input corners | `10px` | `AppTheme.darkTheme` |
| General card corners | `12px` | `AppTheme.darkTheme` |
| Local-flow primary | `#047857` | `localApplicationTheme` |
| Local-flow focus indicator | `#FBBF24`, `2px` | `localApplicationTheme` |
| Local-flow helper/hint text | `#94A3B8` | `localApplicationTheme` |
| Local-flow minimum interactive target | `48 x 48` logical pixels | `localApplicationTheme` button themes |

The general app uses Material 3 dark mode. Its local-application layer keeps white button labels, a clearly visible yellow keyboard-focus border, helper text with recorded contrast guidance, and 48-pixel minimum button targets. Preserve these properties when adjusting the local flow.

## Shared product identity and safety cues

- Keep the dark FinEx base with emerald as the primary action/positive accent and indigo as the secondary accent.
- Preserve existing page routes and component behavior while applying visual changes.
- Keep success, warning, error, and informational states visually distinct and textually clear; do not rely on color alone for meaning.
- Preserve keyboard focus visibility and comfortable touch targets in the Flutter local flow.
- Keep educational and simulated product labels visible where the handbook requires them; do not style simulated financial values as real account balances.

## Source references

- React tokens: `frontend-react/src/index.css`.
- Flutter shared theme: `frontend_flutter/lib/core/theme/app_theme.dart`.
- Flutter local-flow overlay: `frontend_flutter/lib/core/local_application/local_app_theme.dart`.
- Architecture and UI safety requirements: supplied FinEx Final Implementation Plan, sections 1, 3, and 6.
