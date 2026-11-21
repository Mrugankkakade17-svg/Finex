# S1-MI01 Evidence & Verification Report

**Task ID:** `S1-MI01`  
**Task Title:** AI route behind principal; feedback persisted; refusal test set  
**Task Owner:** Mitali (`@mitali2701`)  
**Official Reviewer:** Mrugnak (`@Mrugankkakade17-svg` — verified via Updated Assignment Addendum 1, p. 2)  
**Target Branch:** `dev`  
**Feature Branch:** `feature/S1-MI01-ai-feedback-refusal`  
**Base Commit:** `6ff41437acb5423d6fc3c0286f585cd89b639410` (feat(auth): S1-LI01 current_principal dependency (#125))  
**Date:** 21 November 2026  

---

## 1. Executive Summary & Objective

In accordance with Sprint 1 specifications in the *FinEx Final Implementation Plan* (p. 10, 19, 20) and the *FinEx Combined Implementation Handbook* (p. 9, 19, 20, 21), this task establishes non-negotiable security guardrails, authentication enforcement, persistent scoped storage, and deterministic offline safety evaluation for the FinEx Grounded AI Assistant:

1. **Authentication Protection:** The AI Assistant endpoints (`POST /api/v1/ai/chat`, `POST /api/v1/ai/feedback`, and `GET /api/v1/ai/feedback`) are transitioned from unauthenticated prototype routes to strictly protected routes requiring `CurrentPrincipal = Depends(get_current_principal)`. Missing, invalid, expired, or tampered credentials are automatically rejected with HTTP 401 Unauthorized.
2. **Persistent Feedback Architecture:** Replaced the legacy prototype in-memory list (`_feedback_db`) with a production-ready, disk-persisted `AIFeedbackRepository` and `AIService`. Feedback records survive server restarts and support both SQLite (`local_db_path`) and PostgreSQL (`finex.ai_feedback`). Strict multi-user scoping ensures User A cannot access User B's feedback.
3. **Database Migration:** Created Alembic migration `fx_003b_ai_feedback.py` (`s1mi01_ai_feedback`), chaining cleanly from `s1mr02_fx003`. It establishes `finex.ai_feedback` with composite primary key `(user_id, feedback_id)`, index `ix_ai_feedback_user_created_at`, and foreign key cascade on `finex.users(user_id)`. Reversibility is verified via SQL generation and rollback scripts.
4. **Refusal Test Set & Offline Fake LLM Evaluation:** Authored `ai/eval/refusal_cases.jsonl` with 50 golden test cases (40 refusal cases covering all 6 prohibited keyword categories across mixed/upper/lower cases, prompt injections, and equities + 10 safe educational control queries). Created `ai/eval/run_eval.py` which executes 100% offline with zero network calls (`--fake-llm`) achieving 100% precision, 100% recall, 0 false positives, and 0 false negatives.

---

## 2. Handbook Requirement Traceability Matrix

| Handbook Requirement | Implementation / File | Test / Evidence | Status |
|---|---|---|---|
| **AI route behind principal** (`current_principal` dependency from S1-LI01) | `backend/app/routers/ai_assistant.py`<br>`backend/app/auth/principal.py` | `backend/tests/unit/test_ai_assistant_auth.py`<br>`backend/tests/security/test_prototype_routes_require_auth.py` | **COMPLETED** |
| **Strict 401 Unauthorized on unauthenticated requests** | `backend/app/routers/ai_assistant.py` via `Depends(get_current_principal)` | `test_chat_without_auth_header_returns_401`<br>`test_post_feedback_without_auth_returns_401` | **COMPLETED** |
| **Support for local educational bearer & real JWT sessions** | `backend/app/auth/principal.py`<br>`backend/app/routers/ai_assistant.py` | `test_chat_with_valid_jwt_returns_200`<br>`test_chat_with_synthetic_learner_principal_override` | **COMPLETED** |
| **Feedback persisted across application restarts** | `backend/app/repositories/ai_feedback_repository.py`<br>`backend/app/services/ai_service.py` | `backend/tests/unit/test_ai_feedback_persistence.py::TestAIFeedbackRepositoryPersistence` | **COMPLETED** |
| **User scoping and multi-user feedback isolation** | `AIFeedbackRepository`<br>`AIService.submit_feedback`<br>`AIService.list_feedback` | `test_user_isolation_in_repository`<br>`test_multi_user_api_isolation` | **COMPLETED** |
| **Dual storage support (SQLite for local dev & PostgreSQL for production)** | `backend/app/repositories/ai_feedback_repository.py` | Unit tests verify SQLite file persistence;<br>Database tests verify `finex.ai_feedback` contract | **COMPLETED** |
| **Alembic migration for operational schema** | `backend/alembic/versions/fx_003b_ai_feedback.py` (rev: `s1mi01_ai_feedback`) | Migration chaining verified from `s1mr02_fx003`; static DDL verified for upgrade & downgrade | **COMPLETED** |
| **Refusal test set with 30+ golden cases** | `ai/eval/refusal_cases.jsonl` (50 validated cases) | `test_refusal_cases_count_and_schema` verifies schema, category diversity, and intent classification | **COMPLETED** |
| **Coverage of all prohibited keyword categories** | `ai/eval/refusal_cases.jsonl` | 40 refusal cases covering buy, sell, stock selection, predictions, guarantees, tips, and jailbreaks | **COMPLETED** |
| **Safe educational control queries (zero false positives)** | `ai/eval/refusal_cases.jsonl` | 10 control cases (allocation, DCA, volatility, compound interest); 0 false positives verified | **COMPLETED** |
| **Offline Fake LLM evaluation harness** | `ai/eval/run_eval.py` (`--fake-llm`) | `cd ai; python eval/run_eval.py --fake-llm` executed with zero network calls (100% metrics) | **COMPLETED** |
| **Zero network socket enforcement** | `ai/eval/run_eval.py` (`offline_network_guard`) | `test_network_blocker_raises_on_socket_connect_attempt` verifies socket calls raise `NetworkBlockedError` | **COMPLETED** |
| **Layered architecture (Router -> Service -> Repository)** | `routers/ai_assistant.py`<br>`services/ai_service.py`<br>`repositories/ai_feedback_repository.py` | `ruff check`, `mypy app`, unit tests | **COMPLETED** |
| **Response envelope standards** | `APIResponse.success` in `routers/ai_assistant.py` | `test_lowercase_refusal_cases`, `test_post_feedback_with_valid_token_returns_200` | **COMPLETED** |
| **No sensitive credentials logged** | All routes and repositories | Verified no tokens, secrets, or passwords logged | **COMPLETED** |

---

## 3. Architecture & Data Flow

### 3.1 Layered Design
```
Client Request
      │
      ▼ (Authorization: Bearer <token>)
[FastAPI Router: backend/app/routers/ai_assistant.py]
      │  - Enforces Depends(get_current_principal)
      │  - Validates schemas (AIChatRequest, AIFeedbackRequest)
      │  - Extracts authenticated user_id
      ▼
[Service: backend/app/services/ai_service.py]
      │  - Enforces safety guardrails (COMPILED_PROHIBITED_PATTERNS)
      │  - Grounded educational retrieval (GROUNDED_CORPUS)
      │  - Manages feedback business rules
      ▼
[Repository: backend/app/repositories/ai_feedback_repository.py]
      │  - SQLite (local development / offline testing): local_db_path
      │  - PostgreSQL (production / Lakebase): finex.ai_feedback
      ▼
Persistent Storage (survives restart, strictly user-scoped)
```

### 3.2 Feedback Database Schema (`finex.ai_feedback`)
```sql
CREATE TABLE finex.ai_feedback (
    user_id TEXT NOT NULL,
    feedback_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    rating VARCHAR(20) NOT NULL,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_ai_feedback PRIMARY KEY (user_id, feedback_id),
    CONSTRAINT fk_ai_feedback_user_id_users FOREIGN KEY (user_id)
        REFERENCES finex.users (user_id) ON DELETE CASCADE
);

CREATE INDEX ix_ai_feedback_user_created_at
    ON finex.ai_feedback (user_id, created_at);
```

---

## 4. Migration & Database Verification

### 4.1 Migration Chaining
Alembic heads inspect cleanly:
```bash
$ python -m alembic heads
s1mi01_ai_feedback (head)
```

### 4.2 Upgrade Static SQL Verification
```sql
BEGIN;
CREATE TABLE finex.ai_feedback (
    user_id TEXT NOT NULL, 
    feedback_id TEXT NOT NULL, 
    message_id TEXT NOT NULL, 
    rating VARCHAR(20) NOT NULL, 
    comment TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_ai_feedback PRIMARY KEY (user_id, feedback_id), 
    CONSTRAINT fk_ai_feedback_user_id_users FOREIGN KEY(user_id) REFERENCES finex.users (user_id) ON DELETE CASCADE
);
CREATE INDEX ix_ai_feedback_user_created_at ON finex.ai_feedback (user_id, created_at);
UPDATE alembic_version SET version_num='s1mi01_ai_feedback' WHERE alembic_version.version_num = 's1mr02_fx003';
COMMIT;
```

### 4.3 Downgrade Static SQL Verification (Reversibility)
```sql
BEGIN;
DROP INDEX finex.ix_ai_feedback_user_created_at;
DROP TABLE finex.ai_feedback;
UPDATE alembic_version SET version_num='s1mr02_fx003' WHERE alembic_version.version_num = 's1mi01_ai_feedback';
COMMIT;
```

---

## 5. Offline Fake LLM Evaluation Harness Results

Execution Command (as specified on p. 20 of Implementation Plan):
```bash
cd ai; python eval/run_eval.py --fake-llm
```

Actual Terminal Output:
```text
=================================================================
  FinEx AI Safe Refusal & Education Evaluation Suite
  Mode: Offline Fake LLM (Zero Network)
  Cases File: eval\refusal_cases.jsonl
=================================================================
  Total Cases Evaluated : 50
  Passed Cases          : 50 / 50 (100.0%)
  Failed Cases          : 0
  True Positives (Refused): 40
  True Negatives (Safe)   : 10
  False Positives       : 0 (Target: 0)
  False Negatives       : 0 (Target: 0)
  Precision             : 1.0000 (100.0%)
  Recall                : 1.0000 (100.0%)
  Accuracy              : 1.0000 (100.0%)
  Network Calls Attempted: 0 (Network socket verified blocked)
=================================================================

Result: EVALUATION PASSED (100% deterministic conformance)
```

---

## 6. Test Execution Results

### 6.1 Focused S1-MI01 Test Suite (69 Tests)
Command:
```bash
pytest tests/unit/test_ai_refusal_case.py tests/unit/test_ai_assistant_auth.py tests/unit/test_ai_feedback_persistence.py tests/unit/test_ai_eval.py --no-cov -v
```
Results:
- `test_ai_refusal_case.py`: 50 passed (prohibited advice keywords, mixed/upper/lower case, citations)
- `test_ai_assistant_auth.py`: 12 passed (401 unauthorized, malformed tokens, expired JWTs, valid sessions)
- `test_ai_feedback_persistence.py`: 4 passed (disk persistence, restart survival, user isolation, 422 validations)
- `test_ai_eval.py`: 3 passed (JSONL schema validation, offline eval verification, socket blocker assertion)
- **Summary:** `69 passed in 5.30s` (100% pass rate).

### 6.2 Security Prototype Route Probe
Command:
```bash
pytest tests/security/test_prototype_routes_require_auth.py -k "ai_assistant" --no-cov -v
```
Results:
- `test_prototype_routes_require_auth[ai_assistant_POST_/api/v1/ai/chat]` -> `XPASS` (pehle unprotected tha, ab 401 reject karta hai)
- `test_prototype_routes_require_auth[ai_assistant_POST_/api/v1/ai/feedback]` -> `XPASS` (pehle unprotected tha, ab 401 reject karta hai)
- Status: **PASSED** (Authentication enforced).

### 6.3 Full Backend Test Suite
Command:
```bash
pytest -q
```
Results:
- `2725 passed, 11 skipped, 24 xfailed, 2 xpassed, 2526 warnings in 602.67s (0:10:02)`
- Coverage: **84.69%** (Required threshold: >= 70%)
- Status: **PASSED** (0 failures).

---

## 7. Static Analysis & Code Quality Checks

| Tool | Command | Exit Code | Result |
|---|---|---|---|
| **Ruff Linter** | `python -m ruff check .` | 0 | `All checks passed!` |
| **Ruff Formatter** | `python -m ruff format --check .` | 0 | `293 files already formatted` |
| **Mypy Typechecker** | `python -m mypy app` | 0 | `Success: no issues found in 149 source files` |

---

## 8. Verification & Reviewer Sign-off Checklist

- [x] All AI endpoints behind `current_principal`.
- [x] Unauthenticated requests rejected with HTTP 401.
- [x] Feedback persisted to disk (SQLite + PostgreSQL support).
- [x] Strict user scoping: User A cannot read or modify User B's feedback.
- [x] 50 golden refusal & safe educational cases in `ai/eval/refusal_cases.jsonl`.
- [x] `cd ai; python eval/run_eval.py --fake-llm` passes with zero network calls.
- [x] Alembic migration `s1mi01_ai_feedback` is linear and reversible.
- [x] All 69 unit tests pass.
- [x] Full test suite (2725 tests) passes with 84.69% coverage.
- [x] Linting, formatting, and typing clean.
- [x] Assigned reviewer verified: `@Mrugankkakade17-svg`.
