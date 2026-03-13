"""
Multi-Model Trading Analysis Runner

This script orchestrates backtesting analysis across all commodity/model combinations:
- Coffee: 10 models
- Sugar: 5 models
- Total: 15 backtest runs

For each combination, it:
1. Loads forecast data from Unity Catalog
2. Runs backtest with all trading strategies
3. Saves detailed results and metrics
4. Generates comparison summaries

Results are saved to: ./output/multi_model_analysis/
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis.model_runner import (
    run_analysis_for_model,
    run_analysis_for_all_models,
    run_analysis_for_all_commodities,
    compare_model_performance
)

from data_access.forecast_loader import (
    get_available_models,
    get_available_commodities
)

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Databricks connection
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

# Output directory
OUTPUT_BASE_DIR = "./output/multi_model_analysis"
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

# Commodity configurations (matching trading_prediction_analysis.py)
COMMODITY_CONFIGS = {
    'coffee': {
        'commodity': 'coffee',
        'harvest_volume': 50,
        'harvest_windows': [(5, 9)],  # May-September
        'storage_cost_pct_per_day': 0.025,  # 2.5% per day
        'transaction_cost_pct': 0.25  # 0.25% transaction cost
    },
    'sugar': {
        'commodity': 'sugar',
        'harvest_volume': 50,
        'harvest_windows': [(4, 9)],  # April-September
        'storage_cost_pct_per_day': 0.020,  # 2.0% per day
        'transaction_cost_pct': 0.25  # 0.25% transaction cost
    }
}

# =============================================================================
# PRICE DATA LOADING
# =============================================================================

def load_price_data(commodity_name, connection):
    """
    Load historical price data for backtesting.

    TODO: Replace this with actual price data query from Unity Catalog
    For now, returns mock data for testing.
    """
    print(f"   Loading price data for {commodity_name}...")

    # Mock price data - replace with actual query
    # In production, this would query from commodity.prices or similar table
    dates = pd.date_range(start='2018-01-01', end='2020-12-31', freq='D')
    prices = pd.DataFrame({
        'date': dates,
        'price': 100 + np.random.randn(len(dates)).cumsum() * 0.5
    })
    prices.set_index('date', inplace=True)

    print(f"   ✓ Loaded {len(prices)} days of price data")
    return prices

# =============================================================================
# BACKTEST FUNCTION
# =============================================================================

def run_backtest(commodity, model_version, commodity_config, prices,
                 prediction_matrices, output_dir):
    """
    Run backtest analysis for a single commodity/model combination.

    This function integrates with the existing backtest engine from
    trading_prediction_analysis.py.

    Args:
        commodity: str - Commodity name ('coffee', 'sugar')
        model_version: str - Model identifier
        commodity_config: dict - Commodity parameters
        prices: DataFrame - Historical prices
        prediction_matrices: dict - Forecast predictions
        output_dir: str - Output directory for results

    Returns:
        dict - Backtest results with metrics and strategy performance
    """
    print(f"      Running backtest for {commodity} - {model_version}...")

    # TODO: Integrate actual backtest engine from trading_prediction_analysis.py
    # For now, return mock results structure

    # This would normally:
    # 1. Initialize BacktestEngine with prices, prediction_matrices, config
    # 2. Run each strategy (ConsensusStrategy, AggregateStrategy, etc.)
    # 3. Calculate metrics (earnings, Sharpe ratio, win rate, etc.)
    # 4. Perform statistical analysis (bootstrap CI, t-tests, etc.)
    # 5. Save detailed results

    n_forecast_dates = len(prediction_matrices)
    n_paths = list(prediction_matrices.values())[0].shape[0] if n_forecast_dates > 0 else 0

    # Mock results structure
    results = {
        'metadata': {
            'commodity': commodity,
            'model_version': model_version,
            'n_forecast_dates': n_forecast_dates,
            'n_paths': n_paths,
            'backtest_start': min(prediction_matrices.keys()) if n_forecast_dates > 0 else None,
            'backtest_end': max(prediction_matrices.keys()) if n_forecast_dates > 0 else None,
        },
        'strategy_results': {
            'consensus': {
                'net_earnings': 12500.0,
                'gross_revenue': 15000.0,
                'total_costs': 2500.0,
                'n_trades': 35,
                'win_rate': 0.68,
                'avg_sale_price': 105.2,
                'sharpe_ratio': 1.45,
            },
            'aggregate': {
                'net_earnings': 11800.0,
                'gross_revenue': 14500.0,
                'total_costs': 2700.0,
                'n_trades': 38,
                'win_rate': 0.65,
                'avg_sale_price': 104.8,
                'sharpe_ratio': 1.38,
            },
            'oracle': {
                'net_earnings': 18000.0,
                'gross_revenue': 20000.0,
                'total_costs': 2000.0,
                'n_trades': 30,
                'win_rate': 0.85,
                'avg_sale_price': 108.5,
                'sharpe_ratio': 2.10,
            },
        },
        'statistical_analysis': {
            'bootstrap_ci_95': {
                'net_earnings': (11800, 13200),
                'sharpe_ratio': (1.30, 1.60)
            },
            't_test_vs_baseline': {
                't_statistic': 3.45,
                'p_value': 0.0012
            }
        },
        'harvest_analysis': {
            'total_harvest': commodity_config['harvest_volume'] * n_forecast_dates,
            'sold_in_harvest': 0.15,
            'sold_after_harvest': 0.85,
            'avg_storage_days': 42
        }
    }

    # Save results to file
    output_file = os.path.join(output_dir, f"{commodity}_{model_version}_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"      ✓ Results saved to: {output_file}")

    return results

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution function."""

    print("=" * 80)
    print("MULTI-MODEL TRADING ANALYSIS")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {OUTPUT_BASE_DIR}")
    print("=" * 80)
    print()

    # Connect to Databricks
    print("1. Connecting to Databricks Unity Catalog...")
    connection = sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )
    print("   ✓ Connected\n")

    # Verify available models
    print("2. Querying available models...")
    print("-" * 80)

    all_models = {}
    for commodity in ['Coffee', 'Sugar']:
        models = get_available_models(commodity, connection)
        all_models[commodity.lower()] = models
        print(f"   {commodity}: {len(models)} models")
        for model in models:
            print(f"      - {model}")

    total_runs = sum(len(models) for models in all_models.values())
    print(f"\n   ✓ Total analysis runs: {total_runs}")
    print()

    # Load price data for each commodity
    print("3. Loading price data...")
    print("-" * 80)

    prices_dict = {}
    for commodity in COMMODITY_CONFIGS.keys():
        prices = load_price_data(commodity, connection)
        prices_dict[commodity] = prices

    print()

    # Run analysis for all commodities and models
    print("4. Running multi-model analysis...")
    print("=" * 80)

    start_time = datetime.now()

    all_results = run_analysis_for_all_commodities(
        commodity_configs=COMMODITY_CONFIGS,
        connection=connection,
        prices_dict=prices_dict,
        backtest_function=run_backtest,
        output_base_dir=OUTPUT_BASE_DIR,
        verbose=True
    )

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # Compare model performance
    print("\n5. Comparing model performance...")
    print("=" * 80)

    comparison = compare_model_performance(all_results)
    comparison_df = comparison.get('comparison_table')

    if comparison_df is not None and len(comparison_df) > 0:
        print("\nModel Performance Summary:")
        print("-" * 80)
        print(comparison_df.to_string())

        # Save comparison to CSV
        comparison_file = os.path.join(OUTPUT_BASE_DIR, "model_comparison.csv")
        comparison_df.to_csv(comparison_file, index=False)
        print(f"\n✓ Comparison saved to: {comparison_file}")

    # Final summary
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total execution time: {elapsed_time / 60:.1f} minutes")
    print(f"Results directory: {OUTPUT_BASE_DIR}")
    print("=" * 80)

    # Close connection
    connection.close()

    print("\n✅ Multi-model analysis completed successfully!")
    print("\nNext steps:")
    print("  1. Review results in: " + OUTPUT_BASE_DIR)
    print("  2. Create interactive dashboard for visualization")
    print("  3. Compare model performance across commodities")

if __name__ == "__main__":
    main()
