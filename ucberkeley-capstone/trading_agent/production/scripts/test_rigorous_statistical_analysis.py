"""
Test Rigorous Statistical Analysis

Runs finance-grade statistical tests on coffee-naive model to demonstrate
the comprehensive approach.
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
print("RIGOROUS STATISTICAL ANALYSIS TEST")
print("=" * 80)

from production.analysis.rigorous_statistical_tests import RigorousStatisticalAnalyzer
from pyspark.sql import SparkSession

# Initialize Spark
spark = SparkSession.builder.getOrCreate()
analyzer = RigorousStatisticalAnalyzer(spark=spark)

# Test on coffee-naive model
commodity = 'coffee'
model_version = 'naive'

# Find a prediction strategy to test
print("\n" + "=" * 80)
print("Loading available strategies...")
print("=" * 80)

year_df = analyzer.load_year_by_year_results(commodity, model_version)
strategies = year_df['strategy'].unique()

print(f"\nFound {len(strategies)} strategies:")
for s in strategies:
    print(f"  • {s}")

# Test the best-performing prediction strategy
prediction_keywords = ['Predictive', 'Consensus', 'Expected Value', 'Risk-Adjusted', 'MPC']
prediction_strategies = [s for s in strategies if any(kw in s for kw in prediction_keywords)]

if prediction_strategies:
    test_strategy = prediction_strategies[0]  # Test first prediction strategy

    print(f"\n" + "=" * 80)
    print(f"TESTING: {test_strategy}")
    print("=" * 80)

    # Run comprehensive analysis
    results = analyzer.analyze_strategy_comprehensive(
        commodity=commodity,
        model_version=model_version,
        strategy_name=test_strategy,
        baseline_name='Immediate Sale',
        verbose=True
    )

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    # Show key findings
    print("\nKEY FINDINGS:")

    if results.get('annual'):
        annual = results['annual']
        print(f"\n1. Annual Analysis ({annual['n_years']} years):")
        print(f"   Win rate: {annual['win_rate']:.1%}")
        print(f"   Mean advantage: ${annual['mean_difference']:,.0f}/year")
        print(f"   Binomial test: p={annual['binomial_p_value']:.6f} {'✓' if annual['binomial_significant_05'] else '✗'}")
        print(f"   Wilcoxon test: p={annual['wilcoxon_p_value']:.6f} {'✓' if annual['wilcoxon_significant_05'] else '✗'}")

    if results.get('daily'):
        daily = results['daily']
        print(f"\n2. Daily Returns Analysis ({daily['n_days']:,} days):")
        print(f"   Annualized excess return: {daily['annualized_excess_return']*100:.2f}%")
        print(f"   Sharpe ratio: {daily['sharpe_ratio']:.3f}")
        print(f"   HAC t-test: p={daily['p_value_hac']:.6f} {'✓' if daily['significant_05_hac'] else '✗'}")

    if results.get('monthly'):
        monthly = results['monthly']
        print(f"\n3. Monthly Returns Analysis ({monthly['n_months']} months):")
        print(f"   Win rate: {monthly['win_rate']:.1%}")
        print(f"   Annualized excess return: {monthly['annualized_excess_return']*100:.2f}%")
        print(f"   t-test: p={monthly['p_value']:.6f} {'✓' if monthly['significant_05'] else '✗'}")

else:
    print("\n⚠️  No prediction strategies found to test")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
