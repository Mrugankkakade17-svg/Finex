# S1-MR01 — Local task evidence

Branch: `feature/s1-mr01`
Target: `origin/dev`

Generated repository files:

- `backend/alembic/versions/fx_001_identity_portfolios.py`
- `backend/alembic/versions/fx_002_holdings_numeric_fk.py`
- `backend/tests/db/test_fx002.py`
- `backend/app/models/dat02_models.py`
- `docs/evidence/s1_mr01_evidence.md`
- `.github/workflows/backend-quality.yml` (isolated PostgreSQL CI service)

This folder contains the local PR description and evidence copy for the Sprint 1 migration task.

## Verification

- `python -m alembic upgrade head --sql`: PASS (offline SQL generation)
- `python -m alembic downgrade s1mr01_fx002:s1mr01_fx001 --sql`: PASS (offline SQL generation)
- `python -m ruff check .`: PASS
- `python -m pytest -q -m "not postgres"`: `2625 passed`, `26 xfailed`, `2 deselected`; coverage 86.20%.
- 52 previously failing authentication tests pass after restoring the repository-pinned bcrypt 4.2.1.
- Backend CI run #44882516405: migration upgrade/downgrade/upgrade passed on PostgreSQL 16; `test_fx002.py` passed as part of `2,676 passed, 26 xfailed`.
