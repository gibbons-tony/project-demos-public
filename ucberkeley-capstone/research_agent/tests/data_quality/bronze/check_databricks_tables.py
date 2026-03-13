"""
Check what tables exist in Databricks
"""

from databricks import sql
import os

# Databricks connection
host = os.getenv("DATABRICKS_HOST")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

print("Connecting to Databricks...")
connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

print("\n" + "="*80)
print("DATABRICKS TABLES INVENTORY")
print("="*80)

# Check catalogs
print("\n1. Available Catalogs:")
cursor.execute("SHOW CATALOGS")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

# Check schemas in commodity catalog
print("\n2. Schemas in 'commodity' catalog:")
try:
    cursor.execute("SHOW SCHEMAS IN commodity")
    for row in cursor.fetchall():
        print(f"  - commodity.{row[0]}")
except Exception as e:
    print(f"  Error: {e}")

# Check tables in silver schema (we know this exists)
print("\n3. Tables in 'commodity.silver':")
try:
    cursor.execute("SHOW TABLES IN commodity.silver")
    for row in cursor.fetchall():
        table_name = row[1]  # Second column is table name
        print(f"  - commodity.silver.{table_name}")
except Exception as e:
    print(f"  Error: {e}")

# Check if landing schema exists
print("\n4. Checking for landing schema:")
try:
    cursor.execute("SHOW TABLES IN commodity.landing")
    tables = cursor.fetchall()
    if tables:
        for row in tables:
            print(f"  - commodity.landing.{row[1]}")
    else:
        print("  (no tables found in commodity.landing)")
except Exception as e:
    print(f"  Landing schema does not exist or error: {e}")

# Check bronze schema
print("\n5. Checking for bronze schema:")
try:
    cursor.execute("SHOW TABLES IN commodity.bronze")
    tables = cursor.fetchall()
    if tables:
        for row in tables:
            print(f"  - commodity.bronze.{row[1]}")
    else:
        print("  (no tables found in commodity.bronze)")
except Exception as e:
    print(f"  Bronze schema does not exist or error: {e}")

cursor.close()
connection.close()

print("\n" + "="*80)
