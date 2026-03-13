"""
Test Step 3: Run Optimization with Fixed Parameters

This tests the optimization step independently to diagnose what's failing
when running with the complete analysis flow.
"""

import sys
import os

# Setup path for imports
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/scripts'

trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
if trading_agent_dir not in sys.path:
    sys.path.insert(0, trading_agent_dir)

from pyspark.sql import SparkSession
from production.optimization.run_parameter_optimization import run_optimization

print("=" * 80)
print("TEST STEP 3: OPTIMIZATION")
print("=" * 80)

# Initialize Spark
spark = SparkSession.builder.appName("TestStep3Optimization").getOrCreate()

# Run optimization for coffee only (same as complete flow)
commodity = 'coffee'
objective = 'efficiency'
n_trials = 100  # Same as in complete_analysis_flow.py

print(f"\nOptimizing parameters for {commodity.upper()}...")
print(f"Objective: {objective}")
print(f"Trials: {n_trials}")

try:
    result = run_optimization(
        spark=spark,
        commodity=commodity,
        objective=objective,
        n_trials=n_trials
    )

    print("\n" + "=" * 80)
    print("✓ STEP 3 TEST PASSED - Optimization completed successfully!")
    print("=" * 80)

    print(f"\nResults:")
    print(f"  Theoretical max: ${result['theoretical_max']:,.2f}")
    print(f"  Duration: {result['duration_seconds']:.1f}s")
    print(f"  Strategies optimized: {len(result['results'])}")

except Exception as e:
    print("\n" + "=" * 80)
    print("✗ STEP 3 TEST FAILED - Optimization error")
    print("=" * 80)
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
