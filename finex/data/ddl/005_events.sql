-- =====================================================================
-- Task: S1-DAT-02
-- Catalog: finex_dev
-- Schema: analytics
-- Purpose: Application event log (analytical / history data on Delta)
-- =====================================================================

-- NOTE: This file adds to the analytics schema created by S1-DAT-01
-- (003_analytics.sql).  It does NOT recreate existing tables.

-- ---------------------------------------------------------------------
-- application_events
-- Captures user activity for analytics, DQ lineage, and auditing.
-- Uses STRING UUIDs (not BIGINT) per S1-DAT-02 requirements.
-- The 'environment' column enables logical dev/test/demo separation.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.analytics.application_events (
    event_id        STRING NOT NULL,
    user_id         STRING NOT NULL,
    event_type      STRING NOT NULL,
    event_payload   STRING,
    environment     STRING DEFAULT 'dev',
    created_at      TIMESTAMP
);
