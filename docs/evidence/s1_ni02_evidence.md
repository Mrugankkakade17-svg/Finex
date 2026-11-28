# S1-NI02 implementation evidence

## Scope

Provide registration and email/password sign-in UI behind an explicit frontend feature flag (`REACT_APP_ENABLE_REAL_AUTH=true`) while retaining the local synthetic-persona sign-in by default and preserving PR #150's Good Money Energy & Ledger in Orbit UI redesign and dynamic demo login in `LoginPage.tsx`. The UI uses the merged S1-LI02 API contract: `POST /api/v1/auth/register` with `{name, email, password}` and `POST /api/v1/auth/login` with `{email, password}`. Successful responses return tokens in the shared `data` envelope.

## Implementation & PR #151 Review Resolution

- `frontend-react/src/pages/RealAccountLoginPage.tsx`: Isolated component for real-account registration and sign-in, preserving `frontend-react/src/pages/LoginPage.tsx` (PR #150 UI and dynamic demo login) untouched.
- `frontend-react/src/App.tsx`: Merged latest `origin/dev` (`AuthProvider` / `AppRoutes` structure) and switches `/login` between `<RealAccountLoginPage />` (when `REACT_APP_ENABLE_REAL_AUTH === 'true'`) and `<LocalLoginPage />` (default).
- Password clearing: Clears `password` from React state and resets the password input in the UI after both successful registration-to-login transitions and successful direct logins.
- Validation & HTTP 422 handling: Validates `name` after `.trim()` (rejecting whitespace-only and `< 2` character names after trimming with field-level messages), validates `email` and `password`, and maps backend HTTP 422 `VALIDATION_ERROR` `fieldErrors` to accessible field-level validation messages.
- `frontend-react/src/services/apiClient.ts` & `frontend-react/src/services/authService.ts`: Merged `origin/dev`'s PR #150 `authService` alongside `realAuthService`, keeps real-account JWT tokens in memory only (never `localStorage` or `sessionStorage`), and maps `EMAIL_EXISTS`, `INVALID_CREDENTIALS`, `RATE_LIMIT_EXCEEDED`, `DATABASE_UNAVAILABLE`, `VALIDATION_ERROR` (HTTP 422), and unexpected/unreadable errors safely without exposing backend internals or passwords.
- Tests added:
  - `frontend-react/src/pages/RealAccountLoginPage.test.tsx`: Component tests covering form rendering/mode switching, `.trim()` full-name validation, registration-to-login and direct-login password clearing, memory-only token storage, HTTP 422 `VALIDATION_ERROR` field errors, and API failure mapping.
  - `frontend-react/src/pages/LoginPage.test.tsx`: Regression tests verifying PR #150 `LoginPage.tsx` UI and dynamic/demo login remain intact.
  - `frontend-react/src/services/apiClient.test.ts`: Added tests for `INVALID_CREDENTIALS`, `RATE_LIMIT_EXCEEDED`, `DATABASE_UNAVAILABLE`, `VALIDATION_ERROR` / HTTP 422, unexpected/unreadable responses, and preserved `authService` behavior.
  - `frontend-react/src/App.local.test.tsx`: Verified both `REACT_APP_ENABLE_REAL_AUTH='false'` and `'true'` states and confirmed real-account mode does not unlock local persona routes.

## Verification

Commands run from `frontend-react` after resolving conflicts with `origin/dev` and implementing all review changes:

```text
npm.cmd test -- --watchAll=false --runInBand
Test Suites: 30 passed, 30 total
Tests:       785 passed, 785 total

npm.cmd test -- --watchAll=false --runInBand --runTestsByPath src/App.local.test.tsx src/services/apiClient.test.ts src/pages/RealAccountLoginPage.test.tsx src/pages/LoginPage.test.tsx
Test Suites: 4 passed, 4 total
Tests:       38 passed, 38 total

node .\node_modules\typescript\bin\tsc --noEmit
Exited with code 0

npm.cmd run build
Compiled successfully.
```

## Completion and limits

- Merged latest `origin/dev` into `feature/s1-ni02`, resolved conflicts in `frontend-react/src/App.tsx`, `frontend-react/src/pages/LoginPage.tsx`, and `frontend-react/src/services/authService.ts`, and verified tests, TypeScript check, and production build.
- Real-account tokens remain in memory only and do not authorize the separate synthetic local-application routes; connecting those routes remains outside S1-NI02's scope.
