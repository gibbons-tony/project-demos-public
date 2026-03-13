"""
Intelligent Model Comparison and Statistical Analysis

Workflow:
1. Discover available forecast models and their time periods
2. Find overlapping periods across models
3. Compare models on overlapping period only
4. Select winning model
5. Run statistical tests on winner using its full available time period
6. Save results at each step
"""

import sys
from pyspark.sql import SparkSession
sys.path.append('/Workspace/Repos/gibbons_tony@berkeley.edu/ucberkeley-capstone/trading_agent')

from production.analysis.statistical_tests import StatisticalAnalyzer


def discover_model_availability(spark, commodity='coffee'):
    """
    Find all available models and their valid time periods

    Returns:
        dict: {model_version: {'years': [2018, 2019, ...], 'first': 2018, 'last': 2025}}
    """
    print("=" * 80)
    print(f"DISCOVERING AVAILABLE MODELS FOR {commodity.upper()}")
    print("=" * 80)

    # Get all by_year tables for this commodity
    tables = spark.sql("SHOW TABLES IN commodity.trading_agent").toPandas()
    model_tables = tables[
        (tables['tableName'].str.contains(f'results_{commodity}_by_year', case=False)) &
        (~tables['tableName'].str.contains('synthetic', case=False))  # Exclude synthetic
    ]

    models = {}

    for _, row in model_tables.iterrows():
        table_name = row['tableName']
        # Extract model version from table name: results_coffee_by_year_MODEL
        model_version = table_name.replace(f'results_{commodity}_by_year_', '')

        # Get valid years (exclude years with $0 earnings for any strategy)
        df = spark.table(f"commodity.trading_agent.{table_name}")

        # Find years where ALL strategies have earnings > 0
        year_validity = df.groupBy('year').agg(
            spark_min('net_earnings').alias('min_earnings')
        ).filter('min_earnings > 0').select('year').toPandas()

        if len(year_validity) > 0:
            valid_years = sorted(year_validity['year'].astype(int).tolist())
            models[model_version] = {
                'years': valid_years,
                'first': min(valid_years),
                'last': max(valid_years),
                'n_years': len(valid_years)
            }

            print(f"\n{model_version}:")
            print(f"  Valid years: {valid_years}")
            print(f"  Period: {min(valid_years)}-{max(valid_years)} ({len(valid_years)} years)")

    return models


def find_overlapping_period(models):
    """Find the overlapping time period across all models"""
    print("\n" + "=" * 80)
    print("FINDING OVERLAPPING PERIOD")
    print("=" * 80)

    if not models:
        raise ValueError("No models available")

    # Get intersection of all year sets
    all_year_sets = [set(info['years']) for info in models.values()]
    overlapping_years = sorted(list(set.intersection(*all_year_sets)))

    print(f"\nOverlapping years across all models: {overlapping_years}")
    print(f"Period: {min(overlapping_years)}-{max(overlapping_years)} ({len(overlapping_years)} years)")

    return overlapping_years


def compare_models_on_overlap(spark, commodity, models, overlapping_years, strategy='RollingHorizonMPC'):
    """
    Compare all models on overlapping period for a specific strategy

    Returns:
        dict: {model_version: mean_improvement}
    """
    print("\n" + "=" * 80)
    print(f"COMPARING MODELS ON OVERLAPPING PERIOD ({strategy})")
    print("=" * 80)

    results = {}

    for model_version in models.keys():
        table = f"commodity.trading_agent.results_{commodity}_by_year_{model_version}"
        df = spark.table(table).toPandas()

        # Filter to overlapping years
        df_overlap = df[df['year'].isin(overlapping_years)]

        # Get strategy and baseline performance
        strategy_perf = df_overlap[df_overlap['strategy'] == strategy]['net_earnings'].values
        baseline_perf = df_overlap[df_overlap['strategy'] == 'Immediate Sale']['net_earnings'].values

        if len(strategy_perf) > 0 and len(baseline_perf) > 0:
            improvements = ((strategy_perf - baseline_perf) / baseline_perf) * 100
            mean_improvement = improvements.mean()
            results[model_version] = mean_improvement

            print(f"\n{model_version}: {mean_improvement:+.2f}%")

    return results


def select_winner(model_comparisons):
    """Select the best performing model"""
    print("\n" + "=" * 80)
    print("SELECTING WINNING MODEL")
    print("=" * 80)

    winner = max(model_comparisons.items(), key=lambda x: x[1])

    print(f"\n🏆 Winner: {winner[0]} (+{winner[1]:.2f}%)")

    return winner[0]


def run_final_analysis(spark, commodity, winning_model, full_years):
    """Run statistical tests on winning model using full available period"""
    print("\n" + "=" * 80)
    print(f"FINAL STATISTICAL ANALYSIS: {winning_model.upper()}")
    print(f"Time Period: {min(full_years)}-{max(full_years)} ({len(full_years)} years)")
    print("=" * 80)

    analyzer = StatisticalAnalyzer(spark=spark)

    # Load data and filter to valid years
    table = f"commodity.trading_agent.results_{commodity}_by_year_{winning_model}"
    df = spark.table(table).toPandas()
    df_filtered = df[df['year'].isin(full_years)]

    # Temporarily write filtered data to use with analyzer
    # (analyzer expects to load from table, so we create temp view)
    spark.createDataFrame(df_filtered).createOrReplaceTempView("temp_results")

    # Monkey-patch the loader to use our filtered data
    original_loader = analyzer.load_year_by_year_results
    def filtered_loader(commodity, model_version):
        return spark.table("temp_results").toPandas()
    analyzer.load_year_by_year_results = filtered_loader

    # Run analysis
    results = analyzer.run_full_analysis(
        commodity=commodity,
        model_version=winning_model,
        primary_baseline='Immediate Sale',
        verbose=True
    )

    # Restore original loader
    analyzer.load_year_by_year_results = original_loader

    return results


def main():
    """Main workflow"""
    spark = SparkSession.builder.getOrCreate()
    commodity = 'coffee'

    # Step 1: Discover models
    models = discover_model_availability(spark, commodity)

    # Step 2: Find overlapping period
    overlapping_years = find_overlapping_period(models)

    # Step 3: Compare models on overlap
    model_comparisons = compare_models_on_overlap(
        spark, commodity, models, overlapping_years
    )

    # Step 4: Select winner
    winning_model = select_winner(model_comparisons)

    # Step 5: Run final analysis on winner's full period
    winner_full_years = models[winning_model]['years']
    final_results = run_final_analysis(
        spark, commodity, winning_model, winner_full_years
    )

    # Step 6: Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    # Save model comparison
    comparison_df = spark.createDataFrame([
        {'model': k, 'mean_improvement_pct': v, 'period': f"{min(overlapping_years)}-{max(overlapping_years)}"}
        for k, v in model_comparisons.items()
    ])
    comparison_df.write.mode("overwrite").saveAsTable(
        f"commodity.trading_agent.model_comparison_{commodity}"
    )
    print(f"✓ Model comparison saved to: commodity.trading_agent.model_comparison_{commodity}")

    # Save statistical tests
    analyzer = StatisticalAnalyzer(spark=spark)
    table_name = analyzer.save_results(final_results, save_to_delta=True)
    print(f"✓ Statistical tests saved to: {table_name}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Winning model: {winning_model}")
    print(f"Analysis period: {min(winner_full_years)}-{max(winner_full_years)} ({len(winner_full_years)} years)")
    print(f"Strategies tested: {final_results['n_strategies']}")
    print("\nKey results:")
    for test in final_results['strategy_vs_baseline_tests']:
        sig = "✓" if test['significant_05'] else "✗"
        print(f"  {sig} {test['strategy']}: ${test['mean_difference']:,.0f}, p={test['p_value']:.3f}")


if __name__ == "__main__":
    from pyspark.sql.functions import min as spark_min
    main()
