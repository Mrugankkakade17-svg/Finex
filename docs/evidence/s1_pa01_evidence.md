# S1-PA01 Spending and Alerts Persistence Evidence

## Implementation

- Added principal-scoped SQLite/PostgreSQL repositories for spending transactions and alert rules/notifications.
- Wired `app/routers/spending.py` and `app/routers/alerts.py` behind `current_principal`.
- Preserved existing route prefixes and API response shapes.
- Added cross-principal isolation coverage and persistent category correction/read/delete behavior.
- Removed spending and alerts authentication probes from the Sprint 0 xfail set.

## Verification

Executed:

```text
cd backend
python -m ruff check .
python -m pytest -q --no-cov tests/test_s1_pa01_persistence.py tests/security/test_prototype_routes_require_auth.py
```

Results:

```text
All Ruff checks passed.
21 passed, 5 xfailed, 2 xpassed.
```

The focused suite confirms SQLite persistence, cross-principal spending isolation,
cross-principal alert isolation, alert deletion ownership, and unauthenticated
protection for the spending and alerts routes.
