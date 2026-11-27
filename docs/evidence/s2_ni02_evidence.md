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

The implementation and test source are present, but the prescribed React test and build commands could not be completed in this environment. The checkout had no installed `frontend-react/node_modules`, and the package registry could not be resolved (`ENOTFOUND registry.npmjs.org`) while installing Recharts. The pre-existing `Downloads\FinEx-Git` dependencies could not be linked into this writable checkout by Windows.

Commands and results:

```text
npm install recharts@2.15.4 --save --verbose (initial registry probe)
  Failed: ENOTFOUND registry.npmjs.org

npm install --package-lock-only --ignore-scripts --offline
  Failed: ENOTCACHED; registry metadata for recharts is not available in the local cache

npm test -- --watchAll=false --runInBand --modulePaths=<existing Downloads checkout node_modules>
  PASS: 31 suites, 810 tests. Recharts components are mocked in the focused component tests.

PriceChart focused tests with the same external test dependencies
  PASS: 1 suite, 5 tests.

npm run build with the existing Downloads checkout on PATH/NODE_PATH
  Failed: Module not found: Can't resolve `react-router-dom` in this writable checkout.

Custom lock graph check against the lockfile's package versions and dependency ranges
  PASS: all new Recharts dependency ranges resolve; app direct dependencies match the lockfile.
```

The Recharts 2 install command was an initial registry probe; the committed manifest and lockfile use Recharts 3.10.1 and React 18-matched `react-is`. The build still needs to run from a fully installed checkout with the actual Recharts package. No passing production build is claimed here.

## Contracts and scope

The chart consumes daily OHLCV bars and optional exchange-calendar closure dates from its caller. It does not fetch market history or change a route; that transport is owned by the dependent S2-NI01 work. No database or frozen local route was changed.
