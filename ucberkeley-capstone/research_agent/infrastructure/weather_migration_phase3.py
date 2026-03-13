#!/usr/bin/env python3
"""
Weather v2 Migration - Phase 3: Rename Tables

Renames bronze.weather_v2 → bronze.weather (make v2 canonical)
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
print("PHASE 3: RENAME TABLES (weather_v2 → weather)")
print("="*80)
print(f"Server: {server_hostname}")
print()

connection = sql.connect(
    server_hostname=server_hostname,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# 1. Check existing tables
print("1. Checking existing weather tables...")
cursor.execute("SHOW TABLES IN commodity.bronze LIKE 'weather*'")
tables = cursor.fetchall()

for table in tables:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table_name}")
    count = cursor.fetchone()[0]
    print(f"   bronze.{table_name}: {count:,} rows")

# 2. Drop old weather (v1) table if exists
print("\n2. Dropping old bronze.weather (v1) if exists...")
try:
    cursor.execute("DROP TABLE IF EXISTS commodity.bronze.weather")
    print("   ✅ Dropped old bronze.weather (v1)")
except Exception as e:
    print(f"   ⚠️  {e}")

# 3. Rename weather_v2 → weather
print("\n3. Renaming bronze.weather_v2 → bronze.weather...")
try:
    cursor.execute("ALTER TABLE commodity.bronze.weather_v2 RENAME TO commodity.bronze.weather")
    print("   ✅ Renamed bronze.weather_v2 → bronze.weather")
except Exception as e:
    print(f"   ❌ Failed to rename: {e}")
    cursor.close()
    connection.close()
    exit(1)

# 4. Verify rename
print("\n4. Verifying rename...")
cursor.execute("SHOW TABLES IN commodity.bronze LIKE 'weather*'")
tables_after = cursor.fetchall()

print("   Tables after rename:")
for table in tables_after:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table_name}")
    count = cursor.fetchone()[0]
    print(f"   - bronze.{table_name}: {count:,} rows")

# 5. Verify coordinates (should be v2)
print("\n5. Verifying coordinates (Minas Gerais sample)...")
cursor.execute("""
    SELECT region, latitude, longitude
    FROM commodity.bronze.weather
    WHERE region = 'Minas_Gerais_Brazil'
    LIMIT 1
""")
coords = cursor.fetchone()
if coords:
    print(f"   Region: {coords[0]}")
    print(f"   Latitude: {coords[1]}")
    print(f"   Longitude: {coords[2]}")

    if abs(float(coords[1]) - (-20.3155)) < 0.01:
        print(f"   ✅ CORRECT v2 coordinates!")
    else:
        print(f"   ❌ WRONG coordinates detected!")

# 6. Update table comment
print("\n6. Updating table comment...")
cursor.execute("""
    COMMENT ON TABLE commodity.bronze.weather IS
    'Weather data with CORRECT coordinates (migrated from weather_v2 on 2025-12-05).
    Uses precise growing region coordinates from config/region_coordinates.json.
    Historical note: v1 used state capitals (incorrect), v2+ uses actual growing regions.'
""")
print("   ✅ Table comment updated")

cursor.close()
connection.close()

print("\n" + "="*80)
print("PHASE 3 COMPLETE")
print("="*80)
print("\n✅ Table rename complete")
print("Next: Phase 4 - Update SQL scripts (already done)")
print("Then: Phase 6 - Rebuild unified data")
