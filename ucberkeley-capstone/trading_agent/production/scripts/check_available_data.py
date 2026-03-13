"""
Quick diagnostic to check what prediction data is available
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("CHECKING AVAILABLE PREDICTION DATA")
print("="*80)

# Check commodity.trading_agent.predictions_coffee
print("\n1. Synthetic Predictions (commodity.trading_agent.predictions_coffee):")
try:
    models = spark.sql("""
        SELECT DISTINCT model_version, COUNT(*) as row_count
        FROM commodity.trading_agent.predictions_coffee
        GROUP BY model_version
        ORDER BY model_version
    """).collect()

    if models:
        print(f"   Found {len(models)} model versions:")
        for m in models:
            print(f"     - {m.model_version}: {m.row_count:,} rows")
    else:
        print("   ⚠️  Table exists but is EMPTY")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check commodity.forecast.distributions
print("\n2. Forecast Distributions (commodity.forecast.distributions):")
try:
    models = spark.sql("""
        SELECT DISTINCT
            commodity,
            model_version,
            COUNT(*) as row_count,
            MIN(forecast_start_date) as first_date,
            MAX(forecast_start_date) as last_date
        FROM commodity.forecast.distributions
        WHERE commodity = 'Coffee' AND is_actuals = false
        GROUP BY commodity, model_version
        ORDER BY model_version
    """).collect()

    if models:
        print(f"   Found {len(models)} model versions for Coffee:")
        for m in models:
            print(f"     - {m.model_version}: {m.row_count:,} rows ({m.first_date} to {m.last_date})")
    else:
        print("   ⚠️  No Coffee forecasts found")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)

if not models:
    print("❌ No data found - need to generate/load predictions first")
else:
    print(f"✓ Use model_version from section {1 if len(models) > 0 else 2} above")
    print(f"  Example: --model-version {models[0].model_version if models else 'N/A'}")
