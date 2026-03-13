#!/usr/bin/env python3
"""
Comprehensive validation for commodity.gold.unified_data table.

Validates:
- Schema correctness (columns, types, array structures)
- Data completeness (row counts, date ranges, continuity)
- Data quality (no unexpected nulls, valid ranges)
- Array structure integrity (weather_data, gdelt_themes)
- Pipeline correctness (expected grain, aggregations)

Usage:
    python research_agent/infrastructure/tests/validate_gold_unified_data.py
"""

from databricks import sql
import os
from datetime import datetime

# Load credentials
host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("=" * 80)
print("GOLD.UNIFIED_DATA VALIDATION")
print("=" * 80)
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 80)

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

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

# ============================================================================
# 1. TABLE EXISTENCE & SCHEMA
# ============================================================================
print("\n1. TABLE EXISTENCE & SCHEMA VALIDATION")
print("-" * 80)

try:
    cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data LIMIT 1")
    cursor.fetchone()
    check_pass("Table commodity.gold.unified_data exists")
except Exception as e:
    check_fail("Table existence", str(e))
    print("\n❌ Cannot proceed - table does not exist!")
    exit(1)

# Check expected columns exist
print("\nChecking schema columns...")
cursor.execute("DESCRIBE commodity.gold.unified_data")
columns = {row[0]: row[1] for row in cursor.fetchall()}

expected_columns = {
    "date": "date",
    "commodity": "string",
    "is_trading_day": "int",
    "open": "double",
    "high": "double",
    "low": "double",
    "close": "double",
    "volume": "double",
    "vix": "double",
    # Exchange rates
    "vnd_usd": "double",
    "cop_usd": "double",
    "idr_usd": "double",
    # Arrays
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

# ============================================================================
# 2. ROW COUNTS & GRAIN VALIDATION
# ============================================================================
print("\n2. ROW COUNTS & GRAIN VALIDATION")
print("-" * 80)

# Overall row count
cursor.execute("SELECT COUNT(*) as cnt FROM commodity.gold.unified_data")
total_rows = cursor.fetchone()[0]
print(f"\nTotal rows: {total_rows:,}")

# Expected: ~7k rows (2 commodities × ~3,500 days from 2015-07-07 to present)
# Calculate expected rows
from datetime import date
start_date = date(2015, 7, 7)
today = date.today()
days_elapsed = (today - start_date).days
expected_min_rows = 2 * days_elapsed * 0.95  # 95% threshold
expected_max_rows = 2 * days_elapsed * 1.05  # 105% threshold

if expected_min_rows <= total_rows <= expected_max_rows:
    check_pass(f"Row count is reasonable ({total_rows:,} rows for {days_elapsed} days)")
else:
    check_warn("Row count", f"Expected ~{2 * days_elapsed:,} rows, got {total_rows:,}")

# Check grain: (date, commodity) should be unique
cursor.execute("""
    SELECT COUNT(*) as total, COUNT(DISTINCT date, commodity) as unique_keys
    FROM commodity.gold.unified_data
""")
total, unique = cursor.fetchone()
if total == unique:
    check_pass(f"Grain (date, commodity) is unique - no duplicates")
else:
    check_fail("Unique grain", f"Expected {total} unique (date, commodity), got {unique}")

# Rows per commodity
cursor.execute("""
    SELECT commodity, COUNT(*) as cnt
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""")
print("\nRows per commodity:")
for commodity, cnt in cursor.fetchall():
    print(f"  {commodity}: {cnt:,} rows")
    if cnt < days_elapsed * 0.9:
        check_warn(f"{commodity} row count", f"Only {cnt:,} rows for {days_elapsed} days")
    else:
        check_pass(f"{commodity} has sufficient rows")

# ============================================================================
# 3. DATE RANGE & CONTINUITY
# ============================================================================
print("\n3. DATE RANGE & CONTINUITY")
print("-" * 80)

cursor.execute("""
    SELECT
        commodity,
        MIN(date) as min_date,
        MAX(date) as max_date,
        COUNT(DISTINCT date) as unique_dates,
        DATEDIFF(MAX(date), MIN(date)) + 1 as expected_dates
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""")

for commodity, min_date, max_date, unique_dates, expected_dates in cursor.fetchall():
    print(f"\n{commodity}:")
    print(f"  Date range: {min_date} to {max_date}")
    print(f"  Unique dates: {unique_dates:,}")
    print(f"  Expected dates: {expected_dates:,}")

    if str(min_date) == "2015-07-07":
        check_pass(f"{commodity} starts on 2015-07-07")
    else:
        check_warn(f"{commodity} start date", f"Expected 2015-07-07, got {min_date}")

    if unique_dates == expected_dates:
        check_pass(f"{commodity} has continuous daily data (no gaps)")
    else:
        check_warn(f"{commodity} date continuity", f"Missing {expected_dates - unique_dates} dates")

# ============================================================================
# 4. NULL VALUE CHECKS (Scalar Columns)
# ============================================================================
print("\n4. NULL VALUE CHECKS (Scalar Columns)")
print("-" * 80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_dates,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as null_open,
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as null_vix,
        SUM(CASE WHEN vnd_usd IS NULL THEN 1 ELSE 0 END) as null_vnd,
        SUM(CASE WHEN is_trading_day IS NULL THEN 1 ELSE 0 END) as null_trading_flag
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""")

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL date':<10} {'NULL close':<10} {'NULL open':<10} {'NULL VIX':<10} {'NULL FX':<10} {'NULL flag':<10}")
print("-" * 80)

for row in cursor.fetchall():
    commodity, total, null_dates, null_close, null_open, null_vix, null_vnd, null_flag = row
    print(f"{commodity:<10} {total:<12,} {null_dates:<10} {null_close:<10} {null_open:<10} {null_vix:<10} {null_vnd:<10} {null_flag:<10}")

    # These columns should NEVER be null (forward-filled)
    if null_dates > 0:
        check_fail(f"{commodity} - date nulls", f"{null_dates} null dates found")
    else:
        check_pass(f"{commodity} - no null dates")

    if null_close > 0:
        check_fail(f"{commodity} - close nulls", f"{null_close} null close prices")
    else:
        check_pass(f"{commodity} - no null close prices")

    if null_vix > 0:
        check_fail(f"{commodity} - VIX nulls", f"{null_vix} null VIX values")
    else:
        check_pass(f"{commodity} - no null VIX")

# ============================================================================
# 5. ARRAY STRUCTURE VALIDATION (weather_data)
# ============================================================================
print("\n5. ARRAY STRUCTURE VALIDATION - weather_data")
print("-" * 80)

cursor.execute("""
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
""")

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL arrays':<12} {'Empty arrays':<13} {'Avg regions':<12} {'Min':<6} {'Max':<6}")
print("-" * 80)

for commodity, total, null_weather, empty_arrays, avg_regions, min_regions, max_regions in cursor.fetchall():
    print(f"{commodity:<10} {total:<12,} {null_weather:<12} {empty_arrays:<13} {avg_regions:<12.1f} {min_regions:<6} {max_regions:<6}")

    # Weather arrays should not be null (may be empty for some commodities/regions)
    if null_weather > 0:
        check_warn(f"{commodity} - weather_data nulls", f"{null_weather} null arrays")
    else:
        check_pass(f"{commodity} - no null weather arrays")

    # Check reasonable number of regions
    if min_regions > 0:
        check_pass(f"{commodity} - all rows have weather data")
    else:
        check_warn(f"{commodity} - empty weather arrays", f"{empty_arrays} rows have no weather data")

# Check weather struct fields
print("\nSample weather_data structure:")
cursor.execute("""
    SELECT weather_data
    FROM commodity.gold.unified_data
    WHERE size(weather_data) > 0
    LIMIT 1
""")
sample_weather = cursor.fetchone()
if sample_weather:
    print(f"  Sample: {str(sample_weather[0])[:200]}...")
    check_pass("weather_data contains struct arrays")
else:
    check_warn("weather_data structure", "No non-empty weather arrays found")

# ============================================================================
# 6. ARRAY STRUCTURE VALIDATION (gdelt_themes)
# ============================================================================
print("\n6. ARRAY STRUCTURE VALIDATION - gdelt_themes")
print("-" * 80)

cursor.execute("""
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
""")

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL arrays':<12} {'Empty arrays':<13} {'Avg themes':<12} {'Min':<6} {'Max':<6}")
print("-" * 80)

for commodity, total, null_gdelt, empty_arrays, avg_themes, min_themes, max_themes in cursor.fetchall():
    print(f"{commodity:<10} {total:<12,} {null_gdelt:<12} {empty_arrays:<13} {avg_themes:<12.1f} {min_themes:<6} {max_themes:<6}")

    # GDELT may be null or empty (not every day has articles)
    if null_gdelt > 0:
        check_warn(f"{commodity} - gdelt_themes nulls", f"{null_gdelt} null arrays (OK if forward-filled)")
    else:
        check_pass(f"{commodity} - no null GDELT arrays")

    # Expected 7 theme groups (SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER)
    if max_themes == 7:
        check_pass(f"{commodity} - GDELT has 7 theme groups as expected")
    else:
        check_warn(f"{commodity} - GDELT theme count", f"Expected 7 themes, got max {max_themes}")

# Check GDELT struct fields
print("\nSample gdelt_themes structure:")
cursor.execute("""
    SELECT gdelt_themes
    FROM commodity.gold.unified_data
    WHERE size(gdelt_themes) > 0
    LIMIT 1
""")
sample_gdelt = cursor.fetchone()
if sample_gdelt:
    print(f"  Sample: {str(sample_gdelt[0])[:200]}...")
    check_pass("gdelt_themes contains struct arrays")
else:
    check_warn("gdelt_themes structure", "No non-empty GDELT arrays found")

# ============================================================================
# 7. DATA QUALITY - VALUE RANGES
# ============================================================================
print("\n7. DATA QUALITY - VALUE RANGES")
print("-" * 80)

cursor.execute("""
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
""")

print(f"\n{'Commodity':<10} {'Min Close':<12} {'Max Close':<12} {'Avg Close':<12} {'Min Volume':<12} {'Max Volume':<12} {'Bad Prices':<12}")
print("-" * 80)

for commodity, min_close, max_close, avg_close, min_vol, max_vol, neg_prices in cursor.fetchall():
    print(f"{commodity:<10} {min_close:<12.2f} {max_close:<12.2f} {avg_close:<12.2f} {min_vol:<12,.0f} {max_vol:<12,.0f} {neg_prices:<12}")

    # Prices should be positive
    if neg_prices > 0:
        check_fail(f"{commodity} - price validity", f"{neg_prices} non-positive prices")
    else:
        check_pass(f"{commodity} - all prices are positive")

    # Reasonable price ranges (sanity check)
    if min_close > 0 and max_close < 10000:
        check_pass(f"{commodity} - price range is reasonable")
    else:
        check_warn(f"{commodity} - price range", f"Range {min_close:.2f} to {max_close:.2f} seems unusual")

# ============================================================================
# 8. TRADING DAY FLAG VALIDATION
# ============================================================================
print("\n8. TRADING DAY FLAG VALIDATION")
print("-" * 80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_days,
        SUM(is_trading_day) as trading_days,
        COUNT(*) - SUM(is_trading_day) as non_trading_days,
        ROUND(100.0 * SUM(is_trading_day) / COUNT(*), 1) as trading_pct
    FROM commodity.gold.unified_data
    GROUP BY commodity
    ORDER BY commodity
""")

print(f"\n{'Commodity':<10} {'Total Days':<12} {'Trading Days':<14} {'Non-Trading':<14} {'Trading %':<12}")
print("-" * 80)

for commodity, total, trading, non_trading, pct in cursor.fetchall():
    print(f"{commodity:<10} {total:<12,} {trading:<14,} {non_trading:<14,} {pct:<12.1f}%")

    # Typically ~250 trading days per year (weekdays minus holidays)
    # So roughly 68-72% of days should be trading days
    if 65 <= pct <= 75:
        check_pass(f"{commodity} - trading day percentage is reasonable ({pct}%)")
    else:
        check_warn(f"{commodity} - trading day %", f"{pct}% seems unusual (expected ~70%)")

# ============================================================================
# 9. COMPARISON TO SILVER.UNIFIED_DATA
# ============================================================================
print("\n9. COMPARISON TO SILVER.UNIFIED_DATA")
print("-" * 80)

try:
    cursor.execute("""
        SELECT
            COUNT(*) as silver_rows,
            COUNT(DISTINCT date) as silver_dates,
            COUNT(DISTINCT commodity) as silver_commodities,
            COUNT(DISTINCT region) as silver_regions
        FROM commodity.silver.unified_data
    """)
    silver_rows, silver_dates, silver_commodities, silver_regions = cursor.fetchone()

    cursor.execute("""
        SELECT
            COUNT(*) as gold_rows,
            COUNT(DISTINCT date) as gold_dates,
            COUNT(DISTINCT commodity) as gold_commodities
        FROM commodity.gold.unified_data
    """)
    gold_rows, gold_dates, gold_commodities = cursor.fetchone()

    print(f"\nsilver.unified_data: {silver_rows:,} rows ({silver_dates:,} dates × {silver_commodities} commodities × {silver_regions} regions)")
    print(f"gold.unified_data:   {gold_rows:,} rows ({gold_dates:,} dates × {gold_commodities} commodities)")
    print(f"\nReduction: {100 * (1 - gold_rows / silver_rows):.1f}% fewer rows")

    # Gold should have ~90% fewer rows (aggregating regions into arrays)
    reduction_pct = 100 * (1 - gold_rows / silver_rows)
    if 85 <= reduction_pct <= 95:
        check_pass(f"Row reduction is as expected ({reduction_pct:.1f}% fewer rows)")
    else:
        check_warn("Row reduction", f"{reduction_pct:.1f}% reduction (expected ~90%)")

    # Same number of unique dates
    if gold_dates == silver_dates:
        check_pass("Gold and silver have same date coverage")
    else:
        check_warn("Date coverage", f"Gold has {gold_dates} dates vs Silver {silver_dates}")

except Exception as e:
    check_warn("Silver comparison", f"Could not compare to silver.unified_data: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
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
    exit_code = 0
else:
    print("❌ VALIDATION FAILED. Fix issues above before using this table.")
    exit_code = 1

print("=" * 80)

connection.close()
exit(exit_code)
