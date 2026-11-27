# S1-NI03 Evidence: Shared UI States & Goals/Alerts/Ops Wiring

- **Task ID:** `S1-NI03`
- **Sprint:** Sprint 1: Identity & Onboarding Pilot (`feature/s1-ni03` -> `dev`)
- **Owner:** Nilisha (`@NilishaBhole`)
- **Secondary Reviewer:** Payal (`@payalmude14-star`)
- **Repository:** `Mrugankkakade17-svg/Finex` (`origin/dev`)
- **Pull Request:** `#152`

---

## 1. Files Created & Modified

### Created
- `frontend-react/src/components/SharedStates.css`
- `frontend-react/src/components/LoadingState.tsx`
- `frontend-react/src/components/EmptyState.tsx`
- `frontend-react/src/components/ErrorState.tsx`
- `frontend-react/src/components/CapabilityBanner.tsx`
- `frontend-react/src/components/index.ts`
- `frontend-react/src/components/SharedStates.test.tsx`
- `frontend-react/src/services/platformApi.ts`
- `frontend-react/src/services/platformApi.test.ts`
- `frontend-react/src/pages/GoalsPage.test.tsx`
- `frontend-react/src/pages/AlertsPage.test.tsx`
- `frontend-react/src/pages/OpsPage.test.tsx`
- `docs/evidence/s1_ni03_evidence.md`

### Modified
- `frontend-react/src/context/LocalSessionContext.tsx` (in-memory local bearer registration for `platformApi`, cleared on `endSession`/`unmount`)
- `frontend-react/src/pages/GoalsPage.tsx`
- `frontend-react/src/pages/AlertsPage.tsx`
- `frontend-react/src/pages/OpsPage.tsx`

---

## 2. Implementation & PR #152 Review Resolution

1. **Shared UI State Components (`frontend-react/src/components/`):**
   - `LoadingState`: Accessible `role="status"` + `aria-busy="true"` loading panel styled with Good Money Energy / Ledger in Orbit tokens.
   - `EmptyState`: Consistent empty-data card with optional primary CTA button.
   - `ErrorState`: Accessible `role="alert"` error panel displaying safe user messages, machine error codes, and an optional `Retry` action.
   - `CapabilityBanner`: Displays capability classification (`EDUCATIONAL`, `ANALYTICAL`, `SIMULATED`, `OPERATIONS`), live status (`AVAILABLE`, `LIMITED`, `UNAVAILABLE`), and honest limitations/acceptance notes.

2. **Authenticated Platform API Client (`frontend-react/src/services/platformApi.ts`):**
   - Routes all HTTP requests through the shared `finexApiClient` (`frontend-react/src/services/apiClient.ts`) with no hardcoded origins.
   - Resolves the PR #152 blocking review comment by wiring `getActivePlatformBearerToken` into the default `platformApi` instance (`getActiveAuthSession()?.access_token` from `authService.ts` for real-account JWT sessions, falling back to the active in-memory local persona token registered by `LocalSessionContext.tsx` and cleared on logout/expiry/unmount).
   - Decodes the FinEx v1 `{ success, message, data, meta }` envelope and maps HTTP `401`, `403`, `404`, `422`, timeouts, and unreachable backend failures to `PlatformApiError`.
   - Probes `GET /api/v1/capabilities` (`data.capabilities` map) and handles `404` or unaccepted capability flags cleanly.

3. **Wired Pages (`GoalsPage.tsx`, `AlertsPage.tsx`, `OpsPage.tsx`):**
   - **`GoalsPage.tsx`:** Wired to `GET /api/v1/goals` and `POST /api/v1/goals` with client validation, yearly compounding schedule viewer, `EDUCATIONAL` capability banner, and loading/empty/error states.
   - **`AlertsPage.tsx`:** Restored cleanly after merging `dev` and wired to `GET /api/v1/alerts/notifications`, `POST /api/v1/alerts/notifications/{notif_id}/read`, `GET /api/v1/alerts/rules`, `POST /api/v1/alerts/rules`, and `DELETE /api/v1/alerts/rules/{rule_id}` with `ANALYTICAL` capability banner and loading/empty/error states.
   - **`OpsPage.tsx`:** Wired to `GET /api/v1/ops/observability`, `GET /api/v1/ops/flags`, `POST /api/v1/ops/flags/{flag_key}/toggle`, and `GET /api/v1/ops/preflight` with `OPERATIONS` capability banner, `403` admin-rejection handling, and loading/empty/error states.

---

## 3. Verification Commands & Results

```powershell
cd frontend-react
$env:CI="true"
npm.cmd test -- --runInBand --watchAll=false
node node_modules/typescript/bin/tsc --noEmit
npm.cmd run build
```

- **React Test Suite:** `Test Suites: 35 passed, 35 total` | `Tests: 828 passed, 828 total` (`85.442 s`).
  - Includes 5 new test suites covering `SharedStates`, `platformApi`, `GoalsPage`, `AlertsPage`, and `OpsPage`: loading, empty, error/retry, capability banner, `403` non-admin rejection, stateful reload persistence, and default `platformApi`/page path assertions verifying `Authorization: Bearer <token>` headers from both `realAuthService` and `LocalSessionProvider`.
- **TypeScript (`tsc --noEmit`):** Exit code `0`.
- **Production Build (`npm.cmd run build`):** Compiled successfully (`112.66 kB` JS, `7.19 kB` CSS gzip).
