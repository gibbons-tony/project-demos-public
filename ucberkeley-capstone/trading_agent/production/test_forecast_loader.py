#!/usr/bin/env python3
"""
Test script for forecast prediction loader

Tests:
1. Loading real predictions from commodity.forecast.distributions
2. Sparsity checking (automatically skips sparse forecasts)
3. Matrix format transformation
4. Pickle file output
"""
import sys
from pathlib import Path

# Add parent directory to path
try:
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir.parent))
except NameError:
    # __file__ not defined in Databricks jobs
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from production.config import COMMODITY_CONFIGS, get_model_versions
from production.scripts.load_forecast_predictions import process_model_version

def test_forecast_loader(commodity='coffee'):
    """Test forecast loader with automatic sparsity checking."""

    print(f"\n{'='*80}")
    print(f"TESTING FORECAST LOADER - {commodity.upper()}")
    print(f"{'='*80}\n")

    # Get Spark session
    try:
        spark = SparkSession.builder.getOrCreate()
        print(f"✓ Got Spark session")
    except Exception as e:
        print(f"❌ ERROR getting Spark session: {e}")
        return False

    # Discover available models
    print(f"\nDiscovering available forecast models for {commodity}...")
    try:
        available_models = get_model_versions(commodity, spark)
        print(f"✓ Found {len(available_models)} model version(s)")

        if not available_models:
            print(f"\n⚠️  No forecast models found for {commodity}")
            print(f"   This is expected if no real forecasts have been generated yet")
            return True  # Not a failure, just no data

        for model in available_models:
            print(f"  - {model}")

    except Exception as e:
        print(f"❌ ERROR discovering models: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Process each model
    processed_count = 0
    skipped_count = 0

    for model_version in available_models:
        print(f"\n{'-'*80}")
        print(f"Testing: {commodity} - {model_version}")
        print(f"{'-'*80}")

        try:
            result = process_model_version(commodity, model_version, spark)

            if result is None:
                print(f"⚠️  Skipped (sparse forecast)")
                skipped_count += 1
            else:
                print(f"✅ Successfully processed")
                print(f"   Quality: {result['quality']}")
                print(f"   Matrices: {result['n_matrices']}")
                print(f"   Runs per date: {result['avg_runs_per_date']:.1f}")
                print(f"   Output: {result['output_path']}")
                processed_count += 1

        except Exception as e:
            print(f"❌ ERROR processing {model_version}: {e}")
            import traceback
            traceback.print_exc()
            return False

    # Summary
    print(f"\n{'='*80}")
    print(f"FORECAST LOADER TEST SUMMARY")
    print(f"{'='*80}\n")
    print(f"  Total models found: {len(available_models)}")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Skipped (sparse): {skipped_count}")

    if processed_count > 0:
        print(f"\n✅ FORECAST LOADER TEST PASSED")
        print(f"   {processed_count} well-populated forecast(s) loaded successfully")
        return True
    elif skipped_count > 0:
        print(f"\n⚠️  TEST COMPLETED - All forecasts were sparse")
        print(f"   {skipped_count} forecast(s) skipped due to insufficient coverage")
        print(f"   This is expected if forecasts are still being generated")
        return True
    else:
        print(f"\n⚠️  No forecasts to test")
        return True

if __name__ == '__main__':
    # Test with coffee
    success = test_forecast_loader('coffee')

    if success:
        print(f"\n{'='*80}")
        print("✅ FORECAST LOADER TEST COMPLETE")
        print(f"{'='*80}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*80}")
        print("❌ FORECAST LOADER TEST FAILED")
        print(f"{'='*80}\n")
        sys.exit(1)
