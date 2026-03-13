"""
Analyze table structures for forecast.distributions and unified_data

Purpose: Document the structure, coverage, and alignment of data sources
         to guide proper data loading in production runners.
"""

import sys
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

# Initialize Spark
spark = SparkSession.builder.appName("AnalyzeTableStructures").getOrCreate()

print("=" * 80)
print("TABLE STRUCTURE ANALYSIS")
print("=" * 80)

# ============================================================================
# 1. FORECAST.DISTRIBUTIONS TABLE
# ============================================================================
print("\n" + "=" * 80)
print("1. commodity.forecast.distributions")
print("=" * 80)

print("\nSchema:")
spark.table("commodity.forecast.distributions").printSchema()

print("\nSample data (actuals):")
spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = true"
).limit(5).show(truncate=False)

print("\nSample data (forecasts):")
spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = false"
).limit(5).show(truncate=False)

print("\nDate coverage for Coffee actuals:")
actuals_coverage = spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = true"
).agg(
    F.min("forecast_date").alias("min_date"),
    F.max("forecast_date").alias("max_date"),
    F.count("forecast_date").alias("total_rows"),
    F.countDistinct("forecast_date").alias("distinct_dates")
)
actuals_coverage.show(truncate=False)

print("\nDate coverage for Coffee forecasts:")
forecast_coverage = spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = false"
).agg(
    F.min("forecast_date").alias("min_date"),
    F.max("forecast_date").alias("max_date"),
    F.count("forecast_date").alias("total_rows"),
    F.countDistinct("forecast_date").alias("distinct_dates")
)
forecast_coverage.show(truncate=False)

print("\nModel versions in forecasts:")
spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = false"
).select("model_version").distinct().orderBy("model_version").show(50, truncate=False)

print("\nForecast sparseness check (dates with forecasts vs without):")
forecast_dates = spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = false"
).select("forecast_date").distinct()
print(f"Dates with forecasts: {forecast_dates.count()}")

# ============================================================================
# 2. UNIFIED_DATA TABLE
# ============================================================================
print("\n" + "=" * 80)
print("2. commodity.silver.unified_data")
print("=" * 80)

print("\nSchema:")
spark.table("commodity.silver.unified_data").printSchema()

print("\nSample data for coffee:")
spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).limit(5).show(truncate=False)

print("\nDate coverage for coffee:")
unified_coverage = spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).agg(
    F.min("date").alias("min_date"),
    F.max("date").alias("max_date"),
    F.count("date").alias("total_rows"),
    F.countDistinct("date").alias("distinct_dates")
)
unified_coverage.show(truncate=False)

print("\nRegion breakdown for coffee:")
spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).groupBy("region").agg(
    F.count("*").alias("row_count"),
    F.countDistinct("date").alias("distinct_dates")
).show(truncate=False)

print("\nSample price values (checking if same across regions):")
spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).groupBy("date").agg(
    F.countDistinct("close").alias("distinct_close_prices"),
    F.first("close").alias("sample_close_price")
).orderBy(F.desc("date")).limit(10).show(truncate=False)

# ============================================================================
# 3. ALIGNMENT ANALYSIS
# ============================================================================
print("\n" + "=" * 80)
print("3. ALIGNMENT ANALYSIS - Date Overlap")
print("=" * 80)

# Get date ranges from each source
actuals_dates = spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = true"
).select("forecast_date").distinct()

unified_dates = spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).select("date").distinct()

print(f"\nActuals dates in forecast.distributions: {actuals_dates.count()}")
print(f"Dates in unified_data: {unified_dates.count()}")

# Check overlap
overlap = actuals_dates.join(
    unified_dates,
    actuals_dates.forecast_date == unified_dates.date,
    "inner"
)
print(f"Overlapping dates: {overlap.count()}")

# Find gaps
only_in_actuals = actuals_dates.join(
    unified_dates,
    actuals_dates.forecast_date == unified_dates.date,
    "left_anti"
)
print(f"Dates only in forecast.distributions actuals: {only_in_actuals.count()}")

only_in_unified = unified_dates.join(
    actuals_dates,
    unified_dates.date == actuals_dates.forecast_date,
    "left_anti"
)
print(f"Dates only in unified_data: {only_in_unified.count()}")

# ============================================================================
# 4. PRICE VALUE COMPARISON
# ============================================================================
print("\n" + "=" * 80)
print("4. PRICE VALUE COMPARISON - Are prices consistent?")
print("=" * 80)

# Join on date and compare close prices
price_comparison = spark.table("commodity.forecast.distributions").filter(
    "commodity = 'Coffee' AND is_actuals = true"
).select(
    F.col("forecast_date").alias("date"),
    F.col("close").alias("actuals_close")
).join(
    spark.table("commodity.silver.unified_data").filter(
        "lower(commodity) = 'coffee'"
    ).select("date", F.col("close").alias("unified_close")),
    on="date",
    how="inner"
).withColumn(
    "price_diff",
    F.abs(F.col("actuals_close") - F.col("unified_close"))
)

print("\nPrice comparison (actuals vs unified):")
price_comparison.agg(
    F.count("*").alias("matching_dates"),
    F.avg("price_diff").alias("avg_diff"),
    F.max("price_diff").alias("max_diff"),
    F.sum(F.when(F.col("price_diff") > 0.01, 1).otherwise(0)).alias("dates_with_diff")
).show(truncate=False)

print("\nSample of price comparisons:")
price_comparison.orderBy(F.desc("price_diff")).limit(10).show(truncate=False)

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
