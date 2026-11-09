from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


@dp.table(
    name="w1_application_events",
    comment="S1-DAT-02 – Application events seed for FinEx analytics layer",
)
@dp.expect_or_fail("event_type_not_null", "event_type IS NOT NULL")
@dp.expect_or_fail("user_id_not_null", "user_id IS NOT NULL")
@dp.expect_or_fail("event_id_not_null", "event_id IS NOT NULL")
def w1_application_events():
    """Deterministic seed events for the analytics layer.

    Uses fixed UUIDs so the pipeline is idempotent — running twice
    produces the same rows (DLT handles MERGE semantics).
    """
    spark = SparkSession.builder.getOrCreate()

    data = [
        (
            "e0000000-0000-4000-a000-000000000001",
            "00000000-0000-4000-a000-000000000001",
            "LOGIN",
            '{"source": "web"}',
            "dev",
        ),
        (
            "e0000000-0000-4000-a000-000000000002",
            "00000000-0000-4000-a000-000000000001",
            "VIEW_PORTFOLIO",
            '{"portfolio_id": "p0000000-0000-4000-a000-000000000001"}',
            "dev",
        ),
        (
            "e0000000-0000-4000-a000-000000000003",
            "00000000-0000-4000-a000-000000000002",
            "LOGIN",
            '{"source": "mobile"}',
            "dev",
        ),
        (
            "e0000000-0000-4000-a000-000000000004",
            "00000000-0000-4000-a000-000000000002",
            "CREATE_HOLDING",
            '{"instrument": "MSFT", "qty": 5}',
            "dev",
        ),
        (
            "e0000000-0000-4000-a000-000000000005",
            "00000000-0000-4000-a000-000000000001",
            "LOGIN",
            '{"source": "web"}',
            "test",
        ),
    ]

    return (
        spark.createDataFrame(
            data,
            ["event_id", "user_id", "event_type", "event_payload", "environment"],
        )
        .withColumn("created_at", F.current_timestamp())
    )
