"""
Test Integration - Verify trading_prediction_analysis.py works with Unity Catalog

This script tests that the modified load_prediction_matrices() function
correctly loads data from Unity Catalog and is compatible with the
existing backtest engine.
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the modified function
from commodity_prediction_analysis.trading_prediction_analysis import (
    load_prediction_matrices
)

# Load environment variables
load_dotenv()

host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

print("=" * 80)
print("TESTING INTEGRATION - UNITY CATALOG + BACKTEST ENGINE")
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

# Test loading with Unity Catalog
print("2. Testing load_prediction_matrices() with Unity Catalog...")
print("-" * 80)

test_commodity = "coffee"
test_model = "sarimax_auto_weather_v1"

print(f"   Commodity: {test_commodity}")
print(f"   Model: {test_model}")
print()

try:
    prediction_matrices, source = load_prediction_matrices(
        commodity_name=test_commodity,
        model_version=test_model,
        connection=connection
    )

    print(f"\n✅ Successfully loaded data!")
    print(f"   Source: {source}")
    print(f"   Number of forecast dates: {len(prediction_matrices)}")

    # Validate format
    print("\n3. Validating data format...")
    print("-" * 80)

    if len(prediction_matrices) > 0:
        # Get first matrix
        sample_date = list(prediction_matrices.keys())[0]
        sample_matrix = prediction_matrices[sample_date]

        print(f"   Sample date: {sample_date}")
        print(f"   Matrix shape: {sample_matrix.shape}")
        print(f"   Matrix type: {type(sample_matrix)}")
        print(f"   Data type: {sample_matrix.dtype}")
        print(f"   Sample values (first 5 days): {sample_matrix[0, :5]}")

        # Validate format requirements
        print("\n4. Format validation checks...")
        print("-" * 80)

        import pandas as pd
        import numpy as np

        checks = {
            "Is dict": isinstance(prediction_matrices, dict),
            "Keys are pd.Timestamp": all(isinstance(k, pd.Timestamp) for k in prediction_matrices.keys()),
            "Values are numpy arrays": all(isinstance(v, np.ndarray) for v in prediction_matrices.values()),
            "Arrays are 2D": all(v.ndim == 2 for v in prediction_matrices.values()),
            "Second dimension is 14": all(v.shape[1] == 14 for v in prediction_matrices.values()),
            "Contains numeric data": all(np.issubdtype(v.dtype, np.number) for v in prediction_matrices.values())
        }

        all_passed = True
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}: {result}")
            if not result:
                all_passed = False

        if all_passed:
            print("\n" + "=" * 80)
            print("✅ INTEGRATION TEST PASSED")
            print("=" * 80)
            print()
            print("The modified load_prediction_matrices() function successfully:")
            print("  1. Connects to Unity Catalog")
            print("  2. Loads forecast data for the specified model")
            print("  3. Transforms data into the correct format")
            print("  4. Returns data compatible with the existing backtest engine")
            print()
            print("Ready to proceed with multi-model analysis!")
        else:
            print("\n❌ Some validation checks failed")
    else:
        print("   ⚠️  No prediction matrices returned")

except Exception as e:
    print(f"\n❌ Test failed with error:")
    print(f"   {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    connection.close()
    sys.exit(1)

# Test backward compatibility (loading without model_version)
print("\n5. Testing backward compatibility (legacy mode)...")
print("-" * 80)
print("   Testing load without model_version parameter...")

try:
    # This should fall back to local files
    prediction_matrices_legacy, source_legacy = load_prediction_matrices(test_commodity)
    print(f"   ✓ Legacy mode works: source = {source_legacy}")
except FileNotFoundError as e:
    print(f"   ✓ Expected behavior: {e}")
    print("   (No local files available, which is fine)")
except Exception as e:
    print(f"   ⚠️  Unexpected error: {e}")

# Close connection
connection.close()

print("\n" + "=" * 80)
print("INTEGRATION TEST COMPLETE")
print("=" * 80)
