# Databricks notebook source
# MAGIC %md
# MAGIC # ImputationTransformer Pipeline Test
# MAGIC
# MAGIC Tests the full ml_lib imputation pipeline with gold tables:
# MAGIC 1. Load `commodity.gold.unified_data_raw`
# MAGIC 2. Apply `ImputationTransformer`
# MAGIC 3. Validate NULL removal
# MAGIC 4. Measure performance
# MAGIC
# MAGIC **Cluster**: Use ml-testing-cluster (i3.xlarge)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

import time
from pyspark.sql.functions import col, count, when, isnan, isnull

# Import ImputationTransformer
from forecast_agent.ml_lib.transformers.imputation import create_production_imputer

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 1: Load Raw Table

# COMMAND ----------

print("Loading commodity.gold.unified_data_raw...")
df_raw = spark.table("commodity.gold.unified_data_raw").filter(col("commodity") == "Coffee")
row_count = df_raw.count()
print(f"✓ Loaded {row_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 2: Analyze NULL Rates (Before Imputation)

# COMMAND ----------

print("Analyzing NULL rates BEFORE imputation...")
null_cols = ['vix', 'open', 'high', 'low', 'volume', 'eur_usd', 'jpy_usd', 'brl_usd', 'close']

null_stats_before = {}
for col_name in null_cols:
    null_count = df_raw.filter(col(col_name).isNull()).count()
    null_pct = (null_count / row_count) * 100
    null_stats_before[col_name] = null_pct
    print(f"  {col_name}: {null_pct:.1f}% NULL")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 3: Apply Imputation

# COMMAND ----------

print("Applying production imputation configuration...")
start_time = time.time()

# Create imputer with production config
imputer = create_production_imputer()

# Transform
df_imputed = imputer.transform(df_raw)

# Cache for performance
df_imputed.cache()
materialized_count = df_imputed.count()

imputation_time = time.time() - start_time

print(f"✓ Imputation + cache completed in {imputation_time:.1f} seconds")
print(f"✓ Materialized {materialized_count:,} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 4: Analyze NULL Rates (After Imputation)

# COMMAND ----------

print("Analyzing NULL rates AFTER imputation...")
null_stats_after = {}

for col_name in null_cols:
    null_count = df_imputed.filter(col(col_name).isNull()).count()
    null_pct = (null_count / row_count) * 100
    null_stats_after[col_name] = null_pct

    # Compare before/after
    before_pct = null_stats_before[col_name]
    change = before_pct - null_pct
    status = "✅" if null_pct == 0 else "⚠️"

    print(f"  {col_name}: {null_pct:.1f}% NULL (was {before_pct:.1f}%, reduced {change:.1f}%) {status}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 5: Validation

# COMMAND ----------

print("Validation Results:")
print("="*60)

success = True

# Check 1: Imputation time < 60s
if imputation_time < 60:
    print(f"✅ Imputation time < 60s ({imputation_time:.1f}s)")
else:
    print(f"❌ Imputation time > 60s ({imputation_time:.1f}s)")
    success = False

# Check 2: No NULLs remain (except close should already be 0%)
remaining_nulls = []
for col_name in null_cols:
    if col_name == 'close':
        continue  # Close should already be 0% NULL in raw table
    if null_stats_after[col_name] > 0:
        remaining_nulls.append(f"{col_name} ({null_stats_after[col_name]:.1f}%)")

if len(remaining_nulls) == 0:
    print(f"✅ All features imputed successfully (0% NULLs)")
else:
    print(f"⚠️ Some features still have NULLs: {', '.join(remaining_nulls)}")
    success = False

# Check 3: Row count unchanged
if materialized_count == row_count:
    print(f"✅ Row count unchanged ({row_count:,} rows)")
else:
    print(f"❌ Row count changed ({row_count:,} → {materialized_count:,})")
    success = False

print("="*60)

if success:
    print("\n🎉 ImputationTransformer is working correctly!")
else:
    print("\n⚠️ Issues found - review output above")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 6: Sample Imputed Data

# COMMAND ----------

print("Sample imputed data (latest 5 rows):")
df_imputed.select("date", "commodity", "close", "vix", "open", "eur_usd") \
    .orderBy(col("date").desc()) \
    .show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test 7: Compare with Production Table

# COMMAND ----------

print("Comparing with commodity.gold.unified_data (forward-filled baseline)...")

df_production = spark.table("commodity.gold.unified_data").filter(col("commodity") == "Coffee")

# Compare a sample of values
comparison = df_imputed.alias("imputed").join(
    df_production.alias("prod"),
    on=["date", "commodity"],
    how="inner"
).select(
    "date",
    col("imputed.vix").alias("imputed_vix"),
    col("prod.vix").alias("prod_vix"),
    col("imputed.open").alias("imputed_open"),
    col("prod.open").alias("prod_open")
).orderBy(col("date").desc()).limit(10)

print("Latest 10 rows - Imputed vs Production:")
comparison.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("\n" + "="*80)
print("ImputationTransformer Pipeline Test - SUMMARY")
print("="*80)
print(f"\nDataset: Coffee commodity")
print(f"Rows: {row_count:,}")
print(f"Imputation time: {imputation_time:.1f}s")
print(f"\nNULL Reduction:")
for col_name in null_cols:
    before = null_stats_before[col_name]
    after = null_stats_after[col_name]
    if before > 0:
        print(f"  {col_name}: {before:.1f}% → {after:.1f}%")

print(f"\nStatus: {'✅ PASS' if success else '⚠️ NEEDS REVIEW'}")
print(f"\n{'='*80}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC - [ ] Run cross-validation with imputed data
# MAGIC - [ ] Compare model performance (raw + imputation vs production forward-filled)
# MAGIC - [ ] Benchmark training speed
# MAGIC - [ ] Test with Sugar commodity
