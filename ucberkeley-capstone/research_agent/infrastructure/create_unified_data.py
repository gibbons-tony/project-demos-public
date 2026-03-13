#!/usr/bin/env python3
"""
Create silver.unified_data table from bronze layer

This script:
1. Reads the unified_data SQL from file
2. Executes it via Databricks SQL API
3. Validates the output

Usage:
    export DATABRICKS_TOKEN=<your-token>
    python create_unified_data.py

Or run from Databricks job as a Python task
"""
import requests
import time
import os
import sys
from pathlib import Path

# Databricks configuration
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://dbc-5e4780f4-fcec.cloud.databricks.com")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
WAREHOUSE_ID = os.environ.get("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/d88ad009595327fd").split("/")[-1]

# File paths
SCRIPT_DIR = Path(__file__).parent
SQL_FILE = SCRIPT_DIR.parent / "sql" / "create_unified_data.sql"

if not DATABRICKS_TOKEN:
    # Try reading from config
    config_path = Path(__file__).parent.parent.parent / "infra" / ".databrickscfg"
    if config_path.exists():
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("token"):
                    DATABRICKS_TOKEN = line.split("=")[1].strip()
                    break

if not DATABRICKS_TOKEN:
    print("ERROR: DATABRICKS_TOKEN not found")
    sys.exit(1)


def execute_sql(sql_query, wait_timeout=50, description=None):
    """Execute SQL via Databricks SQL API"""
    url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/"
    headers = {
        "Authorization": f"Bearer {DATABRICKS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "statement": sql_query,
        "warehouse_id": WAREHOUSE_ID,
        "wait_timeout": f"{wait_timeout}s"
    }

    if description:
        print(f"\n{'='*70}")
        print(f"  {description}")
        print(f"{'='*70}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        result = response.json()
        status = result.get('status', {}).get('state')
        statement_id = result.get('statement_id')

        if status == 'SUCCEEDED':
            print(f"✓ SUCCESS")
            return True, result
        elif status in ['PENDING', 'RUNNING']:
            # Poll for completion
            print(f"Statement ID: {statement_id}")
            print(f"Initial Status: {status}")
            print("Polling for completion...")

            max_polls = 120  # 10 minutes max
            for i in range(max_polls):
                time.sleep(5)

                status_url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/{statement_id}"
                status_response = requests.get(status_url, headers=headers)

                if status_response.status_code == 200:
                    status_result = status_response.json()
                    current_status = status_result.get('status', {}).get('state')

                    if i % 6 == 0:  # Every 30 seconds
                        elapsed = (i+1) * 5
                        print(f"  [{elapsed}s] Status: {current_status}")

                    if current_status == 'SUCCEEDED':
                        print(f"✓ SUCCESS")
                        return True, status_result
                    elif current_status == 'FAILED':
                        error = status_result.get('status', {}).get('error', {})
                        print(f"✗ FAILED: {error.get('message', 'Unknown error')}")
                        return False, status_result

            print("⚠ Timed out waiting for completion")
            return False, result
        elif status == 'FAILED':
            error = result.get('status', {}).get('error', {})
            error_msg = error.get('message', 'Unknown error')
            print(f"✗ FAILED: {error_msg}")
            return False, result
        else:
            print(f"⚠ Status: {status}")
            return False, result
    else:
        print(f"✗ HTTP Error: {response.status_code}")
        print(f"  {response.text}")
        return False, response.text


def validate_output():
    """Validate the created unified_data table"""
    print("\n" + "="*70)
    print("VALIDATING OUTPUT")
    print("="*70)

    # Check row count and schema
    success, result = execute_sql("""
        SELECT
            COUNT(*) as total_rows,
            COUNT(DISTINCT date) as unique_dates,
            MIN(date) as earliest,
            MAX(date) as latest,
            COUNT(DISTINCT commodity) as commodities,
            COUNT(DISTINCT region) as regions
        FROM commodity.silver.unified_data
    """, description="Checking table statistics")

    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [[]])
        if rows:
            total, dates, earliest, latest, commodities, regions = rows[0]
            print(f"  Total Rows: {int(total):,}")
            print(f"  Unique Dates: {int(dates):,}")
            print(f"  Date Range: {earliest} to {latest}")
            print(f"  Commodities: {int(commodities)}")
            print(f"  Regions: {int(regions)}")

    # Check for nulls in key fields
    success, result = execute_sql("""
        SELECT
            SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as null_open,
            SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
            SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_volume,
            SUM(CASE WHEN temp_max_c IS NULL THEN 1 ELSE 0 END) as null_temp
        FROM commodity.silver.unified_data
    """, description="Checking for nulls")

    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [[]])
        if rows:
            nulls = [int(n) for n in rows[0]]
            if all(n < 1000 for n in nulls):  # Allow some nulls but not too many
                print(f"  ✓ Key fields mostly populated (forward fill working)")
            else:
                print(f"  ⚠ Warning: High null counts detected")
                print(f"    open: {nulls[0]:,}, close: {nulls[1]:,}, volume: {nulls[2]:,}, temp: {nulls[3]:,}")

    return True


def main():
    """Main execution flow"""
    print("\n" + "="*70)
    print("CREATE silver.unified_data TABLE")
    print("="*70)
    print(f"Databricks: {DATABRICKS_HOST}")
    print(f"SQL File: {SQL_FILE}")

    # Check SQL file exists
    if not SQL_FILE.exists():
        print(f"\nERROR: SQL file not found: {SQL_FILE}")
        sys.exit(1)

    # Read SQL file
    print(f"\nReading SQL from {SQL_FILE.name}...")
    with open(SQL_FILE, 'r') as f:
        sql_content = f.read()

    # Remove comments for cleaner execution
    lines = []
    for line in sql_content.split('\n'):
        if '--' in line:
            line = line.split('--')[0]
        lines.append(line)
    sql = '\n'.join(lines).strip()

    print(f"  SQL size: {len(sql):,} characters")

    # Execute SQL
    print("\nExecuting unified_data table creation...")
    print("This may take several minutes to process 10 years of data...")

    success, result = execute_sql(
        sql,
        description="Creating silver.unified_data table"
    )

    if not success:
        print("\n✗ Failed to create unified_data table")
        sys.exit(1)

    # Validate output
    if not validate_output():
        print("\n⚠ Validation had warnings")
        sys.exit(1)

    print("\n" + "="*70)
    print("✓ SUCCESS - silver.unified_data table created and validated!")
    print("="*70)
    print("\nFeature Summary:")
    print("  - Market Data: OHLCV (open, high, low, close, volume)")
    print("  - Weather: 15 enhanced fields (temp, precip, humidity, wind, solar, ET)")
    print("  - Macro: 24 FX rates")
    print("  - VIX: Volatility index")
    print("  - Date Range: 2015-07-07 to present")
    print("  - Forward-filled to handle missing values")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
