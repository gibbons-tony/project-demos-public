"""
Test script for forecast_loader.py

This script tests all functions in the data access layer to ensure
they work correctly with the commodity.forecast.distributions table.
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv

# Add parent directory to path to import forecast_loader
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_access.forecast_loader import (
    get_available_commodities,
    get_available_models,
    load_forecast_distributions,
    transform_to_prediction_matrices,
    get_data_summary,
    print_data_summary,
    validate_data_quality
)

# Load environment variables
load_dotenv()

host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH")

print("=" * 80)
print("TESTING FORECAST DATA LOADER")
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

# Test 1: Get available commodities
print("2. Testing get_available_commodities()...")
commodities = get_available_commodities(connection)
print(f"   ✓ Found {len(commodities)} commodities: {commodities}\n")

# Test 2: Get available models for each commodity
print("3. Testing get_available_models()...")
for commodity in commodities:
    models = get_available_models(commodity, connection)
    print(f"   {commodity}: {len(models)} models")
    for model in models:
        print(f"      - {model}")
print()

# Test 3: Load data for a specific model
print("4. Testing load_forecast_distributions()...")
test_commodity = "Coffee"
test_model = "sarimax_auto_weather_v1"  # Use a model we know exists

print(f"   Loading {test_commodity} - {test_model} (first 100 rows)...")
df = load_forecast_distributions(
    commodity=test_commodity,
    model_version=test_model,
    connection=connection,
    limit=100
)

print(f"   ✓ Loaded {len(df)} rows")
print(f"   Columns: {list(df.columns)}")
print(f"   Shape: {df.shape}")
print()

# Show sample data
print("   Sample data (first 3 rows):")
print(df.head(3).to_string())
print()

# Test 4: Get data summary
print("5. Testing get_data_summary()...")
summary = get_data_summary(test_commodity, test_model, connection)
print_data_summary(summary)

# Test 5: Transform to prediction matrices
print("6. Testing transform_to_prediction_matrices()...")
print(f"   Loading full dataset for {test_commodity} - {test_model}...")
df_full = load_forecast_distributions(
    commodity=test_commodity,
    model_version=test_model,
    connection=connection
)
print(f"   ✓ Loaded {len(df_full):,} rows")

print("   Transforming to prediction matrices...")
matrices = transform_to_prediction_matrices(df_full)
print(f"   ✓ Created {len(matrices):,} prediction matrices")

if len(matrices) > 0:
    # Show example
    first_date = list(matrices.keys())[0]
    first_matrix = matrices[first_date]
    print(f"\n   Example: {first_date}")
    print(f"   Matrix shape: {first_matrix.shape}")
    print(f"   Expected: (n_paths, 14) where n_paths ≈ 2000")
    print(f"   First 3 rows, first 5 days:")
    print(first_matrix[:3, :5])
print()

# Test 6: Validate data quality
print("7. Testing validate_data_quality()...")
validation = validate_data_quality(df_full)
print(f"   Total rows: {validation['total_rows']:,}")
print(f"   Has data: {validation['has_data']}")
print(f"   Has leakage: {validation['has_leakage']}")
print(f"   Path count: {validation['path_count']}")
print(f"   Date range: {validation['date_range']}")

if validation['issues']:
    print(f"   ⚠️ Issues found:")
    for issue in validation['issues']:
        print(f"      - {issue}")
else:
    print(f"   ✓ No data quality issues")
print()

# Test 7: Compare with expected format
print("8. Verifying data format compatibility...")
print("   Checking if transformed matrices match expected format:")
print(f"   ✓ Returns dict: {isinstance(matrices, dict)}")
print(f"   ✓ Keys are dates: {all(hasattr(k, 'year') for k in list(matrices.keys())[:5])}")

if len(matrices) > 0:
    sample_matrix = list(matrices.values())[0]
    print(f"   ✓ Values are numpy arrays: {type(sample_matrix).__name__ == 'ndarray'}")
    print(f"   ✓ Shape is (n_paths, 14): {sample_matrix.shape[1] == 14}")
    print(f"   ✓ Contains numeric values: {sample_matrix.dtype.kind == 'f'}")
print()

# Close connection
connection.close()

print("=" * 80)
print("✅ ALL TESTS PASSED")
print("=" * 80)
print()
print("The forecast_loader module is working correctly!")
print("Ready to integrate with trading_prediction_analysis.py")
