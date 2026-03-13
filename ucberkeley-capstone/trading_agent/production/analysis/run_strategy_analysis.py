"""
Strategy Analysis Orchestrator

Runs comprehensive strategy analysis using theoretical maximum benchmark.

This is the NEW analysis approach (separate from diagnostics/ which uses OLD paired t-test method).

Purpose:
    - Calculate theoretical maximum performance with perfect foresight
    - Evaluate strategy efficiency (actual vs theoretical max)
    - Identify opportunities for improvement

Usage:
    # Analyze single commodity-model combination
    python analysis/run_strategy_analysis.py --commodity coffee --model arima_v1

    # Compare all strategies for a commodity
    python analysis/run_strategy_analysis.py --commodity coffee --compare-all

    # Specify custom results location
    python analysis/run_strategy_analysis.py --commodity coffee --model arima_v1 \\
        --results-table commodity.trading_agent.results_coffee_arima_v1

Output:
    - Efficiency ratios for all strategies
    - Decision-by-decision comparisons
    - Critical decision analysis
    - Summary reports and visualizations
"""

import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
from pyspark.sql import functions as F

# Add parent directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

# Production imports
from production.config import (
    COMMODITY_CONFIGS,
    get_data_paths,
    VOLUME_PATH
)

# Analysis imports
from analysis.theoretical_max import TheoreticalMaxCalculator
from analysis.efficiency import EfficiencyAnalyzer


def load_data(spark, commodity, model_version):
    """
    Load price data and predictions for analysis.

    Args:
        spark: SparkSession
        commodity: str (e.g., 'coffee')
        model_version: str (e.g., 'arima_v1')

    Returns:
        Tuple of (prices_df, prediction_matrices)
    """
    print("\n" + "=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    # Load price data from unified_data (continuous daily coverage, forward-filled)
    # unified_data grain is (date, commodity, region) but price is same across regions
    # So aggregate by date to get one row per date
    print(f"\n1. Loading price data for {commodity}...")
    prices = spark.table("commodity.silver.unified_data").filter(
        f"lower(commodity) = '{commodity}'"
    ).groupBy("date").agg(
        F.first("close").alias("price")  # Price is same across regions
    ).toPandas()

    prices['date'] = pd.to_datetime(prices['date']).dt.normalize()
    prices = prices.sort_values('date').reset_index(drop=True)

    # Filter to recent data (2022+)
    prices = prices[prices['date'] >= '2022-01-01'].reset_index(drop=True)
    print(f"   ✓ Loaded {len(prices)} price points from {prices['date'].min()} to {prices['date'].max()}")

    # Load predictions
    print(f"\n2. Loading predictions for {commodity} - {model_version}...")

    # Try loading from production pickle files first
    data_paths = get_data_paths(commodity, model_version)
    pred_file = data_paths['prediction_matrices_real']

    try:
        import pickle
        with open(pred_file, 'rb') as f:
            prediction_matrices = pickle.load(f)
        print(f"   ✓ Loaded {len(prediction_matrices)} prediction matrices from pickle file")
    except FileNotFoundError:
        # Fallback: Load from predictions table
        print(f"   Pickle file not found, loading from table...")
        pred_table = f"commodity.trading_agent.predictions_{commodity}"
        pred_df = spark.table(pred_table).filter(
            f"model_version = '{model_version}'"
        ).toPandas()

        # Convert to matrix format
        pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
        prediction_matrices = {}

        for timestamp in pred_df['timestamp'].unique():
            ts_data = pred_df[pred_df['timestamp'] == timestamp]
            matrix = ts_data.pivot_table(
                index='run_id',
                columns='day_ahead',
                values='predicted_price',
                aggfunc='first'
            ).values
            date_key = pd.Timestamp(timestamp).normalize()
            prediction_matrices[date_key] = matrix

        print(f"   ✓ Loaded {len(prediction_matrices)} prediction matrices from table")

    return prices, prediction_matrices


def load_actual_results(spark, commodity, model_version, results_table=None):
    """
    Load actual strategy results for comparison.

    Args:
        spark: SparkSession
        commodity: str
        model_version: str
        results_table: Optional custom table name

    Returns:
        pd.DataFrame with strategy results
    """
    print("\n3. Loading actual strategy results...")

    if results_table is None:
        results_table = f"commodity.trading_agent.results_{commodity}_{model_version}"

    try:
        actual_results = spark.table(results_table).toPandas()
        print(f"   ✓ Loaded {len(actual_results)} strategy results from {results_table}")
        return actual_results
    except Exception as e:
        print(f"   ⚠️  Could not load results from {results_table}: {e}")
        print(f"   Run backtest workflow first to generate results.")
        return None


def run_analysis(commodity, model_version, spark, results_table=None):
    """
    Run complete strategy analysis.

    Args:
        commodity: str
        model_version: str
        spark: SparkSession
        results_table: Optional custom results table

    Returns:
        Dict with analysis results
    """
    print("=" * 80)
    print("STRATEGY ANALYSIS - THEORETICAL MAXIMUM BENCHMARK")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print(f"Commodity: {commodity}")
    print(f"Model Version: {model_version}")
    print("=" * 80)

    # Get commodity config
    if commodity not in COMMODITY_CONFIGS:
        raise ValueError(f"Unknown commodity: {commodity}. Available: {list(COMMODITY_CONFIGS.keys())}")

    config = COMMODITY_CONFIGS[commodity]

    # Load data
    prices, prediction_matrices = load_data(spark, commodity, model_version)
    actual_results = load_actual_results(spark, commodity, model_version, results_table)

    # Calculate theoretical maximum
    print("\n" + "=" * 80)
    print("CALCULATING THEORETICAL MAXIMUM")
    print("=" * 80)
    print("\nUsing dynamic programming to find optimal policy with perfect foresight...")

    calculator = TheoreticalMaxCalculator(
        prices_df=prices,
        predictions=prediction_matrices,
        config={
            'storage_cost_pct_per_day': config['storage_cost_pct_per_day'],
            'transaction_cost_pct': config['transaction_cost_pct']
        }
    )

    optimal_result = calculator.calculate_optimal_policy(
        initial_inventory=config['harvest_volume']
    )

    print(f"\n{'='*80}")
    print("THEORETICAL MAXIMUM (Perfect Foresight + Optimal Policy)")
    print(f"{'='*80}")
    print(f"Net Earnings:        ${optimal_result['total_net_earnings']:,.2f}")
    print(f"Total Revenue:       ${optimal_result['total_revenue']:,.2f}")
    print(f"Transaction Costs:   ${optimal_result['total_transaction_costs']:,.2f}")
    print(f"Storage Costs:       ${optimal_result['total_storage_costs']:,.2f}")
    print(f"Number of Trades:    {optimal_result['num_trades']}")

    # Calculate efficiency ratios
    if actual_results is not None:
        print("\n" + "=" * 80)
        print("EFFICIENCY ANALYSIS")
        print("=" * 80)

        analyzer = EfficiencyAnalyzer(optimal_result)
        efficiency_df = analyzer.calculate_efficiency_ratios(actual_results)

        print(f"\n{efficiency_df.to_string(index=False)}")

        # Generate summary report
        summary = analyzer.get_summary_report(efficiency_df)
        interpretation = analyzer.get_interpretation(summary)

        print(f"\n{interpretation}")

    else:
        efficiency_df = None
        summary = None
        interpretation = None

    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    output_dir = f"{VOLUME_PATH}/analysis"
    os.makedirs(output_dir, exist_ok=True)

    # Save optimal decisions
    decisions_df = pd.DataFrame(optimal_result['optimal_decisions'])
    decisions_file = f"{output_dir}/theoretical_max_decisions_{commodity}_{model_version}.csv"
    decisions_df.to_csv(decisions_file, index=False)
    print(f"✓ Saved optimal decisions to: {decisions_file}")

    # Save efficiency comparison
    if efficiency_df is not None:
        efficiency_file = f"{output_dir}/efficiency_analysis_{commodity}_{model_version}.csv"
        efficiency_df.to_csv(efficiency_file, index=False)
        print(f"✓ Saved efficiency analysis to: {efficiency_file}")

    # Save summary
    summary_data = {
        'timestamp': datetime.now(),
        'commodity': commodity,
        'model_version': model_version,
        'theoretical_max_result': optimal_result,
        'efficiency_df': efficiency_df,
        'summary': summary,
        'interpretation': interpretation
    }

    import pickle
    summary_file = f"{output_dir}/analysis_summary_{commodity}_{model_version}.pkl"
    with open(summary_file, 'wb') as f:
        pickle.dump(summary_data, f)
    print(f"✓ Saved summary to: {summary_file}")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print(f"Completed: {datetime.now()}")
    print("=" * 80)

    return {
        'theoretical_max_result': optimal_result,
        'efficiency_df': efficiency_df,
        'summary': summary,
        'interpretation': interpretation
    }


def main():
    parser = argparse.ArgumentParser(
        description='Run comprehensive strategy analysis with theoretical maximum benchmark'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        required=True,
        help='Commodity to analyze (e.g., coffee, sugar)'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Model version to analyze (e.g., arima_v1). If not specified with --compare-all, will analyze first available model.'
    )
    parser.add_argument(
        '--compare-all',
        action='store_true',
        help='Run analysis for all available models for the commodity'
    )
    parser.add_argument(
        '--results-table',
        type=str,
        help='Custom results table name (default: commodity.trading_agent.results_{commodity}_{model_version})'
    )

    args = parser.parse_args()

    # Initialize Spark
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("StrategyAnalysis").getOrCreate()
        print("✓ Spark session initialized")
    except Exception as e:
        print(f"Error initializing Spark: {e}")
        return 1

    # Validate commodity
    if args.commodity not in COMMODITY_CONFIGS:
        print(f"Error: Unknown commodity '{args.commodity}'")
        print(f"Available: {list(COMMODITY_CONFIGS.keys())}")
        return 1

    # Determine models to analyze
    if args.compare_all:
        # Discover all models for this commodity
        from production.config import get_model_versions
        model_versions = get_model_versions(args.commodity, spark)
        print(f"\nFound {len(model_versions)} models for {args.commodity}: {model_versions}")
    elif args.model:
        model_versions = [args.model]
    else:
        # Default to first available model
        from production.config import get_model_versions
        model_versions = get_model_versions(args.commodity, spark)
        if model_versions:
            model_versions = [model_versions[0]]
            print(f"\nNo model specified, using first available: {model_versions[0]}")
        else:
            print(f"Error: No models found for {args.commodity}")
            return 1

    # Run analysis for each model
    all_results = {}

    for model_version in model_versions:
        try:
            result = run_analysis(
                commodity=args.commodity,
                model_version=model_version,
                spark=spark,
                results_table=args.results_table
            )
            all_results[model_version] = result
        except Exception as e:
            print(f"\n✗ Analysis failed for {model_version}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if all_results:
        print(f"\n{'='*80}")
        print(f"SUMMARY: Analyzed {len(all_results)} model(s) successfully")
        print(f"{'='*80}")
        return 0
    else:
        print("\n✗ No analyses completed successfully")
        return 1


if __name__ == "__main__":
    sys.exit(main())
