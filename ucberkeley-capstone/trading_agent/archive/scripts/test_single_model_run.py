"""
Test Single Model Run - Verify end-to-end workflow

This script tests the complete workflow with a single model:
1. Connect to Databricks
2. Load data for one model
3. Run backtest
4. Save results
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis.model_runner import run_analysis_for_model

# Load environment variables
load_dotenv()

# Databricks connection
host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

# Configuration
COMMODITY_CONFIG = {
    'commodity': 'coffee',
    'harvest_volume': 50,
    'harvest_windows': [(5, 9)],
    'storage_cost_pct_per_day': 0.025,
    'transaction_cost_pct': 0.25
}

# Mock price data
def load_prices():
    """Load mock price data for testing."""
    dates = pd.date_range(start='2018-01-01', end='2020-12-31', freq='D')
    prices = pd.DataFrame({
        'date': dates,
        'price': 100 + np.random.randn(len(dates)).cumsum() * 0.5
    })
    prices.set_index('date', inplace=True)
    return prices

# Backtest function
def minimal_backtest(commodity, model_version, commodity_config, prices,
                     prediction_matrices, output_dir):
    """Minimal backtest for testing."""
    print(f"      Running minimal backtest...")

    n_dates = len(prediction_matrices)
    n_paths = list(prediction_matrices.values())[0].shape[0] if n_dates > 0 else 0

    # Calculate simple statistics
    all_medians = []
    for date, matrix in prediction_matrices.items():
        median_forecast = np.median(matrix, axis=0)
        all_medians.append(median_forecast.mean())

    results = {
        'metadata': {
            'commodity': commodity,
            'model_version': model_version,
            'n_forecast_dates': n_dates,
            'n_paths': n_paths,
        },
        'metrics': {
            'net_earnings': 12500.0 + np.random.randn() * 1000,
            'n_trades': 35,
            'avg_forecast': np.mean(all_medians) if all_medians else 0,
        }
    }

    print(f"      ✓ Backtest complete")
    print(f"         - {n_dates} forecast dates")
    print(f"         - {n_paths} simulation paths")
    print(f"         - Avg forecast: ${results['metrics']['avg_forecast']:.2f}")

    return results

# Main
print("=" * 80)
print("SINGLE MODEL TEST RUN")
print("=" * 80)
print()

print("1. Connecting to Databricks...")
connection = sql.connect(
    server_hostname=host,
    http_path=http_path,
    access_token=token
)
print("   ✓ Connected\n")

print("2. Loading price data...")
prices = load_prices()
print(f"   ✓ Loaded {len(prices)} days\n")

print("3. Running analysis for single model...")
print("-" * 80)

output_dir = "./output/test_single_model"
os.makedirs(output_dir, exist_ok=True)

result = run_analysis_for_model(
    commodity='coffee',
    model_version='sarimax_auto_weather_v1',
    connection=connection,
    commodity_config=COMMODITY_CONFIG,
    prices=prices,
    backtest_function=minimal_backtest,
    output_dir=output_dir,
    verbose=True
)

if result is not None:
    print("\n" + "=" * 80)
    print("✅ SINGLE MODEL TEST PASSED")
    print("=" * 80)
    print(f"\nExecution time: {result['execution_time']:.2f} seconds")
    print(f"Forecast dates: {result['backtest_results']['metadata']['n_forecast_dates']}")
    print(f"Simulation paths: {result['backtest_results']['metadata']['n_paths']}")
    print(f"Net earnings: ${result['backtest_results']['metrics']['net_earnings']:,.2f}")
    print()
    print("✅ Framework verified - ready for full multi-model analysis!")
else:
    print("\n❌ TEST FAILED")
    connection.close()
    sys.exit(1)

connection.close()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
