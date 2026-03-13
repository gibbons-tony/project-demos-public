#!/usr/bin/env python3
"""
Check status of forecast tables before migration using SQL API
"""
import os
import requests
import time
from dotenv import load_dotenv

# Load environment
env_path = "/Users/connorwatson/Documents/Data Science/DS210-capstone/ucberkeley-capstone/research_agent/infrastructure/.env"
load_dotenv(env_path)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
WAREHOUSE_ID = os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]

print(f"Host: {DATABRICKS_HOST}")
print(f"Warehouse ID: {WAREHOUSE_ID}")

def execute_sql(sql_query, description=None):
    """Execute SQL via Databricks SQL API"""
    url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "statement": sql_query,
        "warehouse_id": WAREHOUSE_ID,
        "wait_timeout": "120s"
    }

    if description:
        print(f"\n{description}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        result = response.json()
        status = result.get('status', {}).get('state')

        if status == 'SUCCEEDED':
            return True, result
        elif status in ['PENDING', 'RUNNING']:
            # Poll for completion
            statement_id = result.get('statement_id')
            for i in range(60):
                time.sleep(2)
                status_url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/{statement_id}"
                status_response = requests.get(status_url, headers=headers)

                if status_response.status_code == 200:
                    status_result = status_response.json()
                    current_status = status_result.get('status', {}).get('state')

                    if current_status == 'SUCCEEDED':
                        return True, status_result
                    elif current_status == 'FAILED':
                        error = status_result.get('status', {}).get('error', {})
                        print(f"✗ FAILED: {error.get('message', 'Unknown error')}")
                        return False, status_result

            print("⚠ Timed out")
            return False, result
    else:
        print(f"✗ HTTP Error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return False, response.text

print("="*80)
print("PHASE 0: FORECAST TABLE ASSESSMENT")
print("="*80)

# 1. Check forecast tables
success, result = execute_sql("SHOW TABLES IN commodity.forecast", "1. Checking forecast tables...")
if success and 'result' in result:
    rows = result.get('result', {}).get('data_array', [])
    if rows:
        print(f"\n✅ Found {len(rows)} forecast tables:")
        for row in rows:
            print(f"   - {row[1]}")

        # Check row counts
        print("\n2. Checking row counts...")
        for row in rows:
            table_name = row[1]
            success2, result2 = execute_sql(f"SELECT COUNT(*) as cnt FROM commodity.forecast.{table_name}", None)
            if success2 and 'result' in result2:
                count = result2.get('result', {}).get('data_array', [[0]])[0][0]
                print(f"   {table_name}: {int(count):,} rows")
    else:
        print("\n⚠️  No forecast tables found")

# 3. Check weather tables
success, result = execute_sql("SHOW TABLES IN commodity.bronze LIKE 'weather*'", "\n3. Checking weather tables...")
if success and 'result' in result:
    rows = result.get('result', {}).get('data_array', [])
    for row in rows:
        table_name = row[1]
        success2, result2 = execute_sql(f"SELECT COUNT(*) as cnt FROM commodity.bronze.{table_name}", None)
        if success2 and 'result' in result2:
            count = result2.get('result', {}).get('data_array', [[0]])[0][0]
            print(f"   bronze.{table_name}: {int(count):,} rows")

# 4. Check weather_v2 data quality
sql = """
    SELECT
        MIN(date) as start_date,
        MAX(date) as end_date,
        COUNT(DISTINCT date) as total_days,
        COUNT(DISTINCT region) as total_regions,
        COUNT(*) as total_rows
    FROM commodity.bronze.weather_v2
"""
success, result = execute_sql(sql, "\n4. Validating weather_v2 data quality...")
if success and 'result' in result:
    row = result.get('result', {}).get('data_array', [[]])[0]
    print(f"   Start date: {row[0]}")
    print(f"   End date: {row[1]}")
    print(f"   Total days: {int(row[2]):,}")
    print(f"   Total regions: {int(row[3])}")
    print(f"   Total rows: {int(row[4]):,}")

# 5. Check Minas Gerais coordinates
sql = """
    SELECT region, latitude, longitude
    FROM commodity.bronze.weather_v2
    WHERE region = 'Minas_Gerais_Brazil'
    LIMIT 1
"""
success, result = execute_sql(sql, "\n5. Validating coordinates (Minas Gerais sample)...")
if success and 'result' in result:
    row = result.get('result', {}).get('data_array', [[]])[0]
    print(f"   Region: {row[0]}")
    print(f"   Latitude: {row[1]}")
    print(f"   Longitude: {row[2]}")

    # Check if v2 (correct) or v1 (wrong)
    if abs(float(row[1]) - (-20.3155)) < 0.01:
        print(f"   ✅ CORRECT v2 coordinates!")
    elif abs(float(row[1]) - (-18.5122)) < 0.01:
        print(f"   ❌ WRONG v1 coordinates detected!")
    else:
        print(f"   ⚠️  Unknown coordinates")

print("\n" + "="*80)
print("ASSESSMENT COMPLETE")
print("="*80)
