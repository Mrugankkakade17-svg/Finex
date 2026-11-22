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

According to the official **FinEx Final Implementation Plan** (page 10) and **Issue #26**, the mandatory acceptance criteria for S1-LI02 are:

1. **Existing auth contract tests pass.**
2. **11th failed login in the window is throttled (HTTP 429).**
3. **Hashes never logged (password hashes, raw passwords, tokens never in logs).**

All three criteria and all reviewer requirements from NilishaBhole on PR #126 are 100% satisfied:

- **Criterion 1 (Existing auth contract tests pass):** All existing authentication tests (`tests/contract/test_auth_contract.py`, `tests/test_auth.py`, `tests/test_auth_flow.py`, `tests/test_auth_service.py`, `tests/unit/test_auth_service.py`) pass without regression.
- **Criterion 2 (11th failed login throttled with HTTP 429 across workers):** Implemented thread-safe sliding window rate limiting via `LoginAttemptTracker` backed by `finex.failed_logins` with PostgreSQL advisory locking (`SELECT pg_advisory_lock(hashtext(email))`) and atomic SQL UPSERT. In multi-worker deployments, failed attempts are aggregated globally across all processes. The first 10 consecutive failed login attempts for a normalized email return HTTP 401 Unauthorized; the 11th failed attempt raises `LoginRateLimitExceededException` (HTTP 429, error code `RATE_LIMIT_EXCEEDED`). Successful authentication immediately resets the failed counter. Window expiration correctly clears past failures.
- **Criterion 3 (Hashes never logged):** Verified across all authentication service operations (`register`, `login`, `get_current_user`). Log messages only record operation intent, normalized email, and user ID. Caplog tests verify that neither raw passwords nor bcrypt password hashes are ever logged in debug, info, warning, or error logs.

---

## 2. Reviewer Feedback Resolution Matrix (NilishaBhole PR #126 Audit)

| # | Reviewer Requirement | Issue Description | Implemented Resolution | Verification Test | Status |
|---|----------------------|-------------------|------------------------|-------------------|--------|
| 1 | **Database URL Consistency** | Independent fallback hardcoded to `localhost:5432/finex_test` out of sync with settings. | `PostgresUserRepository.__init__` now sources URL from `get_settings().app_database_url` (with env fallback) and removed hardcoded fallback. | `test_database_url_sourced_from_settings_or_env`, `test_database_url_explicit_override` | **PASSED** |
| 2 | **No Silent In-Memory Fallback** | Unreachable DB silently persisted users into memory in PostgreSQL mode. | `is_postgres_mode()` explicitly enforced; if PostgreSQL is unreachable, raises `DatabaseUnavailableException` (HTTP 503 `DATABASE_UNAVAILABLE`) and refuses silent memory storage. | `test_no_silent_fallback_in_postgres_mode` | **PASSED** |
| 3 | **UUID Route Compatibility** | `GET /api/v1/users/{user_id}` and `/me` rejected string UUIDs and bypassed PostgreSQL repository. | Updated `users.py` to accept `user_id: str`, parse UUIDs or integers, and dynamically route queries through `get_user_repository()`. | `test_users_me_and_get_user_with_uuid`, `test_users_me_and_get_user_with_int_id` | **PASSED** |
| 4 | **Real DB Auth Integration Test** | Existing DB tests only checked async repo; synchronous `auth_service` was untested on real DB. | Added `test_auth_service_real_postgres_integration` running synchronous `register()` and `login()` against PostgreSQL with automated cleanup. | `tests/db/test_postgres_user_repository.py::test_auth_service_real_postgres_integration` | **PASSED** |
| 5 | **Atomic Failed-Login Throttling** | Race condition could allow concurrent attempts to bypass the 10-failure threshold. | Added per-email lock `login_tracker.get_lock(normalized_email)` making check, password verification, and attempt increment fully atomic. Added 20-thread concurrency test. | `test_concurrent_failed_logins_cannot_bypass_throttle` | **PASSED** |
| 6 | **Google Sign-In Compatibility** | Google sign-in metadata (`google_id`, `picture`) could be lost in PostgreSQL mode. | Added `_user_metadata` mapping, updated `create_user` and `_to_model` to preserve `google_id` and `picture`, and implemented `get_or_create_google_user` on `PostgresUserRepository`. | `test_google_sign_in_preserves_google_id_and_picture` | **PASSED** |
| 7 | **Merge Conflict with Dev** | Conflict in `backend/app/repositories/__init__.py` against `dev`. | Cleanly merged `origin/dev`, exporting both `ai_feedback_repository` and `postgres_user_repository`. | `git merge origin/dev` resolved and committed | **RESOLVED** |
| 8 | **PR Description Evidence** | Need live test outputs and exact breakdown recorded in PR. | Captured exact test outputs from pytest execution and updated PR #126 description via GitHub API. | Live PR #126 verification | **COMPLETED** |
| 9 | **Google Sign-In DB Persistence (Feedback item 1)** | `google_id` and `picture` stored in-memory in `_user_metadata`, not surviving process restarts. | Added `google_id` and `picture` to `finex.users` table, created Alembic migration `fx_006_s1_li02_auth_persistence.py`, updated SQL INSERT/SELECT queries in `postgres_user_repository.py`, and added restart-proof integration test. | `test_google_sign_in_persists_to_real_postgres` | **PASSED** |
| 10 | **Multi-Worker Rate Limiting (Feedback item 2)** | Throttling counter and locks stored in process-local memory, allowing multi-worker bypass. | Created `finex.failed_logins` table, implemented PostgreSQL advisory locking (`pg_advisory_lock(hashtext(email))`) with atomic SQL UPSERT (`INSERT ... ON CONFLICT DO UPDATE RETURNING failed_count`). Tested with two independent worker instances. | `test_multi_worker_failed_login_throttling_postgres` | **PASSED** |

---

## 3. Implementation Architecture & Code Changes

### A. Data Models & Alembic Migration
- `backend/app/models/dat02_models.py`:
  - Added `google_id` (`String(255), unique=True, nullable=True`) and `picture` (`Text, nullable=True`) to `User`.
  - Added `FailedLogin` model mapping to `finex.failed_logins` with `email`, `failed_count`, `first_attempt_at`, and `last_attempt_at`.
- `backend/alembic/versions/fx_006_s1_li02_auth_persistence.py`:
  - Chained from `s2mr01_fx005` to maintain linear Alembic migration history.
  - Adds `google_id` and `picture` columns to `finex.users`.
  - Creates unique partial index `ix_users_google_id` on `finex.users(google_id)` where `google_id IS NOT NULL`.
  - Creates table `finex.failed_logins` with primary key `email`, integer `failed_count`, and timestamp columns.

### B. PostgreSQL User Repository (`backend/app/repositories/postgres_user_repository.py`)
- Sourced database URL from `get_settings().app_database_url` (with environment variable fallback).
- Added `get_user_by_google_id(google_id)` for sync and memory fallback.
- Updated `get_user_by_email` and `get_user_by_id` SQL SELECT statements to retrieve `google_id` and `picture`.
- Updated `create_user` to persist `google_id` and `picture` directly into `finex.users`.
- Updated `get_or_create_google_user` to first check `get_user_by_google_id`, and if an existing email/password user exists, link Google credentials in PostgreSQL via `UPDATE finex.users SET google_id = ..., picture = ...`.
- Updated async methods (`get_user_by_email_async`, `get_user_by_id_async`, `create_user_async`) to handle `google_id` and `picture`.

### C. Multi-Worker Rate Limiting & Lockout Tracker (`backend/app/services/auth_service.py`)
- `PostgresKeyLock`: Dual lock acquiring a local thread lock and a PostgreSQL session advisory lock (`SELECT pg_advisory_lock(hashtext(key))`), providing multi-process mutual exclusion across Gunicorn/Uvicorn workers.
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

### Unit, Contract, and Authentication Flow Tests
```
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0 -- backend\.venv\Scripts\python.exe
rootdir: backend, configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False
collected 30 items

tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_first_10_failures_return_401_and_11th_returns_429 PASSED [  3%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_endpoint_returns_http_429_on_11th_failed_login PASSED [  6%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_successful_login_resets_failed_attempt_counter PASSED [ 10%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_window_expiration_clears_throttle PASSED [ 13%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_different_emails_have_isolated_counters PASSED [ 16%]
tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_concurrent_failed_logins_cannot_bypass_throttle PASSED [ 20%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_registration_does_not_log_passwords_or_hashes PASSED [ 23%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_login_success_does_not_log_passwords_or_hashes PASSED [ 26%]
tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_failed_login_does_not_log_raw_password PASSED [ 30%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_create_and_retrieve_user PASSED [ 33%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_duplicate_email_registration_rejected PASSED [ 36%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_update_user_login PASSED [ 40%]
tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_async_repository_methods_with_mock_session PASSED [ 43%]
tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_database_url_sourced_from_settings_or_env PASSED [ 46%]
tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_database_url_explicit_override PASSED [ 50%]
tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_no_silent_fallback_in_postgres_mode PASSED [ 53%]
tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_sign_in_preserves_google_id_and_picture PASSED [ 56%]
tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_uuid PASSED [ 60%]
tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_int_id PASSED [ 63%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_google_callback_success_shape PASSED [ 66%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_register_success_shape PASSED [ 70%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_login_success_shape PASSED [ 73%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_logout_success_shape PASSED [ 76%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_refresh_success_shape PASSED [ 80%]
tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_users_me_success_shape PASSED [ 83%]
tests/contract/test_error_envelope.py::TestErrorEnvelope::test_invalid_google_token_error_shape PASSED [ 86%]
tests/contract/test_error_envelope.py::TestErrorEnvelope::test_invalid_credentials_error_shape PASSED [ 90%]
tests/contract/test_error_envelope.py::TestErrorEnvelope::test_missing_auth_header_error_shape PASSED [ 93%]
tests/contract/test_error_envelope.py::TestErrorEnvelope::test_invalid_token_error_shape PASSED [ 96%]
tests/test_auth_flow.py::test_full_auth_flow PASSED                      [100%]

====================== 30 passed in 36.24s =======================
```

### Full Backend Suite Execution
- **Command:** `pytest -v --no-cov`
- **Result:** `2847 passed, 16 skipped, 5 xfailed, 2 xpassed in 473.42s (0:07:53)`
- **Regressions:** Zero.

### Static Analysis, Linting & Type Checking
- **Ruff Check:** Passed (`All checks passed!`).
- **Ruff Format:** Passed (`315 files already formatted`).
- **Mypy Type Check:** Passed (`Success: no issues found in 157 source files`).
