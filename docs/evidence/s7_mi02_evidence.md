# S7-MI02 Evidence: Flutter Paper Trading and Goals Screens

## 1. Issue Details
- **Issue:** #102 — `[Sprint 7] [S7-MI02] Flutter: paper trading and goals screens`
- **Task ID:** `S7-MI02`
- **Assignee / Owner:** Mitali (`@mitali2701`)
- **Secondary Reviewer:** Mrugnak (`@Mrugankkakade17-svg`)
- **Feature Branch:** `feature/s7-mi02`
- **Target Base Branch:** `dev`
- **Pull Request:** [PR #164](https://github.com/Mrugankkakade17-svg/Finex/pull/164)
- **Latest Commit SHA:** `ab62470637d51a5fb3c103851101d79f9ffc2cf4`
- **GitHub Actions CI Status:** 16 of 16 checks passed (100% green)
- **Primary Acceptance Criterion:** `flutter test green`

---

## 2. Dependency #40 Verification (S2-PA04)
- **Task:** `S2-PA04` — Paper trading service and `/paper` router: idempotent orders, eligible-quote rule, fees from config, ledger entries, positions
- **Issue:** #40 (Closed)
- **PR:** [#146](https://github.com/Mrugankkakade17-svg/Finex/pull/146) — `[S2-PA04] Add ledger-backed paper trading`
- **Merge State:** MERGED into `dev` on 2026-11-24T07:59:40Z by `@Mrugankkakade17-svg`
- **Backend Verified Endpoints:**
  - `GET /api/v1/paper/account` (account balances, positions, recent orders)
  - `GET /api/v1/paper/positions` (open positions with average cost, market value, unrealized PnL)
  - `GET /api/v1/paper/orders` (recent order history)
  - `POST /api/v1/paper/orders` (idempotent paper market order execution)

---

## 3. Dependency #27 Verification (S1-LI03)
- **Task:** `S1-LI03` — Goals behind principal and persistent repository
- **Issue:** #27
- **PR:** [#135](https://github.com/Mrugankkakade17-svg/Finex/pull/135) — `[Sprint 1] [S1-LI03] Goals behind principal and persistent repository`
- **Merge State:** MERGED into `dev` on 2026-11-24T09:03:33Z by `@Mrugankkakade17-svg`
- **Backend Verified Endpoints:**
  - `GET /api/v1/goals` (user-scoped goals retrieval behind `current_principal`)
  - `POST /api/v1/goals` (goal creation with deterministic compound projections)
  - `GET /api/v1/goals/{id}` (goal details and projections breakdown)

---

## 4. Authoritative Documents Consulted
1. `FinEx Final Implementation Plan.pdf` — Sprint 7 tasks, S7-MI02 requirements, Flutter delivery standards.
2. `FinEx Final Implementation Plan - Updated Assignments.pdf` — Owner Mitali (`@mitali2701`), Reviewer Mrugnak (`@Mrugankkakade17-svg`).
3. `FinEx_Master_Product_Design_Delivery_Handbook_v9.1.pdf` — Visual quality, dark calm styling, state management, accessibility, touch targets >= 44px, and user isolation.

---

## 5. Existing Flutter Architecture Inspected
- Inspected `frontend_flutter/lib/core/` (router, local_application, session, theme).
- Verified `LocalSession` lifecycle, owner generations, domain epochs, and revocable leases.
- Preserved existing prototype compatibility seam where `FakeLocalApi` routes to `LocalPendingPage` while real sessions route to `PaperTradingPage` and `GoalsPage`.
- Reused design tokens, `AppCard`, `AppButton`, `EmptyView`, `ErrorView`, `LoadingView`, and established theming.

---

## 6. Backend API Contracts Inspected
- `backend/app/routers/paper.py` & `backend/app/schemas/paper.py`:
  - `PaperOrderRequest`: `instrument_id`, `exchange`, `side`, `quantity`, `idempotency_key`
  - `PaperOrder`: `order_id`, `instrument_id`, `exchange`, `side`, `quantity`, `executed_price`, `notional`, `fee`, `cash_delta`, `status`, `quote_freshness`, `quote_as_of`, `created_at`, `simulation_notice`
  - `PaperPosition`: `instrument_id`, `exchange`, `quantity`, `average_cost`, `last_price`, `market_value`, `unrealized_pnl`
  - `PaperAccount`: `account_id`, `currency`, `cash_balance`, `portfolio_value`, `total_equity`, `positions`, `recent_orders`, `is_simulated`
- `backend/app/routers/goals.py` & `backend/app/schemas/sprint4_paper_goals.py`:
  - `GoalCreateRequest`: `title`, `target_amount`, `current_amount`, `horizon_years`, `monthly_contribution`, `expected_annual_return_pct`
  - `GoalProjection`: `year`, `projected_balance`, `contributions_total`, `growth_total`
  - `GoalResponse`: `goal_id`, `title`, `target_amount`, `current_amount`, `horizon_years`, `monthly_contribution`, `expected_annual_return_pct`, `projected_final_amount`, `shortfall_or_surplus`, `is_on_track`, `assumptions_statement`, `projections`

---

## 7. Files Changed
### Created Files
- `frontend_flutter/lib/features/paper_trading/models/paper_trading_models.dart`: Type-safe request/response DTOs matching backend schema.
- `frontend_flutter/lib/features/paper_trading/services/paper_trading_service.dart`: HTTP client service with error mapping and bearer injection.
- `frontend_flutter/lib/features/paper_trading/presentation/paper_trading_page.dart`: Full-featured paper trading screen.
- `frontend_flutter/lib/features/goals/models/goal_models.dart`: Type-safe goals DTOs matching backend schema.
- `frontend_flutter/lib/features/goals/services/goal_service.dart`: Goals HTTP client service with error mapping and bearer injection.
- `frontend_flutter/lib/features/goals/presentation/goals_page.dart`: Full-featured financial goals & projections screen.
- `frontend_flutter/test/paper_trading_models_test.dart`: Unit tests for paper trading models.
- `frontend_flutter/test/paper_trading_service_test.dart`: Unit tests for paper trading service and error cases.
- `frontend_flutter/test/paper_trading_page_test.dart`: Comprehensive widget tests for PaperTradingPage.
- `frontend_flutter/test/goal_models_test.dart`: Unit tests for goal models and progress calculations.
- `frontend_flutter/test/goal_service_test.dart`: Unit tests for goal service and error cases.
- `frontend_flutter/test/goals_page_test.dart`: Comprehensive widget tests for GoalsPage.
- `frontend_flutter/test/paper_and_goals_contract_parity_test.dart`: Contract parity tests against backend response shapes.
- `docs/evidence/s7_mi02_evidence.md`: Comprehensive delivery evidence.

### Modified Files
- `frontend_flutter/lib/core/local_application/local_session.dart`: Added `isPendingSprint(int sprint)` and `getBearerToken()` helper.
- `frontend_flutter/lib/core/router/app_router.dart`: Wired `/paper-trading` and `/goals` to active screens.
- `frontend_flutter/lib/shared/widgets/app_shell.dart`: Dynamically wired navigation destinations to active screens.

---

## 8. Paper Trading Features Implemented
- Educational simulation banner prominently informing learners that no real funds or broker execution are involved.
- Real account overview displaying cash balance, portfolio value, total equity, and currency (USD).
- Interactive order entry ticket supporting symbol input, quick symbol chips (AAPL, SPY, MSFT, NVDA, GOOGL), BUY/SELL chip selection, exchange dropdown (NASDAQ/NYSE), and quantity.
- Client-side input validation for symbol and quantity (positive integer <= 100,000).
- Idempotency key generation (`pt-<symbol>-<side>-<timestamp>-<rand>`) with key reuse on retry.
- Open positions / holdings list with average cost, quantity, current market value, and colored unrealized PnL.
- Order history list displaying execution price, fees, total amount, side badge, and quote freshness indicator (LIVE/DELAYED/CACHED).
- Manual account refresh button.

---

## 9. Goals Features Implemented
- Educational planning banner clarifying deterministic compounding assumptions and non-personal advice disclaimer.
- Goal list displaying saved user goals, on-track vs. shortfall badge, progress bar, current vs. target amount, horizon, and monthly deposit.
- Expandable projections breakdown table showing year-by-year projected total balance, cumulative contributions, and compounded growth.
- Goal creation form with validation for title (1..100 chars), target (> 0), current (>= 0), horizon (1..50 yrs), monthly deposit (>= 0), and expected return (0..30%).
- Server-confirmed persistence with automated projection calculation.
- Manual goals refresh button.

---

## 10. Screen States Coverage
Both screens implement and test the complete state matrix:
1. **Initial loading:** `LoadingView` with contextual loading message.
2. **Success loaded:** Rendered data cards with live account and goal metrics.
3. **Empty state:** `EmptyView` with helpful onboarding prompts.
4. **Form validation state:** In-form error text for missing or out-of-range fields.
5. **Submission in progress:** Disabled buttons and loading indicators preventing accidental duplicate taps.
6. **API error state:** User-facing error message with safe explanation.
7. **Network error state:** Retryable notice without exposing stack traces or raw tokens.
8. **Rejection state:** Clear rejection message (e.g. `MARKET_CLOSED`, `INSUFFICIENT_FUNDS`).
9. **Safe retry state:** Retry button preserving the exact original logical idempotency key.

---

## 11. Accessibility Verification
- Minimum touch targets: All interactive buttons and inputs meet or exceed 48px height.
- Semantic announcements: Live regions (`Semantics(liveRegion: true)`) for success and error announcements.
- Status by color: Status badges combine color and explicit text (e.g., "ON TRACK", "SHORTFALL", "BUY", "SELL", "LIVE").
- Scalable text: Flexible layouts using `SingleChildScrollView` and `Wrap` preventing pixel overflow on compact views (320px).

---

## 12. User Isolation Verification
- API calls pass authorization headers through current principal tokens.
- Cross-user data isolation: Session replacement (`generation++`, `domainEpoch++`) invalidates in-memory caches and leases.
- The app client does not accept client-provided user IDs for authorization.

---

## 13. Idempotency and Duplicate-Submission Verification
- Order ticket disables the submit button immediately upon tap while request is in flight.
- Unique client-generated idempotency key (min 10 chars) is generated for each new trade intent.
- In case of network failure or rejection, the user is offered a "Safe Retry" action that reuses the exact same idempotency key, preventing double-fill on the backend.

---

## 14. Unit Test Results
- `test/paper_trading_models_test.dart`: 4 tests passed.
- `test/goal_models_test.dart`: 4 tests passed.
- `test/paper_trading_service_test.dart`: 5 tests passed.
- `test/goal_service_test.dart`: 4 tests passed.

---

## 15. Widget Test Results
- `test/paper_trading_page_test.dart`: 6 tests passed.
- `test/goals_page_test.dart`: 6 tests passed.

---

## 16. Integration / Contract Test Results
- `test/paper_and_goals_contract_parity_test.dart`: 3 tests passed.

---

## 17. Full Flutter Test Suite Output
Command:
```bash
cd frontend_flutter && flutter test --no-pub
```
Result:
```
01:51 +866 ~4: All tests passed!
```
Total: **866 passed tests** (33 newly implemented tests + 833 baseline tests, 0 failures, 0 regressions).

---

## 18. Flutter Formatting and Analysis Results
- **Dart Format:**
  ```bash
  dart format --output=none --set-exit-if-changed frontend_flutter/lib frontend_flutter/test
  ```
  Result: `Formatted 16 files (0 changed) in 0.27 seconds.` (Clean exit code 0).
- **Flutter Analyze:**
  ```bash
  cd frontend_flutter && flutter analyze
  ```
  Result: `No issues found! (ran in 9.5s)` (0 errors, 0 warnings, 0 infos).

---

## 19. React Quality Command Results
As required by Issue #102:
- `cd frontend-react && npm test -- --watchAll=false`:
  ```
  Test Suites: 30 passed, 30 total
  Tests:       805 passed, 805 total
  Snapshots:   0 total
  Time:        82.088 s
  Ran all test suites.
  ```
- `cd frontend-react && npm run build`:
  ```
  Creating an optimized production build...
  Compiled successfully.
  ```

---

## 20. Backend Verification Results
- **FastAPI Health:** `GET /api/v1/health` -> 200 OK (`{"status": "healthy", "service": "FinEx Backend"}`)
- **Backend Linting:** `python -m ruff check .` -> `All checks passed!`
- **Backend Paper & Goals Tests:**
  ```bash
  python -m pytest tests/contract/test_paper_api.py tests/unit/test_paper_reconcile.py tests/unit/test_paper_trading_service.py tests/test_goals_persistence.py --no-cov -q
  ```
  Result: `25 passed, 1 skipped, 19 warnings in 2.79s`
  - `test_paper_order_contract_idempotency_and_user_isolation`: **PASSED**
  - `test_paper_routes_are_registered_without_replacing_existing_router`: **PASSED**
  - `test_goal_repository_isolates_users_and_persists`: **PASSED**
  - `test_goals_api_is_scoped_to_authenticated_principal`: **PASSED**
  - `test_buy_is_idempotent_and_posts_fee_adjusted_ledger_effect`: **PASSED**

---

## 21. GitHub Actions CI Verification (PR #164)
All 16 GitHub Actions check runs passed on commit `ab62470`:
- `windows-quality` (PR): **PASS** (6m 28s)
- `windows-quality` (Push): **PASS** (5m 11s)
- `evidence` (PR): **PASS** (2m 27s)
- `evidence` (Push): **PASS** (2m 38s)
- `Flutter journey and accessibility proof` (PR): **PASS** (4m 33s)
- `Flutter journey and accessibility proof` (Push): **PASS** (4m 35s)
- `React journey and accessibility proof` (PR): **PASS** (1m 15s)
- `React journey and accessibility proof` (Push): **PASS** (1m 04s)
- `Owned S1 and S2 native TCP, restart, expiry and wire capture` (PR): **PASS** (4m 07s)
- `Owned S1 and S2 native TCP, restart, expiry and wire capture` (Push): **PASS** (3m 59s)
- `Owned S3 synthetic API native TCP and durable foundation` (PR): **PASS** (1m 45s)
- `Owned S3 synthetic API native TCP and durable foundation` (Push): **PASS** (1m 58s)
- `Compatibility pilot contract and fixture proof` (PR): **PASS** (32s)
- `Compatibility pilot contract and fixture proof` (Push): **PASS** (44s)
- `Publish S1 UAT evidence summary` (PR): **PASS** (3s)
- `Publish S1 UAT evidence summary` (Push): **PASS** (2s)

---

## 22. Known Limitations
- Paper trading executes market orders during simulated or active market hours per backend configuration; limit or stop orders are planned for subsequent milestones.
- Compounding formulas in goals model constant monthly deposits and annualized yields without inflation indexing or tax drag, as documented in educational disclaimers.

---

## 23. Acceptance Criteria Traceability
| Acceptance Criterion | Verification Method | Status |
| :--- | :--- | :--- |
| `flutter test green` | Ran complete `flutter test` suite across all 866 tests | **PASSED** (866/866 green) |
| Idempotent orders | `test/paper_trading_page_test.dart`, `test/paper_trading_service_test.dart` | **PASSED** |
| User isolation | Protected endpoints via `current_principal`, session lease guard | **PASSED** |
| State handling | Loading, empty, success, rejection, and error states tested in widget tests | **PASSED** |
| Contract parity | Parity tests against `backend/app/schemas/paper.py` & `sprint4_paper_goals.py` | **PASSED** |

---

## 24. Final Implementation Summary
Issue #102 (S7-MI02) is fully implemented, verified, formatted, analyzed, and tested. The Flutter frontend now provides fully functional Paper Trading and Goals screens connected to the verified FinEx backend contracts with zero regressions to existing routes. All acceptance criteria and definition of done items are satisfied. PR #164 is ready for secondary review by `@Mrugankkakade17-svg`.
