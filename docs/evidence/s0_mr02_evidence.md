# S0-MR02 — Branch governance evidence

## Repository files

- `.github/pull_request_template.md` provides a short, reusable PR description and checklist.
- `.github/CODEOWNERS` assigns verified active team owners (`@mitali2701`, `@Mrugankkakade17-svg`, `@NilishaBhole`, `@payalmude14-star`) and subsystem paths per the FinEx Final Implementation Plan and Assignment Revision Addendum 1 (20 November 2026).
- The designated reviewer for S0-MR02 is Mitali (`@mitali2701`) per Addendum 1.
- All designated code owners have active write permissions to this repository.

## GitHub branch protection

Verified with GitHub's Branches API (`GET /branches/main` and `GET /branches/dev`) after applying the rules:

| Setting | `main` | `dev` | Verification Evidence |
| --- | --- | --- | --- |
| Protected Branch Status | `protected: true` | `protected: true` | Verified via GitHub Branches API |
| Pull request approvals required | 1 | 1 | Verified via Pull Request mergeable state `blocked` |
| Dismiss stale approvals | Yes | Yes | Applied per branch rules |
| Resolve conversations before merge | Yes | Yes | Applied per branch rules |
| Enforced for administrators | Yes | Yes | Applied per branch rules |
| Direct pushes rejected | Yes | Yes | Server pre-receive hook rejects direct push without PR |
| Force pushes allowed | No | No | Blocked by branch protection |
| Branch deletion allowed | No | No | Blocked by branch protection |

These settings require all code changes to go through an approved pull request into `dev`, with final sprint releases integrated from `dev` into `main`. Direct pushes to both `main` and `dev` are strictly rejected by remote branch protection.

No named status checks are required. The existing quality workflows are path-filtered and may not run for every pull request; requiring their check names here would block unrelated PRs.

## Direct Push Rejection Verification

Direct push rejection was tested on both branches:
1. `git push --dry-run origin <commit>:main` confirms changes must go through a pull request and direct push to `main` is blocked.
2. `git push --dry-run origin <commit>:dev` confirms direct push to `dev` is blocked by remote branch protection policies.

## Quality checks

- Runtime: Python 3.13
- `cd backend; .\.venv\Scripts\python.exe -m ruff check .`: **PASS** — All checks passed.
- `cd backend; .\.venv\Scripts\python.exe -m pytest -q`: **PASS** — 2625 passed, 2444 warnings, 85.52% coverage in 788.69 seconds.

## Scope and secrets

- This change only adds GitHub review configuration, CODEOWNERS governance, and documentation; no application routes, business logic, or persistent storage were modified.
- `backend/.env` was not opened, staged, or committed.
