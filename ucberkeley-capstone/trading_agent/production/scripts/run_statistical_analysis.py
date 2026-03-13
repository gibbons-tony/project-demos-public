"""
Run Statistical Analysis on Existing Backtest Results

This script runs statistical validation on already-computed backtest results
stored in Delta tables. Use this to add statistical tests without re-running
expensive backtests.

Usage:
    # Analyze all commodities and models
    python run_statistical_analysis.py

    # Analyze specific commodity
    python run_statistical_analysis.py --commodity coffee

    # Analyze specific model
    python run_statistical_analysis.py --commodity coffee --model naive

    # Don't save to Delta (just print)
    python run_statistical_analysis.py --no-save
"""

import sys
import os
import argparse
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from production.analysis import StatisticalAnalyzer


def discover_existing_results(spark, commodity: Optional[str] = None) -> List[tuple]:
    """
    Discover existing year-by-year results tables

    Returns:
        List of (commodity, model_version) tuples
    """
    # Query Unity Catalog for tables matching pattern
    tables = spark.sql("""
        SHOW TABLES IN commodity.trading_agent
        LIKE 'results_*_by_year_*'
    """).collect()

    results = []
    for table_row in tables:
        table_name = table_row.tableName
        # Parse: results_{commodity}_by_year_{model}
        parts = table_name.replace('results_', '').replace('_by_year_', '|').split('|')
        if len(parts) == 2:
            table_commodity, model_version = parts
            if commodity is None or table_commodity == commodity:
                results.append((table_commodity, model_version))

    return sorted(results)


def main():
    """Main runner for standalone statistical analysis"""
    parser = argparse.ArgumentParser(
        description='Run statistical analysis on existing backtest results'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        help='Specific commodity to analyze (default: all)'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Specific model version to analyze (default: all for commodity)'
    )
    parser.add_argument(
        '--baseline',
        type=str,
        default='Immediate Sale',
        help='Baseline strategy for comparison (default: Immediate Sale)'
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save results to Delta tables (print only)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress detailed output (summary only)'
    )

    args = parser.parse_args()

    # Initialize Spark (assumes running in Databricks)
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    print("=" * 80)
    print("STATISTICAL ANALYSIS - Existing Backtest Results")
    print("=" * 80)

    # Discover existing results
    print("\nDiscovering existing results tables...")
    commodity_model_pairs = discover_existing_results(spark, args.commodity)

    if not commodity_model_pairs:
        print(f"❌ No results found" + (f" for commodity '{args.commodity}'" if args.commodity else ""))
        return 1

    print(f"✓ Found {len(commodity_model_pairs)} commodity-model combinations:")
    for commodity, model in commodity_model_pairs:
        print(f"  • {commodity} - {model}")

    # Filter by model if specified
    if args.model:
        commodity_model_pairs = [
            (c, m) for c, m in commodity_model_pairs if m == args.model
        ]
        if not commodity_model_pairs:
            print(f"\n❌ No results found for model '{args.model}'")
            return 1
        print(f"\n✓ Filtered to {len(commodity_model_pairs)} combinations matching model '{args.model}'")

    # Initialize analyzer
    analyzer = StatisticalAnalyzer(spark=spark)

    # Run analysis for each combination
    all_results = {}

    for commodity, model_version in commodity_model_pairs:
        try:
            print("\n" + "=" * 80)
            print(f"ANALYZING: {commodity.upper()} - {model_version}")
            print("=" * 80)

            # Run full statistical analysis
            results = analyzer.run_full_analysis(
                commodity=commodity,
                model_version=model_version,
                primary_baseline=args.baseline,
                verbose=not args.quiet
            )

            # Save results if requested
            if not args.no_save:
                table_name = analyzer.save_results(results, save_to_delta=True)
                if table_name:
                    results['saved_to'] = table_name

            # Store results
            if commodity not in all_results:
                all_results[commodity] = {}
            all_results[commodity][model_version] = results

        except Exception as e:
            print(f"\n❌ Error analyzing {commodity}/{model_version}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Print summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    total_tests = sum(
        len(results.get('strategy_vs_baseline_tests', [])) +
        len(results.get('matched_pair_tests', []))
        for commodity_results in all_results.values()
        for results in commodity_results.values()
    )

    print(f"\n✓ Analyzed {len(all_results)} commodities")
    print(f"✓ Total statistical tests: {total_tests}")

    # Print significant findings
    print("\n" + "=" * 80)
    print("SIGNIFICANT FINDINGS (p < 0.05)")
    print("=" * 80)

    found_significant = False
    for commodity, model_results in all_results.items():
        for model_version, results in model_results.items():
            best_pred = results.get('best_prediction_analysis')
            if best_pred and best_pred.get('significant_05'):
                found_significant = True
                print(f"\n✓ {commodity.upper()} - {model_version}")
                print(f"  Strategy: {best_pred['strategy']}")
                print(f"  Mean difference: ${best_pred['mean_difference']:,.0f}")
                print(f"  p-value: {best_pred['p_value']:.4f}")
                print(f"  Effect size: {best_pred['cohens_d']:.3f} ({best_pred['effect_interpretation']})")

    if not found_significant:
        print("\n⚠️  No statistically significant results found (all p ≥ 0.05)")
        print("\nMarginal findings (p < 0.10):")
        for commodity, model_results in all_results.items():
            for model_version, results in model_results.items():
                best_pred = results.get('best_prediction_analysis')
                if best_pred and 0.05 <= best_pred.get('p_value', 1.0) < 0.10:
                    print(f"\n  {commodity.upper()} - {model_version}")
                    print(f"    Strategy: {best_pred['strategy']}")
                    print(f"    p-value: {best_pred['p_value']:.4f}")

    if not args.no_save:
        print("\n" + "=" * 80)
        print("RESULTS SAVED TO DELTA TABLES")
        print("=" * 80)
        for commodity, model_results in all_results.items():
            for model_version, results in model_results.items():
                if 'saved_to' in results:
                    print(f"  • {results['saved_to']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
