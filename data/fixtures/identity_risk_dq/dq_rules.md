# S2-DAT-03 Identity/Risk Data Quality Rules

## DQ-001 - Profile Completeness
- Domain: Identity
- Table: user_profiles
- Severity: Critical
- Rule: Required profile fields must not be NULL or empty.
- Current fixture fields: user_id, first_name, last_name, phone, date_of_birth, country
- Expected failure: incomplete profile is detected.

## DQ-002 - Consent Status
- Domain: Identity
- Table: user_consents
- Severity: Critical
- Rule: Applicable users must have a valid consent record/status.
- Status: Pending S2-DAT-01 schema
- Expected failure: missing or invalid consent is detected.

## DQ-003 - Duplicate Identity
- Domain: Identity
- Table: users
- Severity: Critical
- Rule: An email identity must belong to only one user.
- Expected failure: duplicate email is detected.

## DQ-004 - Orphan Risk Answers
- Domain: Risk
- Table: risk_assessment_answers
- Severity: Critical
- Rule: Every risk answer must reference a valid risk assessment and valid question.
- Status: Pending S2-DAT-02 schema
- Expected failure: orphan risk answer is detected.
