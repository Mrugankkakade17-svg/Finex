# S1-PA01 Spending and Alerts Persistence Evidence

## Implementation

- Added principal-scoped SQLite/PostgreSQL repositories for spending transactions and alert rules/notifications.
- Wired `app/routers/spending.py` and `app/routers/alerts.py` behind `current_principal`.
- Preserved existing route prefixes and API response shapes.
- Added repository restart-persistence checks and principal-exclusive spending/notification isolation checks.
- Added authenticated HTTP integration coverage for spending and alert success payloads and cross-principal writes/deletes.
- Removed the obsolete in-memory spending and alert state, and updated the unauthenticated alert probe to seed repository storage.
- Removed spending and alerts authentication probes from the Sprint 0 xfail set.

## Verification

Executed from `backend`:

```text
python -m ruff check .
python -m pytest -q --no-cov tests/test_s1_pa01_persistence.py tests/security/test_prototype_routes_require_auth.py
```

Results:

```text
All Ruff checks passed.
22 passed, 5 xfailed, 2 xpassed.
```

The five expected failures are the three unmigrated Goals auth probes and two Demo probes.
The two expected passes are AI auth probes that now reject anonymous requests but retain
their non-strict xfail markers until those routes are formally migrated.

The focused suite verifies SQLite data survives repository re-instantiation, including
category corrections and notification read state; principals cannot modify records owned
exclusively by another user; authenticated spending and alerts endpoints return the standard
success envelope; cross-principal category correction and rule deletion return HTTP 404;
and unauthenticated protection remains enforced.
