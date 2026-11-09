# Sprint 2 deterministic risk-profile contract

**Story:** #146 — Specify the Sprint 2 risk contract and golden cases
**Contract version:** s2-risk-contract/v1.0
**Status:** implementation baseline for the FinEx educational prototype
**Owner of the canonical questionnaire:** backend/data/questionnaire/risk_questionnaire_v1.json

## 1. Why this exists

This is the single implementation contract for Sprint 2 risk profiling. It
turns the already-approved v1 questionnaire configuration into a testable
agreement for the scoring engine, API, React app, Flutter app, and UAT pack.

It intentionally does **not** introduce a new investor-suitability model,
change a weight, or implement scoring code. The existing questionnaire
configuration is the source for question IDs, permitted answers, weights, and
category thresholds. This document makes the boundary explicit so later work
cannot silently diverge.

FinEx presents an **educational, self-reported profile only**. It must never
present a score, category, or explanation as individualized financial, tax,
legal, or investment advice.

## 2. Contract map

~~~mermaid
flowchart LR
    Q["Canonical v1 questionnaire<br/>10 required single-choice questions"]
    C["Risk contract v1<br/>this story"]
    G["Golden case pack<br/>normal + boundary + invalid"]
    E["#143 engine audit / implementation"]
    A["#161 API contract"]
    W["#162 React experience"]
    M["#163 Flutter experience"]
    V["#144 evaluation and regression gate"]
    U["#164 UAT evidence"]

    Q --> C
    C --> G
    C --> E
    G --> E
    E --> A
    A --> W
    A --> M
    E --> V
    G --> V
    W --> U
    M --> U
    V --> U
~~~

The two machine-readable artifacts are:

| Artifact | Purpose |
| --- | --- |
| risk-contract.v1.json | Versioned input, score, result, error, safety, and change-control agreement. |
| golden-cases.v1.json | Reusable valid and invalid scenarios with expected deterministic outcomes. |

The accompanying contract test is
backend/tests/contract/test_s2_risk_contract_spec.py. It verifies that the
artifacts stay aligned with the canonical questionnaire without duplicating the
scoring implementation.

## 3. Version and ownership rules

| Rule | Decision |
| --- | --- |
| Canonical questionnaire | risk_questionnaire_v1, version v1; its checked-in status is APPROVED. |
| Contract version | s2-risk-contract/v1.0; this is an internal application contract, not regulatory approval. |
| Approved versus proposed | Existing question IDs, permitted values, scores, weights, and category boundaries are recovered from the approved canonical v1 source. The transport DTO, stable error vocabulary, and tension labels in this document are the explicit Sprint 2 implementation proposal. |
| Question and answer identifiers | Stable, uppercase identifiers. Existing v1 IDs and answer codes must not be renamed or repurposed. |
| Changes to v1 | Never mutate a released v1 rule to change a historical result. Introduce a new questionnaire and contract version instead. |
| Historical replay | Persist the questionnaire ID, questionnaire version, scoring version, inputs permitted by retention policy, and calculation timestamp. |
| Deployment | All contract tests run locally and in CI; no cloud dependency is permitted for scoring or golden-case validation. |

## 4. Input contract

### 4.1 Logical request

The transport/API story may place this inside the standard FinEx response
envelope, but the logical request must contain:

| Field | Required | Rule |
| --- | --- | --- |
| questionnaire_id | yes | Exactly risk_questionnaire_v1 for v1. |
| questionnaire_version | yes | Exactly v1 for v1. |
| answers | yes | Exactly one answer for each of the ten required question IDs. |
| answers[].question_id | yes | One of W1–W5 or C1–C5. |
| answers[].answer_code | yes | A permitted code for that exact question, such as W1_C. |
| correlation_id | API layer | Passed through for traceability; it must not affect calculation. |

All v1 questions are required and single-choice:

~~~mermaid
flowchart TB
    I["One submitted assessment"]
    W["Willingness<br/>W1, W2, W3, W4, W5"]
    C["Capacity<br/>C1, C2, C3, C4, C5"]
    V{"All 10 present,<br/>unique, and permitted?"}
    S["Deterministic calculation"]
    X["Fail closed with stable error code"]

    I --> W
    I --> C
    W --> V
    C --> V
    V -->|yes| S
    V -->|no| X
~~~

The canonical configuration owns the exact answer labels and scores. In v1,
each question has five permissible answer codes and the codes follow
^(W[1-5]|C[1-5])_[A-E]$. A syntactically valid code is still rejected if it
belongs to another question.

### 4.2 Deterministic validation order

Validation must fail closed and return no partial score. When more than one
problem exists, apply this order so tests and clients are deterministic:

1. Validate required fields and basic value types.
2. Validate questionnaire_id and questionnaire_version.
3. Detect duplicate question IDs.
4. Detect unknown question IDs.
5. Detect missing required question IDs.
6. Detect unknown answer codes.
7. Detect answer codes that do not belong to the submitted question.

## 5. Scoring policy

The scoring values below are reproduced from the checked-in canonical v1
configuration. They are an educational classification policy for this
prototype, not a recommendation algorithm.

| Dimension | Questions | Raw range | Normalization |
| --- | --- | --- | --- |
| Willingness | W1–W5 | 5–25 | ((raw_sum - 5) / 20) * 100 |
| Capacity | C1–C5 | 5–25 | ((raw_sum - 5) / 20) * 100 |

The composite is:

    composite = (willingness_score * 0.5) + (capacity_score * 0.5)

| Code | Label | Inclusive lower bound | Exclusive upper bound |
| --- | --- | ---: | ---: |
| CONSERVATIVE | Conservative | 0 | 34 |
| MODERATE | Moderate | 34 | 67 |
| AGGRESSIVE | Aggressive | 67 | 100 inclusive |

The input is discrete. Because each dimension has integer answer scores, a
result from real v1 answers moves in 2.5-point composite increments. The
nearest reachable transitions are 32.5 → 35.0 and 65.0 → 67.5. The logical
thresholds of 34 and 67 still define the category contract and must be tested
directly by the scoring unit.

~~~mermaid
flowchart LR
    A["Validate 10 answers"]
    B["Sum W and C separately"]
    C["Normalize each dimension<br/>0–100"]
    D["Apply fixed 50 / 50 weights"]
    E["Map composite to category"]
    F["Return educational profile + limitations"]

    A --> B --> C --> D --> E --> F
~~~

## 6. Logical result contract

Every successful result must contain, at minimum:

| Field | Meaning |
| --- | --- |
| contract_version | s2-risk-contract/v1.0. |
| questionnaire_id, questionnaire_version | The exact input definition used. |
| scoring_version | Immutable scoring-policy version used for replay. |
| willingness_score, capacity_score, composite_score | Numeric values from 0 to 100. |
| risk_category.code, risk_category.label | One of the three canonical categories. |
| calculated_at | ISO-8601 UTC timestamp; excluded from pure-score determinism assertions. |
| limitation.code | EDUCATIONAL_SELF_REPORTED_PROFILE. |
| informational_tension.code | Optional non-advisory context when willingness and capacity are materially different. |

The numerical values and category must be calculated before any explanation.
An explanation service, template, or model may only describe the already
calculated result. It cannot select, change, round, or override a number or
category.

## 7. Stable error contract

| Error code | When it applies | Score returned? |
| --- | --- | --- |
| MALFORMED_ANSWER | A required answer field is absent or has an invalid type/format. | No |
| UNSUPPORTED_QUESTIONNAIRE_VERSION | Questionnaire ID or version is not supported. | No |
| DUPLICATE_QUESTION_ANSWER | More than one answer is supplied for one question. | No |
| UNKNOWN_QUESTION_ID | A submitted question ID does not exist in this version. | No |
| MISSING_REQUIRED_QUESTION | At least one required question has no answer. | No |
| INVALID_ANSWER_CODE | An answer code is not known by this questionnaire version. | No |
| ANSWER_NOT_PERMITTED_FOR_QUESTION | A known answer code belongs to a different question. This is the v1 contradictory-input case. | No |

At the API boundary, a failure uses the existing FinEx error envelope and
includes a correlation ID. Error messages must not echo the entire submitted
assessment or persist sensitive free text.

## 8. Explanation, privacy, and safety boundary

An allowed explanation:

- states that the result is based on self-reported answers at one point in time;
- describes the separate willingness and capacity dimensions in plain language;
- labels a difference between dimensions as an informational constraint or
  tension, not as an instruction to buy, sell, hold, or allocate money;
- includes the required educational limitation.

An explanation must never:

- name a security, broker, fund, or trading action;
- promise returns, capital protection, or suitability;
- use live market data or a user’s unverified external financial data;
- call an LLM, RAG system, or external service to calculate a score;
- change the deterministic result supplied to it;
- log raw responses, account data, or credentials in client-visible errors.

The only v1 tension labels are CAPACITY_BELOW_WILLINGNESS and
WILLINGNESS_BELOW_CAPACITY. They are descriptive guardrails, not investment
recommendations.

## 9. Golden-case pack

The golden pack contains:

| Coverage | Cases |
| --- | --- |
| Normal outcomes | all-low, all-mid, all-high |
| Reachable boundary outcomes | 32.5, 35.0, 65.0, 67.5 |
| Dimension tension | high willingness / low capacity; low willingness / high capacity |
| Validation failures | missing, duplicate, unknown question, invalid code, mismatched code, malformed answer, unsupported version |

These scenarios are intentionally synthetic. They contain no user identity,
account, market, or production data.

## 10. Downstream acceptance checklist

| Story | Must prove before it is done |
| --- | --- |
| #143 deterministic scoring | Every golden valid case has the exact expected values; validation errors match this contract; no model participates in numeric calculation. |
| #160 assessment fixtures | Fixtures use only the stable IDs, permitted values, and safe synthetic data in this contract. |
| #161 API | The API uses the logical request/result/error contract and does not silently translate a mismatched answer code. |
| #162 React | Consent-gated UI displays required questions, loading/error/retry states, and the educational limitation. |
| #163 Flutter | Same contract and user-facing states as React; no unsupported local data retention. |
| #144 evaluation | Golden pack becomes an automated regression suite, including direct 34/67 boundary assertions and deterministic replay. |
| #164 UAT | Evidence demonstrates normal, invalid, and tension paths on a local no-Docker setup. |

## 11. Local verification

From the repository root, run:

    python -m pytest backend/tests/contract/test_s2_risk_contract_spec.py -q --no-cov

This checks the contract/golden fixture structure and their alignment with the
canonical questionnaire. It does not implement or independently recalculate
the risk score; that remains the responsibility of the downstream engine and
evaluation stories.
