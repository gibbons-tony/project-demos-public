"""
Check forecast coverage in commodity.forecast.distributions table

Purpose: Identify which commodity + model_version combinations are well-populated
         and suitable for backtesting
"""

import sys
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.getOrCreate()

    print("\n" + "=" * 100)
    print("CHECKING FORECAST COVERAGE")
    print("=" * 100)

    # Summary by commodity and model
    print("\n1. FORECAST DATES BY COMMODITY AND MODEL VERSION:")
    print("-" * 100)

    summary = spark.sql("""
        SELECT
            commodity,
            model_version,
            COUNT(DISTINCT forecast_start_date) as n_forecast_dates,
            MIN(forecast_start_date) as first_date,
            MAX(forecast_start_date) as last_date,
            COUNT(*) as total_rows
        FROM commodity.forecast.distributions
        WHERE is_actuals = false
        GROUP BY commodity, model_version
        ORDER BY commodity, n_forecast_dates DESC
    """)

    summary.show(100, truncate=False)

    # Check prediction density
    print("\n2. PREDICTION DENSITY (avg runs per forecast date):")
    print("-" * 100)

    density = spark.sql("""
        WITH runs_per_date AS (
            SELECT
                commodity,
                model_version,
                forecast_start_date,
                COUNT(DISTINCT path_id) as n_runs
            FROM commodity.forecast.distributions
            WHERE is_actuals = false
            GROUP BY commodity, model_version, forecast_start_date
        )
        SELECT
            commodity,
            model_version,
            COUNT(*) as n_dates,
            ROUND(AVG(n_runs), 1) as avg_runs_per_date,
            MIN(n_runs) as min_runs,
            MAX(n_runs) as max_runs,
            PERCENTILE(n_runs, 0.5) as median_runs
        FROM runs_per_date
        GROUP BY commodity, model_version
        ORDER BY avg_runs_per_date DESC, n_dates DESC
    """)

    density.show(100, truncate=False)

    # Quality assessment
    print("\n3. FORECAST QUALITY ASSESSMENT:")
    print("-" * 100)

    quality = spark.sql("""
        WITH stats AS (
            SELECT
                commodity,
                model_version,
                COUNT(DISTINCT forecast_start_date) as n_dates,
                AVG(n_runs) as avg_runs,
                MIN(n_runs) as min_runs,
                MAX(n_runs) as max_runs
            FROM (
                SELECT
                    commodity,
                    model_version,
                    forecast_start_date,
                    COUNT(DISTINCT path_id) as n_runs
                FROM commodity.forecast.distributions
                WHERE is_actuals = false
                GROUP BY commodity, model_version, forecast_start_date
            )
            GROUP BY commodity, model_version
        )
        SELECT
            commodity,
            model_version,
            n_dates,
            ROUND(avg_runs, 1) as avg_runs_per_date,
            min_runs,
            max_runs,
            CASE
                WHEN avg_runs >= 100 AND n_dates >= 100 THEN 'EXCELLENT'
                WHEN avg_runs >= 50 AND n_dates >= 50 THEN 'GOOD'
                WHEN avg_runs >= 20 AND n_dates >= 20 THEN 'MARGINAL'
                ELSE 'SPARSE'
            END as quality_rating
        FROM stats
        ORDER BY
            CASE quality_rating
                WHEN 'EXCELLENT' THEN 1
                WHEN 'GOOD' THEN 2
                WHEN 'MARGINAL' THEN 3
                ELSE 4
            END,
            avg_runs DESC
    """)

    quality.show(100, truncate=False)

    # Get recommended forecasts
    recommended = quality.filter("quality_rating IN ('EXCELLENT', 'GOOD')").collect()

    print("\n" + "=" * 100)
    print("RECOMMENDATION:")
    print("=" * 100)

    if recommended:
        print(f"\n✅ Found {len(recommended)} well-populated forecast(s) suitable for testing:\n")
        for row in recommended:
            print(f"  • {row.commodity} - {row.model_version}")
            print(f"    {row.n_dates} forecast dates, {row.avg_runs_per_date} avg runs/date [{row.quality_rating}]")
    else:
        print("\n⚠️ No well-populated forecasts found (EXCELLENT or GOOD quality)")
        print("   Consider using forecasts with MARGINAL quality for testing")

    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()
