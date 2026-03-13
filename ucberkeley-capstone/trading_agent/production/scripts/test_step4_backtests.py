"""
Test Step 4: Run Backtests with Fixed Reporting

This tests the KeyError fix in step_run_backtests() by:
1. Running backtests via MultiCommodityRunner
2. Calling runner.get_summary() (the fix)
3. Printing summary statistics
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
from production.config import COMMODITY_CONFIGS, VOLUME_PATH, OUTPUT_SCHEMA
from production.runners.multi_commodity_runner import MultiCommodityRunner

print("=" * 80)
print("TEST STEP 4: BACKTESTS WITH FIXED REPORTING")
print("=" * 80)

# Initialize Spark
spark = SparkSession.builder.appName("TestStep4Backtests").getOrCreate()

# Run for coffee only to keep it fast
commodities = ['coffee']
commodity_configs = {k: v for k, v in COMMODITY_CONFIGS.items() if k in commodities}

print(f"\nRunning backtests for: {list(commodity_configs.keys())}")
print(f"Using optimized params: False")

# Initialize runner
runner = MultiCommodityRunner(
    spark=spark,
    commodity_configs=commodity_configs,
    volume_path=VOLUME_PATH,
    output_schema=OUTPUT_SCHEMA,
    use_optimized_params=False,
    run_statistical_tests=False
)

# Run backtests
print("\n" + "=" * 80)
print("RUNNING BACKTESTS...")
print("=" * 80)
results = runner.run_all_commodities(verbose=True)

# THIS IS THE FIX BEING TESTED: Call get_summary() instead of accessing non-existent keys
print("\n" + "=" * 80)
print("TESTING FIXED REPORTING (runner.get_summary())...")
print("=" * 80)
summary = runner.get_summary()

print(f"\n✓ Backtests completed")
print(f"  Total combinations: {summary['total_combinations']}")
print(f"  Commodities: {', '.join(summary['commodities'])}")
for commodity in summary['commodities']:
    print(f"    - {commodity}: {summary[f'{commodity}_models']} models")

print("\n" + "=" * 80)
print("✓ STEP 4 TEST PASSED - Reporting fix works!")
print("=" * 80)
