#!/usr/bin/env python3
"""
Continuous Data Health Checks (SQL Unit Tests)

Fast, lightweight checks to run daily:
- Row counts haven't dropped
- No nulls in critical fields
- Date freshness (data is recent)
- Schema stability

Exit code 0 = all tests pass
Exit code 1 = one or more tests failed (triggers alert)

Usage:
    export DATABRICKS_TOKEN=<your-token>
    python health_checks.py

Or run from Databricks workflow with email alerts on failure.
"""
import requests
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

# Databricks configuration
DATABRICKS_HOST = "https://dbc-fd7b00f3-7a6d.cloud.databricks.com"
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
WAREHOUSE_ID = "3cede8561503a13c"

if not DATABRICKS_TOKEN:
    config_path = Path(__file__).parent.parent.parent.parent.parent / "infra" / ".databrickscfg"
    if config_path.exists():
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("token"):
                    DATABRICKS_TOKEN = line.split("=")[1].strip()
                    break

if not DATABRICKS_TOKEN:
    print("ERROR: DATABRICKS_TOKEN not found", file=sys.stderr)
    sys.exit(1)

# Test results tracking
tests_passed = 0
tests_failed = 0
failures = []


def execute_sql(sql_query, wait_timeout=60):
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

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        result = response.json()
        status = result.get('status', {}).get('state')

        if status == 'SUCCEEDED':
            return True, result
        else:
            return False, result
    else:
        return False, None


def run_test(test_name, sql_query, assertion_func):
    """Run a single test"""
    global tests_passed, tests_failed, failures

    success, result = execute_sql(sql_query)

    if not success:
        tests_failed += 1
        failures.append(f"❌ {test_name}: Query execution failed")
        print(f"❌ {test_name}: Query execution failed")
        return False

    if 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        try:
            if assertion_func(rows):
                tests_passed += 1
                print(f"✓ {test_name}")
                return True
            else:
                tests_failed += 1
                failures.append(f"❌ {test_name}: Assertion failed")
                print(f"❌ {test_name}: Assertion failed")
                return False
        except Exception as e:
            tests_failed += 1
            failures.append(f"❌ {test_name}: {str(e)}")
            print(f"❌ {test_name}: {str(e)}")
            return False
    else:
        tests_failed += 1
        failures.append(f"❌ {test_name}: No result data")
        print(f"❌ {test_name}: No result data")
        return False


def main():
    """Run all health checks"""
    print("="*80)
    print(" " * 25 + "DATA HEALTH CHECKS")
    print("="*80)
    print(f"Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # TEST 1: Unified data has minimum expected rows
    run_test(
        "Test 1: Unified data row count (Coffee >= 70k rows)",
        """
        SELECT COUNT(*) as row_count
        FROM commodity.silver.unified_data
        WHERE commodity = 'Coffee'
        """,
        lambda rows: int(rows[0][0]) >= 70000
    )

    # TEST 2: No nulls in critical OHLC fields
    run_test(
        "Test 2: No nulls in OHLC fields",
        """
        SELECT
            SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) +
            SUM(CASE WHEN high IS NULL THEN 1 ELSE 0 END) +
            SUM(CASE WHEN low IS NULL THEN 1 ELSE 0 END) +
            SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as total_nulls
        FROM commodity.silver.unified_data
        """,
        lambda rows: int(rows[0][0]) == 0
    )

    # TEST 3: Data is fresh (latest date within 5 days)
    run_test(
        "Test 3: Data freshness (<5 days old)",
        """
        SELECT MAX(date) as latest_date
        FROM commodity.silver.unified_data
        """,
        lambda rows: (datetime.now().date() - datetime.strptime(rows[0][0], '%Y-%m-%d').date()).days <= 5
    )

    # TEST 4: Regional coverage (Coffee has >= 15 regions)
    run_test(
        "Test 4: Regional coverage (Coffee >= 15 regions)",
        """
        SELECT COUNT(DISTINCT region) as num_regions
        FROM commodity.silver.unified_data
        WHERE commodity = 'Coffee'
        """,
        lambda rows: int(rows[0][0]) >= 15
    )

    # TEST 5: Weather nulls are reasonable (<2%)
    run_test(
        "Test 5: Weather null rate (<2%)",
        """
        SELECT
            COUNT(*) as total_rows,
            SUM(CASE WHEN temp_max_c IS NULL THEN 1 ELSE 0 END) as null_temp
        FROM commodity.silver.unified_data
        """,
        lambda rows: (float(rows[0][1]) / float(rows[0][0])) < 0.02
    )

    # TEST 6: VIX data present
    run_test(
        "Test 6: VIX data completeness (>95% populated)",
        """
        SELECT
            COUNT(*) as total_rows,
            SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as null_vix
        FROM commodity.silver.unified_data
        """,
        lambda rows: (float(rows[0][1]) / float(rows[0][0])) < 0.05
    )

    # TEST 7: No impossible prices (negative or zero)
    run_test(
        "Test 7: No impossible prices",
        """
        SELECT COUNT(*) as bad_prices
        FROM commodity.bronze.market_data
        WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
          AND date >= CURRENT_DATE - INTERVAL 30 DAYS
        """,
        lambda rows: int(rows[0][0]) == 0
    )

    # TEST 8: No OHLC violations (high < low, etc.)
    run_test(
        "Test 8: No OHLC violations",
        """
        SELECT COUNT(*) as violations
        FROM commodity.bronze.market_data
        WHERE (high < low OR high < open OR high < close OR low > open OR low > close)
          AND date >= CURRENT_DATE - INTERVAL 30 DAYS
        """,
        lambda rows: int(rows[0][0]) == 0
    )

    # TEST 9: Bronze and Silver counts are consistent
    run_test(
        "Test 9: Bronze-Silver consistency (Coffee)",
        """
        WITH bronze_dates AS (
            SELECT COUNT(DISTINCT date) as bronze_count
            FROM commodity.bronze.market_data
            WHERE commodity = 'Coffee' AND date >= '2015-07-07'
        ),
        silver_dates AS (
            SELECT COUNT(DISTINCT date) as silver_count
            FROM commodity.silver.unified_data
            WHERE commodity = 'Coffee'
        )
        SELECT ABS(b.bronze_count - s.silver_count) as date_diff
        FROM bronze_dates b, silver_dates s
        """,
        lambda rows: int(rows[0][0]) < 10  # Allow small differences
    )

    # TEST 10: Schema stability (expected column count)
    run_test(
        "Test 10: Schema stability (45-55 columns)",
        """
        SELECT COUNT(*) as col_count
        FROM information_schema.columns
        WHERE table_catalog = 'commodity'
          AND table_schema = 'silver'
          AND table_name = 'unified_data'
        """,
        lambda rows: 45 <= int(rows[0][0]) <= 55
    )

    # Print summary
    print("\n" + "="*80)
    print(" " * 30 + "SUMMARY")
    print("="*80)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")

    if tests_failed > 0:
        print("\n❌ FAILURES:")
        for failure in failures:
            print(f"  {failure}")
        print("\n⚠️  ACTION REQUIRED: Data pipeline has issues!")
        return False
    else:
        print("\n✓ ALL TESTS PASSED - Data pipeline is healthy")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
