#!/usr/bin/env python3
"""
Query Databricks to see actual data types.
"""
import os
from databricks import sql

# Databricks connection
host = "https://dbc-5e4780f4-fcec.cloud.databricks.com"
http_path = "/sql/1.0/warehouses/d88ad009595327fd"
token = "***REMOVED***"

print("Querying Databricks for gdelt_wide schema...\n")

with sql.connect(
    server_hostname=host.replace('https://', ''),
    http_path=http_path,
    access_token=token
) as connection:

    # Try to query the table
    try:
        cursor = connection.cursor()

        # First, check if table exists and get schema
        cursor.execute("DESCRIBE commodity.silver.gdelt_wide")
        schema = cursor.fetchall()

        print("Current Databricks Schema:")
        print("="*70)
        for row in schema[:15]:  # First 15 columns
            print(f"  {row[0]:45s} {row[1]}")

        print("\n" + "="*70)
        print("\nNow trying to query actual data...")

        # Try to query data
        cursor.execute("""
            SELECT group_ALL_count, group_ALL_tone_avg
            FROM commodity.silver.gdelt_wide
            WHERE article_date = '2022-06-08'
            LIMIT 1
        """)

        result = cursor.fetchone()
        print(f"✓ Query succeeded!")
        print(f"  group_ALL_count: {result[0]} (type: {type(result[0]).__name__})")
        print(f"  group_ALL_tone_avg: {result[1]} (type: {type(result[1]).__name__})")

    except Exception as e:
        print(f"✗ Query failed with error:")
        print(f"  {str(e)}")
        print("\nThis might be the type mismatch error you're seeing.")
