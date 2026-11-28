# Sprint 3 Evidence — `S3-NI03`

- **Task ID:** `S3-NI03`
- **Title:** Goals page progress charts; Spending page and CSV upload on real endpoints
- **Owner:** Nilisha (`@NilishaBhole`)
- **Reviewer:** Payal (`@payalmude14-star`)
- **Branch:** `feature/s3-ni03` (base: `dev`)

---

## 1. Summary of Changes

1. **[frontend-react/src/pages/GoalsPage.tsx](../../frontend-react/src/pages/GoalsPage.tsx)**
   - Removed all hard-coded goal cards (`Weekend away`, `Emergency Cushion`, `Home Down Payment`) and mock creation logic.
   - Added `createGoalsApi` / `defaultGoalsApi` built on `finexApiClient` (`src/services/apiClient.ts`) with Bearer authentication (`getActiveAuthSession()?.access_token ?? sessionStorage.getItem('finex_access_token')`), timeouts, cancellation, and typed error mapping (`401`, `404`, `422`, network failures).
   - Wired all real `S3-LI02` goal endpoints:
     - `GET /api/v1/goals`
     - `POST /api/v1/goals`
     - `PUT /api/v1/goals/{goal_id}`
     - `DELETE /api/v1/goals/{goal_id}`
     - `GET /api/v1/goals/{goal_id}/progress`
     - `GET /api/v1/goals/{goal_id}/contributions`
     - `POST /api/v1/goals/{goal_id}/contributions`
   - Added Recharts visualizations with accessible table alternatives:
     - Overview `BarChart` comparing Current Saved vs Projected Final vs Target Amount across all saved goals (`Chart` / `Table` toggle).
     - Per-goal `AreaChart` plotting yearly `projected_balance`, `contributions_total`, and `growth_total` (`Growth Chart` / `Yearly Schedule` toggle).
   - Added deterministic progress metrics (`progress_pct`, `remaining_amount`, `total_contributed`, `months_remaining`, `required_monthly_contribution` with `null` fallback handling, `monthly_contribution_gap`, `formula_summary`), inline goal editing, two-step goal deletion, contribution recording, and `EDUCATIONAL` capability notice.

2. **[frontend-react/src/pages/SpendingPage.tsx](../../frontend-react/src/pages/SpendingPage.tsx)**
   - Removed all hard-coded spending categories (`Housing & Utilities`, `Groceries & Dining`, `Investment & Savings`, `Weekend & Leisure`) and the simulated upload banner (`42 transactions categorized`).
   - Added `createSpendingApi` / `defaultSpendingApi` built on `finexApiClient` with Bearer authentication, multipart `FormData` upload handling, and typed error mapping (`400`, `401`, `404`, `413`, `415`, `422`).
   - Wired all real spending and `S3-MR02` CSV import endpoints:
     - `GET /api/v1/spending/transactions`
     - `GET /api/v1/spending/trends`
     - `POST /api/v1/spending/imports`
     - `POST /api/v1/spending/correct-category`
   - Added client-side CSV validation (`validateCsvFileSelection`: non-empty, `.csv`/CSV MIME, 5 MiB limit matching backend `MAX_UPLOAD_BYTES`), real upload summary display (`filename`, `total_rows_imported`, `quarantined_rows`, `total_spend_amount`, `categories_detected`), automatic refresh of transactions and trends after upload, Recharts category breakdown `BarChart` + `Table` toggle, inline category correction (`is_user_corrected` badge), and `ANALYTICAL · Privacy Shield Active` disclosure.

3. **Unit & Component Tests**
   - **[frontend-react/src/pages/GoalsPage.test.tsx](../../frontend-react/src/pages/GoalsPage.test.tsx):** 7 tests verifying empty state with zero hard-coded cards, error/retry state, overview `BarChart` + table toggle, create-goal validation & submission, progress `AreaChart` + `null` `required_monthly_contribution` handling + contribution recording, edit/delete flows, and Bearer header propagation.
   - **[frontend-react/src/pages/SpendingPage.test.tsx](../../frontend-react/src/pages/SpendingPage.test.tsx):** 6 tests verifying CSV file validation helper, real spending data rendering with zero hard-coded items, error/retry + empty state, real CSV upload + summary + automatic refresh, inline category correction + trend refresh, and multipart `FormData` + Bearer header transmission.

---

## 2. Acceptance Criteria Verification

- [x] `GoalsPage.tsx`: No hard-coded cards remain; all goal data, progress charts, schedules, and contributions come from `/api/v1/goals*`.
- [x] `SpendingPage.tsx`: No hard-coded categories or simulated CSV upload remain; transactions, trends, category corrections, and CSV imports use `/api/v1/spending/*`.
- [x] Loading, empty, error, validation, and `EDUCATIONAL` / `ANALYTICAL` disclosure states implemented.
- [x] Existing `S3-LI02` and `S3-MR02` backend contracts preserved unchanged.

---

## 3. Verification Commands & Observed Output

### Frontend Checks (`frontend-react/`)

```powershell
Set-Location "frontend-react"
$env:CI = "true"
npx.cmd tsc --noEmit
npm.cmd test -- --watchAll=false
npm.cmd run build
```

- **TypeScript (`npx.cmd tsc --noEmit`):** Exited with code `0` (0 errors).
- **Jest Suite (`CI=true npm.cmd test -- --watchAll=false`):**
  - `Test Suites: 36 passed, 36 total`
  - `Tests:       846 passed, 846 total`
  - `Snapshots:   0 total`
  - `Time:        43.753 s`
  - Includes `src/pages/GoalsPage.test.tsx` and `src/pages/SpendingPage.test.tsx` alongside all existing React parity and journey suites.
- **Production Build (`CI=true npm.cmd run build`):**
  - `Compiled successfully.`
  - `248.67 kB  build\static\js\main.3cbb52b5.js`
  - `6.61 kB    build\static\css\main.7783a283.css`

### Backend Checks (`backend/`)

No backend files were modified in this task; existing backend quality gates and goals/spending suites were executed for contract verification:

```powershell
Set-Location "backend"
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest tests/unit/test_goal_service_s3_li02.py tests/integration/test_s3_li02_goals_api.py tests/unit/test_csv_import_service.py tests/test_s1_pa01_persistence.py -q --no-cov
python -m pytest -m "not postgres" -q --no-cov
```

- **Ruff Lint (`python -m ruff check .`):** `All checks passed!`
- **Ruff Format (`python -m ruff format --check .`):** `392 files already formatted`
- **Mypy (`python -m mypy app`):** `Success: no issues found in 194 source files`
- **Goals & Spending Backend Suite:** `30 passed, 17 warnings in 3.65s`
- **Full Non-Postgres Pytest (`python -m pytest -m "not postgres" -q --no-cov`):** `3154 passed, 4 skipped, 22 deselected, 2 xfailed, 2 xpassed` and `48 failed` (all 48 failures are pre-existing Windows PowerShell `.ps1` launcher tests in `test_local_launcher_boundary.py`, `test_owned_s2_acceptance_launcher.py`, and `test_s1_acceptance_launcher.py` blocked by host PowerShell execution policy `running scripts is disabled on this system`; skipped when `POWERSHELL is None` on Linux CI).
