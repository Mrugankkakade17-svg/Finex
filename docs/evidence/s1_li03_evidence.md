# S1-LI03 Goals behind Principal and Repository

## Implemented

- Secured all `/api/v1/goals` routes with `get_current_principal`.
- Routed goal creation and retrieval through `GoalService`.
- Added the persistent, user-scoped `GoalRepository`.
- Preserved the existing goal request and response schemas and API response envelope.
- Added strict `(user_id, goal_id)` isolation for list and detail operations.
- Added SQLite persistence for local/offline runs and PostgreSQL support for the existing `finex.goals` and `finex.goal_projections` migration tables.

## Verification

Run from the repository root:

```powershell
cd backend
python -m ruff check .
python -m pytest -q
```

## Execution log

- `python -m ruff check .`: passed.
- Focused goal persistence and authentication tests: 16 passed.
- Full backend suite: 2,728 passed, 14 skipped, 10 xfailed, 2 xpassed; 45 launcher/acceptance failures.
- The full-suite failures are host-environment failures where Windows PowerShell script execution is disabled for `.ps1` launchers (`UnauthorizedAccess`), affecting launcher and acceptance tests rather than goal service behavior.
