# Backend baseline (S0-LI01)

- Date: 19 Nov 2026
- Commit: 41539f8882057504e5198827cd61e3b9826fe409
- Branch measured: dev (work branch: feature/S0-LI01-backend-baseline)
- Python: 3.13.17 (virtual environment) | OS: Windows 11, PowerShell 5.1
- Working tree clean at start: yes

## Setup notes
- Python 3.13.17 installed alongside 3.14.5; project run through `py -3.13 -m venv .venv`
- `pip install -r requirements.txt` installed ruff 0.16.2, mypy 2.3.0 and pytest 8.4.1; no extra installs needed

## Results
| Check | Command | Result |
|---|---|---|
| Ruff | `cd backend && python -m ruff check .` | All checks passed |
| Mypy | `cd backend && python -m mypy app` | Success: no issues found in 141 source files |
| Collect-only | `cd backend && python -m pytest --collect-only -q` | 2625 tests collected in 10.75s |
| Pytest | `cd backend && python -m pytest -q` | 2625 passed, 0 failed, 2444 warnings in 317.12s |
| Coverage | (part of pytest run) | 85.52% (6249 statements, 905 missed); required 70% reached |

## Reconciliation with the 886 static count
- Static count in plan: 886
- Actual collected: 2625
- Difference: 1739
- Test functions found by text search (`def test_` in backend/tests): 886
- Reason: the 886 static count matches the number of test functions exactly. The higher collected count is explained by parametrized tests, where one function is collected several times with different inputs.

## Notes
- The coverage line printed during collect-only (47.99%, "FAIL") is not real coverage because no tests executed; the real figure is from the full run above.
- 2444 warnings were reported in the full run; they were not investigated in this task.
- No failing or erroring tests. No environment-related failures.