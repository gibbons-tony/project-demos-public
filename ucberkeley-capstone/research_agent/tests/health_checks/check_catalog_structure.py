"""
Check current Databricks catalog structure
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

print("=" * 80)
print("DATABRICKS CATALOG STRUCTURE")
print("=" * 80)
print()

# Check bronze schema
print("BRONZE SCHEMA:")
print("-" * 80)
cursor.execute("SHOW TABLES IN commodity.bronze")
bronze_tables = cursor.fetchall()
for table in bronze_tables:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name:<40} {count:>15,} rows")

print()

# Check silver schema
print("SILVER SCHEMA:")
print("-" * 80)
cursor.execute("SHOW TABLES IN commodity.silver")
silver_tables = cursor.fetchall()
for table in silver_tables:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) FROM commodity.silver.{table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name:<40} {count:>15,} rows")

print()

# Check landing schema
print("LANDING SCHEMA:")
print("-" * 80)
cursor.execute("SHOW TABLES IN commodity.landing")
landing_tables = cursor.fetchall()
for table in landing_tables:
    table_name = table[1]
    cursor.execute(f"SELECT COUNT(*) FROM commodity.landing.{table_name}")
    count = cursor.fetchone()[0]
    print(f"  {table_name:<40} {count:>15,} rows")

print()

# Check forecasts schema (if exists)
try:
    print("FORECAST SCHEMA:")
    print("-" * 80)
    cursor.execute("SHOW TABLES IN commodity.forecast")
    forecasts_tables = cursor.fetchall()
    if forecasts_tables:
        for table in forecasts_tables:
            table_name = table[1]
            cursor.execute(f"SELECT COUNT(*) FROM commodity.forecast.{table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name:<40} {count:>15,} rows")
    else:
        print("  (no tables)")
except Exception as e:
    print(f"  Schema does not exist or error: {e}")

print()
print("=" * 80)

cursor.close()
connection.close()
