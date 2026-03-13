"""
Step 5: Statistical Analysis of Backtest Results

Runs comprehensive statistical tests on backtest results to validate that prediction-based
strategies significantly outperform baselines.

Uses enhanced statistical framework with:
- Data validation (pre-test diagnostics)
- Parametric tests (paired t-test, confidence intervals, effect sizes)
- Non-parametric tests (permutation test, sign test, bootstrap CI)
- Multiple testing correction (Holm method)
- Multi-granularity analysis (annual, quarterly, monthly)
- Assumption validation (normality checks)

See: STATISTICAL_RIGOR_FOR_DATA_SCIENTISTS.md and MULTI_GRANULARITY_ANALYSIS.md

Usage:
    # Run for all models of a commodity
    python production/analysis/run_statistical_analysis.py \\
        --commodity coffee \\
        --model-version all \\
        --verbose true

    # Run for specific model
    python production/analysis/run_statistical_analysis.py \\
        --commodity coffee \\
        --model-version naive \\
        --verbose true
"""

import sys
import argparse
from datetime import datetime

# Imports
from pyspark.sql import SparkSession

# Handle imports for both local and Databricks environments
try:
    from production.analysis.statistical_tests import StatisticalAnalyzer
except ImportError:
    # Databricks repos path
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')
    from production.analysis.statistical_tests import StatisticalAnalyzer


def main():
    parser = argparse.ArgumentParser(
        description="Run statistical analysis on backtest results"
    )
    parser.add_argument(
        '--commodity',
        type=str,
        required=True,
        help='Commodity to analyze (e.g., coffee)'
    )
    parser.add_argument(
        '--model-version',
        type=str,
        default='all',
        help='Model version to analyze (or "all" for all models)'
    )
    parser.add_argument(
        '--primary-baseline',
        type=str,
        default='Immediate Sale',
        help='Primary baseline strategy name'
    )
    parser.add_argument(
        '--verbose',
        type=str,
        default='true',
        help='Print detailed output (true/false)'
    )

    args = parser.parse_args()

    # Parse boolean
    verbose = args.verbose.lower() == 'true'

    print("=" * 80)
    print("STEP 5: STATISTICAL ANALYSIS OF BACKTEST RESULTS")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Commodity: {args.commodity}")
    print(f"Model version: {args.model_version}")
    print(f"Primary baseline: {args.primary_baseline}")
    print(f"Verbose: {verbose}")
    print("=" * 80)
    print()

    # Initialize Spark
    print("Initializing Spark session...")
    spark = SparkSession.builder \
        .appName(f"Statistical Analysis - {args.commodity}") \
        .getOrCreate()
    print("✓ Spark session initialized")
    print()

    # Initialize analyzer
    analyzer = StatisticalAnalyzer(spark=spark)

    # Determine which models to analyze
    if args.model_version.lower() == 'all':
        # Get all models for this commodity
        print(f"Discovering available models for {args.commodity}...")

        # Query all tables and filter in Python
        # Note: LIKE with _ matches single char, so we filter in Python instead
        all_tables = spark.sql("SHOW TABLES IN commodity.trading_agent").collect()

        model_versions = []
        prefix = f"results_{args.commodity}_by_year_"

        for row in all_tables:
            table_name = row.tableName
            # Extract model version from table name: results_coffee_by_year_<model>
            if table_name.startswith(prefix):
                model_version = table_name[len(prefix):]
                model_versions.append(model_version)

        if not model_versions:
            print(f"⚠️  No results tables found for {args.commodity}")
            print("Step 4 backtesting may not have completed successfully.")
            sys.exit(1)

        print(f"✓ Found {len(model_versions)} models: {model_versions}")
        print()
    else:
        model_versions = [args.model_version]

    # Run analysis for each model
    all_results = {}

    for model_version in model_versions:
        print("=" * 80)
        print(f"ANALYZING: {args.commodity.upper()} - {model_version}")
        print("=" * 80)
        print()

        try:
            # Run full statistical analysis
            results = analyzer.run_full_analysis(
                commodity=args.commodity,
                model_version=model_version,
                primary_baseline=args.primary_baseline,
                verbose=verbose
            )

            all_results[model_version] = results

            print()
            print("=" * 80)
            print(f"✓ Analysis complete for {model_version}")
            print("=" * 80)
            print()

        except Exception as e:
            print(f"✗ Error analyzing {model_version}: {str(e)}")
            import traceback
            traceback.print_exc()
            print()

    # Summary across all models
    if len(model_versions) > 1:
        print("=" * 80)
        print("CROSS-MODEL SUMMARY")
        print("=" * 80)
        print()

        for model_version, results in all_results.items():
            best_strategy = results.get('best_strategy_name', 'Unknown')
            p_value = results.get('best_strategy_p_value', 1.0)
            improvement = results.get('best_strategy_improvement', 0.0)

            sig_marker = "✓" if p_value < 0.05 else "✗"

            print(f"{model_version:30s} | Best: {best_strategy:25s} | "
                  f"Improvement: ${improvement:10,.0f} | "
                  f"p={p_value:.4f} {sig_marker}")

        print()

    print("=" * 80)
    print("STEP 5 COMPLETE")
    print("=" * 80)
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check if any errors occurred
    if len(all_results) < len(model_versions):
        print(f"⚠️  Warning: {len(model_versions) - len(all_results)} models failed analysis")
        sys.exit(1)
    else:
        print(f"✓ Successfully analyzed {len(model_versions)} models")


if __name__ == '__main__':
    main()
