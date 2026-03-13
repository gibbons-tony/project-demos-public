"""
Comprehensive data quality validation for the commodity data pipeline.

Checks for:
- Null values in critical columns
- Data completeness and gaps
- Value ranges and anomalies
- Duplicate records
- Schema integrity
"""

from databricks import sql
import os

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("="*80)
print("DATA QUALITY VALIDATION")
print("="*80)

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# ============================================================================
# 1. NULL VALUE CHECKS
# ============================================================================
print("\n1. NULL VALUE ANALYSIS - unified_data")
print("-"*80)

# Check for nulls in critical columns
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_dates,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) as null_temp,
        SUM(CASE WHEN precipitation_mm IS NULL THEN 1 ELSE 0 END) as null_precip,
        SUM(CASE WHEN region IS NULL THEN 1 ELSE 0 END) as null_region
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Total':<10} {'NULL dates':<12} {'NULL close':<12} {'NULL temp':<12} {'NULL precip':<12} {'NULL region':<12}")
print("-"*80)
for row in cursor.fetchall():
    commodity, total, null_dates, null_close, null_temp, null_precip, null_region = row

    # Highlight any nulls
    issues = []
    if null_dates > 0:
        issues.append(f"dates:{null_dates}")
    if null_close > 0:
        issues.append(f"close:{null_close}")
    if null_temp > 0:
        issues.append(f"temp:{null_temp}")
    if null_precip > 0:
        issues.append(f"precip:{null_precip}")
    if null_region > 0:
        issues.append(f"region:{null_region}")

    status = "❌ NULLS: " + ", ".join(issues) if issues else "✅"
    print(f"{commodity:<10} {total:<10,} {null_dates:<12} {null_close:<12} {null_temp:<12} {null_precip:<12} {null_region:<12} {status}")

# ============================================================================
# 2. DATA COMPLETENESS - DATE GAPS
# ============================================================================
print("\n2. DATE CONTINUITY CHECK (looking for gaps > 7 days)")
print("-"*80)

cursor.execute("""
    WITH date_gaps AS (
        SELECT
            commodity,
            date as current_date,
            LAG(date) OVER (PARTITION BY commodity, region ORDER BY date) as prev_date,
            DATEDIFF(date, LAG(date) OVER (PARTITION BY commodity, region ORDER BY date)) as days_gap,
            region
        FROM commodity.silver.unified_data
    )
    SELECT
        commodity,
        COUNT(DISTINCT region) as regions_with_gaps,
        MAX(days_gap) as max_gap_days,
        COUNT(*) as total_gaps_over_7_days
    FROM date_gaps
    WHERE days_gap > 7
    GROUP BY commodity
""")

results = cursor.fetchall()
if results:
    print(f"\n{'Commodity':<10} {'Regions w/ Gaps':<18} {'Max Gap (days)':<18} {'Total Gaps > 7d':<18}")
    print("-"*80)
    for commodity, regions, max_gap, total_gaps in results:
        status = "⚠️" if total_gaps > 10 else "✅"
        print(f"{commodity:<10} {regions:<18} {max_gap:<18} {total_gaps:<18} {status}")
else:
    print("  ✅ No significant date gaps found")

# ============================================================================
# 3. VALUE RANGE VALIDATION
# ============================================================================
print("\n3. VALUE RANGE VALIDATION")
print("-"*80)

# Check market data ranges
cursor.execute("""
    SELECT
        commodity,
        MIN(close) as min_close,
        MAX(close) as max_close,
        AVG(close) as avg_close,
        MIN(volume) as min_volume,
        MAX(volume) as max_volume
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\nMarket Data Ranges:")
print(f"{'Commodity':<10} {'Min Close':<12} {'Max Close':<12} {'Avg Close':<12} {'Min Volume':<15} {'Max Volume':<15}")
print("-"*80)
for commodity, min_c, max_c, avg_c, min_v, max_v in cursor.fetchall():
    # Flag anomalies (negative prices, zero volumes)
    status = "✅"
    if min_c <= 0:
        status = "❌ Negative/zero price"
    elif min_v == 0:
        status = "⚠️ Zero volume found"

    print(f"{commodity:<10} {min_c:<12.2f} {max_c:<12.2f} {avg_c:<12.2f} {min_v:<15,} {max_v:<15,} {status}")

# Check weather data ranges
cursor.execute("""
    SELECT
        commodity,
        MIN(temp_mean_c) as min_temp,
        MAX(temp_mean_c) as max_temp,
        AVG(temp_mean_c) as avg_temp,
        MIN(precipitation_mm) as min_precip,
        MAX(precipitation_mm) as max_precip
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\nWeather Data Ranges:")
print(f"{'Commodity':<10} {'Min Temp (°C)':<15} {'Max Temp (°C)':<15} {'Avg Temp (°C)':<15} {'Min Precip':<12} {'Max Precip':<12}")
print("-"*80)
for commodity, min_t, max_t, avg_t, min_p, max_p in cursor.fetchall():
    # Flag unrealistic temperatures (< -50°C or > 60°C)
    status = "✅"
    if min_t < -50 or max_t > 60:
        status = "⚠️ Extreme temps"

    print(f"{commodity:<10} {min_t:<15.2f} {max_t:<15.2f} {avg_t:<15.2f} {min_p:<12.2f} {max_p:<12.2f} {status}")

# ============================================================================
# 4. DUPLICATE CHECK
# ============================================================================
print("\n4. DUPLICATE RECORDS CHECK")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        COUNT(DISTINCT date, region) as unique_date_region_pairs,
        COUNT(*) - COUNT(DISTINCT date, region) as duplicates
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Total Rows':<15} {'Unique Pairs':<15} {'Duplicates':<15} {'Status'}")
print("-"*80)
for commodity, total, unique, duplicates in cursor.fetchall():
    status = "❌ DUPLICATES FOUND" if duplicates > 0 else "✅ No duplicates"
    print(f"{commodity:<10} {total:<15,} {unique:<15,} {duplicates:<15,} {status}")

# ============================================================================
# 5. REGION COVERAGE
# ============================================================================
print("\n5. REGION COVERAGE (per commodity)")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(DISTINCT region) as total_regions,
        MIN(date_count) as min_dates_per_region,
        MAX(date_count) as max_dates_per_region,
        AVG(date_count) as avg_dates_per_region
    FROM (
        SELECT
            commodity,
            region,
            COUNT(DISTINCT date) as date_count
        FROM commodity.silver.unified_data
        GROUP BY commodity, region
    )
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Regions':<10} {'Min Dates':<12} {'Max Dates':<12} {'Avg Dates':<12}")
print("-"*80)
for commodity, regions, min_dates, max_dates, avg_dates in cursor.fetchall():
    # Flag if regions have very different date counts
    variance = max_dates - min_dates
    status = "⚠️ High variance" if variance > 100 else "✅"
    print(f"{commodity:<10} {regions:<10} {min_dates:<12,} {max_dates:<12,} {avg_dates:<12,.0f} {status}")

# ============================================================================
# 6. SCHEMA COMPLETENESS
# ============================================================================
print("\n6. SCHEMA VALIDATION - unified_data columns")
print("-"*80)

cursor.execute("DESCRIBE TABLE commodity.silver.unified_data")
columns = [row[0] for row in cursor.fetchall()]

expected_columns = [
    'date', 'commodity', 'region', 'close', 'volume', 'open', 'high', 'low',
    'temp_mean_c', 'precipitation_mm', 'wind_speed_max_kmh'
]

missing = [col for col in expected_columns if col not in columns]
if missing:
    print(f"  ❌ Missing expected columns: {', '.join(missing)}")
else:
    print(f"  ✅ All expected columns present ({len(columns)} total)")

# ============================================================================
# 7. RECENT DATA CHECK (last 7 days)
# ============================================================================
print("\n7. RECENT DATA CHECK (last 7 days)")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(DISTINCT date) as unique_dates_last_7d,
        COUNT(*) as total_rows_last_7d,
        MAX(date) as latest_date
    FROM commodity.silver.unified_data
    WHERE date >= CURRENT_DATE - 7
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Unique Dates':<15} {'Total Rows':<15} {'Latest Date':<15} {'Status'}")
print("-"*80)
for commodity, unique_dates, total_rows, latest_date in cursor.fetchall():
    # Should have data from yesterday at minimum
    from datetime import datetime, timedelta
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    status = "✅" if str(latest_date) >= str(yesterday) else "⚠️ STALE"
    print(f"{commodity:<10} {unique_dates:<15} {total_rows:<15,} {latest_date!s:<15} {status}")

cursor.close()
connection.close()

print("\n" + "="*80)
print("DATA QUALITY VALIDATION COMPLETE")
print("="*80)
