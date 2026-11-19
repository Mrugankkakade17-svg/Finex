# Frontend baseline (S0-NI01)

**Measured:** 2026-11-19
**Source:** the supplied `Finex-main` ZIP, inspected without its `.git` directory.
**Scope:** baseline only; no application source, route, or persistence code was changed.

## Repository and toolchain

| Area | As found | Baseline result |
| --- | --- | --- |
| React | `frontend-react/`, Create React App (`react-scripts` 5.0.1), React 18.2, Node requirement in root README: 24.20.0 | Node.js 24.20.0 and npm 11.19.0 available. `npm ci`, all React tests, and production build completed successfully. |
| Flutter | `frontend_flutter/`, Flutter app using Dart SDK constraint `^3.13.0`; repository README specifies Flutter 3.47.2 / Dart 3.13 | Dart 3.13.2 is available in the SDK at `C:\flutter`. Flutter tool launch is blocked because the SDK cache is not writable in this session; Flutter checks remain unrun. |
| Git state | ZIP source provided without repository metadata | Branch, commit, and dirty-state baseline cannot be determined from this ZIP. |

## React commands

Commands were run from `frontend-react/`.

| Command | Result |
| --- | --- |
| `npm ci` | **Passed.** Installed 1,340 packages. npm reported 44 dependency audit findings (9 low, 8 moderate, 25 high, 2 critical). Two dependency install scripts (`core-js` and `core-js-pure`) were not approved by npm's install-script policy. The lockfile was not changed. |
| `npm test -- --watchAll=false` | **Passed.** 25 test suites and 754 tests passed; 0 snapshots. React Router emitted existing v7 future-flag warnings. |
| `npm run build` | **Passed.** Create React App produced an optimized production build. Node emitted a deprecation warning for `fs.F_OK`. |

The npm audit findings are dependency-level warnings from the installed lockfile. This baseline task did not update dependency versions or run `npm audit fix`.

## Flutter commands

The direct Dart executable reports `Dart SDK version: 3.13.2 (stable)`.

| Command | Result |
| --- | --- |
| Flutter tool version | **Blocked.** Both `flutter.bat --version` and direct invocation of the SDK tool snapshot failed: `Flutter failed to open a file at "C:\flutter\bin\cache\lockfile"`. |
| `flutter pub get` | **Attempted; blocked before package resolution.** Flutter could not open `C:\flutter\bin\cache\lockfile` (exit `-1073741816`). |
| `flutter analyze` | **Attempted; blocked before analysis** by the same SDK cache error (exit `-1073741816`). |
| `flutter test` | **Attempted; blocked before tests** by the same SDK cache error (exit `-1073741816`). |

Flutter dependency resolution, analysis, and test counts remain unmeasured. Do not interpret this as a clean Flutter baseline.

## Runtime API origins found

The following client runtime source files contain a local API origin literal. Test fixtures and package-lock URLs are excluded. The local origin is expected for the current local development setup; direct calls bypass the intended shared/configured client and should be addressed under the handbook's later S1-NI01 task, not this baseline-only task.

| Client | File | Occurrence |
| --- | --- | --- |
| React | `frontend-react/src/pages/ChatPage.tsx` | Direct fetch to `http://127.0.0.1:8000/api/v1/ai/chat`. |
| React | `frontend-react/src/pages/ReleasePage.tsx` | Direct fetches to `/api/v1/release/handover` and `/api/v1/release/uat-signoffs` at `http://127.0.0.1:8000`. |
| React | `frontend-react/src/services/localApplicationClient.ts` | Default local API origin; also allows `REACT_APP_FINEX_API_BASE_URL`. |
| React | `frontend-react/src/services/localS2Client.ts` | Default local API origin; also allows `REACT_APP_FINEX_API_BASE_URL`. |
| React | `frontend-react/src/services/onboardingContract.ts` | Default local API origin; allows `REACT_APP_FINEX_API_BASE_URL`. |
| React | `frontend-react/src/services/riskContract.ts` | Default local API origin; allows `REACT_APP_FINEX_API_BASE_URL`. |
| Flutter | `frontend_flutter/lib/core/local_application/local_api_client.dart` | Default local API origin, configurable through the client environment configuration. |
| Flutter | `frontend_flutter/lib/features/onboarding/models/s1_onboarding_contract.dart` | Default local API origin. |
| Flutter | `frontend_flutter/lib/features/risk/presentation/s2_risk_page.dart` | Default local API origin. |

The React auth/profile code also references an Unsplash image URL for an avatar. It is an image resource, not an API base origin.

## Baseline limits

- The ZIP does not provide Git history or status, so no branch/commit statement can be made.
- React dependencies were installed from the lockfile; the lockfile was not modified. Generated `node_modules` and build output are not part of the deliverable archive.
- The Flutter commands must be rerun from `frontend_flutter/` in an environment where the SDK cache under `C:\flutter\bin\cache` is writable before the full baseline can be considered green.
- This issue does not authorize or require changes to the React API calls, Flutter API client, frozen routes, or persistence.
