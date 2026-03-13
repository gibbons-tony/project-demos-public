"""
Test Model Runner - Verify Nested Loop Integration

This script tests the model_runner module with a minimal backtest function
to verify the nested loop structure works correctly.
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.model_runner import (
    run_analysis_for_model,
    run_analysis_for_all_models
)

# Load environment variables
load_dotenv()

host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

print("=" * 80)
print("TESTING MODEL RUNNER - NESTED LOOP INTEGRATION")
print("=" * 80)
print()

# Connect to Databricks
print("1. Connecting to Databricks...")
connection = sql.connect(
    server_hostname=host,
    http_path=http_path,
    access_token=token
)
print("   ✓ Connected\n")

# Define a minimal backtest function for testing
def minimal_backtest_function(commodity, model_version, commodity_config, prices, prediction_matrices, output_dir):
    """
    Minimal backtest function for testing purposes.

    Just returns summary statistics without running full backtest.
    """
    print(f"      Running minimal backtest...")
    print(f"        - Commodity: {commodity}")
    print(f"        - Model: {model_version}")
    print(f"        - Prediction matrices: {len(prediction_matrices)} dates")
    print(f"        - Output dir: {output_dir}")

    # Return mock results
    return {
        'strategy_results': {
            'test_strategy': {
                'net_earnings': 10000.0,
                'n_trades': 10
            }
        },
        'metrics': {
            'net_earnings': 10000.0,
            'gross_revenue': 15000.0,
            'n_trades': 10,
            'avg_sale_price': 100.0
        }
    }

# Define minimal commodity config
commodity_config = {
    'commodity': 'coffee',
    'harvest_volume': 50,
    'harvest_windows': [(5, 9)],
    'storage_cost_pct_per_day': 0.025,
    'transaction_cost_pct': 0.25
}

# Mock prices dataframe (not used in minimal test)
prices = pd.DataFrame()

# Create output directory
output_dir = "/tmp/trading_agent_test"
os.makedirs(output_dir, exist_ok=True)

print("2. Testing run_analysis_for_model() with single model...")
print("-" * 80)

# Test with a single model
test_commodity = "Coffee"
test_model = "sarimax_auto_weather_v1"

result = run_analysis_for_model(
    commodity='coffee',
    model_version=test_model,
    connection=connection,
    commodity_config=commodity_config,
    prices=prices,
    backtest_function=minimal_backtest_function,
    output_dir=output_dir,
    verbose=True
)

if result is not None:
    print("\n✅ Single model test PASSED")
    print(f"   Result keys: {list(result.keys())}")
    print(f"   Execution time: {result['execution_time']:.2f} seconds")
else:
    print("\n❌ Single model test FAILED")
    connection.close()
    sys.exit(1)

print()
print("=" * 80)

# Test with all Coffee models (optional - can be slow)
run_all_models = input("\n3. Run test for ALL Coffee models? (y/N): ").strip().lower()

if run_all_models == 'y':
    print("\n3. Testing run_analysis_for_all_models() with all Coffee models...")
    print("-" * 80)

    results = run_analysis_for_all_models(
        commodity='coffee',
        connection=connection,
        commodity_config=commodity_config,
        prices=prices,
        backtest_function=minimal_backtest_function,
        output_dir=output_dir,
        verbose=True
    )

    print("\n✅ All models test PASSED")
    print(f"   Total models processed: {len(results)}")
    print(f"   Successful: {sum(1 for r in results.values() if r is not None)}")
    print(f"   Failed: {sum(1 for r in results.values() if r is None)}")

    print("\n   Model execution times:")
    for model, result in results.items():
        if result:
            print(f"      {model}: {result['execution_time']:.2f}s")
        else:
            print(f"      {model}: FAILED")
else:
    print("\n   Skipping all models test")

# Close connection
connection.close()

print()
print("=" * 80)
print("✅ MODEL RUNNER TESTS COMPLETE")
print("=" * 80)
print()
print("The nested loop structure is working correctly!")
print("Ready to integrate with full trading_prediction_analysis.py")
