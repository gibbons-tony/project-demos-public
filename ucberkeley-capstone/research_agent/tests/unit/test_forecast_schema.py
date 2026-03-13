"""
Test forecast schema after catalog cleanup
Verify that commodity.forecast.* tables work correctly
"""
from databricks import sql
import os
import pandas as pd
from datetime import datetime, timedelta

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

print("="*80)
print("FORECAST SCHEMA VALIDATION")
print("="*80)
print()

# Check forecast schema exists
print("Checking forecast schema...")
cursor.execute("SHOW SCHEMAS IN commodity")
schemas = [row[0] for row in cursor.fetchall()]
if 'forecast' in schemas:
    print("✅ commodity.forecast schema exists")
else:
    print("❌ commodity.forecast schema NOT FOUND")
    cursor.close()
    connection.close()
    exit(1)

print()

# Check forecast tables
print("Checking forecast tables:")
print("-"*80)

expected_tables = ['point_forecasts', 'distributions', 'forecast_actuals', 'forecast_metadata']

for table in expected_tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM commodity.forecast.{table}")
        count = cursor.fetchone()[0]
        print(f"  ✅ {table:<25} {count:>15,} rows")
    except Exception as e:
        print(f"  ❌ {table:<25} Error: {e}")

print()

# Check table schemas
print("Verifying table schemas:")
print("-"*80)

# Point forecasts
try:
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_catalog = 'commodity'
        AND table_schema = 'forecast'
        AND table_name = 'point_forecasts'
        ORDER BY ordinal_position
    """)
    cols = cursor.fetchall()
    print("\n  point_forecasts columns:")
    for col in cols:
        print(f"    - {col[0]}: {col[1]}")
except Exception as e:
    print(f"  ❌ Error checking point_forecasts schema: {e}")

# Distributions
try:
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_catalog = 'commodity'
        AND table_schema = 'forecast'
        AND table_name = 'distributions'
        ORDER BY ordinal_position
    """)
    cols = cursor.fetchall()
    print("\n  distributions columns:")
    for col in cols:
        print(f"    - {col[0]}: {col[1]}")
except Exception as e:
    print(f"  ❌ Error checking distributions schema: {e}")

print()

# Check for recent forecasts
print("Checking for recent forecasts:")
print("-"*80)

try:
    cursor.execute("""
        SELECT
            model_name,
            commodity,
            training_end,
            COUNT(*) as forecast_count,
            MIN(forecast_date) as min_date,
            MAX(forecast_date) as max_date
        FROM commodity.forecast.distributions
        GROUP BY model_name, commodity, training_end
        ORDER BY training_end DESC
        LIMIT 10
    """)

    forecasts = cursor.fetchall()
    if forecasts:
        print(f"\n  Most recent {len(forecasts)} forecast runs:")
        for f in forecasts:
            print(f"    {f[0]:<20} {f[1]:<10} trained through {f[2]} -> {f[3]:,} paths ({f[4]} to {f[5]})")
    else:
        print("  ℹ️  No forecasts found in distributions table")

except Exception as e:
    print(f"  ❌ Error querying forecasts: {e}")

print()

# Check metadata
try:
    cursor.execute("""
        SELECT
            model_name,
            commodity,
            training_end,
            created_at,
            parameters
        FROM commodity.forecast.forecast_metadata
        ORDER BY created_at DESC
        LIMIT 5
    """)

    metadata = cursor.fetchall()
    if metadata:
        print(f"Most recent forecast metadata ({len(metadata)} records):")
        for m in metadata:
            print(f"  {m[0]:<20} {m[1]:<10} {m[2]} created {m[3]}")
    else:
        print("ℹ️  No forecast metadata found")

except Exception as e:
    print(f"❌ Error querying metadata: {e}")

print()
print("="*80)
print("✅ FORECAST SCHEMA VALIDATION COMPLETE")
print("="*80)

cursor.close()
connection.close()
