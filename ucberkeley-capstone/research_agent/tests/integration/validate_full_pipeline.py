"""
Comprehensive Pipeline Validation

Validates:
1. All bronze tables exist and have data
2. No unexpected nulls in critical columns
3. Data freshness (last update within reasonable time)
4. Silver layer completeness
5. Forecast layer readiness
"""

import os
from databricks import sql
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load credentials
# When running from tests/ directory, .env is in parent
import pathlib
env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH]):
    print("ERROR: Missing credentials in .env")
    exit(1)


def run_validation():
    """Run full pipeline validation"""
    print("=" * 80)
    print("FULL PIPELINE VALIDATION")
    print("=" * 80)

    connection = sql.connect(
        server_hostname=DATABRICKS_HOST.replace("https://", ""),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )
    cursor = connection.cursor()

    passed = 0
    failed = 0
    warnings = 0

    # TEST 1: Check all bronze tables exist
    print("\n1. BRONZE LAYER - Table Existence")
    print("-" * 80)
    expected_bronze_tables = ['cftc', 'gdelt', 'macro', 'market', 'vix', 'weather']

    cursor.execute("SHOW TABLES IN commodity.bronze")
    existing_tables = {row.tableName for row in cursor.fetchall()}

    for table in expected_bronze_tables:
        if table in existing_tables:
            print(f"   ✅ {table} exists")
            passed += 1
        else:
            print(f"   ❌ {table} MISSING")
            failed += 1

    # TEST 2: Check row counts
    print("\n2. BRONZE LAYER - Row Counts")
    print("-" * 80)
    for table in expected_bronze_tables:
        if table in existing_tables:
            cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table}")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"   ✅ {table}: {count:,} rows")
                passed += 1
            else:
                print(f"   ⚠️  {table}: 0 rows (EMPTY)")
                warnings += 1

    # TEST 3: Check for excessive nulls
    print("\n3. BRONZE LAYER - Null Checks")
    print("-" * 80)

    # Market table
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) - COUNT(date) as date_nulls,
            COUNT(*) - COUNT(commodity) as commodity_nulls,
            COUNT(*) - COUNT(close) as close_nulls
        FROM commodity.bronze.market
    """)
    row = cursor.fetchone()
    total, date_nulls, commodity_nulls, close_nulls = row

    if date_nulls == 0 and commodity_nulls == 0 and close_nulls == 0:
        print(f"   ✅ market: No nulls in critical columns")
        passed += 1
    else:
        print(f"   ❌ market: Nulls found (date:{date_nulls}, commodity:{commodity_nulls}, close:{close_nulls})")
        failed += 1

    # Weather table
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(*) - COUNT(Date) as date_nulls,
            COUNT(*) - COUNT(Region) as region_nulls
        FROM commodity.bronze.weather
    """)
    row = cursor.fetchone()
    total, date_nulls, region_nulls = row

    if date_nulls == 0 and region_nulls == 0:
        print(f"   ✅ weather: No nulls in critical columns")
        passed += 1
    else:
        print(f"   ❌ weather: Nulls found (date:{date_nulls}, region:{region_nulls})")
        failed += 1

    # TEST 4: Silver layer validation
    print("\n4. SILVER LAYER - unified_data")
    print("-" * 80)

    cursor.execute("SELECT COUNT(*) FROM commodity.silver.unified_data")
    unified_count = cursor.fetchone()[0]

    if unified_count > 0:
        print(f"   ✅ Row count: {unified_count:,}")
        passed += 1
    else:
        print(f"   ❌ unified_data is EMPTY")
        failed += 1

    # Check unified_data nulls
    cursor.execute("""
        SELECT
            COUNT(*) - COUNT(date) as date_nulls,
            COUNT(*) - COUNT(commodity) as commodity_nulls,
            COUNT(*) - COUNT(region) as region_nulls
        FROM commodity.silver.unified_data
    """)
    row = cursor.fetchone()
    date_nulls, commodity_nulls, region_nulls = row

    if date_nulls == 0 and commodity_nulls == 0 and region_nulls == 0:
        print(f"   ✅ No nulls in critical columns")
        passed += 1
    else:
        print(f"   ❌ Nulls found (date:{date_nulls}, commodity:{commodity_nulls}, region:{region_nulls})")
        failed += 1

    # TEST 5: Data freshness
    print("\n5. DATA FRESHNESS")
    print("-" * 80)

    cursor.execute("SELECT MAX(date) FROM commodity.bronze.market")
    latest_market_date = cursor.fetchone()[0]
    days_old = (datetime.now().date() - latest_market_date).days

    if days_old <= 7:
        print(f"   ✅ market: Latest data from {latest_market_date} ({days_old} days old)")
        passed += 1
    elif days_old <= 30:
        print(f"   ⚠️  market: Latest data from {latest_market_date} ({days_old} days old)")
        warnings += 1
    else:
        print(f"   ❌ market: Latest data from {latest_market_date} ({days_old} days old - STALE)")
        failed += 1

    # TEST 6: Forecast layer
    print("\n6. FORECAST LAYER")
    print("-" * 80)

    forecast_tables = ['distributions', 'forecast_actuals', 'forecast_metadata', 'point_forecasts']
    cursor.execute("SHOW TABLES IN commodity.forecast")
    existing_forecast_tables = {row.tableName for row in cursor.fetchall()}

    for table in forecast_tables:
        if table in existing_forecast_tables:
            cursor.execute(f"SELECT COUNT(*) FROM commodity.forecast.{table}")
            count = cursor.fetchone()[0]
            if count > 0 or table == 'point_forecasts':  # point_forecasts can be empty
                print(f"   ✅ {table}: {count:,} rows")
                passed += 1
            else:
                print(f"   ⚠️  {table}: 0 rows")
                warnings += 1
        else:
            print(f"   ❌ {table}: MISSING")
            failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {passed}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"❌ Failed: {failed}")

    if failed == 0 and warnings == 0:
        print("\n🎉 ALL CHECKS PASSED! Pipeline is healthy.")
        exit_code = 0
    elif failed == 0:
        print("\n⚠️  Pipeline is operational but has warnings.")
        exit_code = 0
    else:
        print("\n❌ Pipeline has failures that need attention.")
        exit_code = 1

    print("=" * 80)

    cursor.close()
    connection.close()

    return exit_code


if __name__ == "__main__":
    exit(run_validation())
