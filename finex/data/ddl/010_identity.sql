-- =====================================================================
-- Task: S2-DAT-01
-- Catalog: finex_dev
-- Schema: core
-- Purpose: User identity, preferences, consent, and audit data
-- =====================================================================

-- ---------------------------------------------------------------------
-- user_preferences
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.user_preferences (
    preference_id      BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id            BIGINT NOT NULL,
    preference_key     STRING NOT NULL,
    preference_value   STRING,
    created_at         TIMESTAMP,
    updated_at         TIMESTAMP
);

-- ---------------------------------------------------------------------
-- user_consents
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.user_consents (
    consent_id       BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id          BIGINT NOT NULL,
    consent_type     STRING NOT NULL,
    consent_version  STRING NOT NULL,
    is_consented     BOOLEAN NOT NULL,
    consented_at     TIMESTAMP,
    created_at       TIMESTAMP
);

-- ---------------------------------------------------------------------
-- auth_audit_events
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.auth_audit_events (
    auth_audit_event_id  BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id              BIGINT NOT NULL,
    event_type           STRING NOT NULL,
    event_status         STRING,
    ip_address           STRING,
    user_agent           STRING,
    created_at           TIMESTAMP NOT NULL
);

-- ---------------------------------------------------------------------
-- Consent validation checks
-- ---------------------------------------------------------------------
ALTER TABLE finex_dev.core.user_consents
ADD CONSTRAINT valid_consent_type
CHECK (LENGTH(TRIM(consent_type)) > 0);

ALTER TABLE finex_dev.core.user_consents
ADD CONSTRAINT valid_consent_version
CHECK (LENGTH(TRIM(consent_version)) > 0);
