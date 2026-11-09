# Sprint 1 data-quality gate

## Purpose and boundary

This gate validates the versioned, synthetic onboarding fixtures used by Sprint
1. It is a local-only guardrail: it does not connect to a database, cloud
provider, identity provider, or production data source.

The authoritative inputs are:

- `data/fixtures/s1_dat_01/fixture_contract_v1.json`
- `data/fixtures/s1_dat_01/records_v1.json`

Run the gate from `backend` after bootstrapping the backend environment:

```powershell
.\.venv\Scripts\python.exe -m app.fixtures.s1_dat_01 --format json
```

The JSON report is deterministic: it contains only contract versions, check
results, and aggregate counts. It intentionally never writes fixture records,
identifiers, or profile labels to CI output.

## Checks

| Rule | What it proves |
| --- | --- |
| `DQ-S1-001` | Contract/record versions, required fields, and field types are valid. |
| `DQ-S1-002` | Identifiers and timestamps follow the deterministic contract. |
| `DQ-S1-003` | Every record belongs to its declared synthetic user. |
| `DQ-S1-004` | All five required consent/onboarding scenarios exist and are state-consistent. |
| `DQ-S1-005` | Fixtures remain local-only synthetic data with no production, credential, or financial values. |
| `DQ-S1-006` | Audit records use approved event states and the local fixture source. |

GitHub Actions runs the same command and publishes the safe JSON report in the
backend quality-check summary whenever the fixture contract, fixture records,
fixture adapter, or fixture seed script changes.

## Failure handling

Fix a fixture or contract failure with a reviewed, versioned forward change.
Do not edit real user data, and do not introduce a runtime clock, cloud
endpoint, credentials, or personally identifying values to make a test pass.

If a newly merged fixture change must be backed out, revert that change or
restore the previously accepted fixture version through a new pull request.
The fixture store is in-memory and local-only, so there is no database
migration or destructive rollback operation.
