# S2-DAT-01 local assessment fixtures

The Sprint 2 fixture adapter gives every developer the same synthetic
assessment requests and expected outcomes without Docker, a database, a cloud
account, credentials, or market data. It is local-only and is rejected in UAT
and production.

## What it builds

~~~mermaid
flowchart LR
    C["Risk contract v1"]
    G["Golden-case pack"]
    M["S2 fixture manifest"]
    V["Validator"]
    P["In-memory fixture provider"]
    T["Scoring / API / UI tests"]

    C --> V
    G --> V
    M --> V
    V --> P
    P --> T
~~~

The provider does not calculate a score. It materializes the approved golden
requests—including invalid requests—so the scoring engine and API can prove
their own behavior against the same cases.

## Run it locally

From the repository root, after activating the normal native Python
environment:

    python -m scripts.seed_s2_dat_01

For a CI-safe JSON summary with no answers or identifiers:

    python -m scripts.seed_s2_dat_01 --format json

Run the focused tests:

    cd backend
    python -m pytest tests/test_s2_dat_01_fixtures.py -q --no-cov

## Enable the local fixture mode

Set this only in a local development shell:

    $env:FIXTURE_MODE = "s2_dat_01"

The mode supplies an in-memory provider only. It does not seed a shared
database or change an API response until a later API story explicitly wires it
through the data port.

## Reset behavior and safety

Each reset:

1. clears the process-local snapshot;
2. validates the S2 fixture contract, #146 risk contract, golden-case pack,
   and manifest;
3. rebuilds exactly 16 synthetic fixtures from the golden-case pack.

The fixtures cover nine accepted requests and seven expected failures:
missing, duplicate, unknown, invalid, contradictory, malformed, and
unsupported-version input. They intentionally contain no user identity,
account, live-market, security-symbol, recommendation, credential, or
production data.

## Change control

Do not edit a fixture to change an expected score independently. Update the
versioned risk contract and golden-case pack first, then update the manifest
and downstream scoring/API/UI tests in the same release train. Any version
drift or missing golden case causes fixture validation to fail.

Released fixture/questionnaire versions are immutable. Changes require a new
version and an explicit forward-only adapter migration; never silently reinterpret
existing assessment records. This local adapter retains data only for the process
lifetime. Reset or process exit discards it; no shared data is deleted.

Rollback: unset `FIXTURE_MODE` (the default is `disabled`) and restart the local
process. Re-run the focused tests and reset command after changing fixtures.
This story supplies test inputs, not a production assessment persistence layer.
