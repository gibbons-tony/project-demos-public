"""
Compare predictions_coffee vs predictions_prepared_coffee to find real forecasts
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("COMPARING PREDICTION TABLES")
print("="*80)

# Check predictions_coffee
print("\n1. predictions_coffee:")
try:
    models = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_coffee
        ORDER BY model_version
    """).collect()

    print(f"   Found {len(models)} model versions:")
    for m in models:
        print(f"     - {m.model_version}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Check predictions_prepared_coffee
print("\n2. predictions_prepared_coffee:")
try:
    models = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_prepared_coffee
        ORDER BY model_version
    """).collect()

    print(f"   Found {len(models)} model versions:")
    for m in models:
        print(f"     - {m.model_version}")

    # Check if any are real forecasts
    real_keywords = ['arima', 'sarimax', 'xgboost', 'prophet', 'random_walk']
    real_models = [m.model_version for m in models
                   if any(k in m.model_version.lower() for k in real_keywords)]

    if real_models:
        print(f"\n   ✓✓✓ FOUND {len(real_models)} REAL FORECAST MODELS!")
    else:
        print(f"\n   ⚠️  Only synthetic models found")

except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("If real forecasts are in predictions_prepared_coffee,")
print("the optimizer needs to query that table instead of predictions_coffee")
