#!/usr/bin/env python3
"""
Rebuild All Data Layers (Landing → Bronze → Silver)

This script rebuilds all Databricks tables from S3 in the correct order:
1. Landing layer (from S3 CSV files)
2. Bronze views (deduplicated)
3. Silver unified_data (joined and forward-filled)

Run this after:
- Major S3 data backfills
- Schema changes
- Data quality issues

Usage:
    export DATABRICKS_TOKEN=<your-token>
    python rebuild_all_layers.py
"""
import requests
import time
import os
import sys
from pathlib import Path

# Databricks configuration
DATABRICKS_HOST = "https://dbc-fd7b00f3-7a6d.cloud.databricks.com"
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
WAREHOUSE_ID = "3cede8561503a13c"

# SQL file paths
SCRIPT_DIR = Path(__file__).parent
LANDING_SQL = SCRIPT_DIR / "databricks" / "01_create_landing_tables.sql"
BRONZE_SQL = SCRIPT_DIR / "databricks" / "02_create_bronze_views.sql"
UNIFIED_SQL = SCRIPT_DIR.parent / "sql" / "create_unified_data.sql"

if not DATABRICKS_TOKEN:
    config_path = SCRIPT_DIR.parent.parent / "infra" / ".databrickscfg"
    if config_path.exists():
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("token"):
                    DATABRICKS_TOKEN = line.split("=")[1].strip()
                    break

if not DATABRICKS_TOKEN:
    print("ERROR: DATABRICKS_TOKEN not found")
    sys.exit(1)


def split_sql_statements(sql_content):
    """
    Split SQL content into individual statements.
    Handles multi-line statements and comments.
    """
    # Remove single-line comments
    lines = []
    for line in sql_content.split('\n'):
        # Remove comments but preserve quoted strings
        if '--' in line:
            # Simple approach: remove everything after --
            line = line.split('--')[0]
        lines.append(line)

    # Join back and split on semicolons
    cleaned_sql = '\n'.join(lines)
    statements = []

    current_statement = []
    for line in cleaned_sql.split('\n'):
        line = line.strip()
        if not line:
            continue

        current_statement.append(line)

        # If line ends with semicolon, statement is complete
        if line.endswith(';'):
            stmt = '\n'.join(current_statement)
            stmt = stmt.rstrip(';').strip()
            if stmt:
                statements.append(stmt)
            current_statement = []

    # Add any remaining statement
    if current_statement:
        stmt = '\n'.join(current_statement).strip()
        if stmt:
            statements.append(stmt)

    return statements


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
        "wait_timeout": f"{min(wait_timeout, 50)}s"  # Max 50s per Databricks API
    }

    if description:
        print(f"\n{'='*80}")
        print(f"  {description}")
        print(f"{'='*80}")

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
            print(f"Polling for completion (up to 20 minutes)...")

            max_polls = 240  # 20 minutes (5s * 240)
            for i in range(max_polls):
                time.sleep(5)
                status_url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/{statement_id}"
                status_response = requests.get(status_url, headers=headers)

                if status_response.status_code == 200:
                    status_result = status_response.json()
                    current_status = status_result.get('status', {}).get('state')

                    if i % 6 == 0:
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
            print(f"✗ FAILED: {error.get('message', 'Unknown error')}")
            return False, result
    else:
        print(f"✗ HTTP Error: {response.status_code}")
        print(f"  {response.text}")
        return False, None


def rebuild_landing():
    """Step 1: Rebuild landing tables from S3"""
    print("\n" + "="*80)
    print("STEP 1: REBUILD LANDING TABLES FROM S3")
    print("="*80)

    if not LANDING_SQL.exists():
        print(f"✗ SQL file not found: {LANDING_SQL}")
        return False

    with open(LANDING_SQL, 'r') as f:
        sql_content = f.read()

    # Split SQL into individual statements
    statements = split_sql_statements(sql_content)
    print(f"Found {len(statements)} SQL statements to execute\n")

    # Execute each statement individually
    failed_statements = []
    for i, stmt in enumerate(statements, 1):
        # Get a short description of the statement
        first_line = stmt.split('\n')[0][:60]
        description = f"Statement {i}/{len(statements)}: {first_line}..."

        success, result = execute_sql(stmt, wait_timeout=50, description=description)

        if not success:
            # Check if this is a critical statement (CREATE/DROP/ALTER) or informational (SHOW/SELECT)
            is_critical = any(stmt.strip().upper().startswith(cmd) for cmd in ['CREATE', 'DROP', 'ALTER', 'INSERT', 'UPDATE', 'DELETE'])
            if is_critical:
                failed_statements.append((i, first_line))
                print(f"✗ Statement {i} failed, continuing with remaining statements...")
            else:
                print(f"⚠ Statement {i} failed (informational only), continuing...")

    # Summary
    if not failed_statements:
        print("\n✓ Landing tables rebuilt successfully")
        return True
    else:
        print(f"\n✗ Failed to rebuild landing tables ({len(failed_statements)} critical failures)")
        for stmt_num, desc in failed_statements:
            print(f"  - Statement {stmt_num}: {desc}")
        return False


def rebuild_bronze():
    """Step 2: Rebuild bronze views"""
    print("\n" + "="*80)
    print("STEP 2: REBUILD BRONZE VIEWS")
    print("="*80)

    if not BRONZE_SQL.exists():
        print(f"✗ SQL file not found: {BRONZE_SQL}")
        return False

    with open(BRONZE_SQL, 'r') as f:
        sql_content = f.read()

    # Split SQL into individual statements
    statements = split_sql_statements(sql_content)
    print(f"Found {len(statements)} SQL statements to execute\n")

    # Execute each statement individually
    failed_statements = []
    for i, stmt in enumerate(statements, 1):
        # Get a short description of the statement
        first_line = stmt.split('\n')[0][:60]
        description = f"Statement {i}/{len(statements)}: {first_line}..."

        success, result = execute_sql(stmt, wait_timeout=50, description=description)

        if not success:
            # Check if this is a critical statement (CREATE/DROP/ALTER) or informational (SHOW/SELECT)
            is_critical = any(stmt.strip().upper().startswith(cmd) for cmd in ['CREATE', 'DROP', 'ALTER', 'INSERT', 'UPDATE', 'DELETE'])
            if is_critical:
                failed_statements.append((i, first_line))
                print(f"✗ Statement {i} failed, continuing with remaining statements...")
            else:
                print(f"⚠ Statement {i} failed (informational only), continuing...")

    # Summary
    if not failed_statements:
        print("\n✓ Bronze views rebuilt successfully")
        return True
    else:
        print(f"\n✗ Failed to rebuild bronze views ({len(failed_statements)} critical failures)")
        for stmt_num, desc in failed_statements:
            print(f"  - Statement {stmt_num}: {desc}")
        return False


def rebuild_silver():
    """Step 3: Rebuild silver unified_data"""
    print("\n" + "="*80)
    print("STEP 3: REBUILD SILVER UNIFIED_DATA")
    print("="*80)

    if not UNIFIED_SQL.exists():
        print(f"✗ SQL file not found: {UNIFIED_SQL}")
        return False

    with open(UNIFIED_SQL, 'r') as f:
        sql_content = f.read()

    # Remove comments
    lines = []
    for line in sql_content.split('\n'):
        if '--' in line:
            line = line.split('--')[0]
        lines.append(line)
    sql = '\n'.join(lines).strip()

    print("Executing unified_data table creation...")
    print("This may take several minutes to process 10 years of data...")

    success, result = execute_sql(sql, wait_timeout=50, description="Creating silver.unified_data")

    if success:
        print("\n✓ Silver unified_data rebuilt successfully")
        return True
    else:
        print("\n✗ Failed to rebuild silver unified_data")
        return False


def validate_rebuild():
    """Validate the rebuilt tables"""
    print("\n" + "="*80)
    print("VALIDATION: Checking rebuilt tables")
    print("="*80)

    # Check Sugar data specifically
    sql = """
    SELECT
        commodity,
        COUNT(*) as total_rows,
        COUNT(DISTINCT date) as unique_dates,
        COUNT(DISTINCT region) as num_regions,
        MIN(date) as earliest,
        MAX(date) as latest
    FROM commodity.silver.unified_data
    GROUP BY commodity
    ORDER BY commodity
    """

    success, result = execute_sql(sql, description="Validating unified_data")

    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        print("\nUnified Data Summary:")
        print(f"{'Commodity':<10} {'Rows':<12} {'Dates':<10} {'Regions':<10} {'Date Range'}")
        print("-" * 80)

        for row in rows:
            comm, total, dates, regions, earliest, latest = row
            date_range = f"{earliest} to {latest}"
            print(f"{comm:<10} {int(total):<12,} {int(dates):<10,} {int(regions):<10} {date_range}")

            # Validate expectations
            if comm == 'Coffee' and int(dates) < 3000:
                print(f"  ⚠️  WARNING: Coffee has fewer dates than expected")
            elif comm == 'Sugar' and int(dates) < 2000:
                print(f"  ❌ ERROR: Sugar still missing historical data (only {int(dates):,} dates)")
            elif comm == 'Sugar' and int(dates) >= 2000:
                print(f"  ✅ SUCCESS: Sugar now has complete historical data!")

    return True


def main():
    """Main rebuild pipeline"""
    print("="*80)
    print(" " * 25 + "REBUILD ALL DATA LAYERS")
    print("="*80)
    print(f"Databricks: {DATABRICKS_HOST}")
    print("Rebuilding: Landing → Bronze → Silver")
    print("="*80)

    try:
        # Step 1: Landing
        if not rebuild_landing():
            print("\n✗ Rebuild failed at Landing layer")
            return False

        # Step 2: Bronze
        if not rebuild_bronze():
            print("\n✗ Rebuild failed at Bronze layer")
            return False

        # Step 3: Silver
        if not rebuild_silver():
            print("\n✗ Rebuild failed at Silver layer")
            return False

        # Validate
        validate_rebuild()

        print("\n" + "="*80)
        print("✓ ALL LAYERS REBUILT SUCCESSFULLY")
        print("="*80)
        print("\nNext steps:")
        print("1. Review validation output above")
        print("2. Run health checks: python validation/continuous/health_checks.py")
        print("3. If Sugar data is complete, proceed with forecast agent testing")

        return True

    except Exception as e:
        print(f"\n✗ Error during rebuild: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
