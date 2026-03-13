# Databricks notebook source
# MAGIC %md
# MAGIC # Gold.Unified_Data Validation
# MAGIC
# MAGIC **Purpose**: Comprehensive validation of `commodity.gold.unified_data` table
# MAGIC
# MAGIC **Usage**: Run on `unity-catalog-cluster` in Databricks
# MAGIC
# MAGIC **Runs**: 47+ validation checks on schema, data quality, and array structures

# COMMAND ----------

from pyspark.sql.functions import *
from datetime import datetime, date

print("=" * 80)
print("GOLD.UNIFIED_DATA VALIDATION")
print("=" * 80)
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

# Track validation results
validation_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def check_pass(test_name):
    validation_results["passed"].append(test_name)
    print(f"✅ PASS: {test_name}")

def check_fail(test_name, reason):
    validation_results["failed"].append(f"{test_name}: {reason}")
    print(f"❌ FAIL: {test_name}")
    print(f"   Reason: {reason}")

def check_warn(test_name, reason):
    validation_results["warnings"].append(f"{test_name}: {reason}")
    print(f"⚠️  WARN: {test_name}")
    print(f"   Reason: {reason}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Table Existence & Schema

# COMMAND ----------

print("\n1. TABLE EXISTENCE & SCHEMA VALIDATION")
print("-" * 80)

try:
    count = spark.sql("SELECT COUNT(*) FROM commodity.gold.unified_data LIMIT 1").collect()[0][0]
    check_pass("Table commodity.gold.unified_data exists")
except Exception as e:
    check_fail("Table existence", str(e))
    dbutils.notebook.exit("❌ Cannot proceed - table does not exist!")

# Check expected columns
print("\nChecking schema columns...")
columns = {col.name: col.dataType.simpleString() for col in spark.table("commodity.gold.unified_data").schema}

expected_columns = {
    "date": "date",
    "commodity": "string",
    "is_trading_day": "int",
    "close": "double",
    "vix": "double",
    "weather_data": "array",
    "gdelt_themes": "array"
}

for col_name, expected_type in expected_columns.items():
    if col_name not in columns:
        check_fail(f"Column '{col_name}' exists", f"Column not found")
    elif expected_type in columns[col_name].lower():
        check_pass(f"Column '{col_name}' has correct type")
    else:
        check_warn(f"Column '{col_name}' type", f"Expected {expected_type}, got {columns[col_name]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Row Counts & Grain

# COMMAND ----------

print("\n2. ROW COUNTS & GRAIN VALIDATION")
print("-" * 80)

total_rows = spark.sql("SELECT COUNT(*) as cnt FROM commodity.gold.unified_data").collect()[0][0]
print(f"\nTotal rows: {total_rows:,}")

# Expected rows calculation
start_date = date(2015, 7, 7)
today = date.today()
days_elapsed = (today - start_date).days
expected_min_rows = int(2 * days_elapsed * 0.95)
expected_max_rows = int(2 * days_elapsed * 1.05)

if expected_min_rows <= total_rows <= expected_max_rows:
    check_pass(f"Row count is reasonable ({total_rows:,} rows for {days_elapsed} days)")
else:
    check_warn("Row count", f"Expected ~{2 * days_elapsed:,} rows, got {total_rows:,}")

# Check grain uniqueness
grain_check = spark.sql("""
    SELECT COUNT(*) as total, COUNT(DISTINCT date, commodity) as unique_keys
    FROM commodity.gold.unified_data
""").collect()[0]

if grain_check.total == grain_check.unique_keys:
    check_pass(f"Grain (date, commodity) is unique - no duplicates")
else:
    check_fail("Unique grain", f"Expected {grain_check.total} unique (date, commodity), got {grain_check.unique_keys}")

# Rows per commodity
print("\nRows per commodity:")
for row in spark.sql("""
    SELECT commodity, COUNT(*) as cnt
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect():
    print(f"  {row.commodity}: {row.cnt:,} rows")
    if row.cnt < days_elapsed * 0.9:
        check_warn(f"{row.commodity} row count", f"Only {row.cnt:,} rows for {days_elapsed} days")
    else:
        check_pass(f"{row.commodity} has sufficient rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Date Range & Continuity

# COMMAND ----------

print("\n3. DATE RANGE & CONTINUITY")
print("-" * 80)

for row in spark.sql("""
    SELECT
        commodity,
        MIN(date) as min_date,
        MAX(date) as max_date,
        COUNT(DISTINCT date) as unique_dates,
        DATEDIFF(MAX(date), MIN(date)) + 1 as expected_dates
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect():
    print(f"\n{row.commodity}:")
    print(f"  Date range: {row.min_date} to {row.max_date}")
    print(f"  Unique dates: {row.unique_dates:,}")
    print(f"  Expected dates: {row.expected_dates:,}")

    if str(row.min_date) == "2015-07-07":
        check_pass(f"{row.commodity} starts on 2015-07-07")
    else:
        check_warn(f"{row.commodity} start date", f"Expected 2015-07-07, got {row.min_date}")

    if row.unique_dates == row.expected_dates:
        check_pass(f"{row.commodity} has continuous daily data (no gaps)")
    else:
        check_warn(f"{row.commodity} date continuity", f"Missing {row.expected_dates - row.unique_dates} dates")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. NULL Value Checks

# COMMAND ----------

print("\n4. NULL VALUE CHECKS (Scalar Columns)")
print("-" * 80)

null_checks = spark.sql("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_dates,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as null_open,
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as null_vix,
        SUM(CASE WHEN is_trading_day IS NULL THEN 1 ELSE 0 END) as null_trading_flag
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect()

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL date':<10} {'NULL close':<10} {'NULL open':<10} {'NULL VIX':<10} {'NULL flag':<10}")
print("-" * 80)

for row in null_checks:
    print(f"{row.commodity:<10} {row.total_rows:<12,} {row.null_dates:<10} {row.null_close:<10} {row.null_open:<10} {row.null_vix:<10} {row.null_trading_flag:<10}")

    if row.null_dates > 0:
        check_fail(f"{row.commodity} - date nulls", f"{row.null_dates} null dates found")
    else:
        check_pass(f"{row.commodity} - no null dates")

    if row.null_close > 0:
        check_fail(f"{row.commodity} - close nulls", f"{row.null_close} null close prices")
    else:
        check_pass(f"{row.commodity} - no null close prices")

    if row.null_vix > 0:
        check_fail(f"{row.commodity} - VIX nulls", f"{row.null_vix} null VIX values")
    else:
        check_pass(f"{row.commodity} - no null VIX")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Array Structure - weather_data

# COMMAND ----------

print("\n5. ARRAY STRUCTURE VALIDATION - weather_data")
print("-" * 80)

weather_stats = spark.sql("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN weather_data IS NULL THEN 1 ELSE 0 END) as null_weather,
        SUM(CASE WHEN size(weather_data) = 0 THEN 1 ELSE 0 END) as empty_arrays,
        AVG(size(weather_data)) as avg_regions,
        MIN(size(weather_data)) as min_regions,
        MAX(size(weather_data)) as max_regions
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect()

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL arrays':<12} {'Empty arrays':<13} {'Avg regions':<12} {'Min':<6} {'Max':<6}")
print("-" * 80)

for row in weather_stats:
    print(f"{row.commodity:<10} {row.total_rows:<12,} {row.null_weather:<12} {row.empty_arrays:<13} {row.avg_regions:<12.1f} {row.min_regions:<6} {row.max_regions:<6}")

    if row.null_weather > 0:
        check_warn(f"{row.commodity} - weather_data nulls", f"{row.null_weather} null arrays")
    else:
        check_pass(f"{row.commodity} - no null weather arrays")

    if row.min_regions > 0:
        check_pass(f"{row.commodity} - all rows have weather data")
    else:
        check_warn(f"{row.commodity} - empty weather arrays", f"{row.empty_arrays} rows have no weather data")

# Sample weather structure
print("\nSample weather_data structure:")
sample = spark.sql("""
    SELECT weather_data
    FROM commodity.gold.unified_data
    WHERE size(weather_data) > 0
    LIMIT 1
""").collect()
if sample:
    print(f"  {str(sample[0][0])[:150]}...")
    check_pass("weather_data contains struct arrays")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Array Structure - gdelt_themes

# COMMAND ----------

print("\n6. ARRAY STRUCTURE VALIDATION - gdelt_themes")
print("-" * 80)

gdelt_stats = spark.sql("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as null_gdelt,
        SUM(CASE WHEN size(gdelt_themes) = 0 THEN 1 ELSE 0 END) as empty_arrays,
        AVG(size(gdelt_themes)) as avg_themes,
        MIN(size(gdelt_themes)) as min_themes,
        MAX(size(gdelt_themes)) as max_themes
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect()

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL arrays':<12} {'Empty arrays':<13} {'Avg themes':<12} {'Min':<6} {'Max':<6}")
print("-" * 80)

for row in gdelt_stats:
    print(f"{row.commodity:<10} {row.total_rows:<12,} {row.null_gdelt:<12} {row.empty_arrays:<13} {row.avg_themes:<12.1f} {row.min_themes:<6} {row.max_themes:<6}")

    if row.null_gdelt > 0:
        check_warn(f"{row.commodity} - gdelt_themes nulls", f"{row.null_gdelt} null arrays (OK if forward-filled)")
    else:
        check_pass(f"{row.commodity} - no null GDELT arrays")

    if row.max_themes == 7:
        check_pass(f"{row.commodity} - GDELT has 7 theme groups as expected")
    else:
        check_warn(f"{row.commodity} - GDELT theme count", f"Expected 7 themes, got max {row.max_themes}")

# Sample GDELT structure
print("\nSample gdelt_themes structure:")
sample = spark.sql("""
    SELECT gdelt_themes
    FROM commodity.gold.unified_data
    WHERE size(gdelt_themes) > 0
    LIMIT 1
""").collect()
if sample:
    print(f"  {str(sample[0][0])[:150]}...")
    check_pass("gdelt_themes contains struct arrays")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Data Quality - Value Ranges

# COMMAND ----------

print("\n7. DATA QUALITY - VALUE RANGES")
print("-" * 80)

price_stats = spark.sql("""
    SELECT
        commodity,
        MIN(close) as min_close,
        MAX(close) as max_close,
        AVG(close) as avg_close,
        MIN(volume) as min_volume,
        MAX(volume) as max_volume,
        SUM(CASE WHEN close <= 0 THEN 1 ELSE 0 END) as negative_prices
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect()

print(f"\n{'Commodity':<10} {'Min Close':<12} {'Max Close':<12} {'Avg Close':<12} {'Min Volume':<12} {'Max Volume':<12} {'Bad Prices':<12}")
print("-" * 80)

for row in price_stats:
    print(f"{row.commodity:<10} {row.min_close:<12.2f} {row.max_close:<12.2f} {row.avg_close:<12.2f} {row.min_volume:<12,.0f} {row.max_volume:<12,.0f} {row.negative_prices:<12}")

    if row.negative_prices > 0:
        check_fail(f"{row.commodity} - price validity", f"{row.negative_prices} non-positive prices")
    else:
        check_pass(f"{row.commodity} - all prices are positive")

    if row.min_close > 0 and row.max_close < 10000:
        check_pass(f"{row.commodity} - price range is reasonable")
    else:
        check_warn(f"{row.commodity} - price range", f"Range {row.min_close:.2f} to {row.max_close:.2f} seems unusual")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Trading Day Flag

# COMMAND ----------

print("\n8. TRADING DAY FLAG VALIDATION")
print("-" * 80)

trading_stats = spark.sql("""
    SELECT
        commodity,
        COUNT(*) as total_days,
        SUM(is_trading_day) as trading_days,
        COUNT(*) - SUM(is_trading_day) as non_trading_days,
        ROUND(100.0 * SUM(is_trading_day) / COUNT(*), 1) as trading_pct
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""").collect()

print(f"\n{'Commodity':<10} {'Total Days':<12} {'Trading Days':<14} {'Non-Trading':<14} {'Trading %':<12}")
print("-" * 80)

for row in trading_stats:
    print(f"{row.commodity:<10} {row.total_days:<12,} {row.trading_days:<14,} {row.non_trading_days:<14,} {row.trading_pct:<12.1f}%")

    if 65 <= row.trading_pct <= 75:
        check_pass(f"{row.commodity} - trading day percentage is reasonable ({row.trading_pct}%)")
    else:
        check_warn(f"{row.commodity} - trading day %", f"{row.trading_pct}% seems unusual (expected ~70%)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

total_checks = len(validation_results["passed"]) + len(validation_results["failed"]) + len(validation_results["warnings"])
print(f"\nTotal checks: {total_checks}")
print(f"✅ Passed:    {len(validation_results['passed'])}")
print(f"⚠️  Warnings:  {len(validation_results['warnings'])}")
print(f"❌ Failed:    {len(validation_results['failed'])}")

if validation_results["failed"]:
    print("\n❌ FAILED CHECKS:")
    for failure in validation_results["failed"]:
        print(f"  - {failure}")

if validation_results["warnings"]:
    print("\n⚠️  WARNINGS:")
    for warning in validation_results["warnings"]:
        print(f"  - {warning}")

print("\n" + "=" * 80)
if len(validation_results["failed"]) == 0:
    if len(validation_results["warnings"]) == 0:
        print("🎉 ALL CHECKS PASSED! gold.unified_data is valid and ready for use.")
    else:
        print("✅ VALIDATION PASSED with warnings. Review warnings above.")
else:
    print("❌ VALIDATION FAILED. Fix issues above before using this table.")
print("=" * 80)

# COMMAND ----------
