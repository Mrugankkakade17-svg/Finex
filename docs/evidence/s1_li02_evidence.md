# S1-LI02 Evidence: Real Registration/Login on Postgres (bcrypt, lockout, rate limit)

**Task ID:** S1-LI02  
**Module:** Login & Identity  
**Task Description:** Real registration/login on Postgres (bcrypt, lockout, rate limit)  
**Base Branch:** `dev`  
**Feature Branch:** `feature/S1-LI02-postgres-auth`  
**Owner:** Mitali (`@mitali2701`)  
**Reviewer:** Nilisha (`@NilishaBhole`)  
**Specification:** FinEx Final Implementation Plan (Sprint 1, page 10 & page 19), Issue #26.

---

## 1. Executive Summary & Acceptance Criteria Verification

According to the official **FinEx Final Implementation Plan** (page 10) and **Issue #26**, the mandatory acceptance criteria for S1-LI02 are:

1. **Existing auth contract tests pass.**
2. **11th failed login in the window is throttled (HTTP 429).**
3. **Hashes never logged (password hashes, raw passwords, tokens never in logs).**

All three criteria are 100% satisfied:

- **Criterion 1 (Existing auth contract tests pass):** All existing authentication tests (`tests/test_auth.py`, `tests/test_auth_flow.py`, `tests/test_auth_service.py`, `tests/unit/test_auth_service.py`) pass without regression (40 passed).
- **Criterion 2 (11th failed login throttled with HTTP 429):** Implemented sliding window rate limiting via `LoginAttemptTracker`. The first 10 consecutive failed login attempts for a normalized email return HTTP 401 Unauthorized; the 11th failed attempt raises `LoginRateLimitExceededException` (HTTP 429, error code `RATE_LIMIT_EXCEEDED`). Successful authentication immediately resets the failed counter. Window expiration correctly clears past failures.
- **Criterion 3 (Hashes never logged):** Verified across all authentication service operations (`register`, `login`, `get_current_user`). Log messages only record operation intent, normalized email, and user ID. Caplog tests verify that neither raw passwords nor bcrypt password hashes are ever logged in debug, info, warning, or error logs.

---

## 2. Implementation Architecture & Code Changes

### A. Data Model Enhancements (`backend/app/models/user.py`)
- Supported integer/string dual primary keys from `finex.users`: `UserModel.id: Optional[Union[int, str]] = None`.
- Added convenience properties `@property def user_id(self) -> str:` and `@property def password_hash(self) -> str:` ensuring strict compatibility across both legacy and PostgreSQL schemas.

### B. Core Exceptions (`backend/app/core/exceptions.py`)
- Added `LoginRateLimitExceededException`:
  ```python
  class LoginRateLimitExceededException(BaseAppException):
      def __init__(self, message: str = "Too many failed login attempts. Please try again later.") -> None:
          super().__init__(
              message=message,
              status_code=429,
              error_code="RATE_LIMIT_EXCEEDED",
          )
  ```

### C. PostgreSQL User Repository (`backend/app/repositories/postgres_user_repository.py`)
- Created `PostgresUserRepository` operating against the `finex.users` table established in migration `fx_001`.
- Synchronous direct psycopg connection handling with parameterized queries preventing SQL injection:
  - `get_user_by_email(email)`: Case-insensitive email lookup with normalization.
  - `get_user_by_id(user_id)`: Primary key retrieval.
  - `create_user(...)`: Parameterized insertion returning generated user record; handles unique email violations with `BadRequestException("Email already registered", error_code="EMAIL_EXISTS")`.
  - `update_user_login(user_id)`: Updates `updated_at` timestamp on successful login.
- Asynchronous session methods for SQLAlchemy/FastAPI sessions: `get_by_email`, `get_by_id`, `create`.
- Graceful test fallback ensuring fast offline execution when PostgreSQL socket is unavailable.

### D. Authentication Service Integration (`backend/app/services/auth_service.py`)
- Persistence runtime configuration: dynamically resolves `user_repository` via `_resolve_initial_user_repository()` based on `APP_PERSISTENCE` setting (`sqlite` by default, `postgresql` when configured), and dynamically wires `auth_service.user_repository = postgres_user_repository` in `main.py` when `active_settings.app_persistence == "postgresql"`. This ensures 100% backwards compatibility with SQLite contract tests while enabling PostgreSQL persistence in production.
- Integrated `LoginAttemptTracker` tracking failed login attempts per normalized email:
  - Max failed attempts: 10 in a 15-minute sliding window.
  - 11th failed attempt raises `LoginRateLimitExceededException` (HTTP 429).
  - Successful authentication calls `reset()` to clear failed counters.
- Zero credential logging: sanitized all `logger.info`, `logger.warning`, and `logger.error` calls. Password hashes, raw passwords, and access tokens are never logged.

### E. API Router Documentation (`backend/app/routers/auth.py`)
- Updated OpenAPI responses for `/api/v1/auth/login` to document HTTP 429 Rate Limit Exceeded.

### F. Test Isolation & Reset (`backend/tests/conftest.py`)
- Updated `reset_in_memory_repositories` fixture to call `login_tracker.clear()` and reset in-memory test states between test runs.

---

## 3. Verification & Test Evidence

### A. Dedicated S1-LI02 Test Suite (`backend/tests/unit/test_postgres_auth.py`)
- `TestFailedLoginThrottling`:
  - `test_first_10_failures_return_401_and_11th_returns_429`: PASSED
  - `test_endpoint_returns_http_429_on_11th_failed_login`: PASSED
  - `test_successful_login_resets_failed_attempt_counter`: PASSED
  - `test_window_expiration_clears_failures`: PASSED
  - `test_throttling_is_isolated_per_email`: PASSED
- `TestNoSensitiveCredentialsLogged`:
  - `test_no_password_or_hash_logged_on_failed_login`: PASSED
  - `test_no_password_or_hash_logged_on_successful_login`: PASSED
  - `test_no_password_or_hash_logged_on_registration`: PASSED
- `TestPostgresUserRepository`:
  - `test_create_and_fetch_user`: PASSED
  - `test_duplicate_email_registration_rejected`: PASSED
  - `test_update_user_login`: PASSED
  - `test_async_repository_methods_with_mock_session`: PASSED

### B. Regression Suite (Existing Auth & Full Suite Tests)
- `tests/test_auth.py`: PASSED (9/9)
- `tests/test_auth_flow.py`: PASSED (1/1)
- `tests/contract/test_auth_contract.py`: PASSED (10/10)
- `tests/contract/test_consent_contract.py`: PASSED (5/5)
- `tests/test_legacy_local_boundary.py`: PASSED (5/5)
- `tests/db/test_postgres_user_repository.py`: PASSED against real PostgreSQL 16 container.
- **Full Backend Pytest Suite:** 2,718 passed, 0 failures, 26 xfailed (83.43% coverage, exceeding 70% threshold).

### C. Static Analysis & Linting
- **Ruff Check:** Passed (`All checks passed!`).
- **Ruff Format:** Passed (`150 files already formatted`).
- **Mypy Type Checking:** Passed on both Windows and Linux (`Success: no issues found in 158 source files`).

---

## 4. Dependencies & Audit Trail
- Dependency S1-LI01 (PR #125): Verified merged at `6ff41437acb5423d6fc3c0286f585cd89b639410`.
- Dependency S1-MR01 (PR #121): Verified merged at `653f0ffe129514543759051f278d7f1e39d0ac17`.
