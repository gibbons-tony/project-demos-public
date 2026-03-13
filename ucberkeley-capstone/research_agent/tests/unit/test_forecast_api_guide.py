"""
Test Forecast API Guide for Trading Agent

Validates that all example queries in trading_agent/FORECAST_API_GUIDE.md work correctly
"""

import os
from databricks import sql
from dotenv import load_dotenv
import pathlib

# Load credentials
env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH]):
    print("ERROR: Missing credentials in .env")
    exit(1)


def test_api_guide():
    """Test all example queries from API guide"""

    connection = sql.connect(
        server_hostname=DATABRICKS_HOST.replace("https://", ""),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )
    cursor = connection.cursor()

    print("=" * 80)
    print("TESTING FORECAST API GUIDE")
    print("=" * 80)

    passed = 0
    failed = 0
    warnings = 0

    # Test 1: Data Availability
    print("\n1. Data Availability Check:")
    print("-" * 80)
    cursor.execute("SELECT COUNT(*) FROM commodity.forecast.distributions")
    total_rows = cursor.fetchone()[0]
    print(f"Total rows: {total_rows:,}")
    print(f"Guide claims: 622,300 rows")

    if total_rows >= 622300:
        print("Status: OK (Guide outdated but data exists)")
        passed += 1
    else:
        print("Status: WARNING - Less data than expected")
        warnings += 1

    # Test 2: Forecast dates
    cursor.execute("""
        SELECT COUNT(DISTINCT forecast_start_date) as num_dates,
               MIN(forecast_start_date) as earliest,
               MAX(forecast_start_date) as latest
        FROM commodity.forecast.distributions
    """)
    row = cursor.fetchone()
    print(f"\nForecast dates: {row.num_dates} ({row.earliest} to {row.latest})")
    print(f"Guide claims: 42 forecast dates")

    if row.num_dates >= 42:
        print("Status: OK")
        passed += 1
    else:
        print("Status: WARNING - Fewer dates than expected")
        warnings += 1

    # Test 3: Models available
    print("\n2. Models Available:")
    print("-" * 80)
    cursor.execute("""
        SELECT model_version, COUNT(*) as num_rows
        FROM commodity.forecast.distributions
        GROUP BY model_version
        ORDER BY num_rows DESC
    """)
    models = cursor.fetchall()
    for row in models:
        print(f"  {row.model_version}: {row.num_rows:,} rows")

    if len(models) >= 5:
        print("Status: OK (5+ models available)")
        passed += 1
    else:
        print("Status: WARNING - Fewer models than expected")
        warnings += 1

    # Test 4: Example Query #1 (Latest Forecast)
    print("\n3. Test Example Query #1 (Get Latest Forecast):")
    print("-" * 80)
    cursor.execute("""
        SELECT COUNT(*) as num_paths
        FROM commodity.forecast.distributions
        WHERE model_version = 'sarimax_auto_weather_v1'
          AND commodity = 'Coffee'
          AND is_actuals = FALSE
          AND has_data_leakage = FALSE
          AND forecast_start_date = (
            SELECT MAX(forecast_start_date)
            FROM commodity.forecast.distributions
            WHERE model_version = 'sarimax_auto_weather_v1'
          )
    """)
    paths = cursor.fetchone()[0]
    print(f"Paths returned: {paths:,}")
    print(f"Expected: ~2,000 paths")

    if paths > 0:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL - No paths returned")
        failed += 1

    # Test 5: Example Query #2 (VaR Calculation)
    print("\n4. Test Example Query #2 (VaR Calculation):")
    print("-" * 80)
    try:
        cursor.execute("""
            SELECT
              forecast_start_date,
              AVG(day_7) as mean_price,
              STDDEV(day_7) as price_volatility,
              PERCENTILE(day_7, 0.05) as var_95_lower,
              PERCENTILE(day_7, 0.95) as var_95_upper,
              MIN(day_7) as worst_case,
              MAX(day_7) as best_case
            FROM commodity.forecast.distributions
            WHERE model_version = 'sarimax_auto_weather_v1'
              AND commodity = 'Coffee'
              AND is_actuals = FALSE
              AND has_data_leakage = FALSE
            GROUP BY forecast_start_date
            ORDER BY forecast_start_date DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            print(f"Latest forecast: {row.forecast_start_date}")
            print(f"Mean 7-day price: ${row.mean_price:.2f}")
            print(f"Volatility: ${row.price_volatility:.2f}")
            print(f"VaR 95% range: ${row.var_95_lower:.2f} - ${row.var_95_upper:.2f}")
            print("Status: PASS")
            passed += 1
        else:
            print("Status: FAIL - No data returned")
            failed += 1
    except Exception as e:
        print(f"Status: FAIL - {e}")
        failed += 1

    # Test 6: Actuals for backtesting
    print("\n5. Actuals for Backtesting:")
    print("-" * 80)
    cursor.execute("""
        SELECT COUNT(*) as num_actuals
        FROM commodity.forecast.distributions
        WHERE is_actuals = TRUE
          AND commodity = 'Coffee'
    """)
    actuals = cursor.fetchone()[0]
    print(f"Actuals rows: {actuals:,}")

    if actuals > 0:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL - No actuals available")
        failed += 1

    # Test 7: Backtest query (Example #4)
    print("\n6. Test Example Query #4 (Backtest Performance):")
    print("-" * 80)
    try:
        cursor.execute("""
            WITH forecasts AS (
              SELECT
                forecast_start_date,
                AVG(day_7) as forecast_mean_day7,
                PERCENTILE(day_7, 0.05) as forecast_lower_95,
                PERCENTILE(day_7, 0.95) as forecast_upper_95
              FROM commodity.forecast.distributions
              WHERE model_version = 'sarimax_auto_weather_v1'
                AND commodity = 'Coffee'
                AND is_actuals = FALSE
                AND has_data_leakage = FALSE
              GROUP BY forecast_start_date
            ),
            actuals AS (
              SELECT
                forecast_start_date,
                day_7 as actual_day7
              FROM commodity.forecast.distributions
              WHERE path_id = 0
                AND is_actuals = TRUE
                AND commodity = 'Coffee'
            )
            SELECT
              f.forecast_start_date,
              f.forecast_mean_day7,
              a.actual_day7,
              ABS(f.forecast_mean_day7 - a.actual_day7) as abs_error
            FROM forecasts f
            JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
            ORDER BY f.forecast_start_date DESC
            LIMIT 3
        """)
        results = cursor.fetchall()
        if results:
            print(f"Backtest results: {len(results)} forecast windows")
            for row in results:
                print(f"  {row.forecast_start_date}: Forecast=${row.forecast_mean_day7:.2f}, "
                      f"Actual=${row.actual_day7:.2f}, Error=${row.abs_error:.2f}")
            print("Status: PASS")
            passed += 1
        else:
            print("Status: FAIL - No backtest results")
            failed += 1
    except Exception as e:
        print(f"Status: FAIL - {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"PASSED: {passed}")
    print(f"WARNINGS: {warnings}")
    print(f"FAILED: {failed}")

    if failed == 0:
        print("\nOVERALL: API Guide works correctly!")
        print("Note: Guide has outdated row counts but all queries execute successfully")
        exit_code = 0
    else:
        print("\nOVERALL: API Guide has issues that need fixing")
        exit_code = 1

    print("=" * 80)

    cursor.close()
    connection.close()

    return exit_code


if __name__ == "__main__":
    exit(test_api_guide())
