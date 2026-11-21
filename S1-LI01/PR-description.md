# PR Description

**Task:** S1-LI01 - current_principal dependency for local bearer and real sessions

**Summary:**
Implemented a new `principal.py` module providing a `get_principal` helper and FastAPI dependency `CurrentPrincipal`. This resolves the active user principal from either a bearer token or a regular session, raising `401 Unauthorized` when no principal is found. Updated import paths to use existing `dependencies` utilities.

**Changes:**
- Added `app/auth/principal.py` with full implementation and documentation.
- Added `CurrentPrincipal` FastAPI dependency for easy injection in routes.
- Created folder `S1-LI01` mirroring the new module for task organization.

**Tests:**
All existing backend tests pass:
```
cd backend && python -m ruff check . && python -m pytest -q
```
(Ensure new tests for `principal` are added in future.)

**Reviewer:** @mitali2701

**Related Docs:** See `docs/evidence/s1_li01_evidence.md` for test logs and verification steps.
