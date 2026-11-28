# S3-LI02 — Goals: Contributions, Progress, and Documented Monthly-Contribution Formula

## Implemented

- **Documented monthly-contribution formula (`backend/app/services/goal_service.py`):**
  - Preserved `GoalService.calculate_goal_projections` (start-of-month / annuity-due monthly compounding) and added `months_between_dates`, `calculate_required_monthly_contribution`, `calculate_goal_progress`, `update_goal`, `delete_goal`, `record_contribution`, `list_contributions`, `get_goal_progress`, and `list_goals_progress`.
  - Documented the exact deterministic annuity-due closed form matching `calculate_goal_projections`:
    - Monthly rate: `r = (expected_annual_return_pct / 100) / 12`
    - Zero-return (`r == 0`): `M = (target - current) / N` (or `0.00` when `current >= target`, `None` when `N == 0` and `current < target`)
    - Positive-return (`r > 0`): `M = (target - current * (1 + r)^N) * r / ((1 + r) * ((1 + r)^N - 1))` computed at 34-digit `Decimal` precision and rounded to cents with `ROUND_HALF_UP` (or `0.00` when `current * (1 + r)^N >= target`).
  - Edge-date handling (`months_between_dates`): handles same-day (`0`), past target dates (`0`, `is_overdue=True` when incomplete), same-month (`0`), year boundaries, month-end alignment (`Jan 31 -> Feb 28 = 1`), and leap-day targets (`2024-02-29 -> 2025-02-28 = 12`, `2024-02-29 -> 2028-02-29 = 48`), rejecting `datetime` objects explicitly.
- **Persistent contributions, goal CRUD, and progress API (`backend/app/routers/goals.py`, `backend/app/repositories/goal_repo.py`, `backend/app/schemas/sprint4_paper_goals.py`):**
  - Preserved `POST /api/v1/goals`, `GET /api/v1/goals`, `GET /api/v1/goals/{goal_id}`, and existing test seams (`_goals_db`, `_calculate_goal_projections`) with zero breaking changes.
  - Added principal-scoped `PUT /api/v1/goals/{goal_id}`, `DELETE /api/v1/goals/{goal_id}`, `POST /api/v1/goals/{goal_id}/contributions`, `GET /api/v1/goals/{goal_id}/contributions`, and `GET /api/v1/goals/{goal_id}/progress`.
  - Recording a contribution atomically inserts into `goal_contributions`, increments `current_amount`, and updates `projections`, `projected_final_amount`, `shortfall_or_surplus`, and `is_on_track` in both SQLite and PostgreSQL.
- **Reversible database migration (`backend/alembic/versions/s3_li02_goal_contributions.py`):**
  - Chains linearly from `s3pa03_daily_snapshots` -> `s3li02_goal_contributions`.
  - Adds nullable `target_date` (`DATE`) to `finex.goals` and creates `finex.goal_contributions` with `NUMERIC(20, 4)` amount, `amount > 0` check constraint, composite owner foreign key `(user_id, goal_id)` referencing `finex.goals` (`ON DELETE CASCADE`), user foreign key to `finex.users`, and indexes on `(user_id, goal_id, contribution_date)` and `(user_id, created_at)`.

## Tests Added (Existing Goal Tests Unchanged)

- `backend/tests/test_goals_persistence.py` and `backend/tests/security/test_prototype_routes_require_auth.py` remain untouched and pass.
- `backend/tests/unit/test_goal_service_s3_li02.py`: zero-return closed-form tests, zero-return linear projection tests, positive-return projection parity tests, edge-date tests (same day, past date, same month, year boundary, month-end, leap day), empty/overdue/overfunded progress tests, and invalid input rejection.
- `backend/tests/integration/test_s3_li02_goals_api.py`: authentication enforcement (`401`), CRUD + contribution + progress lifecycle, SQLite restart persistence, cross-user `404` isolation across every endpoint, leap-day / overdue / invalid-date HTTP checks, and `422` validation checks.
- `backend/tests/db/test_s3_li02_goal_contributions.py`: `@pytest.mark.postgres` constraint, cross-user FK rejection, cascade delete, and `GoalService` Postgres round-trip tests.

## Verification Commands & Results

Run from `backend/`:

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy app/schemas/sprint4_paper_goals.py app/repositories/goal_repo.py app/services/goal_service.py app/routers/goals.py tests/unit/test_goal_service_s3_li02.py tests/integration/test_s3_li02_goals_api.py tests/db/test_s3_li02_goal_contributions.py --platform win32 --python-version 3.13
python -m mypy app/schemas/sprint4_paper_goals.py app/repositories/goal_repo.py app/services/goal_service.py app/routers/goals.py tests/unit/test_goal_service_s3_li02.py tests/integration/test_s3_li02_goals_api.py tests/db/test_s3_li02_goal_contributions.py --platform linux --python-version 3.13
python -m alembic heads
python -m alembic upgrade s3pa03_daily_snapshots:s3li02_goal_contributions --sql
python -m alembic downgrade s3li02_goal_contributions:s3pa03_daily_snapshots --sql
python -m pytest -q --no-cov tests/test_goals_persistence.py tests/security/test_prototype_routes_require_auth.py tests/unit/test_goal_service_s3_li02.py tests/integration/test_s3_li02_goals_api.py tests/db/test_s3_li02_goal_contributions.py
python -m pytest -q -m "not postgres"
```

### Observed Output

- `ruff check .`: `All checks passed!`
- `ruff format --check .`: `387 files already formatted`
- `mypy` (`win32` & `linux`, Python 3.13): `Success: no issues found in 7 source files`
- `alembic heads`: `s3li02_goal_contributions (head)`
- `alembic upgrade` / `downgrade` (`--sql`): clean reversible DDL for `finex.goals.target_date` and `finex.goal_contributions`.
- Focused goal + security probe tests: `41 passed, 3 skipped, 2 xfailed, 2 xpassed` (`3 skipped` are `@pytest.mark.postgres` tests when `DATABASE_URL` is unset locally; they run in the PostgreSQL CI workflow).
- Full backend suite (`-m "not postgres"`): `3107 passed, 48 failed, 4 skipped, 22 deselected, 2 xfailed, 2 xpassed` (coverage `82.31%`). All 48 failures are pre-existing Windows PowerShell `ExecutionPolicy` (`running scripts is disabled on this system`) errors in `.ps1` launcher tests (`tests/test_local_launcher_boundary.py`, `tests/unit/test_owned_s2_acceptance_launcher.py`, `tests/unit/test_s1_acceptance_launcher.py`), unrelated to `S3-LI02`.
