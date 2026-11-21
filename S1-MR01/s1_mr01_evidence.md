# S1-MR01 — Local task evidence

Branch: `feature/s1-mr01`
Target: `origin/dev`

Generated repository files:

- `backend/alembic/versions/fx_001_identity_portfolios.py`
- `backend/alembic/versions/fx_002_holdings_numeric_fk.py`
- `backend/tests/db/test_fx002.py`
- `backend/app/models/dat02_models.py`
- `docs/evidence/s1_mr01_evidence.md`

This folder contains the local PR description and evidence copy for the Sprint 1 migration task.

## Verification

- Alembic `upgrade head`: PASS
- Alembic `downgrade base`: PASS
- Alembic `upgrade head` after downgrade: PASS
- `test_fx002.py`: PASS, `1 passed`
- Ruff changed-file and backend checks: PASS
- Full backend suite: `2604 passed`, `26 xfailed`, `22 failed` because the local Python 3.14 environment's bcrypt package rejects test passwords over 72 bytes; migration-specific checks pass.
