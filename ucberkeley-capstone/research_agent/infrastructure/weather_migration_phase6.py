#!/usr/bin/env python3
"""
Weather v2 Migration - Phase 6: Rebuild Unified Data

Executes create_gold_unified_data.sql to rebuild with new bronze.weather table.

Note: This can take ~10 minutes. If it times out, run the SQL manually:
1. Open https://dbc-5e4780f4-fcec.cloud.databricks.com/sql/editor
2. Copy/paste contents of sql/create_gold_unified_data.sql
3. Run and wait for completion
"""
import os
import time
from databricks import sql
from dotenv import load_dotenv

# Load from infra/.env
env_path = '../../infra/.env'
load_dotenv(env_path)

token = os.getenv('DATABRICKS_TOKEN')
server_hostname_raw = os.getenv('DATABRICKS_HOST')
if server_hostname_raw:
    server_hostname = server_hostname_raw.replace('https://', ''
else:
    raise ValueError(f"DATABRICKS_HOST not found in {env_path}")
http_path = os.getenv('DATABRICKS_HTTP_PATH')

print("="*80)
print("PHASE 6: REBUILD GOLD.UNIFIED_DATA")
print("="*80)
print(f"Server: {server_hostname}")
print()

# Read SQL file
sql_file_path = '../sql/create_gold_unified_data.sql'
print(f"1. Reading SQL file: {sql_file_path}")

with open(sql_file_path, 'r') as f:
    sql_content = f.read()

print(f"   ✅ SQL file loaded ({len(sql_content):,} characters)")

# Connect to Databricks
print("\n2. Connecting to Databricks...")
connection = sql.connect(
    server_hostname=server_hostname,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()
print("   ✅ Connected")

# Check current row count (before rebuild)
print("\n3. Checking current gold.unified_data row count...")
try:
    cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data")
    old_count = cursor.fetchone()[0]
    print(f"   Current: {old_count:,} rows")
except Exception as e:
    print(f"   ⚠️  Table may not exist yet: {e}")
    old_count = 0

# Execute SQL (this may take ~10 minutes)
print("\n4. Executing create_gold_unified_data.sql...")
print("   ⚠️  This may take ~10 minutes. Please wait...")
print()

start_time = time.time()

try:
    cursor.execute(sql_content)
    elapsed = time.time() - start_time
    print(f"   ✅ SQL execution complete ({elapsed:.1f} seconds)")
except Exception as e:
    elapsed = time.time() - start_time
    print(f"   ❌ SQL execution failed after {elapsed:.1f} seconds")
    print(f"   Error: {e}")
    print()
    print("   💡 If this timed out, run the SQL manually:")
    print("   1. Open https://dbc-5e4780f4-fcec.cloud.databricks.com/sql/editor")
    print("   2. Copy/paste sql/create_gold_unified_data.sql")
    print("   3. Run and wait for completion")
    cursor.close()
    connection.close()
    exit(1)

# Verify new row count
print("\n5. Verifying new row count...")
cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data")
new_count = cursor.fetchone()[0]

print(f"   Old count: {old_count:,} rows")
print(f"   New count: {new_count:,} rows")

if new_count > 0:
    print(f"   ✅ gold.unified_data successfully rebuilt")
else:
    print(f"   ❌ gold.unified_data is empty - something went wrong")

# Check date range
print("\n6. Checking date range...")
cursor.execute("""
    SELECT MIN(date), MAX(date)
    FROM commodity.gold.unified_data
""")
date_range = cursor.fetchone()
print(f"   Date range: {date_range[0]} to {date_range[1]}")

# Sample weather data to verify v2 coordinates are in use
print("\n7. Sampling weather data (verify v2 coordinates)...")
cursor.execute("""
    SELECT commodity, weather
    FROM commodity.gold.unified_data
    WHERE date = CURRENT_DATE() - 1
    LIMIT 1
""")
sample = cursor.fetchone()

if sample and sample[1]:
    print(f"   ✅ Weather data found in gold.unified_data")
    print(f"   Sample regions in array: {len(sample[1])} regions")
else:
    print(f"   ⚠️  No weather data found (check SQL joins)")

cursor.close()
connection.close()

print("\n" + "="*80)
print("PHASE 6 COMPLETE")
print("="*80)
print()
print("✅ gold.unified_data rebuilt with bronze.weather (v2 coordinates)")
print("Next: Phase 7 - Regenerate forecasts (forecast_agent)")
