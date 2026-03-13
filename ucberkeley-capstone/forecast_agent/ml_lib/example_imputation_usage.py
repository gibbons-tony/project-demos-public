"""
Example: Using ImputationTransformer with unified_data_raw

This script demonstrates the imputation workflow for the two-table gold layer strategy:
- commodity.gold.unified_data (forward-filled, production)
- commodity.gold.unified_data_raw (NULLs preserved, experimental)

Performance expectations:
- Imputation overhead: < 60 seconds (for ~7k rows)
- Total training time: < 1.2x baseline (with caching)
- Directional accuracy difference: < 0.01

Usage:
    # From Databricks notebook
    %run ./forecast_agent/ml_lib/example_imputation_usage.py

    # Test imputation performance
    results = test_imputation_performance(commodity='Coffee')
    print(results)

    # Use in production pipeline
    df_imputed = apply_production_imputation('commodity.gold.unified_data_raw', 'Coffee')
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, when, avg, stddev
from forecast_agent.ml_lib.transformers import (
    ImputationTransformer,
    create_production_imputer
)
import time
from typing import Dict, Any


def analyze_null_rates(df, table_name: str = "unified_data_raw"):
    """
    Analyze NULL rates in the dataset.

    Shows:
    - Total rows
    - NULL count and percentage for each column
    - Validation of expected NULL patterns

    Expected NULL rates (from collaboration docs):
    - GDELT: ~73% (data starts 2021-01-01)
    - VIX, FX (24 cols), OHLV: ~30% (weekends/holidays)
    - Weather: < 5% (occasional API gaps)
    - close: 0% (target, always forward-filled)
    """
    total_rows = df.count()
    print(f"\n{'='*80}")
    print(f"NULL Rate Analysis: {table_name}")
    print(f"{'='*80}")
    print(f"Total rows: {total_rows:,}\n")

    # Analyze each column
    null_stats = []
    for col_name in sorted(df.columns):
        null_count = df.filter(col(col_name).isNull()).count()
        null_pct = (null_count / total_rows) * 100

        # Flag unexpected patterns
        flag = ""
        if col_name == 'close' and null_pct > 0:
            flag = "⚠️ UNEXPECTED"
        elif 'gdelt' in col_name.lower() and null_pct > 80:
            flag = "⚠️ HIGH"
        elif 'vix' in col_name.lower() or 'usd' in col_name.lower():
            if null_pct < 20 or null_pct > 40:
                flag = "⚠️ CHECK"

        null_stats.append({
            'column': col_name,
            'null_count': null_count,
            'null_pct': null_pct,
            'flag': flag
        })

    # Print top NULL offenders
    null_stats_sorted = sorted(null_stats, key=lambda x: x['null_pct'], reverse=True)
    print(f"{'Column':<40} {'NULL Count':>12} {'NULL %':>8} {'Flag':>15}")
    print("-" * 80)
    for stat in null_stats_sorted[:20]:  # Top 20
        print(f"{stat['column']:<40} {stat['null_count']:>12,} {stat['null_pct']:>7.1f}% {stat['flag']:>15}")

    print(f"\n{'='*80}\n")
    return null_stats


def test_imputation_performance(
    commodity: str = 'Coffee',
    table_raw: str = 'commodity.gold.unified_data_raw',
    table_baseline: str = 'commodity.gold.unified_data'
) -> Dict[str, Any]:
    """
    Benchmark imputation performance vs baseline.

    Tests:
    1. Load time for raw vs baseline
    2. Imputation overhead
    3. Cache materialization time
    4. Row count validation

    Success criteria (from collaboration docs):
    - Imputation overhead < 60 seconds
    - Total time < 1.2x baseline

    Returns:
        Dict with timing metrics and validation results
    """
    spark = SparkSession.builder.getOrCreate()

    print(f"\n{'='*80}")
    print(f"Imputation Performance Test: {commodity}")
    print(f"{'='*80}\n")

    # Test 1: Baseline (forward-filled table)
    print("Test 1: Baseline (unified_data with forward-fill)")
    start = time.time()
    df_baseline = spark.table(table_baseline).filter(col('commodity') == commodity)
    baseline_count = df_baseline.count()
    baseline_time = time.time() - start
    print(f"  ✓ Loaded {baseline_count:,} rows in {baseline_time:.1f}s\n")

    # Test 2: Raw table (with NULLs)
    print("Test 2: Load raw table (unified_data_raw)")
    start = time.time()
    df_raw = spark.table(table_raw).filter(col('commodity') == commodity)
    raw_count = df_raw.count()
    load_raw_time = time.time() - start
    print(f"  ✓ Loaded {raw_count:,} rows in {load_raw_time:.1f}s\n")

    # Validate row counts match
    if raw_count != baseline_count:
        print(f"  ⚠️ WARNING: Row count mismatch! Baseline: {baseline_count}, Raw: {raw_count}\n")

    # Analyze NULL rates before imputation
    print("Analyzing NULL rates before imputation...")
    null_stats_before = analyze_null_rates(df_raw, table_raw)

    # Test 3: Imputation
    print("Test 3: Apply imputation")
    start = time.time()
    imputer = create_production_imputer()
    df_imputed = imputer.transform(df_raw)
    imputation_time = time.time() - start
    print(f"  ✓ Imputation transform defined in {imputation_time:.1f}s")
    print(f"    (Note: Spark lazy evaluation - actual work happens on cache/count)\n")

    # Test 4: Cache materialization
    print("Test 4: Cache and materialize")
    start = time.time()
    df_imputed.cache()
    imputed_count = df_imputed.count()
    cache_time = time.time() - start
    print(f"  ✓ Cached {imputed_count:,} rows in {cache_time:.1f}s\n")

    # Analyze NULL rates after imputation
    print("Analyzing NULL rates after imputation...")
    null_stats_after = analyze_null_rates(df_imputed, "imputed")

    # Calculate total time
    total_time = load_raw_time + cache_time
    slowdown_factor = total_time / baseline_time if baseline_time > 0 else 0

    # Results
    print(f"\n{'='*80}")
    print("Performance Summary")
    print(f"{'='*80}")
    print(f"Baseline (forward-filled):     {baseline_time:>8.1f}s")
    print(f"Raw load:                      {load_raw_time:>8.1f}s")
    print(f"Imputation + cache:            {cache_time:>8.1f}s")
    print(f"Total (raw + impute + cache):  {total_time:>8.1f}s")
    print(f"Slowdown factor:               {slowdown_factor:>8.2f}x")
    print(f"{'='*80}\n")

    # Validation
    success = True
    print("Validation:")
    if cache_time < 60:
        print(f"  ✅ Imputation overhead < 60s ({cache_time:.1f}s)")
    else:
        print(f"  ❌ Imputation overhead > 60s ({cache_time:.1f}s)")
        success = False

    if slowdown_factor < 1.2:
        print(f"  ✅ Total slowdown < 1.2x ({slowdown_factor:.2f}x)")
    else:
        print(f"  ⚠️ Total slowdown > 1.2x ({slowdown_factor:.2f}x)")
        success = False

    if imputed_count == baseline_count:
        print(f"  ✅ Row counts match ({imputed_count:,})")
    else:
        print(f"  ❌ Row count mismatch (baseline: {baseline_count}, imputed: {imputed_count})")
        success = False

    # Check for remaining NULLs (excluding keep_null columns)
    remaining_nulls = sum(1 for stat in null_stats_after if stat['null_pct'] > 0 and stat['column'] != 'close')
    if remaining_nulls > 0:
        print(f"  ⚠️ {remaining_nulls} columns still have NULLs (may be expected for keep_null strategy)")
    else:
        print(f"  ✅ No NULLs remaining (all imputed successfully)")

    print(f"\nOverall: {'✅ PASS' if success else '❌ FAIL'}\n")

    return {
        'commodity': commodity,
        'baseline_time_sec': baseline_time,
        'load_raw_time_sec': load_raw_time,
        'imputation_cache_time_sec': cache_time,
        'total_time_sec': total_time,
        'slowdown_factor': slowdown_factor,
        'row_count_baseline': baseline_count,
        'row_count_imputed': imputed_count,
        'null_stats_before': null_stats_before,
        'null_stats_after': null_stats_after,
        'success': success
    }


def apply_production_imputation(table_name: str, commodity: str):
    """
    Apply production-ready imputation configuration.

    This is the standard workflow for using unified_data_raw in ML pipelines.

    Args:
        table_name: Name of raw table (e.g., 'commodity.gold.unified_data_raw')
        commodity: Commodity to filter (e.g., 'Coffee')

    Returns:
        Cached DataFrame with imputed values

    Example:
        df_imputed = apply_production_imputation('commodity.gold.unified_data_raw', 'Coffee')

        # Use in cross-validation
        cv = TimeSeriesForecastCV(...)
        results = cv.fit(df_imputed)
    """
    spark = SparkSession.builder.getOrCreate()

    # Load raw data
    df_raw = spark.table(table_name).filter(col('commodity') == commodity)

    # Create production imputer
    imputer = create_production_imputer()

    # Apply imputation
    df_imputed = imputer.transform(df_raw)

    # Cache (critical for performance!)
    df_imputed.cache()
    df_imputed.count()  # Materialize cache

    print(f"✓ Applied production imputation to {commodity}")
    print(f"  Table: {table_name}")
    print(f"  Rows: {df_imputed.count():,}")
    print(f"  Cached: Yes (critical for CV performance)")

    return df_imputed


def compare_feature_distributions(
    commodity: str = 'Coffee',
    sample_features: list = None
):
    """
    Compare feature distributions before/after imputation.

    Validates that imputation doesn't distort distributions.

    Args:
        commodity: Commodity to analyze
        sample_features: List of features to compare (default: VIX, EUR/USD, temp)

    Expected behavior:
    - Mean should be similar (±5%)
    - Std dev might be slightly lower (imputation reduces variance)
    - No extreme outliers introduced
    """
    if sample_features is None:
        sample_features = ['vix_close', 'eur_usd', 'weather_temp_mean_c_avg']

    spark = SparkSession.builder.getOrCreate()

    # Load both tables
    df_baseline = spark.table('commodity.gold.unified_data').filter(col('commodity') == commodity)
    df_raw = spark.table('commodity.gold.unified_data_raw').filter(col('commodity') == commodity)

    # Apply imputation to raw
    imputer = create_production_imputer()
    df_imputed = imputer.transform(df_raw)
    df_imputed.cache()
    df_imputed.count()

    print(f"\n{'='*80}")
    print(f"Feature Distribution Comparison: {commodity}")
    print(f"{'='*80}\n")

    for feature in sample_features:
        if feature not in df_baseline.columns:
            print(f"⚠️ Feature '{feature}' not found, skipping...")
            continue

        # Calculate stats for baseline
        stats_baseline = df_baseline.select(
            avg(col(feature)).alias('mean'),
            stddev(col(feature)).alias('stddev')
        ).collect()[0]

        # Calculate stats for imputed
        stats_imputed = df_imputed.select(
            avg(col(feature)).alias('mean'),
            stddev(col(feature)).alias('stddev')
        ).collect()[0]

        # Compare
        mean_diff_pct = abs(stats_imputed['mean'] - stats_baseline['mean']) / stats_baseline['mean'] * 100
        stddev_diff_pct = abs(stats_imputed['stddev'] - stats_baseline['stddev']) / stats_baseline['stddev'] * 100

        print(f"Feature: {feature}")
        print(f"  Baseline:  mean={stats_baseline['mean']:>10.4f}, stddev={stats_baseline['stddev']:>10.4f}")
        print(f"  Imputed:   mean={stats_imputed['mean']:>10.4f}, stddev={stats_imputed['stddev']:>10.4f}")
        print(f"  Diff:      mean={mean_diff_pct:>9.2f}%,      stddev={stddev_diff_pct:>9.2f}%")

        if mean_diff_pct < 5:
            print(f"  ✅ Mean difference acceptable (< 5%)")
        else:
            print(f"  ⚠️ Mean difference high (> 5%)")

        print()

    print(f"{'='*80}\n")


# Example usage
if __name__ == "__main__":
    # Test 1: Performance benchmarking
    print("Running imputation performance test...\n")
    results = test_imputation_performance(commodity='Coffee')

    # Test 2: Feature distribution comparison
    print("\nRunning feature distribution comparison...\n")
    compare_feature_distributions(commodity='Coffee')

    # Test 3: Production usage example
    print("\nProduction usage example...\n")
    df_imputed = apply_production_imputation('commodity.gold.unified_data_raw', 'Coffee')
    print(f"\nReady to use df_imputed in ML pipeline!")
    print(f"Example: cv = TimeSeriesForecastCV(...); results = cv.fit(df_imputed)")
