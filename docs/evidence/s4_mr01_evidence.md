# S4-MR01: NumPy and SciPy dependencies

## Delivered

- Added pinned NumPy (`2.3.2`) and SciPy (`1.16.1`) dependencies to `backend/requirements.txt` so backend and CI installs can provide numerical and scientific calculation libraries needed by Sprint 4 work.
- No Alembic migration was added. S4-MR01 changes dependency installation only and introduces no database schema change, so there is nothing to upgrade or downgrade.
- No application routes, persistent data, or user isolation behavior were changed by this task.

## Verification

- `python -m ruff check .` (from `backend`) — passed: `All checks passed!`.
- `python -m pytest -q` (from `backend`) — started, but did not complete locally; interrupted after repeated `.s` progress with no summary. No full-suite pass is claimed.
- `python -m pip install -r requirements.txt` — could not complete on the local Python 3.14 environment: the existing `pydantic-core==2.33.2` dependency fell back to a source build, and its temporary Rust bootstrap failed with a Windows permission error. This does not indicate a failure in the new NumPy/SciPy pins; pip resolved both package wheels for CPython 3.14, but installing those wheels into the user site also hit a Windows permission error. CI installation remains to be confirmed by the PR checks.
- `git diff --check` — passed.

## Easy-language summary

The backend's install list now includes NumPy and SciPy, which provide tools for numerical and scientific calculations. No database change was needed because this task does not change stored data or tables.
