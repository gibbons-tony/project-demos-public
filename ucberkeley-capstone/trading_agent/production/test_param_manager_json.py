"""
Quick test to validate parameter_manager JSON loading works correctly.
Tests the new JSON loading functionality added for orchestration.
"""

import sys
import os

# Add repo path for Databricks jobs (fixed path, not using __file__)
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from production.parameter_manager import ParameterManager

def test_parameter_manager():
    """Test that parameter manager can load JSON files."""

    print("=" * 80)
    print("TESTING PARAMETER MANAGER JSON LOADING")
    print("=" * 80)

    # Test 1: Create parameter manager
    print("\n[Test 1] Creating ParameterManager for coffee...")
    pm = ParameterManager(
        commodity='coffee',
        model_version='synthetic_acc90',
        optimization_objective='efficiency',
        verbose=True
    )
    print("✓ ParameterManager created successfully")

    # Test 2: Check if optimized params exist
    print("\n[Test 2] Checking if optimized parameters exist...")
    has_params = pm.has_optimized_params()
    print(f"  Has optimized params: {has_params}")

    # Test 3: Try to load params (latest version)
    print("\n[Test 3] Loading optimized parameters (latest)...")
    params = pm.load_optimized_params(version='latest')

    if params:
        print(f"✓ Loaded {len(params)} strategies")
        print(f"  Strategies: {list(params.keys())}")

        # Show one example
        if 'price_threshold' in params:
            print(f"\n  Example (price_threshold): {params['price_threshold']}")
    else:
        print("  No optimized parameters found (will use defaults)")

    # Test 4: Try to load previous version
    print("\n[Test 4] Loading optimized parameters (previous)...")
    prev_params = pm.load_optimized_params(version='previous')

    if prev_params:
        print(f"✓ Loaded previous version with {len(prev_params)} strategies")
    else:
        print("  No previous version found")

    # Test 5: Get baseline params
    print("\n[Test 5] Getting baseline parameters...")
    baseline = pm.get_baseline_params(source='auto')
    print(f"✓ Got {len(baseline)} baseline strategies")

    # Test 6: Get prediction params
    print("\n[Test 6] Getting prediction parameters...")
    prediction = pm.get_prediction_params(source='auto')
    print(f"✓ Got {len(prediction)} prediction strategies")

    # Test 7: Print summary
    print("\n[Test 7] Parameter summary...")
    pm.print_summary()

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED")
    print("=" * 80)

    return True

if __name__ == "__main__":
    try:
        success = test_parameter_manager()
        if success:
            print("\n✓ All tests passed - script completed successfully")
        else:
            print("\n✗ Tests failed - raising exception")
            raise RuntimeError("Test failures detected")
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise to signal failure to Databricks
