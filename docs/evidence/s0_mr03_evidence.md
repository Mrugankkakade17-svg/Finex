# S0-MR03 — Gitleaks history scan evidence

## Execution

- Scanner: Gitleaks 8.30.1 (official Windows x64 release)
- SHA-256 of downloaded archive: `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`
- Command: `gitleaks git --log-opts='--all' --redact=100 --no-banner .`
- Scope: all refs available locally after fetching from `origin`
- Result: **PASS** — 43 commits scanned, approximately 106.57 MB, no leaks found; exit code 0

The report was not saved to the repository. No secret values were printed or
retained, and no rotation list was generated.

## Environment and scope notes

- `backend/.env` is ignored by Git and was not opened.
- The result applies to Git history reachable from refs fetched for this scan.
- Gitleaks findings would require provider-side validation to determine whether
  a credential is live; zero findings do not establish that every possible
  credential format is absent.

## Quality checks

Commands run from `backend/` with the project virtual environment:

| Command | Result |
| --- | --- |
| `.\.venv\Scripts\python.exe -m ruff check .` | **PASS** — All checks passed |
| `.\.venv\Scripts\python.exe -m pytest -q` | **PASS** — 2625 passed, 2444 warnings, 85.52% coverage in 870.25 seconds |
