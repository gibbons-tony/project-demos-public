#!/usr/bin/env python3
"""
Rebuild unified_data table using weather_v2 instead of weather.
Simple direct execution via databricks.sql connector.
"""
import os
from databricks import sql
from pathlib import Path

# Read credentials from .env
env_path = Path(__file__).parent / ".env"
env_vars = {}
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                env_vars[key] = value

DATABRICKS_HOST = env_vars.get('DATABRICKS_HOST', '').replace('https://', '')
DATABRICKS_TOKEN = env_vars.get('DATABRICKS_TOKEN', '')
DATABRICKS_HTTP_PATH = env_vars.get('DATABRICKS_HTTP_PATH', '')

print(f"Connecting to: {DATABRICKS_HOST}")

# Connect
connection = sql.connect(
    server_hostname=DATABRICKS_HOST,
    http_path=DATABRICKS_HTTP_PATH,
    access_token=DATABRICKS_TOKEN
)

cursor = connection.cursor()

# Read SQL file
sql_file = Path(__file__).parent.parent / "sql" / "create_unified_data.sql"
with open(sql_file) as f:
    sql_query = f.read()

print(f"\nExecuting unified_data rebuild with weather_v2...")
print(f"SQL file: {sql_file}")
print(f"Size: {len(sql_query)} characters\n")

try:
    cursor.execute(sql_query)
    print("✅ unified_data table rebuilt successfully with weather_v2!")

    # Get row count
    cursor.execute("SELECT COUNT(*) as cnt FROM commodity.silver.unified_data")
    count = cursor.fetchone()[0]
    print(f"   Total rows: {count:,}")

    # Sample data
    cursor.execute("""
        SELECT date, commodity, region, temp_mean_c, precipitation_mm
        FROM commodity.silver.unified_data
        WHERE temp_mean_c IS NOT NULL
        LIMIT 5
    """)
    print("\n   Sample rows:")
    for row in cursor.fetchall():
        print(f"     {row}")

except Exception as e:
    print(f"❌ Error: {e}")
    raise
finally:
    cursor.close()
    connection.close()

print("\n✅ P0 BLOCKER CLEARED - Ready for daily forecast backfill!")
