# Sprint 2 risk API (#161)

This release delivers a **stateless local educational pilot**, not an anonymous
cloud endpoint or a production assessment store. Start the backend with
`APP_ENV=local` using the native setup; Docker, hosted models and a database are
not required. The existing authenticated legacy assessment-store endpoints are
unchanged. A future deployed adapter requires authenticated identity, consent,
authorized retention and persistence behind a separately reviewed data port.

~~~mermaid
flowchart LR
    C["React / Flutter"] --> H["Local-only guard + strict HTTP DTO"]
    H --> P["AssessmentScorer port"]
    P --> D["Versioned deterministic domain"]
    D --> R["Assessment + educational explanation"]
    R --> E["FinEx envelope + correlation ID"]
    E --> C
~~~

## Endpoints

| Method / path | Purpose |
| --- | --- |
| GET `/api/v1/risk-contract/questionnaire` | Ten versioned questions and permitted options; no answer weights. |
| POST `/api/v1/risk-contract/assessments` | Calculate the #146 assessment and educational explanation; do not persist answers. |

The POST accepts exactly `questionnaire_id`, `questionnaire_version`, and
`answers` (each with `question_id`, `answer_code`). Read the typed request,
response and error schemas at `http://127.0.0.1:8000/docs` after starting locally.

Success uses the FinEx envelope. `data.assessment` matches the #146 logical
result. `data.explanation` states the method, versions, timestamp and limitations;
`data.scope` is `local_educational_pilot`, and `data.persisted` is `false`.
`meta.dataAsOf` equals the server calculation timestamp; it is not market-data
freshness. The caller cannot submit a score, identity or timestamp.

## Errors and invariants

| HTTP | Stable behavior |
| --- | --- |
| 400 | Version, duplicate, unknown, missing, undefined-option and cross-question errors follow #146 order. |
| 422 | Malformed JSON, missing/wrong-type fields and extra fields return `MALFORMED_ANSWER`; no submitted values are echoed. |
| 403 | `LOCAL_PILOT_ONLY` outside `APP_ENV=local`, including dev/UAT/production. |
| 500 | `RISK_ASSESSMENT_UNAVAILABLE`; no provider diagnostics or secrets are exposed. |

Every response echoes `X-Correlation-ID` in the header and envelope. Scores and
categories are deterministic; timestamps and correlation IDs may differ between
requests. Errors never return a partial score. The scorer port is injectable in
tests; there is no persistence adapter in this pilot and no hidden cloud call.
The older anonymous `/risk/evaluate`, `/risk/explain`, and
`/risk/evaluate-and-explain` routes now share the local-only deployment guard.

## Validate / rollback

From `backend`:

    python -m pytest tests/contract/test_s2_risk_api.py -q --no-cov
    python -m pytest -q
    python -m ruff check .
    python -m mypy app

Tests exercise all 16 golden cases, OpenAPI, local-only restrictions, legacy
route guards, malformed input, error privacy, correlation IDs, timestamp and
educational disclosures. Revert the feature commit and re-run regressions for
rollback; no shared data or deployment was changed.
