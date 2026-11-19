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
| Flutter `pub get` | Passed: dependencies resolved and downloaded in 39.5 seconds. 13 newer versions are outside the existing dependency constraints; dependency files were not changed. |
| Flutter `analyze` | Passed: no issues found; completed in 55.3 seconds. |
| Flutter `test` | Passed: 833 tests passed; 4 tests skipped. |
| Git branch and status | GitHub branch `feature/s0-ni01` created from `dev`; the baseline and UI guide are committed on the branch. |

The React checks were run from `frontend-react/`. Flutter checks were run from `frontend_flutter/` in the supplied project copy using an elevated PowerShell terminal after enabling Windows plugin symlink support.

## Acceptance status

- [x] React and Flutter application baselines inspected in source.
- [x] Hard-coded local API origins in runtime source listed.
- [x] Existing UI tokens and Flutter accessibility cues recorded.
- [x] React test and build results recorded; all tests and build passed.
- [x] Flutter package resolution, analysis, and tests passed (833 passed, 4 skipped).
- [x] `feature/s0-ni01` branch and documentation commits created from `dev`.
- [x] Pull request #114 is open and its 2 GitHub checks passed.
- [ ] Peer review approval by Payal: pending.

The Flutter and React command results are recorded above. Payal's secondary review is still pending.
