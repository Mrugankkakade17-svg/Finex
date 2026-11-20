# Backend baseline (S0-LI01)

- Date: 19 Nov 2026
- Commit: 41539f8882057504e5198827cd61e3b9826fe409
- Branch measured: dev (work branch: feature/S0-LI01-backend-baseline)
- Python: 3.13.17 (virtual environment) | OS: Windows 11, PowerShell 5.1
- Working tree clean at start: yes

## Setup notes
- Python 3.13.17 installed alongside 3.14.5; project run through `py -3.13 -m venv .venv`
- From `backend/`, `pip install -r requirements.txt` installed ruff 0.16.2, mypy 2.3.0 and pytest 8.4.1; no extra installs needed
- PowerShell 5.1 commands below are run after changing to `backend/` with `Set-Location backend`

## Results
| Check | Command | Result |
|---|---|---|
| Ruff | `python -m ruff check .` | All checks passed |
| Mypy | `python -m mypy app` | Success: no issues found in 141 source files |
| Collect-only | `python -m pytest --collect-only -q` | 2625 tests collected in 10.75s |
| Pytest | `python -m pytest -q` | 2625 passed, 0 failed, 2444 warnings in 317.12s |
| Coverage | (part of pytest run) | 85.52% (6249 statements, 905 missed); required 70% reached |

## Raw command output

The attached logs are fresh reruns from 20 Nov 2026, executed from `backend/` with the project virtual environment (Python 3.13.15; Ruff 0.16.2; mypy 2.3.0; pytest 8.4.1). Test counts and coverage match the baseline; runtime varies by environment.

- [Ruff](./logs/ruff.txt)
- [Mypy](./logs/mypy.txt)
- [Pytest](./logs/pytest.txt)

## Reconciliation with the 886 static count
- Static count in plan: 886
- Actual collected: 2625
- Difference: 1739
- Test functions found by text search (`def test_` in backend/tests): 886
- Collected node IDs with parametrized IDs (node IDs containing `[...]`): 1995
- Collected node IDs without parametrized IDs: 630
- Unique base node IDs after removing the `[...]` suffix: 886
- Additional collected items from parametrization: 1739
- Verification: `2625 collected - 886 unique base test IDs = 1739`; this matches the extra items from parametrized node IDs exactly.
- Method: run `python -m pytest --collect-only -q`, count the collected node IDs, strip each `[...]` suffix, and compare unique base IDs with the collected total.
- Conclusion: the 1739-item difference is fully accounted for by parametrized collection in this run. No remaining unverified gap remains.

## Notes
- The coverage line printed during collect-only (47.99%, "FAIL") is not real coverage because no tests executed; the real figure is from the full run above.
- 2444 warnings were reported in the full run; they were not investigated in this task.
- No failing or erroring tests. No environment-related failures.