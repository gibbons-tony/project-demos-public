"""
Test the pipeline end-to-end after catalog cleanup
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
print("PIPELINE TEST - BRONZE LAYER REBUILD")
print("="*80)

# Read and execute bronze layer creation script
with open('research_agent/infrastructure/databricks/02_create_bronze_views.sql', 'r') as f:
    sql_script = f.read()

# Split by semicolon and execute each statement
statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]

for i, stmt in enumerate(statements, 1):
    # Skip SHOW and SELECT statements for now
    if stmt.upper().startswith('SHOW') or stmt.upper().startswith('SELECT'):
        continue

    print(f"\n[{i}/{len(statements)}] Executing: {stmt[:60]}...")
    try:
        cursor.execute(stmt)
        print("  ✅ Success")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "="*80)
print("VERIFYING BRONZE TABLES")
print("="*80)

bronze_tables = ['market', 'vix', 'macro', 'weather', 'cftc', 'gdelt']

for table in bronze_tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table}")
        count = cursor.fetchone()[0]
        print(f"  ✅ {table:<20} {count:>15,} rows")
    except Exception as e:
        print(f"  ❌ {table:<20} Error: {e}")

print("\n" + "="*80)

cursor.close()
connection.close()

print("✅ Bronze layer test complete!")
