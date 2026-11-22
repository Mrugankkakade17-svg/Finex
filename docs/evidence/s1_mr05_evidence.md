# S1-MR05 Evidence

## Scope

Secured the operations, release handover, and privacy routers with the current
principal dependency. Operations feature flag toggles and UAT release sign-offs
require the `admin` role; other authenticated operations and privacy endpoints
remain available to authenticated principals. Security coverage verifies
anonymous rejection, role enforcement, and authenticated route contracts.

Consent history and privacy action records are scoped to the authenticated
principal's user ID. Consent reads return only that user's history, and
revocation updates only that user's active records. A regression test verifies
that User A revoking consent does not change User B's consent.

## Changed files

- `backend/app/auth/__init__.py`
- `backend/app/auth/principal.py`
- `backend/app/routers/ops_hardening.py`
- `backend/app/routers/privacy.py`
- `backend/app/routers/release_handover.py`
- `backend/tests/security/test_prototype_routes_require_auth.py`
- `backend/tests/unit/test_s1_mr05_ops_release_privacy.py`

No database schema changes or migration were needed. The redundant `S1-MR05/`
archive and duplicate PR-description copy were removed; this file is the
authoritative task evidence.

## Verification

GitHub Actions full backend test run:

- Command: `python -m pytest -q` (run from `backend/`)
- Result: **2,758 passed, 15 xfailed, 0 skipped**
- Coverage: **86.06%** (70% minimum met)
- Duration: **161.41 seconds**
- Workflow: [Backend Postgres Tests, run 37](https://github.com/Mrugankkakade17-svg/Finex/actions/runs/44932024340)
- Test output excerpt: [s1_mr05_test_output.txt](s1_mr05_test_output.txt)

The full run includes the privacy isolation regression test. The same PR head's
S1 UAT Evidence, R0-S2 Release Evidence, and Backend Quality Gates workflows
also completed successfully.

## Test output

The captured summary from the successful GitHub Actions run is saved in
`docs/evidence/s1_mr05_test_output.txt`.
