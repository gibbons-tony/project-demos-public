#!/usr/bin/env python3
"""
Test script for parameter optimizer

Tests:
1. Loading predictions and prices
2. Running Optuna optimization
3. Generating optimized parameters
4. Saving results

Full-scale production optimization:
- All 10 strategies
- 200 trials per strategy (standard Optuna optimization)
- Coffee + synthetic_acc90 (validated data)
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
from analysis.optimization.run_parameter_optimization import run_optimization

def test_optimizer(commodity='coffee', model_version='synthetic_acc90'):
    """Test optimizer with minimal configuration."""

    print(f"\n{'='*80}")
    print(f"TESTING PARAMETER OPTIMIZER - {commodity.upper()}")
    print(f"{'='*80}\n")

    # Get Spark session
    try:
        spark = SparkSession.builder.getOrCreate()
        print(f"✓ Got Spark session")
    except Exception as e:
        print(f"❌ ERROR getting Spark session: {e}")
        return False

    # Run full-scale optimization
    print(f"\nRunning FULL-SCALE optimization...")
    print(f"  Commodity: {commodity}")
    print(f"  Model: {model_version}")
    print(f"  Strategies: ALL 10 strategies (baseline + prediction + MPC)")
    print(f"  Trials: 200 per strategy (2000 total)")
    print(f"  Objective: earnings (maximize absolute net earnings)")

    try:
        results = run_optimization(
            commodity=commodity,
            model_version=model_version,
            objective='earnings',  # Production objective
            n_trials=200,  # Full-scale optimization
            strategy_filter=None,  # Optimize ALL strategies
            spark=spark
        )

        print(f"\n✅ Optimization completed successfully")
        print(f"\nResults summary:")
        if results and 'best_params' in results:
            for strategy_name, params in results['best_params'].items():
                print(f"  {strategy_name}:")
                for param, value in params.items():
                    print(f"    {param}: {value}")

        return True

    except Exception as e:
        print(f"\n❌ ERROR during optimization: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # Test with coffee and synthetic_acc90
    success = test_optimizer('coffee', 'synthetic_acc90')

    if success:
        print(f"\n{'='*80}")
        print("✅ OPTIMIZER TEST COMPLETE")
        print(f"{'='*80}\n")
        # Note: Don't use sys.exit() in Databricks jobs - just let script complete
    else:
        print(f"\n{'='*80}")
        print("❌ OPTIMIZER TEST FAILED")
        print(f"{'='*80}\n")
        raise RuntimeError("Optimizer test failed")
