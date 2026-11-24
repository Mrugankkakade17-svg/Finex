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
   - Backed by table `finex.failed_logins` with atomic PostgreSQL UPSERT (`RETURNING failed_count`) and PostgreSQL session-level advisory locks (`pg_advisory_lock(hashtext(email))`) on dedicated connections with `autocommit=True`, ensuring cross-worker synchronization without holding open transaction blocks.
   - Successful login resets the attempt counter immediately via SQL `DELETE FROM finex.failed_logins WHERE email = %(email)s`.
   - **Status:** **PASSED**

3. **Criterion 3: Hashes are never logged.**
   - Plaintext passwords, bcrypt hashed passwords, client secrets, and raw authentication tokens are excluded from all logging statements across `INFO`, `WARNING`, and `ERROR` levels.
   - **Status:** **PASSED**

### Section 8 Definition of Done Verification
- **Reversible Database Migration:** `fx_006` adds `google_id` and `picture` to `finex.users` and creates `finex.failed_logins`. Linear migration chained from `s2mr01_fx005` with tested upgrade and downgrade paths.
- **Backward Compatibility:** Zero breaking changes to frozen routes (`/api/v1/auth/*` and `/api/v1/users/*`). Dynamic parsing in `users.py` handles both integer IDs and UUID strings.
- **Fail-Closed Mode:** When `APP_PERSISTENCE=postgresql`, an unreachable database raises `DatabaseUnavailableException` (HTTP 503 `DATABASE_UNAVAILABLE`), strictly refusing unpersisted in-memory storage.

---

## 2. Reviewer Feedback & Hardening Resolution Matrix

### Category A: Original Reviewer Concerns (Explicitly Raised by @NilishaBhole)

#### Initial Review (Comment #7066861860)
| # | Reviewer Item | Concern Raised | Implemented Resolution | Verification Test | Status |
|---|---------------|----------------|------------------------|-------------------|--------|
| A1 | **Database URL Consistency** | PostgreSQL repository selected URL separately from app settings, risking connecting to a different DB. | `PostgresUserRepository.__init__` sources URL from `get_settings().app_database_url` (with env fallback) and eliminated hardcoded localhost fallback. | `test_database_url_sourced_from_settings_or_env`, `test_database_url_explicit_override` | **PASSED** |
| A2 | **No Silent In-Memory Fallback** | When PostgreSQL was unreachable, registration succeeded silently into in-memory storage, risking data loss on restart. | `is_postgres_mode()` explicitly enforced; raises `DatabaseUnavailableException` (HTTP 503 `DATABASE_UNAVAILABLE`) if PostgreSQL is down, refusing in-memory storage. | `test_no_silent_fallback_in_postgres_mode`, `test_registration_and_login_fail_closed_when_postgres_unavailable` | **PASSED** |
| A3 | **UUID Route Compatibility** | PostgreSQL creates UUID user IDs, but existing user routes expected numeric IDs or read from old memory repo. | Updated `users.py` to accept `user_id: str`, parse UUIDs or integers, and dynamically route queries through `get_user_repository()`. | `test_users_me_and_get_user_with_uuid`, `test_users_me_and_get_user_with_int_id` | **PASSED** |
| A4 | **Real DB Auth Integration Test** | DB tests only checked async repo; synchronous `auth_service` was untested on real PostgreSQL. | Added `test_auth_service_real_postgres_integration` running synchronous `register()` and `login()` against PostgreSQL with automated cleanup. | `test_auth_service_real_postgres_integration` (CI PostgreSQL) | **PASSED** |
| A5 | **Atomic Failed-Login Throttling** | Race condition could allow concurrent attempts to bypass the 11th-attempt limit. | Added per-email lock `login_tracker.get_lock(normalized_email)` making check, password verification, and attempt increment fully atomic. Added 20-thread concurrency test. | `test_concurrent_failed_logins_cannot_bypass_throttle` | **PASSED** |
| A6 | **Google Sign-In Compatibility** | Google sign-in metadata (`google_id`, `picture`) could be lost in PostgreSQL mode. | Added `_user_metadata` mapping, updated `create_user` and `_to_model` to preserve `google_id` and `picture`, and implemented `get_or_create_google_user` on `PostgresUserRepository`. | `test_google_sign_in_preserves_google_id_and_picture` | **PASSED** |
| A7 | **Test Output in PR Description** | Issue asks for test output or log in PR description. | Added complete pytest execution commands and exact logs to PR description. | Verified in PR #126 description | **PASSED** |

#### Follow-Up Review (Comment #7083339212)
| # | Reviewer Item | Concern Raised | Implemented Resolution | Verification Test | Status |
|---|---------------|----------------|------------------------|-------------------|--------|
| A8 | **Google Sign-In DB Persistence (Feedback item 1)** | `google_id` and `picture` were in-memory in `_user_metadata`, not surviving process restarts. | Added `google_id` and `picture` to `finex.users` table, created Alembic migration `fx_006`, updated SQL INSERT/SELECT queries in `postgres_user_repository.py`, and verified survival across fresh repository instances. | `test_google_sign_in_persists_to_real_postgres` | **PASSED** |
| A9 | **Multi-Worker Rate Limiting (Feedback item 2)** | Throttling counter and locks stored in process-local memory, allowing multi-worker bypass. | Created `finex.failed_logins` table, implemented PostgreSQL advisory locking (`pg_advisory_lock(hashtext(email))`) with atomic SQL UPSERT (`INSERT ... ON CONFLICT DO UPDATE RETURNING failed_count`). Tested with two independent worker instances. | `test_multi_worker_failed_login_throttling_postgres` | **PASSED** |

---

### Category B: Additional Implementation Improvements (Engineering Hardening)
| # | Improvement | Purpose / Scope | Implemented Resolution | Verification Test | Status |
|---|-------------|-----------------|------------------------|-------------------|--------|
| B1 | **Explicit Dependency Injection** | Eliminate singleton binding fragility in tests. | Provided `get_user_repository()` factory and explicit repository parameter injection across auth services and routers. | `test_postgres_auth.py` unit suite | **PASSED** |
| B2 | **PostgreSQL Test Schema Isolation** | Prevent state pollution between parallel test runs. | Implemented isolated test database schemas and deterministic transactional cleanup fixtures. | `backend/tests/db/test_postgres_user_repository.py` | **PASSED** |
| B3 | **Zero Credential Logging Guarantee** | Enforce security compliance. | Explicit tests asserting password and hash substrings never appear in captured log records. | `TestPasswordHashNotLogged` (3 tests) | **PASSED** |

---

### Category C: Defensive Security Hardening & Extended Verification (Identified in Audits)
| # | Hardening Item | Security / Resilience Threat | Implemented Resolution | Verification Test | Status |
|---|----------------|------------------------------|------------------------|-------------------|--------|
| C1 | **Google Account Linking Delegation** | `auth_service.login_or_create_google_user` bypassed repository delegation on existing users. | Updated `login_or_create_google_user` to delegate directly to `repo.get_or_create_google_user` whenever available, ensuring PostgreSQL is always updated. | `test_google_linking_to_existing_email_password_user` | **PASSED** |
| C2 | **Google ID Conflict & Hijack Prevention** | An existing Google ID could theoretically be claimed with a different email without validation. | Added validation in `get_or_create_google_user`: if user exists with `google_id` but different email, raises `BadRequestException(error_code="GOOGLE_ACCOUNT_CONFLICT")`. | `test_google_id_conflict_with_different_email_rejected` | **PASSED** |
| C3 | **Transient DB Availability Recovery** | `is_db_available()` permanently cached `False` after a transient outage. | Updated `is_db_available()` to only cache `True`, retrying connection check on subsequent calls so temporary outages do not require process restarts. | `test_is_db_available_rechecks_on_prior_failure` | **PASSED** |
| C4 | **Advisory Lock Autocommit & Session Separation** | PostgreSQL advisory lock on non-autocommit connections could leave idle transaction blocks open. | Configured `PostgresKeyLock` to use dedicated physical connection with `autocommit=True`, verified cross-session mutual exclusion and release on exception. | `test_postgres_key_lock_mutual_exclusion_and_cleanup_real_postgres` | **PASSED** |
| C5 | **Unverified OAuth Identity & Linking Protection** | Unverified Google emails or expired tokens could link to existing accounts or bypass verification. | Enforced `email_verified` validation across `google_auth_service.py`, `auth_service.py`, and `postgres_user_repository.py`. Reject unverified payloads with `UNVERIFIED_GOOGLE_EMAIL` and expired tokens with `EXPIRED_GOOGLE_TOKEN`. | `test_unverified_google_identity_cannot_link_to_existing_password_user`, `test_verify_google_identity_unverified_email_in_jwt_claims_rejected`, `test_verify_google_identity_expired_jwt_rejected` | **PASSED** |

---

### Category D: Critical Security Hardening (Reviewer @Mrugankkakade17-svg — PR #126 Findings)
| # | Hardening Item | Security Threat & Reviewer Finding | Implemented Resolution | Verification Test | Status |
|---|----------------|------------------------------------|------------------------|-------------------|--------|
| D1 | **Elimination of Caller-Supplied Identity Bypass** | An unauthenticated attacker could supply a victim's `email` or `mock_payload` to `/api/v1/auth/google/callback` without credentials and obtain an active session (Account Takeover). | Eliminated all unauthenticated fallback paths in `routers/auth.py` and `google_auth_service.py`. Enforced mandatory credential string (`request.credential` or `request.id_token`). Missing/empty credentials raise `BadRequestException(error_code="MISSING_GOOGLE_CREDENTIAL", status_code=400)`. | `TestCallerSuppliedIdentityBypassRejection` (4 tests), `TestMissingCredentialRejection` (5 tests) | **PASSED** |
| D2 | **Cryptographic JWT Signature Verification against Google JWKS** | `_verify_token_string` decoded claims with `jwt.get_unverified_claims` without verifying cryptographic signatures against Google's public keys. | Implemented `GoogleOAuthVerifier` implementing `GoogleOAuthPort` with cryptographic token verification using Google's public JWKS (`https://www.googleapis.com/oauth2/v3/certs`) via `python-jose` with `RS256`. Added `GoogleJWKSClient` with caching, TTL, and offline test key overrides. | `TestCryptographicSignatureAndTampering` (4 tests) | **PASSED** |
| D3 | **Strict Google Claims Validation** | Tokens with wrong issuer, wrong audience, expired timestamp, or unverified email could be accepted. | Validated standard claims: `iss` in `{"accounts.google.com", "https://accounts.google.com"}`, `aud` matches `GOOGLE_CLIENT_ID`, `exp` not in past (`EXPIRED_GOOGLE_TOKEN`), `sub` non-empty, and `email_verified is True` explicitly required (rejects false, missing, None with `UNVERIFIED_GOOGLE_EMAIL`). | `TestUnverifiedEmailRejection` (3 tests), `TestExpiredTokenRejection` (1 test), `TestAudienceValidation` (1 test), `TestIssuerValidation` (2 tests) | **PASSED** |
| D4 | **Production Mock Gate (Fail-Closed Architecture)** | Mock tokens (`mock:...`) or test payloads could theoretically bypass verification in production configurations. | Gated mock verification behind `allow_mock_google_auth=True` AND `not is_production_like`. In `AppEnv.PROD` or `AppEnv.UAT`, mock verification is strictly forbidden and fails closed (`MOCK_AUTH_DISABLED`, HTTP 401). `Settings` model validator rejects `allow_mock_google_auth=True` in production. | `TestProductionMockGate` (3 tests) | **PASSED** |
| D5 | **Account Linking & Conflict Safeguards** | Verified identity from cryptographic token must be sole authority for email/Google ID; conflicting Google IDs must be rejected across repositories. | Token is the sole authority for identity. Enforced conflict rejection in both `UserRepository` and `PostgresUserRepository`: if a Google ID is already linked to another email, raises `GOOGLE_ACCOUNT_CONFLICT` (HTTP 400). Existing email accounts are safely linked only if email is verified. | `TestLegitimateTokenAndAccountLinking` (3 tests), `TestPostgresRepositoryParity` (2 tests) | **PASSED** |

---

## 3. Implementation Architecture & Code Changes

### A. Data Models & Alembic Migration
- `backend/app/models/dat02_models.py`:
  - Added `google_id` (`String(255), unique=True, nullable=True`) and `picture` (`Text, nullable=True`) to `User`.
  - Added `FailedLogin` model mapping to `finex.failed_logins` with `email` (PK), `failed_count`, `first_attempt_at` (`TIMESTAMP(timezone=True)`), and `last_attempt_at` (`TIMESTAMP(timezone=True)`).
- `backend/alembic/versions/fx_006_s1_li02_auth_persistence.py`:
  - Chained from `s2mr01_fx005` to maintain linear migration history.
  - Adds columns `google_id` (with unique index) and `picture` to `finex.users`.
  - Creates table `finex.failed_logins` with `TIMESTAMP(timezone=True)` for `first_attempt_at` and `last_attempt_at`.
  - Full bidirectional downgrade support (`op.drop_table`, `op.drop_column`, `op.drop_index`).

### B. Multi-Worker Rate Limiting & Advisory Locks
- **Serialization:** Uses PostgreSQL session-level advisory locks via `SELECT pg_advisory_lock(hashtext(%(k)s))` on a dedicated physical connection opened with `autocommit=True`. This prevents open transaction blocks (`IDLE in transaction`) and snapshot bloat.
- **Mutual Exclusion & Cleanup:** Tested across separate physical database sessions in `test_postgres_key_lock_mutual_exclusion_and_cleanup_real_postgres`. If a worker dies or throws an exception, PostgreSQL releases session advisory locks immediately.
- **Atomic UPSERT Query:**
  ```sql
  INSERT INTO finex.failed_logins (email, failed_count, first_attempt_at, last_attempt_at)
  VALUES (%(email)s, 1, NOW(), NOW())
  ON CONFLICT (email) DO UPDATE
  SET failed_count = CASE
          WHEN EXTRACT(EPOCH FROM (NOW() - finex.failed_logins.first_attempt_at)) >= %(window)s THEN 1
          ELSE finex.failed_logins.failed_count + 1
      END,
      first_attempt_at = CASE
          WHEN EXTRACT(EPOCH FROM (NOW() - finex.failed_logins.first_attempt_at)) >= %(window)s THEN NOW()
          ELSE finex.failed_logins.first_attempt_at
      END,
      last_attempt_at = NOW()
  RETURNING failed_count;
  ```
- **Timezone Consistency:** Both `NOW()` and `first_attempt_at` are evaluated inside PostgreSQL as `TIMESTAMPTZ`, eliminating application/database clock skew or naive/aware datetime comparison errors. The 900-second window boundary (`>= %(window)s`) is evaluated cleanly on PostgreSQL.

### C. Google OAuth Cryptographic Identity Verification & Safe Account Linking
- **Hexagonal Architecture Port & Verifiers:**
  - `app/ports/google_oauth_port.py`: Defines the `GoogleOAuthPort` protocol (`verify_google_token(id_token: str) -> GoogleIdentity`).
  - `app/ports/adapters/google_oauth_verifier.py`: Production cryptographic implementation (`GoogleOAuthVerifier`).
    - Uses `GoogleJWKSClient` to fetch and cache Google's public RSA keys (`https://www.googleapis.com/oauth2/v3/certs`).
    - Cryptographically verifies token signatures with `RS256` using `python-jose`.
    - Enforces standard claim validation: `iss` in `{"accounts.google.com", "https://accounts.google.com"}`, `aud == settings.google_client_id`, `exp > time.time()`, non-empty `sub`, non-empty `email`, and `email_verified is True` (rejecting false/missing with `UNVERIFIED_GOOGLE_EMAIL`).
    - Handles transient network errors by raising `ServiceUnavailableException` (HTTP 503).
    - Includes `GoogleJWKSClient.add_key_override()` allowing deterministic, offline RSA key registration in unit and regression tests.
  - `app/ports/adapters/mock_google_verifier.py`: Development/test mock verifier. Strictly gated behind `allow_mock_google_auth=True` and non-production runtime environments (`AppEnv.LOCAL`, `AppEnv.DEV`). In `Settings`, `allow_mock_google_auth` dynamically defaults to `True` only in non-production environments and `False` in production/UAT. Attempting to enable mock auth in `AppEnv.PROD` or `AppEnv.UAT` is strictly rejected by settings model validation with `ConfigurationError`, and runtime execution in production fails closed with `MOCK_AUTH_DISABLED` (HTTP 401).
- **Elimination of Caller-Supplied Identity Bypass:**
  - `app/routers/auth.py`: `google_callback` requires `request.credential` or `request.id_token`. Any request lacking a valid token string is immediately rejected with `BadRequestException(error_code="MISSING_GOOGLE_CREDENTIAL", status_code=400)`. All unauthenticated fallbacks to caller-supplied email or mock payloads have been completely removed.
  - `app/services/google_auth_service.py`: Delegates token verification to `google_oauth_verifier`. Rejects requests missing credentials.
- **Safe Account Linking & Hijack Prevention:**
  - `auth_service.login_or_create_google_user` ensures the cryptographically verified identity is the sole authority for email and Google ID.
  - Conflicting Google IDs (attempting to use an existing Google ID for a different email address, or linking a different Google ID to an already-linked email) are strictly rejected with `BadRequestException(error_code="GOOGLE_ACCOUNT_CONFLICT")` in both `UserRepository` and `PostgresUserRepository`.
  - Application session tokens (`access_token`, `refresh_token`) are issued only upon unconditional cryptographic verification.

---

## 4. Test Verification Evidence

### Authentication Unit, Contract & Flow Test Suite (36 Tests Passing)
```text
pytest backend/tests/unit/test_postgres_auth.py backend/tests/contract/test_auth_contract.py backend/tests/test_auth_flow.py --no-cov
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0
rootdir: backend, configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False
collected 36 items

backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_first_10_failures_return_401_and_11th_returns_429 PASSED [  2%]
backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_endpoint_returns_http_429_on_11th_failed_login PASSED [  5%]
backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_successful_login_resets_failed_attempt_counter PASSED [  8%]
backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_window_expiration_clears_throttle PASSED [ 11%]
backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_different_emails_have_isolated_counters PASSED [ 13%]
backend/tests/unit/test_postgres_auth.py::TestFailedLoginThrottling::test_concurrent_failed_logins_cannot_bypass_throttle PASSED [ 16%]
backend/tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_registration_does_not_log_passwords_or_hashes PASSED [ 19%]
backend/tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_login_success_does_not_log_passwords_or_hashes PASSED [ 22%]
backend/tests/unit/test_postgres_auth.py::TestPasswordHashNotLogged::test_failed_login_does_not_log_raw_password PASSED [ 25%]
backend/tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_create_and_retrieve_user PASSED [ 27%]
backend/tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_duplicate_email_registration_rejected PASSED [ 30%]
backend/tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_update_user_login PASSED [ 33%]
backend/tests/unit/test_postgres_auth.py::TestPostgresUserRepositoryUnit::test_async_repository_methods_with_mock_session PASSED [ 36%]
backend/tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_database_url_sourced_from_settings_or_env PASSED [ 38%]
backend/tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_database_url_explicit_override PASSED [ 41%]
backend/tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_no_silent_fallback_in_postgres_mode PASSED [ 44%]
backend/tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_registration_and_login_fail_closed_when_postgres_unavailable PASSED [ 47%]
backend/tests/unit/test_postgres_auth.py::TestDatabaseUrlConsistencyAndNoSilentFallback::test_is_db_available_rechecks_on_prior_failure PASSED [ 50%]
backend/tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_sign_in_preserves_google_id_and_picture PASSED [ 52%]
backend/tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_id_conflict_with_different_email_rejected PASSED [ 55%]
backend/tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_google_linking_to_existing_email_password_user PASSED [ 58%]
backend/tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_unverified_google_identity_cannot_link_to_existing_password_user PASSED [ 61%]
backend/tests/unit/test_postgres_auth.py::TestGoogleSignInCompatibility::test_login_or_create_google_user_rejects_unverified_email PASSED [ 63%]
backend/tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_uuid PASSED [ 66%]
backend/tests/unit/test_postgres_auth.py::TestUserRoutesUuidCompatibility::test_users_me_and_get_user_with_int_id PASSED [ 69%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_google_callback_success_shape PASSED [ 72%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_register_success_shape PASSED [ 75%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_login_success_shape PASSED [ 77%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_logout_success_shape PASSED [ 80%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_refresh_success_shape PASSED [ 83%]
backend/tests/contract/test_auth_contract.py::TestSuccessEnvelope::test_users_me_success_shape PASSED [ 86%]
backend/tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_google_token_error_shape PASSED [ 88%]
backend/tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_credentials_error_shape PASSED [ 91%]
backend/tests/contract/test_auth_contract.py::TestErrorEnvelope::test_missing_auth_header_error_shape PASSED [ 94%]
backend/tests/contract/test_auth_contract.py::TestErrorEnvelope::test_invalid_token_error_shape PASSED [ 97%]
backend/tests/test_auth_flow.py::test_full_auth_flow PASSED              [100%]

====================== 36 passed, 80 warnings in 54.99s =======================
```

### Token Repository & Google Auth Service Test Suite (16 Tests Passing)
```text
pytest backend/tests/unit/test_token_repo_and_google_service.py --no-cov -v
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0
rootdir: backend, configfile: pyproject.toml
collected 16 items

backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_store_and_validate_refresh_token PASSED [  7%]
backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_revoke_token PASSED [ 14%]
backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_revoke_empty_token PASSED [ 21%]
backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_revoke_user_tokens PASSED [ 28%]
backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_expired_token PASSED [ 35%]
backend/tests/unit/test_token_repo_and_google_service.py::TestTokenRepository::test_clear_repository PASSED [ 42%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_google_identity_with_caller_supplied_fields_rejected PASSED [ 50%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_google_identity_with_mock_payload_rejected PASSED [ 57%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_google_identity_missing_all PASSED [ 64%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_token_string_mock_email PASSED [ 71%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_token_string_empty PASSED [ 78%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_token_string_invalid PASSED [ 85%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_google_identity_unverified_email_in_jwt_claims_rejected PASSED [ 92%]
backend/tests/unit/test_token_repo_and_google_service.py::TestGoogleAuthService::test_verify_google_identity_expired_jwt_rejected PASSED [100%]

======================= 14 passed, 11 warnings in 0.78s =======================
```

### Google OAuth Security Regression Test Suite (28 Tests Passing)
```text
pytest backend/tests/security/test_google_oauth_security.py --no-cov
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0
rootdir: backend, configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
collected 28 items

backend/tests/security/test_google_oauth_security.py::TestCallerSuppliedIdentityBypassRejection::test_post_callback_with_raw_email_only_returns_400 PASSED [  3%]
backend/tests/security/test_google_oauth_security.py::TestCallerSuppliedIdentityBypassRejection::test_post_callback_with_raw_email_and_name_returns_400 PASSED [  7%]
backend/tests/security/test_google_oauth_security.py::TestCallerSuppliedIdentityBypassRejection::test_post_callback_with_mock_payload_dict_without_token_returns_400 PASSED [ 10%]
backend/tests/security/test_google_oauth_security.py::TestCallerSuppliedIdentityBypassRejection::test_service_verify_google_identity_without_token_raises_bad_request PASSED [ 14%]
backend/tests/security/test_google_oauth_security.py::TestMissingCredentialRejection::test_empty_json_body_returns_400 PASSED [ 17%]
backend/tests/security/test_google_oauth_security.py::TestMissingCredentialRejection::test_null_id_token_returns_400 PASSED [ 21%]
backend/tests/security/test_google_oauth_security.py::TestMissingCredentialRejection::test_empty_string_id_token_returns_400 PASSED [ 25%]
backend/tests/security/test_google_oauth_security.py::TestMissingCredentialRejection::test_whitespace_string_id_token_returns_400 PASSED [ 28%]
backend/tests/security/test_google_oauth_security.py::TestMissingCredentialRejection::test_empty_credential_field_returns_400 PASSED [ 32%]
backend/tests/security/test_google_oauth_security.py::TestCryptographicSignatureAndTampering::test_forged_signature_with_untrusted_key_rejected PASSED [ 35%]
backend/tests/security/test_google_oauth_security.py::TestCryptographicSignatureAndTampering::test_unknown_kid_rejected PASSED [ 39%]
backend/tests/security/test_google_oauth_security.py::TestCryptographicSignatureAndTampering::test_tampered_signature_bytes_rejected PASSED [ 42%]
backend/tests/security/test_google_oauth_security.py::TestCryptographicSignatureAndTampering::test_tampered_payload_claims_rejected PASSED [ 46%]
backend/tests/security/test_google_oauth_security.py::TestUnverifiedEmailRejection::test_email_verified_false_rejected PASSED [ 50%]
backend/tests/security/test_google_oauth_security.py::TestUnverifiedEmailRejection::test_missing_email_verified_claim_rejected PASSED [ 53%]
backend/tests/security/test_google_oauth_security.py::TestUnverifiedEmailRejection::test_string_false_email_verified_rejected PASSED [ 57%]
backend/tests/security/test_google_oauth_security.py::TestExpiredTokenRejection::test_expired_token_rejected PASSED [ 60%]
backend/tests/security/test_google_oauth_security.py::TestAudienceValidation::test_mismatched_audience_rejected PASSED [ 64%]
backend/tests/security/test_google_oauth_security.py::TestIssuerValidation::test_untrusted_issuer_rejected PASSED [ 67%]
backend/tests/security/test_google_oauth_security.py::TestIssuerValidation::test_valid_google_issuers_accepted PASSED [ 71%]
backend/tests/security/test_google_oauth_security.py::TestProductionMockGate::test_mock_token_rejected_in_production_environment PASSED [ 75%]
backend/tests/security/test_google_oauth_security.py::TestProductionMockGate::test_mock_token_rejected_when_allow_mock_auth_is_false PASSED [ 78%]
backend/tests/security/test_google_oauth_security.py::TestProductionMockGate::test_settings_validation_forbids_mock_auth_in_production PASSED [ 82%]
backend/tests/security/test_google_oauth_security.py::TestLegitimateTokenAndAccountLinking::test_valid_token_authenticates_and_issues_sessions PASSED [ 85%]
backend/tests/security/test_google_oauth_security.py::TestLegitimateTokenAndAccountLinking::test_verified_token_links_to_existing_password_user PASSED [ 89%]
backend/tests/security/test_google_oauth_security.py::TestLegitimateTokenAndAccountLinking::test_conflicting_google_id_for_different_email_rejected PASSED [ 92%]
backend/tests/security/test_google_oauth_security.py::TestPostgresRepositoryParity::test_postgres_repo_rejects_unverified_email_linking PASSED [ 96%]
backend/tests/security/test_google_oauth_security.py::TestPostgresRepositoryParity::test_postgres_repo_handles_verified_google_identity PASSED [100%]

======================= 28 passed, 21 warnings in 5.64s =======================
```

### Static Analysis, Linting & Type Checking
- `python -m ruff check . ../scripts/serve-s1-web-probe.py` => **All checks passed!**
- `python -m ruff format --check . ../scripts/serve-s1-web-probe.py` => **319 files already formatted.**
- `python -m mypy ... --platform linux --python-version 3.13` => **Success: no issues found in 168 source files.**
- `python -m mypy ... --platform win32 --python-version 3.13` => **Success: no issues found in 168 source files.**

---

## 5. Review Readiness Verdict
**Status:** `READY FOR REVIEW`  
All acceptance criteria, Nilisha's review items, and Mrugank's critical PR #126 security defect findings (caller-supplied identity bypass elimination and cryptographic JWT signature verification) have been completely resolved, architecturally hardened, and verified with 100% green tests.
