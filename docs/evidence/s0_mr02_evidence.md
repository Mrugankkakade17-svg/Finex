# S0-MR02 — Branch governance evidence

## Repository files

- `.github/pull_request_template.md` provides a short, reusable PR description and checklist.
- `.github/CODEOWNERS` assigns `@likhitanikhare` as the code owner.
- The designated reviewer has write access to this repository.

## GitHub branch protection

Verified with GitHub's branch-protection API after applying the rules:

| Setting | `main` | `dev` |
| --- | --- | --- |
| Pull request approvals required | 1 | 1 |
| Code-owner approval required | Yes | Yes |
| Dismiss stale approvals | Yes | Yes |
| Resolve conversations before merge | Yes | Yes |
| Enforced for administrators | Yes | Yes |
| Force pushes allowed | No | No |
| Branch deletion allowed | No | No |

These settings require changes to go through an approved pull request, including for administrators, so direct pushes are blocked.

No named status checks are required. The existing quality workflows are path-filtered and may not run for every pull request; requiring their check names here would block unrelated PRs.

## Quality checks

- Runtime: Python 3.13
- `cd backend; .\.venv\Scripts\python.exe -m ruff check .`: **PASS** — All checks passed.
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`: **PASS** — 2625 passed, 2444 warnings, 85.52% coverage in 788.69 seconds.

## Scope and secrets

- This change only adds GitHub review configuration and documentation; no routes, application logic, or persistent storage were changed.
- `backend/.env` was not opened, staged, or committed.
