# S1-NI01 evidence

## Scope

One shared React API transport and removal of hard-coded backend origins from application request code. The screenshot identifies the new file as `frontend-react/src/services/apiClient.ts`; the pasted issue text truncates this path as `t.ts`.

## Implementation

- Added `frontend-react/src/services/apiClient.ts` to resolve and validate the configured API origin, send JSON-friendly requests, optionally attach a Bearer token, omit cookies, reject redirects, and disable response caching.
- Routed Chat and Release page requests through the shared client.
- Routed the existing onboarding, risk, local application, and local S2 services through the shared transport while preserving their route-specific response validation, local-origin restrictions, cancellation, timeouts, and payloads.
- Kept the default development API origin in the shared configuration module. A frontend source scan found no other literal loopback API origin in non-test application code.
- No backend routes, database schemas, migrations, or persistent-storage behavior changed.

## Verification

Commands run from `frontend-react`:

```text
npm ci --ignore-scripts --no-audit --no-fund
npm test -- --runInBand
Test Suites: 28 passed, 28 total
Tests:       762 passed, 762 total
npm run build
Compiled successfully.
After the final transport default change, 7 targeted suites / 126 tests passed and the production build compiled successfully (97.77 kB JS / 3.79 kB CSS gzip).
```

Commands run from `backend`:

```text
python -m ruff check .
All checks passed!

$env:PSExecutionPolicyPreference = 'Bypass' (this test process only)
python -m pytest -q --no-cov -p no:cacheprovider
2628 passed, 2173 warnings in 637.87s
```

The first full backend run hit Windows execution policy in 10 launcher tests. I reran those and the full suite with a process-only execution-policy setting; all tests passed. No machine-wide policy was changed, and no backend source was changed for S1-NI01.

## Acceptance status and limits

- Shared client, configurable origin, no hard-coded application request origins, React tests, and production build: complete.
- Backend Ruff: passed.
- Backend pytest: all 2,628 tests passed. The final rerun used a process-only policy setting; the machine-wide policy was not changed.
- Authentication: the shared client sends Bearer tokens when supplied, and existing session-bound local clients use it. The current Chat and Release backend routes have no documented auth contract or token source in those pages, so their existing tokenless behavior is preserved. If S1-NI01 requires those routes to become authenticated, that needs an explicit backend/session contract.
- No database migration was applicable.
- The assignment PDF was reviewed. Its S1-NI01 row confirms the shared API client, the Chat and Release pages, onboarding and risk contracts, and the no-literal-origin acceptance criterion.
- Changes are committed on `feature/s1-ni01`, based on `dev`. No PR was opened and no reviewer was assigned, per the user's instruction.
