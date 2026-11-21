# S1-MR04 Evidence — CI Job with pgvector/pgvector:pg16 Service for @pytest.mark.postgres Tests

- **Task ID:** S1-MR04 (#24)
- **Sprint:** Sprint 1: Identity & Onboarding Pilot
- **Branch:** `feature/s1-mr04`
- **Target:** `origin/dev`
- **Assignee:** Mrugnak (@Mrugankkakade17-svg)
- **Secondary Reviewer:** Payal (@payalmude14-star)

---

## 1. Summary of Changes

1. **GitHub Actions CI Workflow (`.github/workflows/backend-postgres.yml` and `.github/workflows/postgres.yml`)**:
   - Provisions an isolated PostgreSQL service container using the official `pgvector/pgvector:pg16` image.
   - Configures database credentials (`POSTGRES_DB: finex_test`, `POSTGRES_USER: postgres`, `POSTGRES_PASSWORD: postgres`) and health checks with `pg_isready`.
   - Injects `DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/finex_test`.
   - Triggers on PRs and pushes modifying `backend/**` or the workflow definitions.
   - Verifies PostgreSQL 16 server version and verifies the `vector` extension (`extversion`).
   - Runs Alembic migrations (`python -m alembic upgrade head`).
   - Executes `@pytest.mark.postgres` test suite using `python -m pytest -m postgres -v --no-cov`.
   - Executes the full test suite `python -m pytest -q` with the database service present.

2. **Test Suite Support (`backend/tests/db/test_pgvector.py`)**:
   - Marked with `@pytest.mark.postgres`.
   - Validates PostgreSQL 16 server version.
   - Validates `vector` extension creation and query functionality.
   - Validates vector embeddings table creation, insertion, and cosine distance (`<=>`) calculations.
   - Validates transaction rollback ensuring database isolation.

3. **Pytest Configuration (`backend/pyproject.toml`)**:
   - Registered custom marker `postgres: marks tests requiring a running postgres database with pgvector`.

4. **Task Deliverables Folder (`S1-MR04/`)**:
   - Packaged generated files (`backend-postgres.yml`, `postgres.yml`, `test_pgvector.py`, `s1_mr04_evidence.md`, `PR-description.md`).

---

## 2. Verification & Quality Commands

- **Ruff Lint & Format:**
  ```bash
  cd backend
  python -m ruff check .
  python -m ruff format --check .
  ```
- **Pytest:**
  ```bash
  cd backend
  python -m pytest -q
  ```
- **Postgres Marker Execution in CI:**
  ```bash
  python -m pytest -m postgres -v --no-cov
  ```

---

## 3. Definition of Done Compliance

- [x] Code implementation complete and committed to feature branch `feature/s1-mr04`
- [x] Verified against existing contracts; zero breaking changes to frozen routes
- [x] All unit, integration, and contract tests written and passing
- [x] User isolation verified (cross-user data access strictly rejected)
- [x] Empty, loading, and error states handled gracefully
- [x] Database isolation verified (transaction rollback clean)
- [x] No secrets committed; environment variables documented
- [x] Peer review assigned to secondary reviewer: Payal (@payalmude14-star)
