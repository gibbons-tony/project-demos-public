"""
Check Sugar weather data in bronze layer
"""

from databricks import sql
import os

# Databricks connection
host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("Connecting to Databricks...")
connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

print("\n" + "="*80)
print("SUGAR WEATHER DATA INVESTIGATION")
print("="*80)

# Check weather data by commodity
print("\n1. Weather data counts by commodity:")
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as total_rows,
        COUNT(DISTINCT date) as unique_dates,
        COUNT(DISTINCT region) as num_regions,
        MIN(date) as start_date,
        MAX(date) as end_date
    FROM commodity.bronze.weather_data
    GROUP BY commodity
    ORDER BY commodity
""")
for row in cursor.fetchall():
    commodity, rows, dates, regions, start, end = row
    print(f"  {commodity}: {rows:,} rows, {dates:,} dates, {regions} regions ({start} to {end})")

# Check sample Sugar weather data
print("\n2. Sample Sugar weather regions (first 10):")
cursor.execute("""
    SELECT DISTINCT region
    FROM commodity.bronze.weather_data
    WHERE commodity = 'Sugar'
    ORDER BY region
    LIMIT 10
""")
results = cursor.fetchall()
if results:
    for (region,) in results:
        print(f"  - {region}")
else:
    print("  ❌ NO SUGAR WEATHER DATA FOUND")

# Check Coffee weather regions for comparison
print("\n3. Coffee weather regions (first 10 for comparison):")
cursor.execute("""
    SELECT DISTINCT region
    FROM commodity.bronze.weather_data
    WHERE commodity = 'Coffee'
    ORDER BY region
    LIMIT 10
""")
for (region,) in cursor.fetchall():
    print(f"  - {region}")

# Check if Sugar data exists in landing/bronze weather tables
print("\n4. Weather data in LANDING table:")
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as rows,
        MIN(date) as start,
        MAX(date) as end
    FROM commodity.landing.weather_data_inc
    GROUP BY commodity
""")
results = cursor.fetchall()
if results:
    for row in results:
        commodity, rows, start, end = row
        print(f"  {commodity}: {rows:,} rows ({start} to {end})")
else:
    print("  (no data or table doesn't exist)")

cursor.close()
connection.close()

print("\n" + "="*80)
print("DIAGNOSIS:")
print("="*80)
print("If Sugar has no weather data, that explains why unified_data only has 380 rows.")
print("The unified_data SQL joins market data with weather data by (date, commodity, region).")
print("Without weather data for Sugar regions, those rows get filtered out.")
print("\n" + "="*80)
