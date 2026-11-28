# S3-LI03 cash-flow service evidence

## Implementation

- Added `backend/app/services/cashflow_service.py` as a deterministic service over
  the existing principal-scoped spending repository. No routes or persistence
  schemas changed, so no migration is required.
- Added ordered `CategoryRule` support and default income rules for payroll,
  salary, refunds, reimbursements, cashback, dividends, and earned interest.
  Unmatched positive amounts follow the existing spending convention and count
  as expenses; negative credits count as income.
- Period boundaries are inclusive. Each transaction is rounded to cents using
  `ROUND_HALF_UP` before aggregation. Category totals form the income and expense
  totals, and net cash flow is income minus expenses.
- Added unit coverage for cent reconciliation, rounding, classification,
  date boundaries, empty periods, invalid input, and deterministic ordering.
  Added a persistence integration check that verifies user isolation.

## Verification

- From `backend`, `python -m ruff check .` — passed.
- From `backend`, `python -m ruff format --check .` — passed (378 files formatted).
- Focused mypy on the service and S3-LI03 tests — passed (3 source files).
- `python -m pytest tests/unit/test_cashflow_service.py tests/integration/test_s3_li03_cashflow.py -q -o addopts=''` — 9 passed.
- Full `python -m pytest -q` — 3,082 passed, 26 skipped, 2 xfailed, 2 xpassed,
  45 failed. The failures are existing Windows-specific SQLite schema-upgrade
  concurrency and evidence/acceptance launcher tests in
  `test_local_s3_schema.py`, `test_owned_s2_acceptance_launcher.py`,
  `test_s1_acceptance_launcher.py`, `test_s2_evidence_pair_validation.py`,
  and `test_verify_s3_foundation.py`. No S3-LI03 test failed.
