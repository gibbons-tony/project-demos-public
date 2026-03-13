#!/usr/bin/env python3
"""
Quick diagnostic to check predictions table status
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("\n" + "="*80)
print("CHECKING PREDICTIONS TABLE")
print("="*80)

# Check coffee predictions
try:
    coffee_preds = spark.table("commodity.trading_agent.predictions_coffee")
    print("\n✓ Table 'commodity.trading_agent.predictions_coffee' exists")

    # Check model versions
    models = coffee_preds.select("model_version").distinct().collect()
    print(f"\nAvailable model versions: {len(models)}")
    for m in models:
        print(f"  - {m['model_version']}")

    # Check record count
    count = coffee_preds.count()
    print(f"\nTotal records: {count:,}")

    if count > 0:
        # Check date range and stats by model
        coffee_preds.createOrReplaceTempView("preds")
        stats = spark.sql("""
            SELECT
                model_version,
                COUNT(*) as record_count,
                MIN(timestamp) as min_date,
                MAX(timestamp) as max_date
            FROM preds
            GROUP BY model_version
            ORDER BY model_version
        """)
        print("\nStats by model version:")
        stats.show(truncate=False)

        # Show sample records
        print("\nSample records:")
        coffee_preds.limit(5).show(truncate=False)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("\nListing available tables in commodity.trading_agent:")
    spark.sql("SHOW TABLES IN commodity.trading_agent").show(truncate=False)

print("\n" + "="*80)
print("DONE")
print("="*80)
