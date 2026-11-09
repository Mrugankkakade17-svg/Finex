# S2-DAT-02 — Risk Questionnaire v1 Handoff

## Status
Completed and ready for downstream use.

## Owner
Nayan

## Deliverables
- `backend/data/questionnaire/risk_questionnaire_v1.json`
- `backend/data/questionnaire/risk_questionnaire_v1_review.csv`
- `backend/notebooks/load_risk_questionnaire_v1.ipynb`
- Risk questionnaire database tables:
  - `risk_questionnaires`
  - `risk_questions`
  - `risk_assessments`
  - `risk_assessment_answers`

## Questionnaire
- Version: v1
- Status: APPROVED
- Active from: 2026-08-23
- Questions: 10
- Willingness questions: 5
- Capacity questions: 5
- Answer options: 50
- Response type: single_choice
- All questions required

## Scoring
- Proposed scores: 1–5
- Willingness weight: 0.5
- Capacity weight: 0.5
- Total score:
  `(willingness_score * 0.5) + (capacity_score * 0.5)`
- Categories:
  - 0–33.99: Conservative
  - 34–66.99: Moderate
  - 67–100: Aggressive

## Validation / Verification
- Questionnaire validation: PASS
- Scoring verification: PASS
- Data quality checks: PASS
- Idempotency check: PASS
- Existing v1 matches source questionnaire
- Database contains 10 questions and 50 answer options

## Downstream Usage
Downstream services can retrieve v1 from PostgreSQL using
`risk_questionnaires` and `risk_questions`.

Questions are ordered using `position`.
Answer choices and proposed scores are stored in `answer_options`.

## Important
The questionnaire is now approved and active.
Do not modify the questionnaire questions, answer codes, or scoring
without updating the source JSON and rerunning the validation/loader.

## Dependency for downstream work

S2-DAT-02 provides the questionnaire definition and answer metadata
required by downstream risk-assessment functionality.

Use the persisted `question_id` / `text_key`, `position`, `dimension`,
`response_type`, `required`, and `answer_options` fields when consuming
the questionnaire.

Do not create a separate copy of the questionnaire in downstream code.