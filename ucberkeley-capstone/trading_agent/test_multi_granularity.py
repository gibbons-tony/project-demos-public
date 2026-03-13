import sys
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from production.analysis.statistical_tests import StatisticalAnalyzer

spark = SparkSession.builder.getOrCreate()
analyzer = StatisticalAnalyzer(spark=spark)

print("=" * 80)
print("MULTI-GRANULARITY STATISTICAL ANALYSIS TEST")
print("=" * 80)

results = analyzer.run_multi_granularity_analysis(
    commodity='coffee',
    model_version='naive',
    strategy_name='RollingHorizonMPC',
    baseline_name='Immediate Sale',
    granularities=['year', 'quarter', 'month'],
    verbose=True
)

print("\n" + "=" * 80)
print("RESULTS SUMMARY")
print("=" * 80)
print(f"Interpretation: {results.get('interpretation', 'N/A')}")

for gran, res in results.get('results_by_granularity', {}).items():
    if 'error' not in res:
        n = res.get('n_years', res.get('n_periods', 'N/A'))
        mean_diff = res.get('mean_difference', 0)
        p = res.get('p_value', 1.0)
        sig = "✓ SIGNIFICANT" if p < 0.05 else "✗ NOT SIGNIFICANT"
        print(f"\n{gran.upper()}: n={n}, mean=${mean_diff:,.0f}, p={p:.4f} {sig}")
