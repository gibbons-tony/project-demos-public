"""
Multi-Granularity Statistical Analysis

Validates trading strategy performance at multiple time scales:
- Annual (by_year tables)
- Quarterly (by_quarter tables)
- Monthly (by_month tables)

Uses paired t-tests to assess statistical significance of improvements.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any


def run_granular_analysis(
    spark,
    commodity: str,
    model_version: str,
    strategy_name: str = 'RollingHorizonMPC',
    baseline_name: str = 'Immediate Sale',
    schema: str = 'commodity.trading_agent',
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run statistical analysis at multiple granularities

    Args:
        spark: Spark session
        commodity: Commodity name
        model_version: Model version
        strategy_name: Strategy to test
        baseline_name: Baseline strategy
        schema: Database schema
        verbose: Print results

    Returns:
        Dictionary with test results for each granularity
    """
    results = {}

    for granularity, time_col in [('year', 'year'), ('quarter', 'quarter'), ('month', 'month')]:
        table_name = f"{schema}.results_{commodity}_by_{granularity}_{model_version}"

        try:
            # Load data
            df = spark.table(table_name).toPandas()

            # Filter to target strategies
            strategy_data = df[df['strategy'] == strategy_name].sort_values(time_col)
            baseline_data = df[df['strategy'] == baseline_name].sort_values(time_col)

            if len(strategy_data) == 0 or len(baseline_data) == 0:
                if verbose:
                    print(f"  ⚠️  {granularity.upper()}: No data for {strategy_name} or {baseline_name}")
                results[granularity] = {'status': 'no_data'}
                continue

            if len(strategy_data) < 2:
                if verbose:
                    print(f"  ⚠️  {granularity.upper()}: Insufficient data (n={len(strategy_data)})")
                results[granularity] = {'status': 'insufficient_data', 'n': len(strategy_data)}
                continue

            # Align data by time period
            # Note: All strategies for a given model have the same periods by construction
            # (they're all backtested on the same filtered date range)
            strategy_aligned = strategy_data.set_index(time_col).sort_index()
            baseline_aligned = baseline_data.set_index(time_col).sort_index()

            # Get periods from strategy data
            periods = sorted(strategy_aligned.index.tolist())
            n_periods = len(periods)

            # Calculate differences
            differences = strategy_aligned['net_earnings'] - baseline_aligned['net_earnings']
            mean_diff = differences.mean()
            std_diff = differences.std()

            # Paired t-test
            t_stat, p_value = stats.ttest_rel(
                strategy_aligned['net_earnings'],
                baseline_aligned['net_earnings']
            )

            # Percentage improvement
            baseline_mean = baseline_aligned['net_earnings'].mean()
            pct_improvement = (mean_diff / baseline_mean * 100) if baseline_mean != 0 else 0

            # Store results
            results[granularity] = {
                'status': 'success',
                'n': n_periods,
                'periods': periods,
                'mean_diff': float(mean_diff),
                'std_diff': float(std_diff),
                'pct_improvement': float(pct_improvement),
                't_statistic': float(t_stat),
                'p_value': float(p_value),
                'significant': p_value < 0.05,
                'strategy_mean': float(strategy_aligned['net_earnings'].mean()),
                'baseline_mean': float(baseline_mean)
            }

            # Verbose output
            if verbose:
                sig_marker = "✓" if p_value < 0.05 else "✗"
                print(f"  {sig_marker} {granularity.upper()}: "
                      f"{pct_improvement:+.2f}% improvement "
                      f"(p={p_value:.4f}, n={n_periods})")

        except Exception as e:
            if verbose:
                print(f"  ✗ {granularity.upper()}: Error - {e}")
            results[granularity] = {'status': 'error', 'error': str(e)}

    return results


def run_multi_commodity_granular_analysis(
    spark,
    commodities: List[str],
    schema: str = 'commodity.trading_agent',
    verbose: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Run granular analysis for multiple commodities and all their models

    Args:
        spark: Spark session
        commodities: List of commodity names
        schema: Database schema
        verbose: Print results

    Returns:
        Nested dictionary: {commodity: {model: {granularity: results}}}
    """
    all_results = {}

    for commodity in commodities:
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"COMMODITY: {commodity.upper()}")
            print(f"{'=' * 80}")

        # Refresh Spark catalog to ensure we see latest tables created by Step 4
        # This prevents catalog caching issues where newly created tables aren't visible
        try:
            # Refresh all by_year tables for this commodity
            temp_tables = spark.sql(f"SHOW TABLES IN {schema}").toPandas()
            by_year_pattern = f'results_{commodity}_by_year_'
            refresh_tables = temp_tables[temp_tables['tableName'].str.startswith(by_year_pattern)]
            for _, row in refresh_tables.iterrows():
                spark.catalog.refreshTable(f"{schema}.{row['tableName']}")
        except Exception as e:
            # If refresh fails, log but continue - table discovery will still work
            if verbose:
                print(f"  Warning: Catalog refresh failed: {e}")

        # Discover models from by_year tables
        # Use Python filter instead of SQL LIKE (LIKE pattern doesn't work reliably with underscores)
        all_tables = spark.sql(f"SHOW TABLES IN {schema}").toPandas()
        pattern = f'results_{commodity}_by_year_'
        by_year_tables = all_tables[all_tables['tableName'].str.startswith(pattern)]

        models = [
            name.replace(pattern, '')
            for name in by_year_tables['tableName'].tolist()
        ]

        if verbose:
            print(f"  Models found: {models}")

        commodity_results = {}

        for model in models:
            if verbose:
                print(f"\n  MODEL: {model}")

            model_results = run_granular_analysis(
                spark=spark,
                commodity=commodity,
                model_version=model,
                schema=schema,
                verbose=verbose
            )

            commodity_results[model] = model_results

        all_results[commodity] = commodity_results

    return all_results


def print_granular_summary(results: Dict[str, Dict[str, Any]]):
    """
    Print summary of multi-granularity analysis

    Args:
        results: Results from run_multi_commodity_granular_analysis
    """
    print(f"\n{'=' * 80}")
    print("MULTI-GRANULARITY ANALYSIS SUMMARY")
    print(f"{'=' * 80}")

    for commodity, models in results.items():
        print(f"\n{commodity.upper()}:")

        for model, granularities in models.items():
            print(f"  {model}:")

            for gran, result in granularities.items():
                if result.get('status') == 'success':
                    sig = "✓" if result['significant'] else "✗"
                    print(f"    {gran:8s}: {sig} {result['pct_improvement']:+6.2f}% "
                          f"(p={result['p_value']:.4f}, n={result['n']})")
                else:
                    print(f"    {gran:8s}: {result.get('status', 'unknown')}")
