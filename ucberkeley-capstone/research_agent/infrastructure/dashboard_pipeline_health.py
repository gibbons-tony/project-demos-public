"""
Pipeline Health Dashboard

Monitors the Research Agent data pipeline health:
- Lambda → S3 → Databricks → unified_data
- Data freshness, completeness, and quality
"""

from databricks import sql
import os
from datetime import datetime, timedelta

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("="*80)
print("RESEARCH AGENT - PIPELINE HEALTH DASHBOARD")
print("="*80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# ============================================================================
# 1. DATA FRESHNESS - How current is our data?
# ============================================================================
print("1. DATA FRESHNESS")
print("-"*80)

cursor.execute("""
    SELECT
        'Landing (Market)' as layer,
        commodity,
        MAX(date) as latest_date,
        DATEDIFF(CURRENT_DATE, MAX(date)) as days_old,
        COUNT(*) as total_rows
    FROM commodity.landing.market_data_inc
    GROUP BY commodity
    UNION ALL
    SELECT
        'Landing (Weather)' as layer,
        commodity,
        MAX(date) as latest_date,
        DATEDIFF(CURRENT_DATE, MAX(date)) as days_old,
        COUNT(*) as total_rows
    FROM commodity.landing.weather_data_inc
    GROUP BY commodity
    UNION ALL
    SELECT
        'Silver (Unified)' as layer,
        commodity,
        MAX(date) as latest_date,
        DATEDIFF(CURRENT_DATE, MAX(date)) as days_old,
        COUNT(*) as total_rows
    FROM commodity.silver.unified_data
    GROUP BY commodity
    ORDER BY commodity, layer
""")

print(f"\n{'Layer':<20} {'Commodity':<10} {'Latest Date':<15} {'Age (days)':<12} {'Total Rows':<15} {'Status'}")
print("-"*80)

for layer, commodity, latest_date, days_old, total_rows in cursor.fetchall():
    # Determine status
    if days_old == 0:
        status = "✅ TODAY"
    elif days_old == 1:
        status = "✅ YESTERDAY"
    elif days_old <= 2:
        status = "✅ FRESH"
    elif days_old <= 7:
        status = "⚠️ WARN"
    else:
        status = "❌ STALE"

    print(f"{layer:<20} {commodity:<10} {latest_date!s:<15} {days_old:<12} {total_rows:<15,} {status}")

print()

# ============================================================================
# 2. DATA COMPLETENESS - Do we have expected data?
# ============================================================================
print("2. DATA COMPLETENESS")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        COUNT(DISTINCT date) as unique_dates,
        COUNT(DISTINCT region) as unique_regions,
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        DATEDIFF(MAX(date), MIN(date)) as date_span_days
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Rows':<12} {'Dates':<10} {'Regions':<10} {'Date Range':<30} {'Status'}")
print("-"*80)

for commodity, total_rows, unique_dates, unique_regions, earliest, latest, span_days in cursor.fetchall():
    date_range = f"{earliest} to {latest}"

    # Expected: ~10 years = ~3,650 days
    expected_days = 3650
    completeness_pct = (unique_dates / expected_days) * 100

    if completeness_pct >= 100:
        status = "✅ COMPLETE"
    elif completeness_pct >= 80:
        status = "✅ GOOD"
    elif completeness_pct >= 50:
        status = "⚠️ PARTIAL"
    else:
        status = "❌ INCOMPLETE"

    print(f"{commodity:<10} {total_rows:<12,} {unique_dates:<10,} {unique_regions:<10} {date_range:<30} {status}")

print()

# ============================================================================
# 3. DATA QUALITY - Nulls, duplicates, anomalies
# ============================================================================
print("3. DATA QUALITY METRICS")
print("-"*80)

# Check for nulls in critical columns
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) as null_temp,
        SUM(CASE WHEN precipitation_mm IS NULL THEN 1 ELSE 0 END) as null_precip,
        SUM(CASE WHEN region IS NULL THEN 1 ELSE 0 END) as null_region,
        MIN(close) as min_price,
        MAX(close) as max_price
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Total Rows':<12} {'NULL Close':<12} {'NULL Temp':<12} {'NULL Precip':<12} {'Price Range':<20} {'Status'}")
print("-"*80)

for commodity, total, null_close, null_temp, null_precip, null_region, min_price, max_price in cursor.fetchall():
    price_range = f"${min_price:.2f}-${max_price:.2f}"

    # Check for any quality issues
    total_nulls = null_close + null_temp + null_precip + null_region

    if total_nulls == 0 and min_price > 0:
        status = "✅ CLEAN"
    elif total_nulls < total * 0.01:  # Less than 1% nulls
        status = "⚠️ MINOR"
    else:
        status = "❌ ISSUES"

    print(f"{commodity:<10} {total:<12,} {null_close:<12} {null_temp:<12} {null_precip:<12} {price_range:<20} {status}")

print()

# Check for duplicates
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        COUNT(DISTINCT date, region) as unique_combinations,
        COUNT(*) - COUNT(DISTINCT date, region) as duplicates
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print("Duplicate Check:")
print(f"{'Commodity':<10} {'Total Rows':<12} {'Unique':<12} {'Duplicates':<12} {'Status'}")
print("-"*80)

for commodity, total, unique, duplicates in cursor.fetchall():
    status = "✅ NONE" if duplicates == 0 else f"❌ {duplicates}"
    print(f"{commodity:<10} {total:<12,} {unique:<12,} {duplicates:<12} {status}")

print()

# ============================================================================
# 4. PIPELINE FLOW - Data propagation through layers
# ============================================================================
print("4. PIPELINE FLOW (Last 7 Days)")
print("-"*80)

cursor.execute("""
    SELECT
        date,
        commodity,
        SUM(CASE WHEN layer = 'landing_market' THEN 1 ELSE 0 END) as landing_market,
        SUM(CASE WHEN layer = 'landing_weather' THEN 1 ELSE 0 END) as landing_weather,
        SUM(CASE WHEN layer = 'silver' THEN 1 ELSE 0 END) as silver
    FROM (
        SELECT date, commodity, 'landing_market' as layer
        FROM commodity.landing.market_data_inc
        WHERE date >= CURRENT_DATE - 7
        UNION ALL
        SELECT date, commodity, 'landing_weather' as layer
        FROM commodity.landing.weather_data_inc
        WHERE date >= CURRENT_DATE - 7
        UNION ALL
        SELECT date, commodity, 'silver' as layer
        FROM commodity.silver.unified_data
        WHERE date >= CURRENT_DATE - 7
    )
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")

print(f"\n{'Date':<12} {'Commodity':<10} {'Market':<10} {'Weather':<10} {'Unified':<10} {'Status'}")
print("-"*80)

for date, commodity, market, weather, unified in cursor.fetchall():
    # Check if data flowed through all layers
    if market > 0 and weather > 0 and unified > 0:
        status = "✅ FLOW"
    elif market > 0 or weather > 0:
        status = "⚠️ PARTIAL"
    else:
        status = "❌ MISSING"

    print(f"{date!s:<12} {commodity:<10} {market:<10} {weather:<10} {unified:<10} {status}")

print()

# ============================================================================
# 5. RECENT ACTIVITY - What's happening now?
# ============================================================================
print("5. RECENT ACTIVITY (Last 24 Hours)")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        date,
        COUNT(DISTINCT region) as regions_updated
    FROM commodity.silver.unified_data
    WHERE date >= CURRENT_DATE - 1
    GROUP BY commodity, date
    ORDER BY date DESC, commodity
""")

results = cursor.fetchall()

if results:
    print(f"\n{'Commodity':<10} {'Date':<12} {'Regions Updated':<20} {'Status'}")
    print("-"*80)

    for commodity, date, regions in results:
        # Expected regions: Coffee=29, Sugar=38
        expected = 29 if commodity == 'Coffee' else 38

        if regions == expected:
            status = "✅ COMPLETE"
        elif regions > expected * 0.8:
            status = "⚠️ PARTIAL"
        else:
            status = "❌ INCOMPLETE"

        print(f"{commodity:<10} {date!s:<12} {regions:<20} {status}")
else:
    print("\n  ⚠️ No updates in last 24 hours")

print()

# ============================================================================
# 6. HISTORICAL COVERAGE - Do we have complete history?
# ============================================================================
print("6. HISTORICAL DATA COVERAGE")
print("-"*80)

cursor.execute("""
    SELECT
        commodity,
        COUNT(DISTINCT YEAR(date)) as years_covered,
        MIN(YEAR(date)) as earliest_year,
        MAX(YEAR(date)) as latest_year,
        COUNT(DISTINCT date) as total_dates
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

print(f"\n{'Commodity':<10} {'Years':<10} {'Year Range':<15} {'Total Dates':<15} {'Status'}")
print("-"*80)

for commodity, years, earliest_year, latest_year, total_dates in cursor.fetchall():
    year_range = f"{earliest_year}-{latest_year}"

    # Expected: 2015-2025 = 11 years
    if years >= 10:
        status = "✅ COMPLETE"
    elif years >= 5:
        status = "✅ GOOD"
    elif years >= 2:
        status = "⚠️ PARTIAL"
    else:
        status = "❌ LIMITED"

    print(f"{commodity:<10} {years:<10} {year_range:<15} {total_dates:<15,} {status}")

print()

# ============================================================================
# SUMMARY & HEALTH SCORE
# ============================================================================
print("="*80)
print("PIPELINE HEALTH SUMMARY")
print("="*80)
print()

# Calculate overall health score
cursor.execute("""
    SELECT
        COUNT(DISTINCT commodity) as commodities,
        COUNT(*) as total_rows,
        MAX(date) as latest_date,
        DATEDIFF(CURRENT_DATE, MAX(date)) as data_age_days,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_prices,
        COUNT(DISTINCT date) as unique_dates
    FROM commodity.silver.unified_data
""")

commodities, total_rows, latest_date, data_age, null_prices, unique_dates = cursor.fetchone()

print(f"📊 Pipeline Metrics:")
print(f"   - Commodities: {commodities}")
print(f"   - Total Rows: {total_rows:,}")
print(f"   - Unique Dates: {unique_dates:,}")
print(f"   - Latest Date: {latest_date}")
print(f"   - Data Age: {data_age} days")
print()

# Health score calculation
health_score = 100

if data_age > 2:
    health_score -= 30
    print(f"⚠️  Data is {data_age} days old (expected: ≤2 days)")

if null_prices > 0:
    health_score -= 20
    print(f"⚠️  {null_prices} rows with null prices")

if commodities < 2:
    health_score -= 25
    print(f"⚠️  Only {commodities} commodity(ies) found (expected: 2+)")

if unique_dates < 3000:
    health_score -= 15
    print(f"⚠️  Only {unique_dates} unique dates (expected: ~3,700)")

print()

# Overall health status
if health_score >= 90:
    status = "🟢 EXCELLENT"
    message = "Pipeline is healthy and operating normally"
elif health_score >= 70:
    status = "🟡 GOOD"
    message = "Pipeline is operational with minor issues"
elif health_score >= 50:
    status = "🟠 FAIR"
    message = "Pipeline has issues that need attention"
else:
    status = "🔴 POOR"
    message = "Pipeline requires immediate attention"

print(f"Overall Health Score: {health_score}/100 - {status}")
print(f"{message}")
print()

print("="*80)
print()

print("💡 Monitoring Recommendations:")
print("   1. Check this dashboard daily")
print("   2. Investigate if data age > 2 days")
print("   3. Alert if null prices > 0")
print("   4. Verify Lambda functions if data stops flowing")
print("   5. Run rebuild_all_layers.py if pipeline is broken")
print()

cursor.close()
connection.close()
