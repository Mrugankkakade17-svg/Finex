# S1-MR05: Ops flags, release sign-offs, and privacy authorization

## Summary

- Added a reusable admin-role dependency to the current principal auth module.
- Required an authenticated principal across operations, release, and privacy
  routers.
- Restricted feature flag toggles and UAT sign-off submission to admins; kept
  read operations and privacy actions available to authenticated principals.
- Promoted the three secured routers out of the prototype auth tests' expected
  failure set and added focused authorization and response contract coverage.
- Added task evidence at `docs/evidence/s1_mr05_evidence.md` and an `S1-MR05/`
  archive containing copies of all seven changed source/test files.

## Verification

- `cd backend && python -m ruff check .` — passed.
- `cd backend && python -m pytest -q` — **2,747 passed, 10 skipped, 15
  xfailed**; total coverage **83.73%** (70% minimum met).

## Review request

Target branch: `dev`

Reviewer: @NilishaBhole
