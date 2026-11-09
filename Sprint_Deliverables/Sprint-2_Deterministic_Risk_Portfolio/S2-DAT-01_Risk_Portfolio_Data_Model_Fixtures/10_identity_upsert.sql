-- =====================================================================
-- Task: S2-DAT-01
-- Notebook: 10_identity_upsert
-- Purpose: Insert or update user identity records using MERGE
-- =====================================================================

-- ---------------------------------------------------------------------
-- Create sample source data
-- ---------------------------------------------------------------------
CREATE OR REPLACE TEMP VIEW user_upsert_source AS
SELECT
    'nilisha@example.com' AS email,
    'sample_password_hash' AS password_hash,
    'Nilisha' AS name,
    'user' AS role,
    'moderate' AS risk_profile,
    TRUE AS is_active,
    current_timestamp() AS created_at,
    current_timestamp() AS updated_at;

-- ---------------------------------------------------------------------
-- Check for duplicate emails in source data
-- ---------------------------------------------------------------------
SELECT
    email,
    COUNT(*) AS email_count
FROM user_upsert_source
GROUP BY email
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------
-- MERGE / UPSERT user data
-- ---------------------------------------------------------------------
MERGE INTO finex_dev.core.users AS target
USING user_upsert_source AS source
ON target.email = source.email

WHEN MATCHED THEN
UPDATE SET
    target.password_hash = source.password_hash,
    target.name = source.name,
    target.role = source.role,
    target.risk_profile = source.risk_profile,
    target.is_active = source.is_active,
    target.updated_at = current_timestamp()

WHEN NOT MATCHED THEN
INSERT (
    email,
    password_hash,
    name,
    role,
    risk_profile,
    is_active,
    created_at,
    updated_at
)
VALUES (
    source.email,
    source.password_hash,
    source.name,
    source.role,
    source.risk_profile,
    source.is_active,
    source.created_at,
    source.updated_at
);

-- ---------------------------------------------------------------------
-- Verify the user record
-- ---------------------------------------------------------------------
SELECT
    user_id,
    email,
    name,
    role,
    risk_profile,
    is_active,
    created_at,
    updated_at
FROM finex_dev.core.users
WHERE email = 'nilisha@example.com';
