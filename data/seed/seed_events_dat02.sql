-- =====================================================================
-- S1-DAT-02 – Idempotent seed for finex_dev.analytics.application_events
-- Uses MERGE to avoid duplicate rows on repeated execution.
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

-- Verification: count should be exactly 5 after any number of runs
SELECT COUNT(*) AS total_seed_events FROM finex_dev.analytics.application_events
WHERE event_id LIKE 'e0000000-0000-4000-a000-%';
