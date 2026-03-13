"""
Batch Statistical Analysis - Run on All Commodity-Model Combinations

This script discovers all year-by-year results tables and runs statistical
analysis on each one to identify which models (if any) show statistically
significant improvements over the Immediate Sale baseline.
"""

# Setup Python path for imports
import sys
import os

# Handle both local and Databricks execution environments
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # __file__ not defined in Databricks spark_python_task
    script_dir = os.getcwd()
    if 'trading_agent' not in script_dir:
        script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/scripts'

trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
if trading_agent_dir not in sys.path:
    sys.path.insert(0, trading_agent_dir)

from production.analysis import StatisticalAnalyzer
from pyspark.sql import SparkSession

print("=" * 80)
print("BATCH STATISTICAL ANALYSIS - ALL MODELS")
print("=" * 80)

# Initialize Spark
spark = SparkSession.builder.getOrCreate()
analyzer = StatisticalAnalyzer(spark=spark)

# Discover all year-by-year results tables
print("\nDiscovering year-by-year results tables...")
tables = spark.sql("""
    SHOW TABLES IN commodity.trading_agent
    LIKE 'results_*_by_year_*'
""").collect()

print(f"✓ Found {len(tables)} year-by-year results tables\n")

# Parse table names to extract commodity-model pairs
commodity_models = []
for table_row in tables:
    table_name = table_row.tableName
    # Parse: results_{commodity}_by_year_{model}
    parts = table_name.replace('results_', '').replace('_by_year_', '|').split('|')
    if len(parts) == 2:
        commodity, model_version = parts
        commodity_models.append((commodity, model_version))

print(f"Will analyze {len(commodity_models)} commodity-model combinations:\n")

# Track results
all_results = []
significant_results = []
errors = []

# Run analysis on each commodity-model pair
for i, (commodity, model_version) in enumerate(commodity_models, 1):
    print("=" * 80)
    print(f"[{i}/{len(commodity_models)}] Analyzing: {commodity} - {model_version}")
    print("=" * 80)

    try:
        # Run full statistical analysis
        results = analyzer.run_full_analysis(
            commodity=commodity,
            model_version=model_version,
            primary_baseline='Immediate Sale',
            verbose=False  # Reduce output noise
        )

        # Check if any strategies are statistically significant
        best = results.get('best_prediction_analysis')
        if best and best['significant_05']:
            print(f"✓ SIGNIFICANT: {best['strategy']}")
            print(f"  Mean improvement: ${best['mean_difference']:,.0f}")
            print(f"  p-value: {best['p_value']:.4f}")
            print(f"  Effect size: {best['cohens_d']:.3f} ({best['effect_interpretation']})")
            print(f"  Years positive: {best['n_years_positive']}/{best['n_years']}")
            significant_results.append((commodity, model_version, best))
        else:
            print(f"✗ No significant improvements found")
            if best:
                print(f"  Best: {best['strategy']} (p={best['p_value']:.4f}, Δ=${best['mean_difference']:,.0f})")

        # Save results
        table_name = analyzer.save_results(results, save_to_delta=True)
        print(f"✓ Saved to: {table_name}")

        all_results.append((commodity, model_version, results))

    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        errors.append((commodity, model_version, str(e)))
        continue

print("\n" + "=" * 80)
print("SUMMARY: BATCH STATISTICAL ANALYSIS")
print("=" * 80)

print(f"\nTotal analyzed: {len(all_results)}/{len(commodity_models)}")
print(f"Errors: {len(errors)}")
print(f"Statistically significant improvements: {len(significant_results)}")

if significant_results:
    print("\n" + "=" * 80)
    print("🏆 MODELS WITH STATISTICALLY SIGNIFICANT IMPROVEMENTS")
    print("=" * 80)

    for commodity, model_version, best in significant_results:
        print(f"\n{commodity.upper()} - {model_version}")
        print(f"  Strategy: {best['strategy']}")
        print(f"  Mean improvement: ${best['mean_difference']:,.0f}")
        print(f"  p-value: {best['p_value']:.4f}")
        print(f"  Effect size: {best['cohens_d']:.3f} ({best['effect_interpretation']})")
        print(f"  95% CI: [${best['ci_95_lower']:,.0f}, ${best['ci_95_upper']:,.0f}]")
        print(f"  Years positive: {best['n_years_positive']}/{best['n_years']}")
else:
    print("\n⚠️  NO STATISTICALLY SIGNIFICANT IMPROVEMENTS FOUND")
    print("\nNone of the 29 commodity-model combinations showed trading strategies")
    print("that significantly outperform simply selling immediately.")
    print("\nThis suggests:")
    print("  • Forecast accuracy may not be sufficient for profitable trading")
    print("  • Transaction costs may offset any forecast-driven gains")
    print("  • Immediate sale is a strong baseline for farmers")

if errors:
    print("\n" + "=" * 80)
    print("ERRORS")
    print("=" * 80)
    for commodity, model_version, error in errors:
        print(f"\n{commodity} - {model_version}")
        print(f"  Error: {error}")

print("\n" + "=" * 80)
print("BATCH ANALYSIS COMPLETE")
print("=" * 80)
print(f"\nResults saved to Delta tables:")
print(f"  commodity.trading_agent.statistical_tests_{{commodity}}_{{model}}")
