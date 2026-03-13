"""
Test Daily-Level Statistical Analysis

Run this on Databricks to test daily-level analysis with ~4,000 observations
"""

# Setup Python path
import sys
import os

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()
    if 'trading_agent' not in script_dir:
        script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/scripts'

trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
if trading_agent_dir not in sys.path:
    sys.path.insert(0, trading_agent_dir)

print("=" * 80)
print("DAILY-LEVEL STATISTICAL ANALYSIS TEST")
print("=" * 80)

# Test with coffee - naive model first (should have data)
from production.analysis.daily_level_statistics import DailyLevelAnalyzer

analyzer = DailyLevelAnalyzer()

# Find available pickle files
import glob
# Default volume path used by MultiCommodityRunner
pickle_pattern = "/Volumes/commodity/trading_agent/files/results_detailed_*.pkl"

print("\nSearching for detailed results files...")
try:
    pickle_files = glob.glob(pickle_pattern)
    if pickle_files:
        print(f"✓ Found {len(pickle_files)} detailed results files")
        for f in pickle_files[:10]:  # Show first 10
            print(f"  • {os.path.basename(f)}")
    else:
        print("⚠️  No pickle files found in /Volumes/commodity/trading_agent/files/")
        print("   Trying alternative paths...")
        # Try results directory
        pickle_pattern = "/Volumes/commodity/trading_agent/results/results_detailed_*.pkl"
        pickle_files = glob.glob(pickle_pattern)
        if pickle_files:
            print(f"✓ Found {len(pickle_files)} files in results directory")
        else:
            # Try DBFS path
            pickle_pattern = "/dbfs/Volumes/commodity/trading_agent/files/results_detailed_*.pkl"
            pickle_files = glob.glob(pickle_pattern)
            if pickle_files:
                print(f"✓ Found {len(pickle_files)} files in DBFS mount")
except Exception as e:
    print(f"⚠️  Error searching for files: {e}")
    pickle_files = []

# Try to analyze coffee-naive if file exists
print("\n" + "=" * 80)
print("TEST CASE: Coffee - Naive Model")
print("=" * 80)

try:
    # Try common pickle paths (default is /files/ not /results/)
    possible_paths = [
        "/Volumes/commodity/trading_agent/files/results_detailed_coffee_naive.pkl",
        "/Volumes/commodity/trading_agent/results/results_detailed_coffee_naive.pkl",
        "/dbfs/Volumes/commodity/trading_agent/files/results_detailed_coffee_naive.pkl",
        "/dbfs/mnt/commodity/trading_agent/files/results_detailed_coffee_naive.pkl"
    ]

    pickle_path = None
    for path in possible_paths:
        if os.path.exists(path):
            pickle_path = path
            print(f"✓ Found detailed results at: {path}")
            break

    if pickle_path is None:
        print("⚠️  Could not find detailed results file")
        print("   Tried:")
        for path in possible_paths:
            print(f"     - {path}")
        raise FileNotFoundError("Detailed results pickle file not found")

    # Load and analyze
    results = analyzer.analyze_all_prediction_strategies(
        commodity='coffee',
        model_version='naive',
        pickle_path=pickle_path,
        verbose=True
    )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Analyzed: {results['n_strategies']} prediction strategies")
    print(f"Significant results found: {results['has_significant_results']}")

    if results['best_significant']:
        print("\n✓ STATISTICALLY SIGNIFICANT IMPROVEMENT FOUND AT DAILY LEVEL!")
        best = results['best_significant']
        print(f"  Strategy: {best['strategy']}")
        print(f"  Mean daily advantage: ${best['mean_difference']:,.2f}")
        print(f"  p-value: {best['p_value']:.4f}")
        print(f"  Sample size: {best['n_days']:,} days across {best['n_years']} years")
        print(f"  Daily success rate: {best['daily_success_rate']:.1%}")
    else:
        print("\n✗ No statistically significant improvements found even at daily level")

        # Show closest results
        if results['strategy_results']:
            print("\nClosest to significance:")
            sorted_results = sorted(
                results['strategy_results'].items(),
                key=lambda x: x[1]['p_value']
            )
            for strategy_name, res in sorted_results[:3]:
                print(f"  {strategy_name}: p={res['p_value']:.4f}, Δ=${res['mean_difference']:,.2f}")

except Exception as e:
    print(f"❌ Error during analysis: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
