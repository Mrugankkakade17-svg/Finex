# Sprint 2 deterministic scoring (#143)

The strict boundary `ai.risk.contract.evaluate_risk_contract` implements the
logical [risk contract](../features/risk-profiling/risk-contract.v1.json), using
the existing deterministic engine for every numeric decision. It accepts only
the three documented fields: `questionnaire_id`, `questionnaire_version`, and
`answers` (each with `question_id` and `answer_code`). It does not accept identity,
client-supplied scores, or a client-controlled timestamp.

~~~mermaid
flowchart LR
    R["Versioned request"] --> V["Strict validation / stable errors"]
    V --> E["Approved v1 deterministic engine"]
    E --> S["Scores + category + server timestamp"]
    S --> X["Educational explanation only"]
    G["16 synthetic golden cases"] --> V
~~~

Validation follows the error order in #146. Invalid input never produces a
partial score; errors do not echo answers. Questionnaire or scoring policy drift
fails closed. New questions, weights, or category semantics require a new
version, not an in-place change to approved v1.

The `educational_explanation` helper describes a server-computed result; it
must not receive an unverified client result. It states the method, versions,
calculation timestamp, and self-reported limitations. Dimension tension is
informational only. No cloud, LLM, market data, advice, trading, or persistence
is involved. Scores are deterministic; a new server timestamp may differ.

## Local validation

From the backend directory in the native Python environment:

    python -m pytest tests/contract/test_s2_risk_scoring.py ../ai/risk/test_scoring.py -q --no-cov
    python -m pytest -q

The first command checks all 16 golden cases, error precedence, version and
weight drift, deterministic replay, boundaries, and explanation safety. Use
`calculated_at` only in trusted internal tests for exact replay; HTTP clients
must not control this argument. The API/client wiring is delivered separately
in #161–#163. Legacy scoring callers remain compatible but now reject an
unsupported questionnaire version and use non-advisory deterministic text.

Rollback is a revert of this feature commit in W40 followed by the regression
suite; no persistent records or shared environment are changed by this story.
