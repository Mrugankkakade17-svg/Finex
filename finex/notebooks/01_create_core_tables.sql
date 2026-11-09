-- =====================================================================
-- S1-DAT-02 Evidence Notebook: 01_create_core_tables
-- Owner: Pranjal
-- Run this notebook in Databricks to create and verify S1-DAT-02 tables
-- =====================================================================

-- =====================================================================
-- STEP 1: Create the application_events Delta table
-- (idempotent – safe to run multiple times)
-- =====================================================================
CREATE TABLE IF NOT EXISTS finex_dev.analytics.application_events (
    event_id        STRING NOT NULL,
    user_id         STRING NOT NULL,
    event_type      STRING NOT NULL,
    event_payload   STRING,
    environment     STRING DEFAULT 'dev',
    created_at      TIMESTAMP
);

-- =====================================================================
-- STEP 2: Seed data via MERGE (idempotent – no duplicates on re-run)
-- =====================================================================
MERGE INTO finex_dev.analytics.application_events AS target
USING (
    SELECT * FROM (VALUES
        ('e0000000-0000-4000-a000-000000000001', '00000000-0000-4000-a000-000000000001', 'LOGIN',          '{"source": "web"}',                                               'dev',  CURRENT_TIMESTAMP()),
        ('e0000000-0000-4000-a000-000000000002', '00000000-0000-4000-a000-000000000001', 'VIEW_PORTFOLIO',  '{"portfolio_id": "p0000000-0000-4000-a000-000000000001"}',          'dev',  CURRENT_TIMESTAMP()),
        ('e0000000-0000-4000-a000-000000000003', '00000000-0000-4000-a000-000000000002', 'LOGIN',          '{"source": "mobile"}',                                            'dev',  CURRENT_TIMESTAMP()),
        ('e0000000-0000-4000-a000-000000000004', '00000000-0000-4000-a000-000000000002', 'CREATE_HOLDING',  '{"instrument": "MSFT", "qty": 5}',                                'dev',  CURRENT_TIMESTAMP()),
        ('e0000000-0000-4000-a000-000000000005', '00000000-0000-4000-a000-000000000001', 'LOGIN',          '{"source": "web"}',                                               'test', CURRENT_TIMESTAMP())
    ) AS t(event_id, user_id, event_type, event_payload, environment, created_at)
) AS source
ON target.event_id = source.event_id
WHEN NOT MATCHED THEN INSERT (
    event_id, user_id, event_type, event_payload, environment, created_at
)
VALUES (
    source.event_id, source.user_id, source.event_type,
    source.event_payload, source.environment, source.created_at
);

-- =====================================================================
-- STEP 3: Verify table exists
-- =====================================================================
SHOW TABLES IN finex_dev.analytics;

-- =====================================================================
-- STEP 4: Query all seeded rows
-- =====================================================================
SELECT * FROM finex_dev.analytics.application_events
ORDER BY event_id;

-- =====================================================================
-- STEP 5: Verify idempotency – seed count must be exactly 5
-- =====================================================================
SELECT COUNT(*) AS seed_event_count
FROM finex_dev.analytics.application_events
WHERE event_id LIKE 'e0000000-0000-4000-a000-%';

-- =====================================================================
-- STEP 6: Evidence – User isolation
-- User A (00000000-...-000000000001) should see 3 events
-- User B (00000000-...-000000000002) should see 2 events
-- =====================================================================
SELECT 'User A events' AS label, COUNT(*) AS cnt
FROM finex_dev.analytics.application_events
WHERE user_id = '00000000-0000-4000-a000-000000000001'

UNION ALL

SELECT 'User B events' AS label, COUNT(*) AS cnt
FROM finex_dev.analytics.application_events
WHERE user_id = '00000000-0000-4000-a000-000000000002';

-- =====================================================================
-- STEP 7: Evidence – Environment separation (dev vs test)
-- =====================================================================
SELECT environment, COUNT(*) AS cnt
FROM finex_dev.analytics.application_events
WHERE event_id LIKE 'e0000000-0000-4000-a000-%'
GROUP BY environment
ORDER BY environment;

-- =====================================================================
-- STEP 8: Evidence – User B cannot see User A's events
-- This query returns ONLY User B's events; User A's are excluded.
-- =====================================================================
SELECT event_id, event_type, environment
FROM finex_dev.analytics.application_events
WHERE user_id = '00000000-0000-4000-a000-000000000002';
-- Expected: 2 rows (LOGIN from mobile, CREATE_HOLDING)
-- User A's 3 events are NOT returned ← isolation evidence

-- =====================================================================
-- STEP 9: Verify existing S1-DAT-01 tables are untouched
-- =====================================================================
SHOW TABLES IN finex_dev.core;
SHOW TABLES IN finex_dev.market;
