"""
Check what's actually in the landing table for Sugar
"""

from databricks import sql
import os

# Databricks connection
host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("Connecting to Databricks...")
connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

print("\n" + "="*80)
print("LANDING TABLE INVESTIGATION")
print("="*80)

# Check row counts by commodity
print("\n1. Landing table row counts:")
cursor.execute("""
    SELECT commodity, COUNT(*) as rows, MIN(date), MAX(date)
    FROM commodity.landing.market_data_inc
    GROUP BY commodity
    ORDER BY commodity
""")
for row in cursor.fetchall():
    commodity, count, min_date, max_date = row
    print(f"  {commodity}: {count:,} rows ({min_date} to {max_date})")

# Check if we can read directly from S3
print("\n2. Reading directly from S3 history folder:")
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as rows,
        MIN(date) as start,
        MAX(date) as end
    FROM read_files(
        's3://groundtruth-capstone/landing/market_data/history/*.csv',
        format => 'csv',
        header => true
    )
    GROUP BY commodity
    ORDER BY commodity
""")
results = cursor.fetchall()
for row in results:
    commodity, count, start, end = row
    print(f"  {commodity}: {count:,} rows ({start} to {end})")

# Check both paths together
print("\n3. Reading from BOTH S3 paths (regular + history):")
cursor.execute("""
    SELECT
        'regular' as source,
        commodity,
        COUNT(*) as rows
    FROM read_files(
        's3://groundtruth-capstone/landing/market_data/*.csv',
        format => 'csv',
        header => true
    )
    GROUP BY commodity
    UNION ALL
    SELECT
        'history' as source,
        commodity,
        COUNT(*) as rows
    FROM read_files(
        's3://groundtruth-capstone/landing/market_data/history/*.csv',
        format => 'csv',
        header => true
    )
    GROUP BY commodity
    ORDER BY source, commodity
""")
results = cursor.fetchall()
for row in results:
    source, commodity, count = row
    print(f"  {source:10} - {commodity}: {count:,} rows")

cursor.close()
connection.close()

print("\n" + "="*80)
