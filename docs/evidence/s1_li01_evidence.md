# S1-LI01 Evidence: current_principal Dependency for Local Bearer and Real Sessions

**Task ID:** S1-LI01  
**Module:** Login & Identity  
**Task Description:** current_principal dependency for local bearer and real sessions  
**Base Branch:** `dev`  
**Feature Branch:** `s1-li01-clean`  
**Reviewer:** Mitali (`@mitali2701`)  
**Specification:** FinEx Final Implementation Plan (Sprint 1, page 10 & page 19)

---

## 1. Executive Summary & Acceptance Criteria Verification

According to the official **FinEx Final Implementation Plan** (page 10), the mandatory acceptance criteria for S1-LI01 are:
1. **Unit tests.**
2. **learner-a and learner-b unaffected.**

Both criteria are fully satisfied:
- **Criterion 1 (Unit tests):** Comprehensive test suite in `backend/tests/unit/test_principal.py` containing 27 targeted test cases covering data structures, credential extraction, local bearer authentication, real JWT session authentication, cross-user isolation, expiry, revocation, and HTTP 401 error responses.
- **Criterion 2 (Learner-a and Learner-b Unaffected):** Local sessions for both `learner-a` and `learner-b` resolve correctly to synthetic principals (`is_synthetic=True`, `roles=["user", "learner"]`) with strict identity isolation (`principal_a.user_id != principal_b.user_id`). Existing local application endpoints, contract tests, and legacy flows remain completely intact and unaffected.

---

## 2. Implementation Details

### File Placement & Cleanup
- Implemented in `backend/app/auth/principal.py`.
- Exported via `backend/app/auth/__init__.py`.
- Removed disconnected root-level directories `app/auth/` and `S1-LI01/` that previously bypassed Backend CI paths.

### Principal Data Model
Defined an immutable, frozen `Principal` dataclass that supports both object attribute access and dictionary subscripting:
```python
@dataclass(frozen=True)
class Principal:
    user_id: str
    is_synthetic: bool = False
    roles: list[str] = field(default_factory=lambda: ["user"])

    def __getitem__(self, item: str) -> Any: ...
    def get(self, item: str, default: Any = None) -> Any: ...
    def to_dict(self) -> dict[str, Any]: ...
```

### Dual-Authentication Strategy
The `get_principal` / `get_current_principal` dependency distinguishes and processes two distinct token classes:
1. **Real JWT Sessions:**
   - Identified by standard 3-part dot-separated JWT format (`token.count(".") == 2`).
   - Decoded using `decode_token(token)`.
   - Verified that `type == "access"`.
   - Verified that `jti` is not in `token_revocation_store`.
   - Returns `Principal(user_id=..., is_synthetic=False, roles=...)`.
2. **Local Educational Bearer Sessions:**
   - Validated against 43-character base64url format.
   - Looked up in `LocalApplicationStore` using SHA-256 token digest (`digest_token(token)`).
   - Validates that session exists, is not revoked (`revoked_at is None`), and has not expired (`expires_at > now`).
   - Returns `Principal(user_id=session.user.id, is_synthetic=True, roles=["user", "learner"])`.

### Strict HTTP 401 Error Handling
Consistent with FinEx security specifications, invalid, missing, expired, or revoked credentials return HTTP 401 Unauthorized:
- Missing `Authorization` header -> `HTTP 401 Unauthorized`
- Malformed header (non-Bearer scheme, extra parts, empty token) -> `HTTP 401 Unauthorized`
- Expired token (both JWT and local session) -> `HTTP 401 Unauthorized`
- Revoked token (both JWT revocation store and local session table) -> `HTTP 401 Unauthorized`
- Unknown / non-existent token -> `HTTP 401 Unauthorized`

---

## 3. Verification & Test Evidence

### A. Unit Tests (`backend/tests/unit/test_principal.py`)
```bash
cd backend && python -m pytest tests/unit/test_principal.py --no-cov -v
```
**Results:**
- `TestPrincipalDataModel`:
  - `test_principal_attributes` PASSED
  - `test_principal_dict_access` PASSED
  - `test_principal_to_dict` PASSED
  - `test_principal_immutable` PASSED
- `TestLocalBearerAuthentication`:
  - `test_learner_a_success` PASSED
  - `test_learner_b_success` PASSED
  - `test_learner_a_and_b_cross_isolation` PASSED
  - `test_local_session_expired_raises_401` PASSED
  - `test_local_session_revoked_raises_401` PASSED
  - `test_unknown_local_session_raises_401` PASSED
  - `test_malformed_local_token_format_raises_401` PASSED
- `TestRealJWTSession`:
  - `test_valid_real_jwt_session` PASSED
  - `test_valid_jwt_with_sub_fallback` PASSED
  - `test_valid_jwt_with_roles_list` PASSED
  - `test_expired_jwt_raises_401` PASSED
  - `test_revoked_jwt_raises_401` PASSED
  - `test_refresh_token_rejected_as_access` PASSED
  - `test_tampered_jwt_raises_401` PASSED
- `TestCredentialExtractionErrors`:
  - `test_missing_auth_header_raises_401` PASSED
  - `test_invalid_scheme_raises_401` PASSED
  - `test_malformed_header_parts_raises_401` PASSED
  - `test_empty_token_raises_401` PASSED
  - `test_explicit_token_param` PASSED
- `TestFastAPIDependencyIntegration`:
  - `test_endpoint_with_local_learner` PASSED
  - `test_endpoint_with_real_jwt` PASSED
  - `test_endpoint_without_auth_header_returns_401` PASSED
  - `test_endpoint_with_invalid_token_returns_401` PASSED

**Summary:** 27 passed, 0 failures.

### B. Linting & Formatting (`ruff`)
```bash
cd backend && python -m ruff check app tests
cd backend && python -m ruff format --check app tests
```
**Output:**
- `ruff check`: All checks passed!
- `ruff format --check`: 256 files already formatted.

### C. Type Checking (`mypy`)
```bash
cd backend && python -m mypy app
```
**Output:**
```
Success: no issues found in 142 source files
```

---

## 4. Unaffected Learners & Cross-Isolation Verification

Both `learner-a` and `learner-b` authenticate through their existing local session stores. When tested with real simulated session digests:
1. `learner-a` resolves to `Principal(user_id='uuid-learner-a', is_synthetic=True, roles=['user', 'learner'])`.
2. `learner-b` resolves to `Principal(user_id='uuid-learner-b', is_synthetic=True, roles=['user', 'learner'])`.
3. Identity isolation is strictly maintained (`user_id` values are independent and non-overlapping).
4. No modification was made to existing local store interfaces or database schemas.
