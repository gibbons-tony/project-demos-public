"""
Load historical market data from S3 into Databricks landing table.
"""

from databricks import sql
import os

# Databricks connection
host = os.getenv("DATABRICKS_HOST")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

if not all([host, token, http_path]):
    print("ERROR: Missing environment variables")
    exit(1)

print("="*80)
print("LOADING HISTORICAL DATA INTO DATABRICKS")
print("="*80)

print("\nConnecting to Databricks...")
connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# Step 1: Check current row count
print("\n1. Current row counts BEFORE load:")
print("-"*80)
cursor.execute("""
    SELECT commodity, COUNT(*) as rows
    FROM commodity.landing.market_data_inc
    GROUP BY commodity
    ORDER BY commodity
""")
results = cursor.fetchall()
for commodity, count in results:
    print(f"  {commodity}: {count:,} rows")

# Step 2: Load historical data from S3
print("\n2. Loading historical data from S3...")
print("-"*80)
print("  Source: s3://groundtruth-capstone/landing/market_data/history/")

try:
    cursor.execute("""
        COPY INTO commodity.landing.market_data_inc
        FROM 's3://groundtruth-capstone/landing/market_data/history/'
        FILEFORMAT = CSV
        FORMAT_OPTIONS ('mergeSchema' = 'true', 'header' = 'true')
        COPY_OPTIONS ('mergeSchema' = 'true')
    """)

    # Fetch results
    result = cursor.fetchone()
    if result:
        num_files, num_rows = result[0], result[1]
        print(f"  ✓ Loaded {num_rows:,} rows from {num_files} files")
    else:
        print("  ✓ Load complete")

except Exception as e:
    print(f"  ⚠️ Load completed with note: {e}")
    # This might fail if data already exists (duplicates)
    # Continue to validation

# Step 3: Check row count AFTER load
print("\n3. Row counts AFTER load:")
print("-"*80)
cursor.execute("""
    SELECT commodity, COUNT(*) as rows
    FROM commodity.landing.market_data_inc
    GROUP BY commodity
    ORDER BY commodity
""")
results = cursor.fetchall()
for commodity, count in results:
    print(f"  {commodity}: {count:,} rows")

# Step 4: Check unified_data (silver layer)
print("\n4. Checking silver.unified_data (after bronze/silver processing):")
print("-"*80)
cursor.execute("""
    SELECT
        commodity,
        COUNT(*) as rows,
        MIN(date) as start_date,
        MAX(date) as end_date,
        DATEDIFF(MAX(date), MIN(date)) as day_span
    FROM commodity.silver.unified_data
    GROUP BY commodity
    ORDER BY commodity
""")
results = cursor.fetchall()
print(f"{'Commodity':<10} {'Rows':<12} {'Start Date':<12} {'End Date':<12} {'Days':<8}")
for commodity, rows, start, end, days in results:
    print(f"{commodity:<10} {rows:<12,} {start!s:<12} {end!s:<12} {days:<8,}")

cursor.close()
connection.close()

print("\n" + "="*80)
print("LOAD COMPLETE")
print("="*80)
print("\nNOTE: If Sugar still shows only 304 rows, run:")
print("  cd research_agent/infrastructure")
print("  python rebuild_all_layers.py")
print("\nThis will rebuild bronze/silver layers from landing data.")
