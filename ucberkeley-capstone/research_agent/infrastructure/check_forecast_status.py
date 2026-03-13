#!/usr/bin/env python3
"""
Check status of forecast tables before migration
"""
import os
from databricks import sql
from dotenv import load_dotenv

# Load environment
load_dotenv()
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

print("="*80)
print("PHASE 0: FORECAST TABLE ASSESSMENT")
print("="*80)

connection = sql.connect(
    server_hostname=DATABRICKS_HOST.replace("https://", ""),
    http_path=DATABRICKS_HTTP_PATH,
    access_token=DATABRICKS_TOKEN
)
cursor = connection.cursor()

# Check forecast tables
print("\n1. Checking forecast tables...")
cursor.execute("SHOW TABLES IN commodity.forecast")
tables = cursor.fetchall()

if tables:
    print(f"\n✅ Found {len(tables)} forecast tables:")
    for table in tables:
        print(f"   - {table[1]}")
else:
    print("\n⚠️  No forecast tables found")

# Check row counts for each table
print("\n2. Checking row counts...")
for table in tables:
    table_name = table[1]
    try:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM commodity.forecast.{table_name}")
        count = cursor.fetchone()[0]
        print(f"   {table_name}: {count:,} rows")
    except Exception as e:
        print(f"   {table_name}: ERROR - {e}")

# Check weather table status
print("\n3. Checking weather tables...")
cursor.execute("SHOW TABLES IN commodity.bronze LIKE 'weather*'")
weather_tables = cursor.fetchall()

for table in weather_tables:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) as cnt FROM commodity.bronze.{table_name}")
    count = cursor.fetchone()[0]
    print(f"   bronze.{table_name}: {count:,} rows")

# Check weather_v2 data quality
print("\n4. Validating weather_v2 data quality...")
cursor.execute("""
    SELECT
        MIN(date) as start_date,
        MAX(date) as end_date,
        COUNT(DISTINCT date) as total_days,
        COUNT(DISTINCT region) as total_regions,
        COUNT(*) as total_rows
    FROM commodity.bronze.weather_v2
""")
result = cursor.fetchone()
print(f"   Start date: {result[0]}")
print(f"   End date: {result[1]}")
print(f"   Total days: {result[2]:,}")
print(f"   Total regions: {result[3]}")
print(f"   Total rows: {result[4]:,}")

# Check Minas Gerais coordinates (should be v2)
print("\n5. Validating coordinates (Minas Gerais sample)...")
cursor.execute("""
    SELECT region, latitude, longitude
    FROM commodity.bronze.weather_v2
    WHERE region = 'Minas_Gerais_Brazil'
    LIMIT 1
""")
coords = cursor.fetchone()
if coords:
    print(f"   Region: {coords[0]}")
    print(f"   Latitude: {coords[1]}")
    print(f"   Longitude: {coords[2]}")

    # Check if v2 (correct) or v1 (wrong)
    if abs(coords[1] - (-20.3155)) < 0.01:
        print(f"   ✅ CORRECT v2 coordinates!")
    elif abs(coords[1] - (-18.5122)) < 0.01:
        print(f"   ❌ WRONG v1 coordinates detected!")
    else:
        print(f"   ⚠️  Unknown coordinates")

cursor.close()
connection.close()

print("\n" + "="*80)
print("ASSESSMENT COMPLETE")
print("="*80)
