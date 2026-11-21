# S1-MR05 Evidence

## Scope

Secured the operations, release handover, and privacy routers with the current
principal dependency. Operations feature flag toggles and UAT release sign-offs
require the `admin` role; other authenticated operations and privacy endpoints
remain available to authenticated principals. Added security coverage that
removes the expected-failure marker from these three secured routers and
comprehensive tests for anonymous, regular-user, and admin behavior.

## Changed files

- `backend/app/auth/__init__.py`
- `backend/app/auth/principal.py`
- `backend/app/routers/ops_hardening.py`
- `backend/app/routers/privacy.py`
- `backend/app/routers/release_handover.py`
- `backend/tests/security/test_prototype_routes_require_auth.py`
- `backend/tests/unit/test_s1_mr05_ops_release_privacy.py`

## Verification

Commands run from `backend/`:

- `python -m ruff check .` — passed.
- Focused S1-MR05 and prototype security tests: **41 passed, 15 xfailed**.
  The focused invocation exits nonzero only because the repository's global
  coverage gate is 70% and the focused subset reports 37% total coverage.
- `python -m pytest -q` — **2,747 passed, 10 skipped, 15 xfailed**; total
  coverage **83.73%** (70% minimum met), completed in 1,049.50 seconds.

The focused tests verify 401 responses for anonymous requests, 403 responses
for non-admin flag toggles and sign-offs, successful admin operations, and
authenticated access to the corresponding read and privacy routes.

## Storage and migration

No database schema or persistent storage behavior was changed; no migration is
required. Existing in-memory route stores and response contracts are preserved.
