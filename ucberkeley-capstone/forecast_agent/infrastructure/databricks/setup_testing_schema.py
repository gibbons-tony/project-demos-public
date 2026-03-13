"""
Set up commodity.forecast_testing schema for ml_lib validation.

This creates a parallel testing schema to validate the new ml_lib pipeline
before promoting models to production (commodity.forecast).
"""
import os
from databricks import sql
from dotenv import load_dotenv

# Load credentials
load_dotenv('../infra/.env')

token = os.environ['DATABRICKS_TOKEN']
host = os.environ['DATABRICKS_HOST'].replace('https://', '')
http_path = os.environ['DATABRICKS_HTTP_PATH']

print("="*80)
print("Setting up commodity.forecast_testing schema")
print("="*80)

# Connect to Databricks
connection = sql.connect(
    server_hostname=host,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# Read SQL file
sql_file = "infrastructure/databricks/sql/create_forecast_testing_schema.sql"
print(f"\nReading {sql_file}...")

with open(sql_file, 'r') as f:
    sql_content = f.read()

# Split into individual statements (simple split on semicolon)
statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]

print(f"Found {len(statements)} SQL statements to execute\n")

# Execute each statement
for i, statement in enumerate(statements, 1):
    # Skip comments and empty statements
    if statement.startswith('--') or len(statement) < 10:
        continue

    # Get first line for display
    first_line = statement.split('\n')[0][:60]

    try:
        cursor.execute(statement)
        print(f"✓ Statement {i}/{len(statements)}: {first_line}...")
    except Exception as e:
        print(f"❌ Statement {i}/{len(statements)} failed: {first_line}")
        print(f"   Error: {e}")
        continue

print("\n" + "="*80)
print("Schema setup complete!")
print("="*80)

# Verify tables were created
print("\nVerifying tables...")
cursor.execute("SHOW TABLES IN commodity.forecast_testing")
tables = cursor.fetchall()

print(f"\nTables in commodity.forecast_testing:")
for table in tables:
    print(f"  - {table[1]}")

cursor.close()
connection.close()

print("\n✅ forecast_testing schema is ready for use!")
print("\nNext steps:")
print("1. Run ml_lib pipeline tests")
print("2. Save results to commodity.forecast_testing tables")
print("3. Compare metrics vs production")
print("4. Promote successful models to commodity.forecast")
