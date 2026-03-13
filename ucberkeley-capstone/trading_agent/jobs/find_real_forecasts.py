"""
Find where the real forecast models actually are
Check all prediction tables to see which ones contain arima, sarimax, xgboost, prophet, etc.
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("SEARCHING FOR REAL FORECAST MODELS")
print("="*80)

# Get all prediction tables
print("\n1. Finding all prediction tables:")
tables = spark.sql("SHOW TABLES IN commodity.trading_agent LIKE 'predictions*'").collect()
print(f"   Found {len(tables)} prediction tables:")
for t in tables:
    print(f"     - {t.tableName}")

# Check each table for real forecast models
print("\n2. Checking each table for real forecast models:")
print("   (Looking for arima, sarimax, xgboost, prophet, random_walk)")

real_forecast_keywords = ['arima', 'sarimax', 'xgboost', 'prophet', 'random_walk']

for table in tables:
    table_name = f"commodity.trading_agent.{table.tableName}"
    print(f"\n   Checking: {table_name}")

    try:
        # Check if table has model_version column
        columns = spark.sql(f"DESCRIBE {table_name}").collect()
        has_model_version = any(c.col_name == 'model_version' for c in columns)

        if not has_model_version:
            print(f"     ⚠️  No model_version column")
            continue

        # Get distinct model versions
        models = spark.sql(f"""
            SELECT DISTINCT model_version
            FROM {table_name}
            ORDER BY model_version
        """).collect()

        if not models:
            print(f"     ⚠️  Table is empty")
            continue

        # Check if any are real forecast models
        real_models = [m.model_version for m in models
                      if any(keyword in m.model_version.lower() for keyword in real_forecast_keywords)]

        synthetic_models = [m.model_version for m in models
                           if not any(keyword in m.model_version.lower() for keyword in real_forecast_keywords)]

        if real_models:
            print(f"     ✓✓✓ FOUND REAL FORECASTS! ✓✓✓")
            print(f"     Real models ({len(real_models)}):")
            for m in real_models:
                print(f"       - {m}")

        if synthetic_models:
            print(f"     Synthetic models ({len(synthetic_models)}):")
            for m in synthetic_models[:5]:  # Show first 5
                print(f"       - {m}")
            if len(synthetic_models) > 5:
                print(f"       ... and {len(synthetic_models) - 5} more")

    except Exception as e:
        print(f"     ❌ Error: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
