"""
Test unified_data rebuild with new bronze table names
"""
from databricks import sql
import os

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
print("PIPELINE TEST - UNIFIED_DATA REBUILD")
print("="*80)
print()

# Get row count before rebuild
print("Current unified_data row count:")
cursor.execute("SELECT COUNT(*) FROM commodity.silver.unified_data")
before_count = cursor.fetchone()[0]
print(f"  {before_count:,} rows")
print()

# Read and execute unified_data creation script
print("Rebuilding unified_data...")
print("(This may take a few minutes)")
print()

with open('research_agent/sql/create_unified_data.sql', 'r') as f:
    sql_script = f.read()

try:
    cursor.execute(sql_script)
    print("✅ Unified_data rebuild successful!")
except Exception as e:
    print(f"❌ Error: {e}")
    cursor.close()
    connection.close()
    exit(1)

# Verify row count after rebuild
print()
print("Verifying new unified_data:")
cursor.execute("SELECT COUNT(*) FROM commodity.silver.unified_data")
after_count = cursor.fetchone()[0]
print(f"  {after_count:,} rows")

# Check for nulls in critical columns
cursor.execute("""
    SELECT
        COUNT(*) as total_rows,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) as null_temp,
        COUNT(DISTINCT commodity) as commodities,
        COUNT(DISTINCT region) as regions,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
    FROM commodity.silver.unified_data
""")

row = cursor.fetchone()
print()
print("Data Quality Checks:")
print(f"  Total rows: {row[0]:,}")
print(f"  Null close prices: {row[1]:,}")
print(f"  Null temperatures: {row[2]:,}")
print(f"  Commodities: {row[3]}")
print(f"  Regions: {row[4]}")
print(f"  Date range: {row[5]} to {row[6]}")

print()
print("="*80)

# Comparison
if after_count == before_count:
    print("✅ Row count matches - data integrity preserved!")
elif abs(after_count - before_count) / before_count < 0.01:
    print(f"⚠️  Row count differs slightly ({abs(after_count - before_count):,} rows)")
else:
    print(f"❌ Row count differs significantly ({abs(after_count - before_count):,} rows)")

cursor.close()
connection.close()
