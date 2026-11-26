# S1-LI03 Goals behind Principal and Repository

## Implemented

- Secured all `/api/v1/goals` routes with `get_current_principal`.
- Routed goal creation and retrieval through `GoalService`.
- Added the persistent, user-scoped `GoalRepository`.
- Preserved the existing goal request and response schemas and API response envelope.
- Added strict `(user_id, goal_id)` isolation for list and detail operations.
- Added SQLite persistence for local/offline runs and PostgreSQL support for the existing `finex.goals` and `finex.goal_projections` migration tables.
- Configured synchronous goal persistence to use the installed psycopg 3 SQLAlchemy driver.
- Added PostgreSQL-backed goal create/read/list coverage and retained all migrated routes in the auth-probe secured set.

## Verification

Run from the repository root:

```powershell
cd backend
python -m ruff check app/repositories/goal_repo.py tests/test_goals_persistence.py tests/security/test_prototype_routes_require_auth.py
python -m ruff format --check app/repositories/goal_repo.py tests/test_goals_persistence.py tests/security/test_prototype_routes_require_auth.py
python -m mypy app/repositories/goal_repo.py --platform win32 --python-version 3.13
python -m pytest -q --no-cov tests/test_goals_persistence.py tests/security/test_prototype_routes_require_auth.py
```

## Execution log

- `python -m ruff check .`: passed.
- Ruff check, format check, and mypy for the changed goal files: passed.
- Focused goal persistence and authentication tests: 25 passed, 1 skipped, 2 xfailed, 2 xpassed.
- PostgreSQL goal persistence test: added; skipped locally without `DATABASE_URL`, and runs in PostgreSQL CI after migrations.
- Full backend suite: 2,728 passed, 14 skipped, 10 xfailed, 2 xpassed; 45 launcher/acceptance failures.
- The full-suite failures are host-environment failures where Windows PowerShell script execution is disabled for `.ps1` launchers (`UnauthorizedAccess`), affecting launcher and acceptance tests rather than goal service behavior.
