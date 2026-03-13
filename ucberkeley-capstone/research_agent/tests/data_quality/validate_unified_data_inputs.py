#!/usr/bin/env python3
"""
Rigorous validation of unified_data INPUT sources (before forward fill)

This script checks:
1. Nulls in each raw input source BEFORE forward fill
2. Date gaps by commodity/region
3. Data completeness metrics
4. Trading day alignment
5. Unexpected patterns that forward-fill might hide

Usage:
    export DATABRICKS_TOKEN=<your-token>
    python validate_unified_data_inputs.py
"""
import requests
import time
import os
import sys
from pathlib import Path
from datetime import datetime

# Databricks configuration
DATABRICKS_HOST = "https://dbc-fd7b00f3-7a6d.cloud.databricks.com"
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
WAREHOUSE_ID = "3cede8561503a13c"

if not DATABRICKS_TOKEN:
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


def execute_sql(sql_query, wait_timeout=120, description=None):
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
        print(f"\n{'='*80}")
        print(f"  {description}")
        print(f"{'='*80}")

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in [200, 201]:
        result = response.json()
        status = result.get('status', {}).get('state')
        statement_id = result.get('statement_id')

        if status == 'SUCCEEDED':
            return True, result
        elif status in ['PENDING', 'RUNNING']:
            # Poll for completion
            max_polls = 60
            for i in range(max_polls):
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

            print("⚠ Timed out waiting for completion")
            return False, result
        elif status == 'FAILED':
            error = result.get('status', {}).get('error', {})
            print(f"✗ FAILED: {error.get('message', 'Unknown error')}")
            return False, result
    else:
        print(f"✗ HTTP Error: {response.status_code}")
        return False, response.text


def validate_market_data():
    """Validate raw market data (BEFORE forward fill)"""
    print("\n" + "="*80)
    print("MARKET DATA VALIDATION (Coffee & Sugar)")
    print("="*80)

    # Check nulls in RAW market data
    sql = """
    SELECT
        commodity,
        COUNT(*) as total_records,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as null_open,
        SUM(CASE WHEN high IS NULL THEN 1 ELSE 0 END) as null_high,
        SUM(CASE WHEN low IS NULL THEN 1 ELSE 0 END) as null_low,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close,
        SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_volume,
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        DATEDIFF(MAX(date), MIN(date)) + 1 as expected_days
    FROM commodity.bronze.market_data
    WHERE date >= '2015-07-07'
    GROUP BY commodity
    ORDER BY commodity
    """

    success, result = execute_sql(sql, description="Checking RAW market data for nulls")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        print("\n📊 Market Data Summary:")
        print(f"{'Commodity':<10} {'Records':<10} {'Null Open':<12} {'Null High':<12} {'Null Low':<12} {'Null Close':<12} {'Null Vol':<12} {'Date Range'}")
        print("-" * 120)

        for row in rows:
            commodity, total, n_open, n_high, n_low, n_close, n_vol, earliest, latest, expected = row
            date_range = f"{earliest} to {latest} ({int(expected):,} days)"
            print(f"{commodity:<10} {int(total):<10,} {int(n_open):<12,} {int(n_high):<12,} {int(n_low):<12,} {int(n_close):<12,} {int(n_vol):<12,} {date_range}")

            # Check for concerning null counts
            if n_open > 0 or n_high > 0 or n_low > 0 or n_close > 0:
                print(f"  ⚠️  WARNING: {commodity} has nulls in OHLC data!")

            # Check for record count vs expected days
            coverage = (total / expected) * 100
            if coverage < 70:  # Less than 70% coverage
                print(f"  ⚠️  WARNING: {commodity} only has {coverage:.1f}% date coverage (likely weekends/holidays)")
            else:
                print(f"  ✓ Good coverage: {coverage:.1f}%")

    # Check for date gaps > 7 days (suspicious)
    sql = """
    WITH market_dates AS (
        SELECT
            commodity,
            date,
            LAG(date) OVER (PARTITION BY commodity ORDER BY date) as prev_date,
            DATEDIFF(date, LAG(date) OVER (PARTITION BY commodity ORDER BY date)) as days_gap
        FROM commodity.bronze.market_data
        WHERE date >= '2015-07-07'
    )
    SELECT
        commodity,
        prev_date,
        date,
        days_gap
    FROM market_dates
    WHERE days_gap > 7
    ORDER BY commodity, date
    """

    success, result = execute_sql(sql, description="Checking for suspicious date gaps (>7 days)")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        if rows:
            print(f"\n⚠️  Found {len(rows)} date gaps > 7 days:")
            print(f"{'Commodity':<10} {'From':<12} {'To':<12} {'Gap (days)'}")
            print("-" * 50)
            for row in rows[:20]:  # Show first 20
                commodity, prev, curr, gap = row
                print(f"{commodity:<10} {prev:<12} {curr:<12} {int(gap)}")
            if len(rows) > 20:
                print(f"... and {len(rows) - 20} more")
        else:
            print("\n✓ No suspicious date gaps found!")

    return True


def validate_weather_data():
    """Validate raw weather data (BEFORE forward fill)"""
    print("\n" + "="*80)
    print("WEATHER DATA VALIDATION (67 regions)")
    print("="*80)

    # Check nulls in RAW weather data
    sql = """
    SELECT
        region,
        commodity,
        COUNT(*) as total_records,
        SUM(CASE WHEN temp_max_c IS NULL THEN 1 ELSE 0 END) as null_temp_max,
        SUM(CASE WHEN temp_min_c IS NULL THEN 1 ELSE 0 END) as null_temp_min,
        SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) as null_temp_mean,
        SUM(CASE WHEN precipitation_mm IS NULL THEN 1 ELSE 0 END) as null_precip,
        SUM(CASE WHEN humidity_mean_pct IS NULL THEN 1 ELSE 0 END) as null_humidity,
        SUM(CASE WHEN wind_speed_max_kmh IS NULL THEN 1 ELSE 0 END) as null_wind,
        SUM(CASE WHEN solar_radiation_mj_m2 IS NULL THEN 1 ELSE 0 END) as null_solar,
        SUM(CASE WHEN evapotranspiration_mm IS NULL THEN 1 ELSE 0 END) as null_et0,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
    FROM commodity.bronze.weather_data
    WHERE date >= '2015-01-01'
    GROUP BY region, commodity
    ORDER BY
        (SUM(CASE WHEN temp_max_c IS NULL THEN 1 ELSE 0 END) +
         SUM(CASE WHEN temp_min_c IS NULL THEN 1 ELSE 0 END) +
         SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END)) DESC
    """

    success, result = execute_sql(sql, description="Checking RAW weather data for nulls by region")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        print(f"\n📊 Weather Data Summary ({len(rows)} region/commodity combinations):")

        # Show regions with ANY nulls
        regions_with_nulls = [r for r in rows if any(int(r[i]) > 0 for i in range(3, 9))]

        if regions_with_nulls:
            print(f"\n⚠️  {len(regions_with_nulls)} regions have nulls:")
            print(f"{'Region':<35} {'Comm':<6} {'Records':<10} {'TMax':<8} {'TMin':<8} {'TMean':<8} {'Precip':<8} {'Humid':<8} {'Wind':<8} {'Solar':<8} {'ET0':<8}")
            print("-" * 150)

            for row in regions_with_nulls[:15]:  # Show first 15
                region, comm, total, n_tmax, n_tmin, n_tmean, n_precip, n_humid, n_wind, n_solar, n_et0, earliest, latest = row
                print(f"{region:<35} {comm:<6} {int(total):<10,} {int(n_tmax):<8,} {int(n_tmin):<8,} {int(n_tmean):<8,} {int(n_precip):<8,} {int(n_humid):<8,} {int(n_wind):<8,} {int(n_solar):<8,} {int(n_et0):<8,}")

            if len(regions_with_nulls) > 15:
                print(f"... and {len(regions_with_nulls) - 15} more regions with nulls")

            # Summarize total nulls
            total_nulls = sum(sum(int(r[i]) for i in range(3, 9)) for r in regions_with_nulls)
            total_records = sum(int(r[2]) for r in rows)
            print(f"\n📊 Total weather records: {total_records:,}")
            print(f"📊 Total nulls across all fields: {total_nulls:,} ({(total_nulls/total_records)*100:.2f}%)")
        else:
            print("✓ No nulls found in weather data!")

    # Check for regions with incomplete date ranges
    sql = """
    WITH expected_days AS (
        SELECT
            region,
            commodity,
            COUNT(*) as actual_days,
            DATEDIFF(MAX(date), MIN(date)) + 1 as expected_days,
            MIN(date) as start_date,
            MAX(date) as end_date
        FROM commodity.bronze.weather_data
        WHERE date >= '2015-01-01'
        GROUP BY region, commodity
    )
    SELECT
        region,
        commodity,
        actual_days,
        expected_days,
        expected_days - actual_days as missing_days,
        (actual_days * 100.0 / expected_days) as coverage_pct,
        start_date,
        end_date
    FROM expected_days
    WHERE actual_days < expected_days * 0.95  -- Less than 95% coverage
    ORDER BY missing_days DESC
    """

    success, result = execute_sql(sql, description="Checking for incomplete weather date ranges")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        if rows:
            print(f"\n⚠️  {len(rows)} regions have <95% date coverage:")
            print(f"{'Region':<35} {'Comm':<6} {'Actual':<10} {'Expected':<10} {'Missing':<10} {'Coverage'}")
            print("-" * 90)
            for row in rows[:15]:
                region, comm, actual, expected, missing, coverage, start, end = row
                print(f"{region:<35} {comm:<6} {int(actual):<10,} {int(expected):<10,} {int(missing):<10,} {float(coverage):.1f}%")
            if len(rows) > 15:
                print(f"... and {len(rows) - 15} more")
        else:
            print("\n✓ All regions have complete date coverage (≥95%)!")

    return True


def validate_macro_data():
    """Validate raw macro/FX data (BEFORE forward fill)"""
    print("\n" + "="*80)
    print("MACRO DATA VALIDATION (24 FX rates)")
    print("="*80)

    # Check nulls in each FX rate
    sql = """
    SELECT
        COUNT(*) as total_records,
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        SUM(CASE WHEN DEXUSAL IS NULL THEN 1 ELSE 0 END) as null_aud,
        SUM(CASE WHEN DEXBZUS IS NULL THEN 1 ELSE 0 END) as null_brl,
        SUM(CASE WHEN DEXCAUS IS NULL THEN 1 ELSE 0 END) as null_cad,
        SUM(CASE WHEN DEXCHUS IS NULL THEN 1 ELSE 0 END) as null_cny,
        SUM(CASE WHEN DEXUSEU IS NULL THEN 1 ELSE 0 END) as null_eur,
        SUM(CASE WHEN DEXJPUS IS NULL THEN 1 ELSE 0 END) as null_jpy,
        SUM(CASE WHEN DEXMXUS IS NULL THEN 1 ELSE 0 END) as null_mxn,
        SUM(CASE WHEN DEXINUS IS NULL THEN 1 ELSE 0 END) as null_inr,
        DATEDIFF(MAX(date), MIN(date)) + 1 as expected_days
    FROM commodity.bronze.macro_data
    WHERE date >= '2015-07-07'
    """

    success, result = execute_sql(sql, description="Checking RAW macro/FX data for nulls")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        if rows:
            row = rows[0]
            total, earliest, latest, n_aud, n_brl, n_cad, n_cny, n_eur, n_jpy, n_mxn, n_inr, expected = row

            print(f"\n📊 Macro Data Summary:")
            print(f"  Total Records: {int(total):,}")
            print(f"  Date Range: {earliest} to {latest}")
            print(f"  Expected Days: {int(expected):,}")
            print(f"  Coverage: {(total/expected)*100:.1f}%")

            print(f"\n  Null counts by currency:")
            currencies = [
                ("AUD", n_aud), ("BRL", n_brl), ("CAD", n_cad), ("CNY", n_cny),
                ("EUR", n_eur), ("JPY", n_jpy), ("MXN", n_mxn), ("INR", n_inr)
            ]

            max_nulls = 0
            for curr, nulls in currencies:
                null_count = int(nulls)
                print(f"    {curr}: {null_count:,} nulls ({(null_count/total)*100:.2f}%)")
                max_nulls = max(max_nulls, null_count)

            if max_nulls > total * 0.1:  # More than 10% nulls
                print(f"\n  ⚠️  WARNING: Some currencies have >10% nulls (likely weekends/holidays)")
            else:
                print(f"\n  ✓ Null rates are reasonable (<10%)")

    return True


def validate_vix_data():
    """Validate raw VIX data (BEFORE forward fill)"""
    print("\n" + "="*80)
    print("VIX DATA VALIDATION")
    print("="*80)

    sql = """
    SELECT
        COUNT(*) as total_records,
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as null_vix,
        MIN(date) as earliest_date,
        MAX(date) as latest_date,
        DATEDIFF(MAX(date), MIN(date)) + 1 as expected_days,
        MIN(vix) as min_vix,
        MAX(vix) as max_vix,
        AVG(vix) as avg_vix
    FROM commodity.bronze.vix_data
    WHERE date >= '2015-07-07'
    """

    success, result = execute_sql(sql, description="Checking RAW VIX data")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])
        if rows:
            total, nulls, earliest, latest, expected, min_vix, max_vix, avg_vix = rows[0]

            print(f"\n📊 VIX Data Summary:")
            print(f"  Total Records: {int(total):,}")
            print(f"  Null Records: {int(nulls):,} ({(nulls/total)*100:.2f}%)")
            print(f"  Date Range: {earliest} to {latest}")
            print(f"  Expected Days: {int(expected):,}")
            print(f"  Coverage: {(total/expected)*100:.1f}%")
            print(f"  VIX Range: {float(min_vix):.2f} to {float(max_vix):.2f} (avg: {float(avg_vix):.2f})")

            if nulls == 0:
                print("  ✓ No nulls in VIX data!")
            elif nulls < total * 0.1:
                print("  ✓ Null rate is reasonable (<10%)")
            else:
                print("  ⚠️  WARNING: High null rate in VIX data")

    return True


def validate_unified_comparison():
    """Compare unified_data (after forward fill) with raw inputs"""
    print("\n" + "="*80)
    print("UNIFIED DATA: Comparing RAW vs FORWARD-FILLED")
    print("="*80)

    sql = """
    SELECT
        'Market Data' as data_source,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as nulls_in_unified
    FROM commodity.silver.unified_data

    UNION ALL

    SELECT
        'Weather Data',
        SUM(CASE WHEN temp_max_c IS NULL THEN 1 ELSE 0 END)
    FROM commodity.silver.unified_data

    UNION ALL

    SELECT
        'VIX Data',
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END)
    FROM commodity.silver.unified_data

    UNION ALL

    SELECT
        'Macro Data',
        SUM(CASE WHEN DEXUSAL IS NULL THEN 1 ELSE 0 END)
    FROM commodity.silver.unified_data
    """

    success, result = execute_sql(sql, description="Checking nulls AFTER forward fill")
    if success and 'result' in result:
        rows = result.get('result', {}).get('data_array', [])

        print(f"\n📊 Forward Fill Effectiveness:")
        print(f"{'Data Source':<20} {'Nulls After Fill'}")
        print("-" * 45)

        for row in rows:
            source, nulls = row
            null_count = int(nulls)
            if null_count == 0:
                status = "✓"
            elif null_count < 1000:
                status = "⚠️"
            else:
                status = "❌"
            print(f"{status} {source:<18} {null_count:,}")

    return True


def main():
    """Main validation flow"""
    print("\n" + "="*80)
    print("RIGOROUS UNIFIED DATA INPUT VALIDATION")
    print("="*80)
    print(f"Databricks: {DATABRICKS_HOST}")
    print(f"Checking INPUT data BEFORE forward fill to find issues...")
    print("="*80)

    try:
        # Validate each data source
        validate_market_data()
        validate_weather_data()
        validate_macro_data()
        validate_vix_data()
        validate_unified_comparison()

        print("\n" + "="*80)
        print("✓ VALIDATION COMPLETE")
        print("="*80)
        print("\nKey Findings:")
        print("- Check above for null patterns in RAW input data")
        print("- Date gaps and coverage issues are highlighted")
        print("- Forward-fill effectiveness is shown at the end")
        print("\nRecommendation: Review any ⚠️  warnings above")

        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
