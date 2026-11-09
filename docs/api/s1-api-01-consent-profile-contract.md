# Sprint 1 API — consent and profile contract

This document is the human-readable guide for the versioned onboarding
contract implemented at `/api/v1/onboarding-contract`. The running service's
`/openapi.json` is the canonical, machine-readable contract; the contract test
locks its paths, request schema, and success status codes against this guide.

## Scope and safety boundary

This is an educational pilot flow only. It accepts a short display label and a
self-declared experience level. It does not accept authentication credentials,
financial-account data, risk answers, or production personal data. The Sprint
1 in-memory adapter is intentionally behind the API service boundary so it can
be replaced later without a client contract change.

| Endpoint | Success | Requirement |
| --- | --- | --- |
| `POST /consent` | `201` | `consent_version: "consent.v1"`, `consent_given: true` |
| `POST /profile` | `201` | Consent already captured on the same correlation ID |
| `POST /complete` | `200` | Consent and profile already captured on the same correlation ID |

All endpoints are under `/api/v1/onboarding-contract` and use the FinEx v1
success/error envelope. Send `X-Correlation-ID` on every call; it is returned
in `meta.correlationId` and identifies the transient local pilot journey.

## Requests

Capture consent:

```json
{ "consent_version": "consent.v1", "consent_given": true }
```

Submit a profile:

```json
{
  "profile_schema_version": "profile.v1",
  "display_name": "Test Investor",
  "experience_level": "beginner"
}
```

`experience_level` is one of `beginner`, `intermediate`, or `advanced`.
`display_name` is trimmed, must be 1–80 characters after trimming, and is a
non-sensitive label—not a legal name.

Complete onboarding:

```json
{ "consent_version": "consent.v1", "profile_schema_version": "profile.v1" }
```

## Error behavior

| Status | Error code | Meaning |
| --- | --- | --- |
| `400` | `UNSUPPORTED_CONSENT_VERSION` | The consent version is not `consent.v1`. |
| `400` | `CONSENT_NOT_GIVEN` | The user did not accept consent. |
| `400` | `UNSUPPORTED_PROFILE_VERSION` | The profile version is not `profile.v1`. |
| `400` | `CONSENT_MISSING` | A profile or completion was requested before consent. |
| `400` | `PROFILE_MISSING` | Completion was requested before a profile. |
| `422` | `VALIDATION_ERROR` | The request is missing or violates the typed contract. |

Errors use the shared FinEx error envelope and include the correlation ID.

## Local fixture compatibility

`FIXTURE_MODE=s1_dat_01` is permitted only for local/development use. The
application configuration rejects it in UAT or production. The API version
constants are tested against the validated synthetic fixture contract in
`data/fixtures/s1_dat_01/fixture_contract_v1.json`; no fixture contains real
people, credentials, or cloud endpoints.

## Client integration rule

React and Flutter call these HTTP endpoints through their own API client
boundary. Neither client reads fixture files or talks directly to a datastore.
Generated OpenAPI types may be used, but clients must preserve the FinEx
envelope and send a correlation ID for every journey step.

## Verification

From `backend/`, run:

```powershell
python -m pytest tests/test_s1_api_01_consent_profile.py -q
python -m ruff check .
python -m mypy app
```
