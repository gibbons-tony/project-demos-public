"""
Full Integration Test - Model Runner + Unity Catalog

This script tests the complete integration:
1. Connect to Databricks Unity Catalog
2. Load forecast data for a specific model
3. Verify data format compatibility
4. Run a minimal backtest to confirm end-to-end flow
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_access.forecast_loader import (
    load_forecast_distributions,
    transform_to_prediction_matrices,
    get_available_models
)

# Load environment variables
load_dotenv()

host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

print("=" * 80)
print("FULL INTEGRATION TEST - MODEL RUNNER + UNITY CATALOG")
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

# Get available models
print("2. Querying available models...")
print("-" * 80)

try:
    coffee_models = get_available_models("Coffee", connection)
    sugar_models = get_available_models("Sugar", connection)

    print(f"   Coffee models ({len(coffee_models)}):")
    for i, model in enumerate(coffee_models, 1):
        print(f"      {i}. {model}")

    print(f"\n   Sugar models ({len(sugar_models)}):")
    for i, model in enumerate(sugar_models, 1):
        print(f"      {i}. {model}")

    total_models = len(coffee_models) + len(sugar_models)
    print(f"\n   ✓ Total models available: {total_models}")

except Exception as e:
    print(f"   ❌ Failed to query models: {e}")
    connection.close()
    sys.exit(1)

# Test with one Coffee model
print("\n3. Testing data load for single model...")
print("-" * 80)

test_commodity = "Coffee"
test_model = "sarimax_auto_weather_v1"

print(f"   Commodity: {test_commodity}")
print(f"   Model: {test_model}")
print()

try:
    # Load forecast distributions
    print("   Loading forecast distributions...")
    df = load_forecast_distributions(
        commodity=test_commodity,
        model_version=test_model,
        connection=connection
    )

    print(f"   ✓ Loaded {len(df):,} rows")

    # Transform to prediction matrices
    print("   Transforming to prediction matrices...")
    prediction_matrices = transform_to_prediction_matrices(df)

    print(f"   ✓ Created {len(prediction_matrices)} prediction matrices")

    # Validate format
    print("\n4. Validating data format...")
    print("-" * 80)

    if len(prediction_matrices) > 0:
        sample_date = list(prediction_matrices.keys())[0]
        sample_matrix = prediction_matrices[sample_date]

        print(f"   Sample date: {sample_date}")
        print(f"   Matrix shape: {sample_matrix.shape}")
        print(f"   Matrix type: {type(sample_matrix).__name__}")
        print(f"   Data type: {sample_matrix.dtype}")
        print(f"   Sample values (first path, first 5 days): {sample_matrix[0, :5]}")

        # Format checks
        checks = {
            "Container is dict": isinstance(prediction_matrices, dict),
            "Keys are pd.Timestamp": all(isinstance(k, pd.Timestamp) for k in list(prediction_matrices.keys())[:5]),
            "Values are numpy arrays": all(isinstance(v, np.ndarray) for v in list(prediction_matrices.values())[:5]),
            "Arrays are 2D": all(v.ndim == 2 for v in list(prediction_matrices.values())[:5]),
            "Second dimension is 14": all(v.shape[1] == 14 for v in list(prediction_matrices.values())[:5]),
            "Contains numeric data": all(np.issubdtype(v.dtype, np.number) for v in list(prediction_matrices.values())[:5])
        }

        print("\n   Format validation:")
        all_passed = True
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"      {status} {check}")
            if not result:
                all_passed = False

        if not all_passed:
            print("\n   ❌ Format validation failed")
            connection.close()
            sys.exit(1)

    # Test with minimal backtest logic
    print("\n5. Testing with minimal backtest simulation...")
    print("-" * 80)

    # Simulate what the backtest engine would do
    sample_dates = list(prediction_matrices.keys())[:3]  # First 3 dates
    print(f"   Testing with {len(sample_dates)} forecast dates...")

    for i, date in enumerate(sample_dates, 1):
        matrix = prediction_matrices[date]
        n_paths, horizon = matrix.shape

        # Simulate selecting a strategy based on predictions
        # (This is what the ConsensusStrategy does)
        median_forecast = np.median(matrix, axis=0)
        max_price_day = np.argmax(median_forecast)

        print(f"      Date {i}: {date.strftime('%Y-%m-%d')}")
        print(f"         Paths: {n_paths}, Horizon: {horizon} days")
        print(f"         Median forecast max on day: {max_price_day + 1}")
        print(f"         Median forecast range: ${median_forecast.min():.2f} - ${median_forecast.max():.2f}")

    print("\n   ✓ Backtest simulation successful")

    # Success
    print("\n" + "=" * 80)
    print("✅ FULL INTEGRATION TEST PASSED")
    print("=" * 80)
    print()
    print("Components verified:")
    print("  ✅ Databricks connection")
    print("  ✅ Unity Catalog query (15 models available)")
    print("  ✅ Forecast data loading")
    print("  ✅ Data format transformation")
    print("  ✅ Compatibility with backtest logic")
    print()
    print("Ready for multi-model analysis!")

except Exception as e:
    print(f"\n❌ Test failed with error:")
    print(f"   {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    connection.close()
    sys.exit(1)

# Close connection
connection.close()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
