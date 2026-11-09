-- =====================================================================
-- S2-DAT-03 - Identity / Risk Data Quality Checks
-- =====================================================================
-- Purpose:
--   Validate identity/profile data and risk-assessment relationships.
--
-- DQ-001 Profile Completeness
-- DQ-002 Consent Status
-- DQ-003 Duplicate Identity
-- DQ-004 Orphan Risk Answers
-- =====================================================================


-- ---------------------------------------------------------------------
-- DQ-001: Profile Completeness
-- ---------------------------------------------------------------------
-- Every user should have a corresponding user_profiles record.
-- The source schema does not define first_name, last_name, phone,
-- date_of_birth, or country as mandatory, so this check does not
-- invent additional required fields.

SELECT
    u.user_id,
    u.email,
    'DQ-001' AS rule_id,
    'PROFILE_MISSING' AS dq_rule,
    'CRITICAL' AS severity
FROM finex_dev.core.users u
LEFT JOIN finex_dev.core.user_profiles p
    ON p.user_id = u.user_id
WHERE p.user_id IS NULL;


-- ---------------------------------------------------------------------
-- DQ-002: Consent Status
-- ---------------------------------------------------------------------
-- Every user should have a valid consent record.
-- Invalid means:
--   1. No consent record
--   2. is_consented = FALSE
--   3. Blank consent_type
--   4. Blank consent_version

SELECT
    u.user_id,
    u.email,
    'DQ-002' AS rule_id,
    'CONSENT_INVALID' AS dq_rule,
    'CRITICAL' AS severity
FROM finex_dev.core.users u
LEFT JOIN finex_dev.core.user_consents c
    ON c.user_id = u.user_id
WHERE c.user_id IS NULL
   OR c.is_consented = FALSE
   OR c.consent_type IS NULL
   OR TRIM(c.consent_type) = ''
   OR c.consent_version IS NULL
   OR TRIM(c.consent_version) = '';


-- ---------------------------------------------------------------------
-- DQ-003: Duplicate Identity
-- ---------------------------------------------------------------------
-- Email is the identity key.
-- Comparison is case-insensitive and ignores surrounding whitespace.

SELECT
    LOWER(TRIM(email)) AS normalized_email,
    COUNT(*) AS duplicate_count,
    'DQ-003' AS rule_id,
    'DUPLICATE_IDENTITY' AS dq_rule,
    'CRITICAL' AS severity
FROM finex_dev.core.users
WHERE email IS NOT NULL
  AND TRIM(email) <> ''
GROUP BY LOWER(TRIM(email))
HAVING COUNT(*) > 1;


-- ---------------------------------------------------------------------
-- DQ-003 Detail: Affected Users
-- ---------------------------------------------------------------------

SELECT
    user_id,
    email,
    name
FROM finex_dev.core.users
WHERE LOWER(TRIM(email)) IN (
    SELECT LOWER(TRIM(email))
    FROM finex_dev.core.users
    WHERE email IS NOT NULL
      AND TRIM(email) <> ''
    GROUP BY LOWER(TRIM(email))
    HAVING COUNT(*) > 1
)
ORDER BY LOWER(TRIM(email)), user_id;


-- ---------------------------------------------------------------------
-- DQ-004: Orphan Risk Answers
-- ---------------------------------------------------------------------
-- Every risk answer must reference:
--   1. An existing risk assessment
--   2. An existing risk question

SELECT
    a.answer_id,
    a.assessment_id,
    a.question_id,
    'DQ-004' AS rule_id,
    'ORPHAN_RISK_ANSWER' AS dq_rule,
    'CRITICAL' AS severity,
    CASE
        WHEN ra.assessment_id IS NULL
         AND rq.question_id IS NULL
            THEN 'MISSING_ASSESSMENT_AND_QUESTION'
        WHEN ra.assessment_id IS NULL
            THEN 'MISSING_ASSESSMENT'
        WHEN rq.question_id IS NULL
            THEN 'MISSING_QUESTION'
    END AS failure_reason
FROM risk_assessment_answers a
LEFT JOIN risk_assessments ra
    ON ra.assessment_id = a.assessment_id
LEFT JOIN risk_questions rq
    ON rq.question_id = a.question_id
WHERE ra.assessment_id IS NULL
   OR rq.question_id IS NULL;


-- ---------------------------------------------------------------------
-- DQ Audit Summary
-- ---------------------------------------------------------------------
-- Clean dataset expectation:
-- total_critical_failures = 0

WITH profile_failures AS (
    SELECT COUNT(*) AS failure_count
    FROM finex_dev.core.users u
    LEFT JOIN finex_dev.core.user_profiles p
        ON p.user_id = u.user_id
    WHERE p.user_id IS NULL
),

consent_failures AS (
    SELECT COUNT(*) AS failure_count
    FROM finex_dev.core.users u
    LEFT JOIN finex_dev.core.user_consents c
        ON c.user_id = u.user_id
    WHERE c.user_id IS NULL
       OR c.is_consented = FALSE
       OR c.consent_type IS NULL
       OR TRIM(c.consent_type) = ''
       OR c.consent_version IS NULL
       OR TRIM(c.consent_version) = ''
),

duplicate_failures AS (
    SELECT COALESCE(SUM(duplicate_count), 0) AS failure_count
    FROM (
        SELECT
            LOWER(TRIM(email)) AS normalized_email,
            COUNT(*) AS duplicate_count
        FROM finex_dev.core.users
        WHERE email IS NOT NULL
          AND TRIM(email) <> ''
        GROUP BY LOWER(TRIM(email))
        HAVING COUNT(*) > 1
    ) duplicates
),

orphan_failures AS (
    SELECT COUNT(*) AS failure_count
    FROM risk_assessment_answers a
    LEFT JOIN risk_assessments ra
        ON ra.assessment_id = a.assessment_id
    LEFT JOIN risk_questions rq
        ON rq.question_id = a.question_id
    WHERE ra.assessment_id IS NULL
       OR rq.question_id IS NULL
)

SELECT
    profile_failures.failure_count AS profile_missing,
    consent_failures.failure_count AS consent_invalid,
    duplicate_failures.failure_count AS duplicate_identity,
    orphan_failures.failure_count AS orphan_risk_answer,
    (
        profile_failures.failure_count
        + consent_failures.failure_count
        + duplicate_failures.failure_count
        + orphan_failures.failure_count
    ) AS total_critical_failures
FROM profile_failures,
     consent_failures,
     duplicate_failures,
     orphan_failures;