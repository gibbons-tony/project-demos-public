"""
Quick test: ImputationTransformer with real gold tables.

Tests the production imputation configuration on commodity.gold.unified_data_raw.
"""
import os
import sys
import time
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from forecast_agent.ml_lib.transformers.imputation import create_production_imputer

# Load credentials
load_dotenv('../infra/.env')

# Create Spark session with Databricks
spark = SparkSession.builder \
    .appName("ImputationTest") \
    .config("spark.databricks.service.address", os.environ['DATABRICKS_HOST']) \
    .config("spark.databricks.service.token", os.environ['DATABRICKS_TOKEN']) \
    .getOrCreate()

print("="*80)
print("ImputationTransformer Integration Test")
print("="*80)

# Test 1: Load raw table
print("\n1. Loading commodity.gold.unified_data_raw...")
df_raw = spark.table("commodity.gold.unified_data_raw").filter(col("commodity") == "Coffee")
row_count = df_raw.count()
print(f"   Loaded {row_count:,} rows")

# Test 2: Analyze NULL rates before imputation
print("\n2. Analyzing NULL rates BEFORE imputation...")
null_cols = ['vix', 'open', 'high', 'low', 'volume', 'eur_usd', 'jpy_usd', 'close']
null_stats_before = {}

for col_name in null_cols:
    null_count = df_raw.filter(col(col_name).isNull()).count()
    null_pct = (null_count / row_count) * 100
    null_stats_before[col_name] = null_pct
    print(f"   {col_name}: {null_pct:.1f}% NULL")

# Test 3: Apply imputation
print("\n3. Applying production imputation configuration...")
start = time.time()

imputer = create_production_imputer()
df_imputed = imputer.transform(df_raw)

# Cache for performance
df_imputed.cache()
df_imputed.count()  # Materialize

imputation_time = time.time() - start
print(f"   ✓ Imputation + cache completed in {imputation_time:.1f} seconds")

# Test 4: Analyze NULL rates after imputation
print("\n4. Analyzing NULL rates AFTER imputation...")
null_stats_after = {}

for col_name in null_cols:
    null_count = df_imputed.filter(col(col_name).isNull()).count()
    null_pct = (null_count / row_count) * 100
    null_stats_after[col_name] = null_pct
    status = "✅" if null_pct == 0 else "⚠️"
    print(f"   {col_name}: {null_pct:.1f}% NULL {status}")

# Test 5: Validate success criteria
print("\n5. Validation:")
success = True

# Check imputation time
if imputation_time < 60:
    print(f"   ✅ Imputation time < 60s ({imputation_time:.1f}s)")
else:
    print(f"   ❌ Imputation time > 60s ({imputation_time:.1f}s)")
    success = False

# Check no NULLs remain (except close, which should already be 0%)
for col_name in null_cols:
    if col_name == 'close':
        continue  # Close should already be 0% NULL
    if null_stats_after[col_name] > 0:
        print(f"   ⚠️ {col_name} still has {null_stats_after[col_name]:.1f}% NULLs")
        success = False

if success:
    print(f"   ✅ All features imputed successfully")

# Test 6: Sample data
print("\n6. Sample imputed data (latest 3 rows):")
sample = df_imputed.select("date", "commodity", "close", "vix", "open", "eur_usd") \
    .orderBy(col("date").desc()) \
    .limit(3) \
    .collect()

for row in sample:
    print(f"   {row['date']} | close={row['close']:.2f} | vix={row['vix']:.2f if row['vix'] else 'NULL'} | open={row['open']:.2f if row['open'] else 'NULL'} | eur_usd={row['eur_usd']:.4f if row['eur_usd'] else 'NULL'}")

print("\n" + "="*80)
print("Test Complete!")
print("="*80)

if success:
    print("\n✅ ImputationTransformer is working correctly with gold tables!")
    print(f"\nPerformance: {imputation_time:.1f}s for {row_count:,} rows")
    print(f"Ready to use in ml_lib pipeline")
else:
    print("\n❌ Issues found - review output above")

spark.stop()
