"""
Diagnostic: Accuracy Threshold Analysis

Comprehensive test to determine minimum prediction accuracy needed for
statistically significant benefit over baseline strategies.

Tests synthetic predictions at 60%, 70%, 80%, 90%, and 100% accuracy levels.

For each accuracy level:
1. Compare ALL prediction strategies vs ALL baseline strategies
2. Run statistical significance tests (paired t-test, bootstrap CI)
3. Calculate effect sizes (Cohen's d)
4. Identify accuracy threshold for positive benefit

Output:
- Accuracy vs improvement curves
- Statistical significance by accuracy level
- Minimum accuracy threshold recommendation
- Confidence-based performance analysis
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from scipy import stats
from pathlib import Path

# Databricks imports
from pyspark.sql import SparkSession
import sys
import os

# Import strategies
import importlib.util

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics/all_strategies_pct.py',
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find all_strategies_pct.py")

spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

# Import all strategies
EqualBatchStrategy = strat.EqualBatchStrategy
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
ExpectedValueStrategy = strat.ExpectedValueStrategy
ConsensusStrategy = strat.ConsensusStrategy
RiskAdjustedStrategy = strat.RiskAdjustedStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive


class BacktestEngine:
    """Enhanced backtest engine with daily state tracking for statistical tests"""

    def __init__(self, prices_df, prediction_matrices, costs):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.storage_cost_pct = costs['storage_cost_pct_per_day']
        self.transaction_cost_pct = costs['transaction_cost_pct']

    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest with daily state tracking"""
        inventory = initial_inventory
        total_revenue = 0.0
        total_transaction_costs = 0.0
        total_storage_costs = 0.0
        trades = []
        daily_state = []

        for day in range(len(self.prices) - 14):
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']
            predictions = self.prediction_matrices.get(current_date, None)
            price_history = self.prices.iloc[:day+1].copy()

            decision = strategy.decide(day, inventory, current_price, price_history, predictions)

            net_revenue_today = 0.0
            storage_cost_today = 0.0

            if decision['action'] == 'SELL' and decision['amount'] > 0:
                sell_amount = min(decision['amount'], inventory)
                revenue = sell_amount * current_price
                transaction_cost = revenue * (self.transaction_cost_pct / 100)
                net_revenue = revenue - transaction_cost

                total_revenue += net_revenue
                total_transaction_costs += transaction_cost
                inventory -= sell_amount
                net_revenue_today = net_revenue

                trades.append({
                    'day': day,
                    'date': current_date,
                    'price': current_price,
                    'amount': sell_amount,
                    'revenue': net_revenue,
                    'reason': decision.get('reason', 'unknown')
                })

            if inventory > 0:
                storage_cost = inventory * current_price * (self.storage_cost_pct / 100)
                total_storage_costs += storage_cost
                storage_cost_today = storage_cost

            # Track daily state
            daily_state.append({
                'day': day,
                'date': current_date,
                'inventory': inventory,
                'price': current_price,
                'net_revenue_today': net_revenue_today,
                'storage_cost_today': storage_cost_today
            })

        # Forced liquidation
        if inventory > 0:
            final_day = len(self.prices) - 14
            final_price = self.prices.iloc[final_day]['price']
            final_revenue = inventory * final_price
            final_transaction_cost = final_revenue * (self.transaction_cost_pct / 100)
            final_net = final_revenue - final_transaction_cost

            total_revenue += final_net
            total_transaction_costs += final_transaction_cost

            trades.append({
                'day': final_day,
                'date': self.prices.iloc[final_day]['date'],
                'price': final_price,
                'amount': inventory,
                'revenue': final_net,
                'reason': 'forced_liquidation'
            })

            daily_state.append({
                'day': final_day,
                'date': self.prices.iloc[final_day]['date'],
                'inventory': 0,
                'price': final_price,
                'net_revenue_today': final_net,
                'storage_cost_today': 0
            })

        net_earnings = total_revenue - total_storage_costs

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'trades': trades,
            'num_trades': len(trades),
            'daily_state': pd.DataFrame(daily_state)
        }


def get_daily_portfolio_values(results, initial_value=50000):
    """Calculate daily portfolio value from results"""
    daily_state = results['daily_state']

    accumulated_net = 0
    portfolio_values = []

    for idx, row in daily_state.iterrows():
        accumulated_net += row['net_revenue_today'] - row['storage_cost_today']
        inventory_value = row['inventory'] * row['price']
        portfolio_value = accumulated_net + inventory_value
        portfolio_values.append(portfolio_value)

    return np.array(portfolio_values)


def statistical_comparison(pred_results, baseline_results, initial_value=50000):
    """
    Compare prediction vs baseline with statistical tests

    Returns:
    - t_statistic, p_value: Paired t-test results
    - cohens_d: Effect size
    - mean_daily_diff: Average daily difference
    - ci_lower, ci_upper: 95% confidence interval on daily differences
    """
    pred_pv = get_daily_portfolio_values(pred_results, initial_value)
    baseline_pv = get_daily_portfolio_values(baseline_results, initial_value)

    # Daily changes
    pred_changes = np.diff(pred_pv)
    baseline_changes = np.diff(baseline_pv)

    # Align lengths
    min_len = min(len(pred_changes), len(baseline_changes))
    pred_changes = pred_changes[:min_len]
    baseline_changes = baseline_changes[:min_len]

    # Differences
    diff = pred_changes - baseline_changes

    # Paired t-test
    t_stat, p_value = stats.ttest_rel(pred_changes, baseline_changes)

    # Effect size (Cohen's d)
    cohens_d = np.mean(diff) / np.std(diff) if np.std(diff) > 0 else 0

    # Confidence interval
    ci = stats.t.interval(0.95, len(diff)-1, loc=np.mean(diff), scale=stats.sem(diff))

    # Mean daily difference
    mean_daily_diff = np.mean(diff)

    return {
        't_statistic': t_stat,
        'p_value': p_value,
        'significant': p_value < 0.05,
        'cohens_d': cohens_d,
        'mean_daily_diff': mean_daily_diff,
        'ci_lower': ci[0],
        'ci_upper': ci[1]
    }


def bootstrap_ci(portfolio_values, n_boot=1000):
    """Bootstrap 95% confidence interval for final earnings"""
    daily_changes = np.diff(portfolio_values)
    initial_value = portfolio_values[0]

    final_values = []
    for _ in range(n_boot):
        resampled_changes = np.random.choice(daily_changes, size=len(daily_changes), replace=True)
        final_value = initial_value + np.sum(resampled_changes)
        final_values.append(final_value)

    final_values = np.array(final_values)

    return {
        'mean': np.mean(final_values),
        'ci_lower': np.percentile(final_values, 2.5),
        'ci_upper': np.percentile(final_values, 97.5)
    }


def main():
    print("="*80)
    print("DIAGNOSTIC: ACCURACY THRESHOLD ANALYSIS")
    print("="*80)
    print(f"Execution time: {datetime.now()}")
    print("\nObjective: Determine minimum prediction accuracy for statistically")
    print("significant benefit over baseline strategies.")

    commodity = 'coffee'
    spark = SparkSession.builder.getOrCreate()

    # Output paths
    volume_path = "/Volumes/commodity/trading_agent/files"

    # Load prices
    print("\n1. Loading prices...")
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = '{commodity}'"
    ).toPandas()

    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
    prices_df = prices_df[prices_df['date'] >= '2022-01-01'].reset_index(drop=True)

    print(f"✓ Loaded {len(prices_df)} days of prices")

    # Test accuracy levels
    accuracy_levels = [60, 70, 80, 90, 100]

    # Costs
    costs = {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    }

    # Results storage
    all_results = []
    statistical_results = []

    # Run baselines once (they don't use predictions)
    print(f"\n{'='*80}")
    print("2. RUNNING BASELINE STRATEGIES (prediction-independent)")
    print(f"{'='*80}")

    baseline_strategies = [
        ('Equal Batches', EqualBatchStrategy()),
        ('Price Threshold', PriceThresholdStrategy()),
        ('Moving Average', MovingAverageStrategy())
    ]

    # Create engine with empty predictions for baselines
    engine_baseline = BacktestEngine(prices_df, {}, costs)

    baseline_results_dict = {}
    for name, strategy in baseline_strategies:
        print(f"\n  Running {name}...")
        result = engine_baseline.run_backtest(strategy)
        baseline_results_dict[name] = result
        print(f"    Net Earnings: ${result['net_earnings']:,.0f}")
        print(f"    Trades: {result['num_trades']}")

    best_baseline_name = max(baseline_results_dict.keys(),
                            key=lambda k: baseline_results_dict[k]['net_earnings'])
    best_baseline_earnings = baseline_results_dict[best_baseline_name]['net_earnings']

    print(f"\n  🏆 Best Baseline: {best_baseline_name} = ${best_baseline_earnings:,.0f}")

    # Test each accuracy level
    for accuracy in accuracy_levels:
        model_version = f'synthetic_acc{accuracy}'

        print(f"\n{'='*80}")
        print(f"3. TESTING ACCURACY LEVEL: {accuracy}%")
        print(f"{'='*80}")

        # Load predictions
        print(f"\n  Loading {model_version} predictions...")
        pred_df = spark.table(f"commodity.trading_agent.predictions_{commodity}").filter(
            f"model_version = '{model_version}'"
        ).toPandas()

        if len(pred_df) == 0:
            print(f"  ⚠️  No predictions found, skipping...")
            continue

        # Convert to matrix format
        pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
        prediction_matrices = {}

        for timestamp in pred_df['timestamp'].unique():
            ts_data = pred_df[pred_df['timestamp'] == timestamp]
            matrix = ts_data.pivot_table(
                index='run_id',
                columns='day_ahead',
                values='predicted_price',
                aggfunc='first'
            ).values
            date_key = pd.Timestamp(timestamp).normalize()
            prediction_matrices[date_key] = matrix

        print(f"  ✓ Loaded {len(prediction_matrices)} prediction timestamps")

        # Calculate CV
        cvs = []
        for date_key, matrix in list(prediction_matrices.items())[:10]:
            for horizon in range(14):
                mean = np.mean(matrix[:, horizon])
                std = np.std(matrix[:, horizon])
                if mean > 0:
                    cvs.append(std / mean)

        avg_cv = np.mean(cvs) if cvs else 0
        print(f"  Average CV: {avg_cv:.4f} ({avg_cv*100:.2f}%)")

        # Create engine with predictions
        engine = BacktestEngine(prices_df, prediction_matrices, costs)

        # Run prediction strategies
        print(f"\n  Running prediction strategies...")

        prediction_strategies = [
            ('Expected Value', ExpectedValueStrategy(
                storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
                transaction_cost_pct=costs['transaction_cost_pct']
            )),
            ('Consensus', ConsensusStrategy(
                storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
                transaction_cost_pct=costs['transaction_cost_pct']
            )),
            ('Risk-Adjusted', RiskAdjustedStrategy(
                storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
                transaction_cost_pct=costs['transaction_cost_pct']
            )),
            ('Price Threshold Pred', PriceThresholdPredictive(
                storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
                transaction_cost_pct=costs['transaction_cost_pct']
            )),
            ('Moving Average Pred', MovingAveragePredictive(
                storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
                transaction_cost_pct=costs['transaction_cost_pct']
            ))
        ]

        for pred_name, pred_strategy in prediction_strategies:
            print(f"\n    {pred_name}...")
            pred_result = engine.run_backtest(pred_strategy)

            improvement = pred_result['net_earnings'] - best_baseline_earnings
            improvement_pct = (improvement / best_baseline_earnings) * 100

            print(f"      Earnings: ${pred_result['net_earnings']:,.0f}")
            print(f"      Improvement: ${improvement:+,.0f} ({improvement_pct:+.1f}%)")

            # Statistical comparison
            stat_comp = statistical_comparison(
                pred_result,
                baseline_results_dict[best_baseline_name]
            )

            print(f"      p-value: {stat_comp['p_value']:.4f} {'***' if stat_comp['significant'] else 'ns'}")
            print(f"      Cohen's d: {stat_comp['cohens_d']:+.3f}")

            # Bootstrap CI
            pred_pv = get_daily_portfolio_values(pred_result)
            boot_ci = bootstrap_ci(pred_pv, n_boot=1000)

            # Store results
            all_results.append({
                'accuracy': accuracy,
                'model_version': model_version,
                'avg_cv': avg_cv,
                'strategy': pred_name,
                'net_earnings': pred_result['net_earnings'],
                'num_trades': pred_result['num_trades'],
                'improvement_vs_baseline': improvement,
                'improvement_pct': improvement_pct,
                'baseline_name': best_baseline_name,
                'baseline_earnings': best_baseline_earnings
            })

            statistical_results.append({
                'accuracy': accuracy,
                'model_version': model_version,
                'strategy': pred_name,
                'baseline': best_baseline_name,
                'p_value': stat_comp['p_value'],
                'significant': stat_comp['significant'],
                'cohens_d': stat_comp['cohens_d'],
                'mean_daily_diff': stat_comp['mean_daily_diff'],
                'ci_lower': stat_comp['ci_lower'],
                'ci_upper': stat_comp['ci_upper'],
                'boot_mean': boot_ci['mean'],
                'boot_ci_lower': boot_ci['ci_lower'],
                'boot_ci_upper': boot_ci['ci_upper']
            })

    # Analysis
    print(f"\n{'='*80}")
    print("4. COMPREHENSIVE ANALYSIS")
    print(f"{'='*80}")

    results_df = pd.DataFrame(all_results)
    stat_df = pd.DataFrame(statistical_results)

    # Find accuracy threshold
    print("\nAccuracy Threshold Analysis:")
    print("-" * 60)

    for strategy in results_df['strategy'].unique():
        strategy_results = results_df[results_df['strategy'] == strategy].sort_values('accuracy')
        strategy_stats = stat_df[stat_df['strategy'] == strategy].sort_values('accuracy')

        # Find first accuracy with significant positive improvement
        significant_rows = strategy_stats[
            (strategy_stats['significant'] == True) &
            (strategy_results['improvement_pct'] > 0)
        ]

        if len(significant_rows) > 0:
            threshold_accuracy = significant_rows['accuracy'].min()
            threshold_improvement = strategy_results[
                strategy_results['accuracy'] == threshold_accuracy
            ]['improvement_pct'].iloc[0]

            print(f"\n  {strategy}:")
            print(f"    Threshold: {threshold_accuracy}% accuracy")
            print(f"    Improvement at threshold: {threshold_improvement:+.1f}%")
        else:
            print(f"\n  {strategy}:")
            print(f"    ⚠️  No statistically significant improvement at any accuracy level")

    # Summary tables
    print(f"\n{'='*80}")
    print("5. SUMMARY TABLES")
    print(f"{'='*80}")

    print("\nImprovement by Accuracy Level:")
    pivot = results_df.pivot_table(
        index='strategy',
        columns='accuracy',
        values='improvement_pct',
        aggfunc='first'
    )
    print(pivot.to_string())

    print("\nStatistical Significance (p < 0.05):")
    sig_pivot = stat_df.pivot_table(
        index='strategy',
        columns='accuracy',
        values='significant',
        aggfunc='first'
    )
    print(sig_pivot.to_string())

    # Save results
    print(f"\n{'='*80}")
    print("6. SAVING RESULTS")
    print(f"{'='*80}")

    output_file = f"{volume_path}/diagnostic_accuracy_threshold_results.pkl"
    csv_file = f"{volume_path}/diagnostic_accuracy_threshold_summary.csv"
    stat_file = f"{volume_path}/diagnostic_accuracy_threshold_stats.csv"

    results_data = {
        'execution_time': datetime.now(),
        'commodity': commodity,
        'accuracy_levels': accuracy_levels,
        'baseline_results': baseline_results_dict,
        'best_baseline': best_baseline_name,
        'all_results': results_df,
        'statistical_results': stat_df
    }

    with open(output_file, 'wb') as f:
        pickle.dump(results_data, f)
    print(f"✓ Saved results to: {output_file}")

    results_df.to_csv(csv_file, index=False)
    stat_df.to_csv(stat_file, index=False)
    print(f"✓ Saved summary to: {csv_file}")
    print(f"✓ Saved statistics to: {stat_file}")

    print(f"\n{'='*80}")
    print("✓ ACCURACY THRESHOLD ANALYSIS COMPLETE")
    print(f"{'='*80}")

    return True


if __name__ == "__main__":
    success = main()
    if not success:
        raise RuntimeError("Accuracy threshold analysis failed!")
