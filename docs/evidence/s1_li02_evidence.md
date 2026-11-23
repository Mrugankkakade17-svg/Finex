# S1-LI02 Evidence: Real Registration/Login on Postgres (bcrypt, lockout, rate limit)

**Task ID:** S1-LI02  
**Module:** Login & Identity  
**Task Description:** Real registration/login on Postgres (bcrypt, lockout, rate limit)  
**Base Branch:** `dev`  
**Feature Branch:** `feature/S1-LI02-postgres-auth`  
**Owner:** Mitali (`@mitali2701`)  
**Secondary Reviewer:** Nilisha (`@NilishaBhole`)  
**Specification:** FinEx Final Implementation Plan (Sprint 1, page 10 & page 19), Issue #26, PR #126.

---

## 1. Executive Summary & Acceptance Criteria Verification

According to the official **FinEx Final Implementation Plan** (page 10) and **Issue #26 (Section 6)**, there are exactly **three (3) formal acceptance criteria** for S1-LI02:

1. **Criterion 1: Existing auth contract tests pass.**
   - All existing authentication contract and flow tests pass without regression:
     - `tests/contract/test_auth_contract.py` (10 tests)
     - `tests/test_auth_flow.py` (1 test)
     - Response envelope formats strictly match `APIResponse.success`.
   - **Status:** **PASSED**

2. **Criterion 2: 11th failed login in the window is throttled (HTTP 429).**
   - The first 10 consecutive failed login attempts for a normalized email return HTTP 401 (`INVALID_CREDENTIALS`).
   - The 11th failed login attempt within the 900-second window raises `LoginRateLimitExceededException` (HTTP 429 `RATE_LIMIT_EXCEEDED`).
   - Backed by table `finex.failed_logins` with atomic PostgreSQL UPSERT (`RETURNING failed_count`) and PostgreSQL session advisory locking (`pg_advisory_lock`), guaranteeing cross-worker rate-limiting across multi-process application deployments (e.g., Gunicorn/Uvicorn).
   - Successful authentication immediately resets the failed attempt counter in PostgreSQL.
   - Window expiration (900 seconds) correctly clears past failures.
   - **Status:** **PASSED**

3. **Criterion 3: Hashes never logged.**
   - Verified across all authentication service operations (`register`, `login`, `get_current_user`, `google_callback`).
   - Caplog assertions confirm that neither plaintext passwords, bcrypt hashes, nor JWT tokens ever appear in debug, info, warning, or error logs.
   - **Status:** **PASSED**

### Supporting Definition of Done (Issue #26 Section 8) Verification
- **Reversible Database Migration:** `backend/alembic/versions/fx_006_s1_li02_auth_persistence.py` adds `google_id`, `picture` to `finex.users`, and table `finex.failed_logins`. Cleanly downgrades and chains linearly from `s2mr01_fx005`.
- **Zero Breaking Changes to Frozen Routes:** User routes accept both string UUIDs and integer IDs without 422 validation errors.
- **Strict User Isolation:** `GET /api/v1/users/{user_id}` enforces `req_uid == token_uid`, raising HTTP 404 on mismatch to prevent horizontal privilege escalation.
- **Fail-Closed PostgreSQL Mode:** If PostgreSQL is unreachable when `APP_PERSISTENCE=postgresql`, the repository refuses silent in-memory fallback and raises `DatabaseUnavailableException` (HTTP 503).

---

## 2. Reviewer Feedback Resolution Matrix (NilishaBhole PR #126 Audit)

| # | Reviewer Requirement | Issue Description | Implemented Resolution | Verification Test | Status |
|---|----------------------|-------------------|------------------------|-------------------|--------|
| 1 | **Database URL Consistency** | Independent fallback hardcoded to `localhost:5432/finex_test` out of sync with settings. | `PostgresUserRepository.__init__` now sources URL from `get_settings().app_database_url` (with env fallback) and removed hardcoded fallback. | `test_database_url_sourced_from_settings_or_env`, `test_database_url_explicit_override` | **PASSED** |
| 2 | **No Silent In-Memory Fallback** | Unreachable DB silently persisted users into memory in PostgreSQL mode. | `is_postgres_mode()` explicitly enforced; if PostgreSQL is unreachable, raises `DatabaseUnavailableException` (HTTP 503 `DATABASE_UNAVAILABLE`) and refuses silent memory storage. | `test_no_silent_fallback_in_postgres_mode`, `test_registration_and_login_fail_closed_when_postgres_unavailable` | **PASSED** |
| 3 | **UUID Route Compatibility** | `GET /api/v1/users/{user_id}` and `/me` rejected string UUIDs and bypassed PostgreSQL repository. | Updated `users.py` to accept `user_id: str`, parse UUIDs or integers, and dynamically route queries through `get_user_repository()`. | `test_users_me_and_get_user_with_uuid`, `test_users_me_and_get_user_with_int_id` | **PASSED** |
| 4 | **Real DB Auth Integration Test** | Existing DB tests only checked async repo; synchronous `auth_service` was untested on real DB. | Added `test_auth_service_real_postgres_integration` running synchronous `register()` and `login()` against PostgreSQL with automated cleanup. | `tests/db/test_postgres_user_repository.py::test_auth_service_real_postgres_integration` | **PASSED** |
| 5 | **Atomic Failed-Login Throttling** | Race condition could allow concurrent attempts to bypass the 10-failure threshold. | Added per-email lock `login_tracker.get_lock(normalized_email)` making check, password verification, and attempt increment fully atomic. Added 20-thread concurrency test. | `test_concurrent_failed_logins_cannot_bypass_throttle` | **PASSED** |
| 6 | **Google Sign-In Compatibility** | Google sign-in metadata (`google_id`, `picture`) could be lost in PostgreSQL mode. | Added `_user_metadata` mapping, updated `create_user` and `_to_model` to preserve `google_id` and `picture`, and implemented `get_or_create_google_user` on `PostgresUserRepository`. | `test_google_sign_in_preserves_google_id_and_picture` | **PASSED** |
| 7 | **Merge Conflict with Dev** | Conflict in `backend/app/repositories/__init__.py` against `dev`. | Cleanly merged `origin/dev`, exporting both `ai_feedback_repository` and `postgres_user_repository`. | Clean merge commits | **RESOLVED** |
| 8 | **PR Description Evidence** | Need live test outputs and exact breakdown recorded in PR. | Captured exact test outputs from pytest execution and updated PR #126 description via GitHub API. | Live PR #126 verification | **COMPLETED** |
| 9 | **Google Sign-In DB Persistence (Feedback item 1)** | `google_id` and `picture` stored in-memory in `_user_metadata`, not surviving process restarts. | Added `google_id` and `picture` to `finex.users` table, created Alembic migration `fx_006_s1_li02_auth_persistence.py`, updated SQL INSERT/SELECT queries in `postgres_user_repository.py`, and added restart-proof integration test. | `test_google_sign_in_persists_to_real_postgres` | **PASSED** |
| 10 | **Multi-Worker Rate Limiting (Feedback item 2)** | Throttling counter and locks stored in process-local memory, allowing multi-worker bypass. | Created `finex.failed_logins` table, implemented PostgreSQL advisory locking (`pg_advisory_lock(hashtext(email))`) with atomic SQL UPSERT (`INSERT ... ON CONFLICT DO UPDATE RETURNING failed_count`). Tested with two independent worker instances. | `test_multi_worker_failed_login_throttling_postgres` | **PASSED** |
| 11 | **Google Account Linking Delegation** | `auth_service.login_or_create_google_user` bypassed repository delegation on existing users, updating only local memory. | Updated `login_or_create_google_user` to delegate directly to `repo.get_or_create_google_user` whenever available, ensuring PostgreSQL is always updated. | `test_google_linking_to_existing_email_password_user` | **PASSED** |
| 12 | **Google ID Conflict & Hijack Prevention** | An existing Google ID could theoretically be claimed with a different email without validation. | Added validation in `get_or_create_google_user`: if user exists with `google_id` but different email, raises `BadRequestException(error_code="GOOGLE_ACCOUNT_CONFLICT")`. | `test_google_id_conflict_with_different_email_rejected` | **PASSED** |
| 13 | **Transient DB Availability Recovery** | `is_db_available()` permanently cached `False` after a failed connection. | Updated `is_db_available()` to only cache `True`, retrying connection check on subsequent calls so temporary outages do not require process restarts. | `test_is_db_available_rechecks_on_prior_failure` | **PASSED** |
| 14 | **Advisory Lock Autocommit & Session Separation** | PostgreSQL advisory lock on non-autocommit connections could leave idle transaction blocks open. | Configured `PostgresKeyLock` to use dedicated physical connection with `autocommit=True`, verified cross-session mutual exclusion and release on exception. | `test_postgres_key_lock_mutual_exclusion_and_cleanup_real_postgres` | **PASSED** |

---

## 3. Implementation Architecture & Code Changes

### A. Data Models & Alembic Migration
- `backend/app/models/dat02_models.py`:
  - Added `google_id` (`String(255), unique=True, nullable=True`) and `picture` (`Text, nullable=True`) to `User`.
  - Added `FailedLogin` model mapping to `finex.failed_logins` with `email` (PK), `failed_count`, `first_attempt_at`, and `last_attempt_at`.
- `backend/alembic/versions/fx_006_s1_li02_auth_persistence.py`:
  - Chained from `s2mr01_fx005` to maintain linear Alembic migration history (single head).
  - Adds `google_id` and `picture` columns to `finex.users`.
  - Creates unique partial index `ix_finex_users_google_id` on `finex.users(google_id)` where `google_id IS NOT NULL`.
  - Creates table `finex.failed_logins` with primary key `email`, integer `failed_count`, and timestamp columns.

### B. PostgreSQL User Repository (`backend/app/repositories/postgres_user_repository.py`)
- Sourced database URL from `get_settings().app_database_url` (with environment variable fallback).
- Added `get_user_by_google_id(google_id)` for sync and memory fallback.
- Updated `get_user_by_email` and `get_user_by_id` SQL SELECT statements to retrieve `google_id` and `picture`.
- Updated `create_user` to persist `google_id` and `picture` directly into `finex.users`.
- Updated `get_or_create_google_user` to:
  1. Check `get_user_by_google_id(google_id)`. If found, verify email match (raising `GOOGLE_ACCOUNT_CONFLICT` on mismatch).
  2. If user exists by email, link Google credentials in PostgreSQL via `UPDATE finex.users SET google_id = ..., picture = ...`.
  3. If user does not exist, create new user with Google metadata.
- Resilient `is_db_available()` checking that retries after transient failures.

### C. Multi-Worker Rate Limiting & Lockout Tracker (`backend/app/services/auth_service.py`)
- `PostgresKeyLock`: Dual lock acquiring a local thread lock and a dedicated PostgreSQL session advisory lock (`SELECT pg_advisory_lock(hashtext(key))`) with `autocommit=True`, providing multi-process mutual exclusion across Gunicorn/Uvicorn workers without leaving open server transactions.
- `LoginAttemptTracker`:
  - In PostgreSQL mode, queries and updates `finex.failed_logins`.
  - `is_throttled(key)`: Checks `failed_count` and window expiration in `finex.failed_logins`.
  - `record_failed_attempt(key)`: Executes atomic PostgreSQL `INSERT ... ON CONFLICT (email) DO UPDATE` returning the updated `failed_count`.
  - `reset_attempts(key)`: Deletes record from `finex.failed_logins` upon successful login.
  - Graceful fallback to thread-safe in-memory sliding window when PostgreSQL is not configured or in local test mode.

### D. User Profile Routes (`backend/app/routers/users.py`)
- `GET /api/v1/users/{user_id}` accepts `user_id: str` supporting both integer IDs and string UUIDs without 422 validation errors.
- Queries routed dynamically to active persistence repository.

---

## 4. Test Verification Evidence

### Unit, Contract, and Authentication Flow Tests (34 Tests)
```
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0 -- backend/.venv/Scripts/python.exe
rootdir: backend, configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False
collected 34 items

tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_first_10_failures_return_401_and_11th_returns_429 PASSED [  2%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_endpoint_returns_http_429_on_11th_failed_login PASSED [  5%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_successful_login_resets_failed_attempt_counter PASSED [  8%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_window_expiration_clears_throttle PASSED [ 11%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_different_emails_have_isolated_counters PASSED [ 14%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_concurrent_failed_logins_cannot_bypass_throttle PASSED [ 17%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_registration_does_not_log_passwords_or_hashes PASSED [ 20%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_login_success_does_not_log_passwords_or_hashes PASSED [ 23%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_failed_login_does_not_log_raw_password PASSED [ 26%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_create_and_retrieve_user PASSED [ 29%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_duplicate_email_registration_rejected PASSED [ 32%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_update_user_login PASSED [ 35%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_async_repository_methods_with_mock_session PASSED [ 38%]
tests/unit/test_database_url_consistency_and_no_silent_fallback.py::test_database_url_sourced_from_settings_or_env PASSED [ 41%]
tests/unit/test_database_url_consistency_and_no_silent_fallback.py::test_database_url_explicit_override PASSED [ 44%]
tests/unit/test_database_url_consistency_and_no_silent_fallback.py::test_no_silent_fallback_in_postgres_mode PASSED [ 47%]
tests/unit/test_database_url_consistency_and_no_silent_fallback.py::test_registration_and_login_fail_closed_when_postgres_unavailable PASSED [ 50%]
tests/unit/test_database_url_consistency_and_no_silent_fallback.py::test_is_db_available_rechecks_on_prior_failure PASSED [ 52%]
tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_sign_in_preserves_google_id_and_picture PASSED [ 55%]
tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_id_conflict_with_different_email_rejected PASSED [ 58%]
tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_linking_to_existing_email_password_user PASSED [ 61%]
tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_uuid PASSED [ 64%]
tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_int_id PASSED [ 67%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_google_callback_success_shape PASSED [ 70%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_register_success_shape PASSED [ 73%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_login_success_shape PASSED [ 76%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_logout_success_shape PASSED [ 79%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_refresh_success_shape PASSED [ 82%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_users_me_success_shape PASSED [ 85%]
tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_google_token_error_shape PASSED [ 88%]
tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_credentials_error_shape PASSED [ 91%]
tests/contract/test_auth_contract.py::TestErrorEnvelope::test_missing_auth_header_error_shape PASSED [ 94%]
tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_token_error_shape PASSED [ 97%]
tests/test_auth_flow.py::test_full_auth_flow PASSED                      [100%]

====================== 34 passed in 54.26s =======================
```

### Static Analysis, Linting & Type Checking
- **Ruff Check:** Passed (`All checks passed!`).
- **Ruff Format:** Passed (`316 files already formatted`).
- **Mypy Type Check:** Passed (`Success: no issues found in 157 source files`).
