from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


@dp.table(
    name="w0_sample_delta",
    comment="Week 0 sample Delta table for FinEx Databricks bootstrap",
)
@dp.expect_or_fail("symbol_not_null", "symbol IS NOT NULL")
@dp.expect_or_fail("price_positive", "price > 0")
def w0_sample_delta():
    spark = SparkSession.builder.getOrCreate()

    data = [
        (1, "AAPL", 200.0),
        (2, "MSFT", 400.0),
        (3, "GOOGL", 180.0),
    ]

    return (
        spark.createDataFrame(
            data,
            ["id", "symbol", "price"],
        )
        .withColumn("created_at", F.current_timestamp())
    )