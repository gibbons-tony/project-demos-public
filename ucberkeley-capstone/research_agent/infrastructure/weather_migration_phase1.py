#!/usr/bin/env python3
"""
Weather v2 Migration - Phase 1: Clean Contaminated Forecasts

Drops all forecast tables that were generated with v1 (incorrect) weather data.
"""
import os
from databricks import sql
from dotenv import load_dotenv

# Load from infra/.env
env_path = '../../infra/.env'
load_dotenv(env_path)

token = os.getenv('DATABRICKS_TOKEN')
server_hostname_raw = os.getenv('DATABRICKS_HOST')
if server_hostname_raw:
    server_hostname = server_hostname_raw.replace('https://', '')
else:
    raise ValueError(f"DATABRICKS_HOST not found in {env_path}")
http_path = os.getenv('DATABRICKS_HTTP_PATH')

print("="*80)
print("PHASE 1: CLEAN CONTAMINATED FORECASTS")
print("="*80)
print(f"Server: {server_hostname}")
print()

connection = sql.connect(
    server_hostname=server_hostname,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# List forecast tables before deletion
print("1. Checking existing forecast tables...")
cursor.execute("SHOW TABLES IN commodity.forecast")
tables = cursor.fetchall()

if tables:
    print(f"\n✅ Found {len(tables)} forecast tables:")
    for table in tables:
        print(f"   - {table[1]}")

    # Get row counts
    print("\n2. Checking row counts before deletion...")
    for table in tables:
        table_name = table[1]
        try:
            cursor.execute(f"SELECT COUNT(*) as cnt FROM commodity.forecast.{table_name}")
            count = cursor.fetchone()[0]
            print(f"   {table_name}: {count:,} rows")
        except Exception as e:
            print(f"   {table_name}: ERROR - {e}")

    # Drop all forecast tables
    print("\n3. Dropping forecast tables (generated with v1 weather)...")
    print("⚠️  These will be regenerated with v2 weather data")

    for table in tables:
        table_name = table[1]
        try:
            print(f"   Dropping commodity.forecast.{table_name}...")
            cursor.execute(f"DROP TABLE IF EXISTS commodity.forecast.{table_name}")
            print(f"   ✅ Dropped {table_name}")
        except Exception as e:
            print(f"   ❌ Failed to drop {table_name}: {e}")

    # Verify tables are dropped
    print("\n4. Verifying tables are dropped...")
    cursor.execute("SHOW TABLES IN commodity.forecast")
    remaining = cursor.fetchall()

    if remaining:
        print(f"⚠️  {len(remaining)} tables still exist:")
        for table in remaining:
            print(f"   - {table[1]}")
    else:
        print("✅ All forecast tables successfully dropped")

else:
    print("\n⚠️  No forecast tables found (already cleaned)")

cursor.close()
connection.close()

print("\n" + "="*80)
print("PHASE 1 COMPLETE")
print("="*80)
print("\n✅ Forecast cleanup complete")
print("Next: Phase 3 - Rename weather_v2 → weather")
