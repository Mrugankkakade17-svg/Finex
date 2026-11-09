# S1-DAT-01 local fixtures

The S1-DAT-01 adapter supplies deterministic, synthetic consent, profile,
onboarding, and audit records for local development and tests. It is intentionally
in-memory: it requires neither Docker nor a database and must stay disabled in
UAT and production.

## Run locally

1. From the repository root, create and activate the backend virtual environment
   using the existing native setup instructions.
2. Set `FIXTURE_MODE=s1_dat_01` only for the local shell that needs fixture data.
3. Validate and reset the dataset:

   ```powershell
   python -m scripts.seed_s1_dat_01 --reset
   ```

4. Run the focused tests:

   ```powershell
   cd backend
   python -m pytest tests/test_s1_dat_01_fixtures.py -q
   ```

The API service may resolve this adapter only when `FIXTURE_MODE=s1_dat_01`.
The setting is rejected in UAT and production so synthetic local fixtures cannot
be promoted into a shared environment.

## Data guarantees

- All records are synthetic and contain no credentials, PII, or real financial data.
- IDs and timestamps are fixed, making tests repeatable across machines.
- The validator rejects contract-version drift, unknown fields, cross-user ownership,
  duplicate IDs, unsupported states, and missing required scenarios.
