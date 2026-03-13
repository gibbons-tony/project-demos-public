"""
Identify Best Forecast Model

Compares all models in the manifest using statistical tests
and identifies the best performing model for detailed analysis.

This is Step 5 in the production workflow.

Usage:
    python production/scripts/identify_best_model.py --commodity coffee
"""

import sys
import json
import argparse

sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from pyspark.sql.functions import min as spark_min
from scipy import stats
import pandas as pd


def load_manifest(volume_path, commodity):
    """Load forecast manifest for commodity"""
    import os
    manifest_path = os.path.join(volume_path, f'forecast_manifest_{commodity}.json')

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        return manifest
    except FileNotFoundError:
        print(f"ERROR: Manifest not found at {manifest_path}")
        print("Run load_forecast_predictions.py first to generate manifest")
        return None


def compare_models(spark, commodity, manifest_models):
    """
    Compare models using their backtest results

    Returns:
        dict: {model: {'avg_improvement': float, 'valid_years': list, 'n_years': int}}
    """
    print("=" * 80)
    print(f"COMPARING MODELS FOR {commodity.upper()}")
    print("=" * 80)
    print(f"Models in manifest: {manifest_models}\n")

    results = {}

    for model in manifest_models:
        table = f"commodity.trading_agent.results_{commodity}_by_year_{model}"

        try:
            # Check if table exists
            spark.sql(f"DESCRIBE TABLE {table}")
        except Exception:
            print(f"⚠️  Table {table} not found - skipping")
            continue

        df = spark.table(table).toPandas()

        # Find valid years (where all strategies have earnings > 0)
        df_spark = spark.table(table)
        year_validity = df_spark.groupBy('year').agg(
            spark_min('net_earnings').alias('min_earnings')
        ).filter('min_earnings > 0').select('year').toPandas()

        valid_years = sorted(year_validity['year'].astype(int).tolist())

        # Filter to valid years
        df_filtered = df[df['year'].isin(valid_years)]

        # Get MPC vs Baseline
        mpc_data = df_filtered[df_filtered['strategy'] == 'RollingHorizonMPC']['net_earnings'].values
        baseline_data = df_filtered[df_filtered['strategy'] == 'Immediate Sale']['net_earnings'].values

        if len(mpc_data) > 0 and len(baseline_data) > 0:
            # Calculate annual improvements
            annual_improvements = ((mpc_data - baseline_data) / baseline_data) * 100
            avg_improvement = annual_improvements.mean()

            results[model] = {
                'avg_improvement': float(avg_improvement),
                'valid_years': valid_years,
                'n_years': len(valid_years)
            }

            print(f"{model}:")
            print(f"  Avg improvement: {avg_improvement:+.2f}%")
            print(f"  Valid years: {valid_years}")
            print(f"  N years: {len(valid_years)}\n")

    return results


def select_winner(model_results):
    """Select best model by average improvement"""
    if not model_results:
        return None, None

    winner_model = max(model_results.items(), key=lambda x: x[1]['avg_improvement'])
    return winner_model[0], winner_model[1]


def run_detailed_stats(spark, commodity, winning_model, valid_years):
    """Run detailed statistical analysis on winning model"""
    print("=" * 80)
    print(f"DETAILED STATISTICAL ANALYSIS: {winning_model.upper()}")
    print("=" * 80)

    table = f"commodity.trading_agent.results_{commodity}_by_year_{winning_model}"
    df = spark.table(table).toPandas()

    # Filter to valid years
    df_filtered = df[df['year'].isin(valid_years)]

    # Get MPC and Baseline
    mpc = df_filtered[df_filtered['strategy'] == 'RollingHorizonMPC'].sort_values('year')
    baseline = df_filtered[df_filtered['strategy'] == 'Immediate Sale'].sort_values('year')

    # Statistics
    differences = mpc['net_earnings'].values - baseline['net_earnings'].values
    mean_diff = differences.mean()
    std_diff = differences.std()

    # Paired t-test
    t_stat, p_value = stats.ttest_rel(mpc['net_earnings'], baseline['net_earnings'])

    # Percentage
    baseline_mean = baseline['net_earnings'].mean()
    pct_improvement = (mean_diff / baseline_mean * 100) if baseline_mean != 0 else 0

    # Effect size
    cohens_d = mean_diff / std_diff if std_diff > 0 else 0

    print(f"\nMean difference: ${mean_diff:,.2f}")
    print(f"Percentage improvement: {pct_improvement:.2f}%")
    print(f"T-statistic: {t_stat:.4f}")
    print(f"P-value: {p_value:.6f}")
    print(f"Cohen's d: {cohens_d:.4f}")

    if p_value < 0.001:
        significance = "HIGHLY SIGNIFICANT (p < 0.001)"
    elif p_value < 0.01:
        significance = "VERY SIGNIFICANT (p < 0.01)"
    elif p_value < 0.05:
        significance = "SIGNIFICANT (p < 0.05)"
    else:
        significance = "NOT SIGNIFICANT (p >= 0.05)"

    print(f"\nResult: {significance}")

    return {
        'mean_diff': float(mean_diff),
        'pct_improvement': float(pct_improvement),
        't_stat': float(t_stat),
        'p_value': float(p_value),
        'cohens_d': float(cohens_d),
        'significance': significance,
        'n_years': len(valid_years)
    }


def main():
    parser = argparse.ArgumentParser(description='Identify best forecast model')
    parser.add_argument('--commodity', type=str, default='coffee', help='Commodity to analyze')
    parser.add_argument('--volume-path', type=str, default='/dbfs/production/files', help='Path to volume storage')
    args = parser.parse_args()

    spark = SparkSession.builder.getOrCreate()

    print("=" * 80)
    print("BEST MODEL IDENTIFICATION WORKFLOW")
    print("=" * 80)
    print(f"Commodity: {args.commodity}")
    print("=" * 80)

    # Step 1: Load manifest
    print("\nStep 1: Load forecast manifest...")
    manifest = load_manifest(args.volume_path, args.commodity)

    if not manifest or 'models' not in manifest:
        print("ERROR: No models found in manifest")
        sys.exit(1)

    manifest_models = list(manifest['models'].keys())
    print(f"✓ Found {len(manifest_models)} models in manifest: {manifest_models}")

    # Step 2: Compare models
    print("\nStep 2: Compare models...")
    model_results = compare_models(spark, args.commodity, manifest_models)

    if not model_results:
        print("ERROR: No valid model results found")
        sys.exit(1)

    # Step 3: Select winner
    print("\nStep 3: Select best model...")
    winning_model, winner_stats = select_winner(model_results)

    print("=" * 80)
    print("WINNER")
    print("=" * 80)
    print(f"🏆 Best Model: {winning_model}")
    print(f"📊 Average Improvement: {winner_stats['avg_improvement']:+.2f}%")
    print(f"📅 Sample Size: {winner_stats['n_years']} years")

    # Step 4: Detailed statistical analysis
    print("\nStep 4: Detailed statistical analysis...")
    detailed_stats = run_detailed_stats(
        spark, args.commodity, winning_model, winner_stats['valid_years']
    )

    # Final summary
    summary = {
        'commodity': args.commodity,
        'manifest_models': manifest_models,
        'model_comparisons': model_results,
        'winning_model': winning_model,
        'winner_stats': winner_stats,
        'detailed_statistics': detailed_stats
    }

    print("\n" + "=" * 80)
    print("JSON SUMMARY")
    print("=" * 80)
    print(json.dumps(summary, indent=2))

    return summary


if __name__ == "__main__":
    result = main()
    sys.exit(0)
