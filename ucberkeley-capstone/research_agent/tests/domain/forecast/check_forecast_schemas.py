"""
Check actual schemas of forecast tables
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
print("FORECAST TABLE SCHEMAS")
print("="*80)

tables = ['point_forecasts', 'distributions', 'forecast_actuals', 'forecast_metadata']

for table in tables:
    print(f"\n{table.upper()}:")
    print("-"*80)
    try:
        cursor.execute(f"DESCRIBE commodity.forecast.{table}")
        cols = cursor.fetchall()
        for col in cols:
            print(f"  {col[0]:<30} {col[1]}")

        # Get sample data
        cursor.execute(f"SELECT * FROM commodity.forecast.{table} LIMIT 3")
        rows = cursor.fetchall()
        if rows:
            print(f"\nSample data ({len(rows)} rows):")
            for i, row in enumerate(rows, 1):
                print(f"  Row {i}: {row[:5]}...")  # First 5 columns
        else:
            print("\nNo data in table")

    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*80)

cursor.close()
connection.close()
