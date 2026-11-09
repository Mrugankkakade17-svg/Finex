# Sprint 1 Product/UI Handoff: B-S1-UI (Market Search and Watchlist Foundation)

## Overview
- **Track**: Product/UI (React + Flutter)
- **Ticket / Task ID**: `B-S1-UI`
- **Module**: Beta Pod - B1 Market Search and Watchlist Foundation
- **Owner**: Shivraj (Beta Pod)
- **API scope referenced**: `MKT-01..03`, `WAT-01`
- **Status**: UI complete against a mock service layer. Real backend (`B-S1-API`) not yet implemented in this repository — see Known Limitations.

---

## 1. Scope & Deliverables

Implements the user-facing Sprint 1 outcome: *"User searches a supported security, sees freshness, and manages a default watchlist."*

Delivered on both clients:
- **React web** (`/market`, `/watchlist` routes)
- **Flutter mobile** (`/market`, `/watchlist` routes)

### Key components implemented

**React (`frontend-react/src/`)**
- `types/market.ts` — canonical `MarketSecurity`, `MarketQuote`, `WatchlistItem`, `DataStatus` types matching the handbook's response envelope (`dataAsOf` / `dataStatus`).
- `services/marketService.ts` — mock service implementing `search` (MKT-01), `getQuote` (MKT-02), `getWatchlist`/`addToWatchlist`/`removeFromWatchlist` (WAT-01). Idempotent add/remove per the handbook's completion gate.
- `pages/MarketPage.tsx` — search input, results list, quote panel with source/status/as-of freshness label, add-to-watchlist action.
- `pages/WatchlistPage.tsx` — list view with remove action and refresh.
- Routes registered in `App.tsx`, nav entries added to `AppShell.tsx`.

**Flutter (`frontend_flutter/lib/features/market/`)**
- `models/market_models.dart` — `MarketSecurity`, `MarketQuote`, `WatchlistItem`, `DataStatus` enum mirroring the React types.
- `services/market_service.dart` — mock service with the same MKT-01..03 / WAT-01 behavior, including the `DOWN` provider-outage demo symbol.
- `presentation/market_page.dart`, `presentation/watchlist_page.dart` — equivalent UI to the React pages, built from the existing shared widgets (`AppCard`, `LoadingView`, `EmptyView`, `ErrorView`).
- Routes registered in `core/router/app_router.dart`, nav entries added to `shared/widgets/app_shell.dart`.

---

## 2. UI States Covered (per module contract)

| State | React | Flutter |
|---|---|---|
| Loading (search) | `market-search-loading` | `LoadingView` while `_searchLoading` |
| Empty (no match) | `market-search-empty` | `EmptyView` ("No matches") |
| Validation (blank query) | inline amber message | inline `_InlineMessage` |
| Provider unavailable / retry | inline red message + Retry button | inline `_InlineMessage` with Retry |
| Quote unavailable (`PRICE_UNAVAILABLE`) | `quote-unavailable` | `ErrorView` keyed `quote-unavailable` |
| Success + freshness label | `quote-freshness` (source/status/as-of) | `Key('quote-freshness')` |
| Watchlist loading | `watchlist-loading` | `LoadingView` keyed `watchlist-loading` |
| Watchlist empty | `watchlist-empty` | `EmptyView` keyed `watchlist-empty` |
| Watchlist error/retry | `watchlist-error` | `ErrorView` keyed `watchlist-error` |

A dedicated `DOWN` demo symbol is seeded in both mock services specifically to exercise the provider-unavailable / `PRICE_UNAVAILABLE` path in tests and manual QA.

---

## 3. Test Evidence

### React (`npx react-scripts test --watchAll=false`)
```
PASS src/services/onboardingService.test.ts
PASS src/pages/WatchlistPage.test.tsx
PASS src/pages/MarketPage.test.tsx
PASS src/services/marketService.test.ts

Test Suites: 4 passed, 4 total
Tests:       19 passed, 19 total
```

### Flutter (`flutter test`)
```
00:03 +26: All tests passed!
```
`flutter analyze` clean of any new issues (4 pre-existing `deprecated_member_use` infos remain in unrelated onboarding/risk files, not touched by this task).

---

## 4. Environment Fixes Made Along the Way

Two pre-existing gaps in the React app were blocking any RTL-based test from running, fixed as part of this task since they affect every future UI test, not just this feature:
1. `@testing-library/react` and `@testing-library/jest-dom` were declared in `package.json` but not actually installed in `node_modules` — ran `npm install` to reconcile.
2. `src/setupTests.ts` (the standard CRA file that registers jest-dom matchers like `toBeInTheDocument`) did not exist — added it.

---

## 5. Known Limitations / Not Done

- **No real backend integration.** `B-S1-API` (FastAPI router/service/repository for `MKT-01..03`, `WAT-01`) does not exist in this repository yet. Both clients call an in-memory mock service, matching the "if blocked, build against generated mock responses" guidance in the handbook.
- **Handbook task-ID mismatch flagged separately**: this repo's actual code uses a different task-naming convention (`S{sprint}-{TRACK}-{num}`) than the `B-S1-UI` / pod-based IDs in the handbook. This card was implemented against the handbook's B1 module contract directly since no matching `docs/features/b1/spec.md` exists in-repo.
- Quote data is static mock data with fixed prices; no live/cached provider call occurs.
- Watchlist state is held in a module-level singleton (React) / singleton service (Flutter), not persisted to a database — resets on page/app reload.

## 6. Unblocks

Per the handbook's dependency chain: `B-S1-INT`, `B-S1-UAT`, and `B-S2-SPEC` (Paper Account and Order Ticket) plus all Sprint 2 Beta implementation cards, once B-S1-API and B-S1-DATA are also completed and this UI is re-pointed at the real endpoints.
