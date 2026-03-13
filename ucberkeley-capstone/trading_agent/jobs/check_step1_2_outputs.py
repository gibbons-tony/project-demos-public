"""
Check if Step 1 and Step 2 outputs exist
"""
from pyspark.sql import SparkSession
import os

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("CHECKING STEP 1 & 2 OUTPUTS")
print("="*80)

# Check Step 1 outputs (manifest files in /Volumes/)
print("\n1. Step 1 Outputs (Forecast Manifests):")
print("   Checking /Volumes/commodity/trading_agent/files/manifests/")
try:
    files = spark.sql("""
        LIST 'dbfs:/Volumes/commodity/trading_agent/files/manifests/'
    """).collect()
    if files:
        print(f"   ✓ Found {len(files)} manifest files")
        for f in files[:5]:
            print(f"     - {f}")
    else:
        print("   ⚠️  No manifest files found")
except Exception as e:
    print(f"   ℹ️  Directory may not exist or using different path: {e}")

# Check Step 2 outputs (prediction matrices - could be in DB or pickle files)
print("\n2. Step 2 Outputs (Loaded Predictions):")

# Option A: Check if predictions are loaded into trading_agent.predictions_* tables
print("   A. Checking database tables:")
try:
    tables = spark.sql("SHOW TABLES IN commodity.trading_agent LIKE 'predictions_*'").collect()
    if tables:
        print(f"   ✓ Found {len(tables)} prediction tables:")
        for t in tables:
            print(f"     - {t.tableName}")
    else:
        print("   ⚠️  No prediction tables found")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Option B: Check forecast.distributions directly (real forecasts)
print("\n   B. Checking commodity.forecast.distributions:")
try:
    count = spark.sql("""
        SELECT COUNT(*) as cnt
        FROM commodity.forecast.distributions
        WHERE commodity = 'Coffee' AND is_actuals = false
    """).first().cnt
    print(f"   ✓ Found {count:,} forecast rows for Coffee")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("✓ If forecast.distributions has data, Step 3 can query it directly")
print("✓ Or Step 3 can use predictions_* tables if they exist")
