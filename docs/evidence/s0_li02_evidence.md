# FinEx Sprint 0 Task S0-LI02 Evidence: Auth Probe Test for Prototype Routers and Demo

- **Task ID:** S0-LI02
- **GitHub Issue:** #15
- **Document Reference:** `FINEX-EVIDENCE-S0-LI02-V1`
- **Owner / Author:** Mitali Dobale (`@mitali2701`)
- **Assigned Reviewer:** Mrugank Kakade (`@Mrugankkakade17-svg`)
- **Target File:** `backend/tests/security/test_prototype_routes_require_auth.py`
- **Feature Branch:** `feature/s0-li02` (Base: `dev`)
- **Authoritative Acceptance Criterion:** *"One xfail per route now, pass after S1."*
- **Date:** 20 November 2026

---

## 1. Executive Summary

Task **S0-LI02** establishes security probe tests for the seven prototype routers and demo endpoints in the FinEx platform. In Sprint 0, these prototype endpoints are mounted without authentication dependencies to enable parallel feature prototyping. In Sprint 1, when centralized authentication (`current_principal` / JWT bearer dependency) is mounted across the API, these routes will enforce strict authentication.

Per the authoritative acceptance criterion:
> *"One xfail per route now, pass after S1."*

This implementation establishes an exhaustive test suite covering all 26 individual route operations across the eight target routers. In Sprint 0, all 26 tests report `XFAIL` (exit code `0`). In Sprint 1, once authentication is introduced, these tests will transition to passing.

---

## 2. Inventory of All 26 Target Endpoint Operations

All 26 endpoint operations across the 7 prototype routers and the demo router were inspected and mapped to valid schemas and seeded resources to ensure requests reach their intended handlers:

| # | Router Module | HTTP Method | Endpoint Route Path | Expected S0 Status | S0 Auth Probe Behavior |
| :-: | :--- | :---: | :--- | :---: | :--- |
| 1 | `goals.py` | `POST` | `/api/v1/goals` | `200 OK` | Reaches handler; creates goal with deterministic compounding |
| 2 | `goals.py` | `GET` | `/api/v1/goals` | `200 OK` | Reaches handler; returns goals list |
| 3 | `goals.py` | `GET` | `/api/v1/goals/{goal_id}` | `200 OK` | Reaches handler; retrieves seeded goal `seed-goal-001` |
| 4 | `spending.py` | `GET` | `/api/v1/spending/transactions` | `200 OK` | Reaches handler; returns masked transactions |
| 5 | `spending.py` | `POST` | `/api/v1/spending/correct-category` | `200 OK` | Reaches handler; corrects category for `tx-001` |
| 6 | `spending.py` | `GET` | `/api/v1/spending/trends` | `200 OK` | Reaches handler; computes deterministic spending trends |
| 7 | `alerts.py` | `GET` | `/api/v1/alerts/rules` | `200 OK` | Reaches handler; lists active alert rules |
| 8 | `alerts.py` | `POST` | `/api/v1/alerts/rules` | `200 OK` | Reaches handler; creates alert rule |
| 9 | `alerts.py` | `DELETE` | `/api/v1/alerts/rules/{rule_id}` | `200 OK` | Reaches handler; deletes seeded rule `rule-del-001` |
| 10 | `alerts.py` | `GET` | `/api/v1/alerts/notifications` | `200 OK` | Reaches handler; lists notifications with unread counts |
| 11 | `alerts.py` | `POST` | `/api/v1/alerts/notifications/{id}/read` | `200 OK` | Reaches handler; marks notification `notif-001` as read |
| 12 | `ops_hardening.py` | `GET` | `/api/v1/ops/observability` | `200 OK` | Reaches handler; reports observability metrics |
| 13 | `ops_hardening.py` | `GET` | `/api/v1/ops/flags` | `200 OK` | Reaches handler; lists feature flags |
| 14 | `ops_hardening.py` | `POST` | `/api/v1/ops/flags/{flag_key}/toggle` | `200 OK` | Reaches handler; toggles feature flag |
| 15 | `ops_hardening.py` | `GET` | `/api/v1/ops/preflight` | `200 OK` | Reaches handler; returns release preflight report |
| 16 | `release_handover.py` | `GET` | `/api/v1/release/manifest` | `200 OK` | Reaches handler; returns Golden Master manifest |
| 17 | `release_handover.py` | `GET` | `/api/v1/release/uat-signoffs` | `200 OK` | Reaches handler; returns Anand Sharma & Priya Patel sign-offs |
| 18 | `release_handover.py` | `POST` | `/api/v1/release/uat-signoffs` | `201 Created` | Reaches handler; records new UAT verification record |
| 19 | `release_handover.py` | `GET` | `/api/v1/release/dr-drill` | `200 OK` | Reaches handler; returns DR drill metrics (RTO/RPO) |
| 20 | `release_handover.py` | `GET` | `/api/v1/release/handover` | `200 OK` | Reaches handler; returns full platform handover summary |
| 21 | `privacy.py` | `GET` | `/api/v1/privacy/consent` | `200 OK` | Reaches handler; returns consent audit status |
| 22 | `privacy.py` | `POST` | `/api/v1/privacy/action` | `200 OK` | Reaches handler; queues data export action |
| 23 | `ai_assistant.py` | `POST` | `/api/v1/ai/chat` | `200 OK` | Reaches handler; generates grounded educational response |
| 24 | `ai_assistant.py` | `POST` | `/api/v1/ai/feedback` | `200 OK` | Reaches handler; logs thumbs-up/down feedback |
| 25 | `demo.py` | `GET` | `/api/v1/demo/error` | `400 Bad Request` | Reaches handler; triggers demo 400 client exception |
| 26 | `demo.py` | `GET` | `/api/v1/demo/error500` | `500 Server Error` | Reaches handler; triggers demo 500 server exception |

---

## 3. Test Design & XFAIL Transition Architecture

### 3.1 Strict Security Assertion
The test evaluates authentic authorization gating by asserting:
```python
assert response.status_code in (
    status.HTTP_401_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN,
), f"Expected HTTP 401 or 403 for unauthenticated access to {path}, got HTTP {response.status_code}"
```

### 3.2 Safe XFAIL Transition Mechanism
- In Sprint 0, the test is decorated with:
  ```python
  @pytest.mark.xfail(
      strict=False,
      reason="Prototype route does not yet enforce authentication in Sprint 0; will pass in Sprint 1",
  )
  ```
- **Sprint 0:** Unauthenticated requests reach the route handlers (returning 200, 201, 400, or 500). Because `status_code not in (401, 403)`, an `AssertionError` is raised. Pytest catches this and reports `XFAIL` (exit code `0`).
- **Sprint 1:** When authentication is attached, unauthenticated requests return `401` or `403`. With `strict=False`, Pytest reports `XPASS` (exit code `0`), preventing CI failures. Removing the decorator produces permanent `PASSED` results.

---

## 4. Quality Validation & Terminal Output

### 4.1 Ruff Lint Check
- **Command:** `cd backend; .\.venv\Scripts\python.exe -m ruff check tests/security/test_prototype_routes_require_auth.py`
- **Exit Code:** `0`
- **Output:**
```text
All checks passed!
```

### 4.2 Ruff Format Check
- **Command:** `cd backend; .\.venv\Scripts\python.exe -m ruff format --check tests/security/test_prototype_routes_require_auth.py`
- **Exit Code:** `0`
- **Output:**
```text
1 file already formatted
```

### 4.3 Pytest Execution on S0-LI02 Test File
- **Command:** `cd backend; .\.venv\Scripts\python.exe -m pytest tests/security/test_prototype_routes_require_auth.py -v -o addopts=""`
- **Exit Code:** `0`
- **Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.13.17, pytest-8.4.1, pluggy-1.7.0 -- C:\Users\ASUS\Downloads\Finex-extracted\Finex\backend\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\ASUS\Downloads\Finex-extracted\Finex\backend
configfile: pyproject.toml
plugins: anyio-4.16.0, asyncio-1.4.0, cov-7.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 26 items

tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[goals_POST_/api/v1/goals] XFAIL [  3%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[goals_GET_/api/v1/goals] XFAIL [  7%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[goals_GET_/api/v1/goals/seed-goal-001] XFAIL [ 11%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[spending_GET_/api/v1/spending/transactions] XFAIL [ 15%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[spending_POST_/api/v1/spending/correct-category] XFAIL [ 19%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[spending_GET_/api/v1/spending/trends] XFAIL [ 23%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[alerts_GET_/api/v1/alerts/rules] XFAIL [ 26%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[alerts_POST_/api/v1/alerts/rules] XFAIL [ 30%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[alerts_DELETE_/api/v1/alerts/rules/rule-del-001] XFAIL [ 34%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[alerts_GET_/api/v1/alerts/notifications] XFAIL [ 38%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[alerts_POST_/api/v1/alerts/notifications/notif-001/read] XFAIL [ 42%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ops_hardening_GET_/api/v1/ops/observability] XFAIL [ 46%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ops_hardening_GET_/api/v1/ops/flags] XFAIL [ 50%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ops_hardening_POST_/api/v1/ops/flags/FEATURE_AI_ASSISTANT/toggle] XFAIL [ 53%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ops_hardening_GET_/api/v1/ops/preflight] XFAIL [ 57%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[release_handover_GET_/api/v1/release/manifest] XFAIL [ 61%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[release_handover_GET_/api/v1/release/uat-signoffs] XFAIL [ 65%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[release_handover_POST_/api/v1/release/uat-signoffs] XFAIL [ 69%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[release_handover_GET_/api/v1/release/dr-drill] XFAIL [ 73%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[release_handover_GET_/api/v1/release/handover] XFAIL [ 76%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[privacy_GET_/api/v1/privacy/consent] XFAIL [ 80%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[privacy_POST_/api/v1/privacy/action] XFAIL [ 84%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ai_assistant_POST_/api/v1/ai/chat] XFAIL [ 88%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[ai_assistant_POST_/api/v1/ai/feedback] XFAIL [ 92%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[demo_GET_/api/v1/demo/error] XFAIL [ 96%]
tests/security/test_prototype_routes_require_auth.py::test_prototype_routes_require_auth[demo_GET_/api/v1/demo/error500] XFAIL [100%]

====================== 26 xfailed, 12 warnings in 2.84s =======================
```

### 4.4 Full Backend Test Suite Execution
- **Command:** `cd backend; .\.venv\Scripts\python.exe -m pytest`
- **Exit Code:** `0`
- **Coverage Result:** `Required test coverage of 70% reached. Total coverage: 87.42%`
- **Summary:** `2625 passed, 26 xfailed, 2449 warnings in 578.20s (0:09:38)`
- **Regression Check:** 0 failures, 0 regressions in existing tests.

---

## 5. Scope & Limitations Analysis

1. **Zero Blocked Endpoints:** All 26 target route operations are reached and return their expected Sprint 0 behavior.
2. **Prerequisite Resource Seeding:** An autouse fixture cleanly seeds temporary in-memory records (`seed-goal-001` and `rule-del-001`) and pops them upon teardown, preventing cross-test pollution and ensuring path operations execute successfully.
3. **No Unintended Changes:** No application routers, middlewares, schemas, or existing test suites were modified.
4. **No Unnecessary Files:** No redundant `__init__.py` or auxiliary packages were added.
