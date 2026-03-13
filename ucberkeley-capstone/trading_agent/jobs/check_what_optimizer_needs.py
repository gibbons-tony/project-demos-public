"""
Check what data the optimizer actually needs and if it exists
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("WHAT DOES THE OPTIMIZER NEED?")
print("="*80)

# The optimizer queries: commodity.trading_agent.predictions_{commodity}
# Let's see what's actually in there

print("\n1. What's in commodity.trading_agent.predictions_coffee?")
try:
    result = spark.sql("""
        SELECT
            model_version,
            COUNT(*) as row_count,
            MIN(timestamp) as first_date,
            MAX(timestamp) as last_date,
            COUNT(DISTINCT timestamp) as n_dates
        FROM commodity.trading_agent.predictions_coffee
        GROUP BY model_version
        ORDER BY model_version
    """).collect()

    print(f"   Found {len(result)} model versions:")
    for r in result:
        print(f"     {r.model_version}:")
        print(f"       Rows: {r.row_count:,}")
        print(f"       Dates: {r.n_dates} ({r.first_date} to {r.last_date})")
        print()
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n2. Are there REAL forecast models in predictions_coffee?")
print("   (Looking for arima, sarimax, xgboost, prophet, random_walk)")

try:
    real_models = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_coffee
        WHERE model_version LIKE '%arima%'
           OR model_version LIKE '%sarimax%'
           OR model_version LIKE '%xgboost%'
           OR model_version LIKE '%prophet%'
           OR model_version LIKE '%random_walk%'
        ORDER BY model_version
    """).collect()

    if real_models:
        print(f"   ✓ YES! Found {len(real_models)} real forecast models:")
        for m in real_models:
            print(f"     - {m.model_version}")
    else:
        print("   ❌ NO real forecast models found")
        print("   ⚠️  Only synthetic models available")
        print("   ⚠️  Step 2 (load_forecast_predictions) needs to be run first!")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
