# S0-NI01 evidence

**Measured:** 2026-11-19
**Issue:** #19, `[S0-NI01] Measure React and Flutter baselines; list hard-coded origins; record UI tokens to preserve`
**Source checkout:** supplied ZIP; project files were cross-checked against GitHub `dev` at `41539f8828057504e5198827cd61e3b9826fe409`.

## Evidence artifacts

- [Frontend baseline](../frontend-baseline.md): toolchain, origin inventory, command outcomes, and blockers.
- [UI identity](../ui-identity.md): React and Flutter token inventory and preservation notes.

## Execution record

| Check | Recorded result |
| --- | --- |
| Node.js | `v24.20.0` |
| npm | `11.19.0` |
| `npm ci` | Passed; installed 1,340 packages. npm reported 44 audit findings: 9 low, 8 moderate, 25 high, and 2 critical. Two dependency install scripts were not approved by npm's install-script policy. `package-lock.json` was not modified. |
| `npm test -- --watchAll=false` | Passed: 25 test suites, 754 tests, 0 snapshots. Existing React Router future-flag warnings appeared. |
| `npm run build` | Passed: optimized production build compiled successfully. Node emitted an `fs.F_OK` deprecation warning. |
| Dart | `Dart SDK version: 3.13.2 (stable)` |
| Flutter tool startup | Blocked: Flutter could not access `C:\flutter\bin\cache\lockfile`. Direct invocation of the SDK snapshot returned the same cache access error. |
| Flutter `pub get`, `analyze`, `test` | Each was attempted through the SDK tool snapshot. Each stopped before doing work because Flutter could not open `C:\flutter\bin\cache\lockfile` (exit `-1073741816`). No Flutter check is represented as passing. |
| Git branch and status | GitHub branch `feature/s0-ni01` created from `dev`; the baseline and UI guide are committed on the branch. |

The React checks were run from `frontend-react/`. Flutter checks require rerunning in an environment with an accessible, writable Flutter SDK cache. The current session could read the SDK but not write its cache lockfile.

## Acceptance status

- [x] React and Flutter application baselines inspected in source.
- [x] Hard-coded local API origins in runtime source listed.
- [x] Existing UI tokens and Flutter accessibility cues recorded.
- [x] React test and build results recorded; all tests and build passed.
- [ ] Flutter package resolution, analysis, and test results: pending accessible Flutter toolchain.
- [x] `feature/s0-ni01` branch and documentation commits created from `dev`.
- [ ] Pull request, CI run, and Payal's review: pending.

This evidence records blocked checks honestly; it does not claim a green baseline or issue completion against the command-based acceptance criteria.
