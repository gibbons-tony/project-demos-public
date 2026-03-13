"""
Batch Rigorous Statistical Analysis

Runs rigorous statistical tests (daily HAC + monthly) on all prediction strategies
across all commodity-model combinations to identify which (if any) show statistical
significance.
"""

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

from production.analysis.rigorous_statistical_tests import RigorousStatisticalAnalyzer
from pyspark.sql import SparkSession

print("=" * 80)
print("BATCH RIGOROUS STATISTICAL ANALYSIS")
print("=" * 80)

# Initialize Spark
spark = SparkSession.builder.getOrCreate()
analyzer = RigorousStatisticalAnalyzer(spark=spark)

# Discover all year-by-year results tables
print("\nDiscovering commodity-model combinations...")
tables = spark.sql("""
    SHOW TABLES IN commodity.trading_agent
    LIKE 'results_*_by_year_*'
""").collect()

print(f"✓ Found {len(tables)} year-by-year results tables\n")

# Parse table names
commodity_models = []
for table_row in tables:
    table_name = table_row.tableName
    parts = table_name.replace('results_', '').replace('_by_year_', '|').split('|')
    if len(parts) == 2:
        commodity, model_version = parts
        commodity_models.append((commodity, model_version))

print(f"Will analyze {len(commodity_models)} commodity-model combinations\n")

# Track results
all_results = []
significant_results = []
errors = []

# Prediction strategy keywords
prediction_keywords = ['Predictive', 'Consensus', 'Expected Value', 'Risk-Adjusted', 'MPC']

# Run analysis on each commodity-model pair
for i, (commodity, model_version) in enumerate(commodity_models, 1):
    print("=" * 80)
    print(f"[{i}/{len(commodity_models)}] {commodity.upper()} - {model_version}")
    print("=" * 80)

    try:
        # Load year-by-year results to find strategies
        year_df = analyzer.load_year_by_year_results(commodity, model_version)
        strategies = year_df['strategy'].unique()

        # Filter to prediction strategies
        prediction_strategies = [s for s in strategies if any(kw in s for kw in prediction_keywords)]

        if not prediction_strategies:
            print(f"  ⚠️  No prediction strategies found")
            continue

        print(f"\nFound {len(prediction_strategies)} prediction strategies to test")

        # Test each prediction strategy
        for strategy in prediction_strategies:
            print(f"\n{'-'*80}")
            print(f"Testing: {strategy}")
            print('-'*80)

            try:
                results = analyzer.analyze_strategy_comprehensive(
                    commodity=commodity,
                    model_version=model_version,
                    strategy_name=strategy,
                    baseline_name='Immediate Sale',
                    verbose=False  # Reduce output noise in batch mode
                )

                # Check if significant
                is_significant = False
                if results.get('daily') and results['daily']['significant_05_hac']:
                    is_significant = True
                if results.get('monthly') and results['monthly']['significant_05']:
                    is_significant = True

                if is_significant:
                    print(f"✓ SIGNIFICANT!")
                    if results.get('daily'):
                        print(f"  Daily HAC: p={results['daily']['p_value_hac']:.4f}, excess={results['daily']['annualized_excess_return']*100:.2f}%")
                    if results.get('monthly'):
                        print(f"  Monthly: p={results['monthly']['p_value']:.4f}, excess={results['monthly']['annualized_excess_return']*100:.2f}%")

                    significant_results.append({
                        'commodity': commodity,
                        'model_version': model_version,
                        'strategy': strategy,
                        'results': results
                    })
                else:
                    print(f"✗ Not significant")
                    if results.get('daily'):
                        print(f"  Daily HAC: p={results['daily']['p_value_hac']:.4f}")
                    if results.get('monthly'):
                        print(f"  Monthly: p={results['monthly']['p_value']:.4f}")

                all_results.append({
                    'commodity': commodity,
                    'model_version': model_version,
                    'strategy': strategy,
                    'results': results
                })

            except Exception as e:
                print(f"  ❌ Error testing {strategy}: {str(e)}")
                continue

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        errors.append((commodity, model_version, str(e)))
        continue

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("BATCH ANALYSIS COMPLETE")
print("=" * 80)

print(f"\nTotal strategies analyzed: {len(all_results)}")
print(f"Statistically significant strategies: {len(significant_results)}")
print(f"Errors: {len(errors)}")

if significant_results:
    print("\n" + "=" * 80)
    print("🏆 STRATEGIES WITH STATISTICAL SIGNIFICANCE")
    print("=" * 80)

    for result in significant_results:
        print(f"\n{result['commodity'].upper()} - {result['model_version']}")
        print(f"  Strategy: {result['strategy']}")

        if result['results'].get('daily'):
            daily = result['results']['daily']
            print(f"  Daily HAC test:")
            print(f"    p-value: {daily['p_value_hac']:.6f} {'✓' if daily['significant_05_hac'] else '✗'}")
            print(f"    Annualized excess: {daily['annualized_excess_return']*100:.2f}%")
            print(f"    Sharpe ratio: {daily['sharpe_ratio']:.3f}")

        if result['results'].get('monthly'):
            monthly = result['results']['monthly']
            print(f"  Monthly test:")
            print(f"    p-value: {monthly['p_value']:.6f} {'✓' if monthly['significant_05'] else '✗'}")
            print(f"    Annualized excess: {monthly['annualized_excess_return']*100:.2f}%")
            print(f"    Win rate: {monthly['win_rate']:.1%}")
else:
    print("\n" + "=" * 80)
    print("⚠️  NO STATISTICALLY SIGNIFICANT STRATEGIES FOUND")
    print("=" * 80)
    print("\nNone of the prediction strategies showed statistically significant")
    print("improvements over the Immediate Sale baseline when tested with:")
    print("  • Daily returns (HAC-adjusted for autocorrelation)")
    print("  • Monthly returns (standard t-test)")
    print("\nThis suggests:")
    print("  • Forecast accuracy may not translate to profitable trading")
    print("  • Transaction costs and storage costs offset gains")
    print("  • Immediate sale is a strong baseline for farmers")

if errors:
    print("\n" + "=" * 80)
    print("ERRORS ENCOUNTERED")
    print("=" * 80)
    for commodity, model_version, error in errors:
        print(f"\n{commodity} - {model_version}")
        print(f"  Error: {error}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
