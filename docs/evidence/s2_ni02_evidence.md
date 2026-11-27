# S2-NI02 implementation evidence

**Issue:** [#46 - Price chart with Recharts and a table alternative](https://github.com/Mrugankkakade17-svg/Finex/issues/46)

**Branch:** `feature/s2-ni02` (based on `dev`)

**Verification date:** 2026-11-27

## Implementation

- Added `frontend-react/src/components/charts/PriceChart.tsx` with a Recharts closing-price chart and an accessible OHLCV table view.
- Chart points are ordered by exchange date. Missing weekdays are rendered as null points so the line does not interpolate through an absent session. Caller-supplied exchange-calendar closures are separately marked as closed, and no missing price is estimated.
- Loading, empty, error, and retry states are available to the calling page.
- Added focused unit coverage for ordering, weekday gaps, explicit closed days, weekend handling, the table alternative, and loading/error/empty states.
- Added Recharts 3.10.1 and the React 18 matching `react-is` package to the React app manifest and lockfile.

## Verification status

All checks below completed in GitHub Actions on the PR head after the lockfile was corrected and the ES5 iterator compatibility issue was fixed.

Commands and results:

```text
cd "$GITHUB_WORKSPACE/frontend-react" && npm ci --package-lock=true
  PASS: dependencies installed from the committed lockfile.

cd "$GITHUB_WORKSPACE/frontend-react" && npm test -- --watchAll=false
  PASS: 31 suites, 810 tests, including all 5 PriceChart tests.

cd "$GITHUB_WORKSPACE/frontend-react" && npm run build
  PASS: optimized production build completed.
```

The committed manifest and lockfile use Recharts 3.10.1 and React 18-matched `react-is`. The React quality workflow uses the fully installed package tree, so the production build also validates the actual chart dependency.

## Contracts and scope

The chart consumes daily OHLCV bars and optional exchange-calendar closure dates from its caller. It does not fetch market history or change a route; that transport is owned by the dependent S2-NI01 work. No database or frozen local route was changed.

