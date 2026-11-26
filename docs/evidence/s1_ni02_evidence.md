# S1-NI02 implementation evidence

## Scope

Provide registration and email/password sign-in UI behind an explicit frontend feature flag while retaining the local synthetic-persona sign-in by default. The UI uses the merged S1-LI02 API contract: `POST /api/v1/auth/register` with `{name, email, password}` and `POST /api/v1/auth/login` with `{email, password}`. Successful responses contain the tokens in the shared `data` envelope. S1-LI02 reports `EMAIL_EXISTS` for a duplicate registration and `RATE_LIMIT_EXCEEDED` for throttled login.

## Implementation

- `frontend-react/src/App.tsx` reads `REACT_APP_ENABLE_REAL_AUTH`. Only the exact string `true` selects the real-account screen at `/login`; the default remains `LocalLoginPage`.
- `frontend-react/src/pages/LoginPage.tsx` provides sign-in and registration forms, native field validation, pending state, and safe success/error feedback.
- `frontend-react/src/services/authService.ts` adds `realAuthService`, validates the auth response envelope, calls the existing auth endpoints, maps known safe errors, and keeps login tokens in module memory only. Registration responses do not activate a session. The old service exports remain for disconnected legacy components so they continue to compile.
- The real-account page does not imply that a legacy JWT unlocks the local educational application's synthetic-persona routes.
- `frontend-react/README.md` documents the flag and its scope.

## Verification

Commands run from `frontend-react`:

```text
npm test -- --watchAll=false --runInBand
Test Suites: 28 passed, 28 total
Tests:       766 passed, 766 total

npm test -- --watchAll=false --runInBand --runTestsByPath src/App.local.test.tsx src/services/apiClient.test.ts
Test Suites: 2 passed, 2 total
Tests:       19 passed, 19 total

npm run build
Compiled successfully.
```

The local-login/feature-flag test and API contract tests are in `App.local.test.tsx` and `services/apiClient.test.ts`. The production build emitted only the existing dependency deprecation warning for `fs.F_OK`.

## Completion and limits

- Registration/sign-in UI, flag-off local behavior, API request/response checks, and React production build: complete.
- No database migration was needed in this frontend-only task.
- The project folder was supplied as a ZIP and contains no `.git` directory. A local `feature/s1-ni02` branch or commit could not be created in this checkout.
- No reviewer was assigned, as requested by the task owner.
- Real-account tokens do not authorize the separate synthetic local-application routes; that remains outside S1-NI02's UI acceptance scope.

