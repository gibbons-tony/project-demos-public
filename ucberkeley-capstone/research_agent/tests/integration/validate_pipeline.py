"""
Validate the full pipeline: Lambda → S3 → Databricks → unified_data
"""

from databricks import sql
import os
from datetime import datetime, timedelta

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("="*80)
print("PIPELINE VALIDATION: Lambda → S3 → Databricks → unified_data")
print("="*80)

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# Step 1: Check latest data in landing tables
print("\n1. LANDING LAYER (from S3)")
print("-"*80)

print("\nMarket Data (last 5 days):")
cursor.execute("""
    SELECT date, commodity, COUNT(*) as rows
    FROM commodity.landing.market_data_inc
    WHERE date >= CURRENT_DATE - 5
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")
market_results = cursor.fetchall()
for date, commodity, rows in market_results:
    print(f"  {date} - {commodity}: {rows} rows")

print("\nWeather Data (last 5 days):")
cursor.execute("""
    SELECT date, commodity, COUNT(*) as rows
    FROM commodity.landing.weather_data_inc
    WHERE date >= CURRENT_DATE - 5
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")
weather_results = cursor.fetchall()
for date, commodity, rows in weather_results:
    print(f"  {date} - {commodity}: {rows} rows")

# Step 2: Check bronze layer (deduplicated views)
print("\n2. BRONZE LAYER (deduplicated views)")
print("-"*80)

print("\nMarket Data (last 5 days):")
cursor.execute("""
    SELECT date, commodity, COUNT(*) as rows
    FROM commodity.bronze.market_data
    WHERE date >= CURRENT_DATE - 5
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")
for date, commodity, rows in cursor.fetchall():
    print(f"  {date} - {commodity}: {rows} rows")

print("\nWeather Data (last 5 days):")
cursor.execute("""
    SELECT date, commodity, COUNT(*) as rows
    FROM commodity.bronze.weather_data
    WHERE date >= CURRENT_DATE - 5
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")
for date, commodity, rows in cursor.fetchall():
    print(f"  {date} - {commodity}: {rows} rows")

# Step 3: Check silver unified_data
print("\n3. SILVER LAYER (unified_data)")
print("-"*80)

print("\nLast 5 days in unified_data:")
cursor.execute("""
    SELECT date, commodity, COUNT(*) as rows
    FROM commodity.silver.unified_data
    WHERE date >= CURRENT_DATE - 5
    GROUP BY date, commodity
    ORDER BY date DESC, commodity
""")
unified_results = cursor.fetchall()
for date, commodity, rows in cursor.fetchall():
    print(f"  {date} - {commodity}: {rows} rows")

# Step 4: Overall stats
print("\n4. OVERALL PIPELINE HEALTH")
print("-"*80)

cursor.execute("""
    SELECT
        'Landing (market)' as layer,
        commodity,
        COUNT(*) as total_rows,
        MAX(date) as latest_date
    FROM commodity.landing.market_data_inc
    GROUP BY commodity
    UNION ALL
    SELECT
        'Landing (weather)' as layer,
        commodity,
        COUNT(*) as total_rows,
        MAX(date) as latest_date
    FROM commodity.landing.weather_data_inc
    GROUP BY commodity
    UNION ALL
    SELECT
        'Silver (unified)' as layer,
        commodity,
        COUNT(*) as total_rows,
        MAX(date) as latest_date
    FROM commodity.silver.unified_data
    GROUP BY commodity
    ORDER BY commodity, layer
""")

print(f"\n{'Layer':<20} {'Commodity':<10} {'Total Rows':<15} {'Latest Date':<15}")
print("-"*80)
for layer, commodity, total, latest in cursor.fetchall():
    print(f"{layer:<20} {commodity:<10} {total:<15,} {latest!s:<15}")

# Step 5: Check for data freshness issues
print("\n5. DATA FRESHNESS CHECK")
print("-"*80)

today = datetime.now().date()
yesterday = today - timedelta(days=1)

cursor.execute(f"""
    SELECT
        commodity,
        MAX(date) as latest_date,
        DATEDIFF(CURRENT_DATE, MAX(date)) as days_old
    FROM commodity.silver.unified_data
    GROUP BY commodity
""")

for commodity, latest, days_old in cursor.fetchall():
    status = "✅ FRESH" if days_old <= 2 else "⚠️ STALE"
    print(f"  {commodity}: Latest = {latest} ({days_old} days old) {status}")

cursor.close()
connection.close()

print("\n" + "="*80)
print("PIPELINE VALIDATION COMPLETE")
print("="*80)
