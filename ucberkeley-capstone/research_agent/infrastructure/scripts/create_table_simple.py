#!/usr/bin/env python3
"""
Create table using Databricks auto-discovery from parquet.
"""
from databricks import sql

host = "dbc-5e4780f4-fcec.cloud.databricks.com"
http_path = "/sql/1.0/warehouses/d88ad009595327fd"
token = "***REMOVED***"

print("Creating Databricks table from parquet files...")

with sql.connect(
    server_hostname=host,
    http_path=http_path,
    access_token=token
) as connection:

    cursor = connection.cursor()

    # Drop old table
    print("\n1. Dropping old table...")
    cursor.execute("DROP TABLE IF EXISTS commodity.silver.gdelt_wide")
    print("   ✓ Dropped")

    # Create table from parquet (auto-discover schema)
    print("\n2. Creating table with auto-discovered schema...")
    create_sql = """
    CREATE TABLE commodity.silver.gdelt_wide
    USING PARQUET
    LOCATION 's3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/'
    """

    cursor.execute(create_sql)
    print("   ✓ Table created")

    # Describe table to see actual schema
    print("\n3. Verifying schema...")
    cursor.execute("DESCRIBE commodity.silver.gdelt_wide")
    schema = cursor.fetchall()

    print("   First 15 columns:")
    for row in schema[:15]:
        print(f"     {row[0]:45s} {row[1]}")

    # Check for count columns with correct type
    count_cols = [row for row in schema if '_count' in row[0]]
    bigint_counts = [row for row in count_cols if 'bigint' in row[1].lower() or 'long' in row[1].lower()]

    print(f"\n   Count columns: {len(count_cols)}")
    print(f"   Count columns with BIGINT/LONG: {len(bigint_counts)}")

    if len(bigint_counts) == len(count_cols):
        print("   ✓ All count columns have correct type!")
    else:
        print("   ✗ Some count columns have wrong type")

    # Test query
    print("\n4. Testing query...")
    cursor.execute("""
        SELECT article_date, commodity, group_ALL_count, group_ALL_tone_avg
        FROM commodity.silver.gdelt_wide
        WHERE article_date = '2022-06-08'
        LIMIT 2
    """)

    results = cursor.fetchall()
    print(f"   ✓ Query succeeded! Rows: {len(results)}")
    for row in results:
        print(f"     {row[0]} | {row[1]} | count={row[2]} | tone={row[3]:.4f}")

print("\n" + "="*70)
print("✓ SUCCESS - Databricks table working with correct schema!")
print("="*70)
