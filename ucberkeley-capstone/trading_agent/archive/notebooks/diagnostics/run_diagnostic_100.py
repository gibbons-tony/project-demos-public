"""
Diagnostic 100: Algorithm Validation with 100% Accuracy
Databricks execution script with result saving
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path

# Databricks imports
from pyspark.sql import SparkSession
import sys
import os

# Import strategies using importlib to avoid notebook import issues
import importlib.util

# Try multiple paths to find all_strategies_pct.py
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),  # Same directory as this script
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics/all_strategies_pct.py',
    '/Workspace/Users/gibbons_tony@berkeley.edu/all_strategies_pct.py',
    'all_strategies_pct.py'  # Fallback to relative path
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        print(f"Found all_strategies_pct.py at: {path}")
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find all_strategies_pct.py. Tried: {possible_paths}")

spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

EqualBatchStrategy = strat.EqualBatchStrategy
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
ExpectedValueStrategy = strat.ExpectedValueStrategy
ConsensusStrategy = strat.ConsensusStrategy
RiskAdjustedStrategy = strat.RiskAdjustedStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive


class SimpleBacktestEngine:
    """Minimal backtest engine for algorithm validation"""
    def __init__(self, prices_df, prediction_matrices, costs):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.storage_cost_pct = costs['storage_cost_pct_per_day']
        self.transaction_cost_pct = costs['transaction_cost_pct']
        self.predictions_found_count = 0
        self.predictions_missing_count = 0

    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest and return final net earnings"""
        inventory = initial_inventory
        total_revenue = 0.0
        total_transaction_costs = 0.0
        total_storage_costs = 0.0
        trades = []

        for day in range(len(self.prices) - 14):
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']
            predictions = self.prediction_matrices.get(current_date, None)

            # DEBUG: Track prediction lookups
            if predictions is not None:
                self.predictions_found_count += 1
            else:
                self.predictions_missing_count += 1
                if self.predictions_missing_count <= 3:  # Only log first 3 misses
                    print(f"    DEBUG: No predictions for {current_date} (type: {type(current_date).__name__})")

            price_history = self.prices.iloc[:day+1].copy()

            decision = strategy.decide(day, inventory, current_price, price_history, predictions)

            if decision['action'] == 'SELL' and decision['amount'] > 0:
                sell_amount = min(decision['amount'], inventory)
                revenue = sell_amount * current_price
                transaction_cost = revenue * (self.transaction_cost_pct / 100)
                net_revenue = revenue - transaction_cost

                total_revenue += net_revenue
                total_transaction_costs += transaction_cost
                inventory -= sell_amount

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

        # Forced liquidation
        if inventory > 0:
            final_price = self.prices.iloc[-14]['price']
            final_revenue = inventory * final_price
            final_transaction_cost = final_revenue * (self.transaction_cost_pct / 100)
            total_revenue += (final_revenue - final_transaction_cost)
            total_transaction_costs += final_transaction_cost

            trades.append({
                'day': len(self.prices) - 14,
                'date': self.prices.iloc[-14]['date'],
                'price': final_price,
                'amount': inventory,
                'revenue': final_revenue - final_transaction_cost,
                'reason': 'forced_liquidation'
            })

        net_earnings = total_revenue - total_storage_costs

        # DEBUG: Print prediction lookup stats
        total_days = len(self.prices) - 14
        print(f"  DEBUG - Prediction lookups: {self.predictions_found_count}/{total_days} found, {self.predictions_missing_count}/{total_days} missing")

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'trades': trades,
            'num_trades': len(trades)
        }


def main():
    print("="*80)
    print("DIAGNOSTIC 100: ALGORITHM VALIDATION WITH 100% ACCURACY")
    print("="*80)
    print(f"Execution time: {datetime.now()}")

    commodity = 'coffee'
    spark = SparkSession.builder.getOrCreate()

    # Output paths
    volume_path = "/Volumes/commodity/trading_agent/files"
    output_file = f"{volume_path}/diagnostic_100_results.pkl"

    print(f"\nOutput will be saved to: {output_file}")

    # Load prices
    print("\n1. Loading prices from Delta table...")
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = '{commodity}'"
    ).toPandas()

    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
    prices_df = prices_df[prices_df['date'] >= '2022-01-01'].reset_index(drop=True)

    print(f"✓ Loaded {len(prices_df)} days of prices")

    # Load predictions
    print("\n2. Loading predictions from Delta table...")
    pred_df = spark.table(f"commodity.trading_agent.predictions_{commodity}").filter(
        "model_version = 'synthetic_acc100'"
    ).toPandas()

    if len(pred_df) == 0:
        raise ValueError(f"No synthetic_acc100 predictions found!")

    print(f"✓ Loaded {len(pred_df)} prediction rows")

    # Convert to matrix format
    print("\n3. Converting to matrix format...")
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
        # Normalize to date-only for consistent dictionary lookups
        date_key = pd.Timestamp(timestamp).normalize()
        prediction_matrices[date_key] = matrix

    print(f"✓ Converted to {len(prediction_matrices)} timestamps")
    print(f"  Matrix shape: {matrix.shape[0]} runs × {matrix.shape[1]} horizons")

    # DEBUG: Show actual dictionary keys
    if len(prediction_matrices) > 0:
        sample_keys = list(prediction_matrices.keys())[:5]
        print(f"\n  DEBUG - Sample prediction keys:")
        for i, key in enumerate(sample_keys):
            print(f"    {i+1}. {key} (type: {type(key).__name__})")

        sample_prices = prices_df['date'].head()
        print(f"\n  DEBUG - Sample price dates:")
        for i, date in enumerate(sample_prices):
            print(f"    {i+1}. {date} (type: {type(date).__name__})")

        # Check if first price date matches any prediction key
        first_price_date = prices_df['date'].iloc[0]
        if first_price_date in prediction_matrices:
            print(f"\n  ✓ First price date FOUND in prediction_matrices!")
        else:
            print(f"\n  ❌ First price date NOT FOUND in prediction_matrices")
            print(f"     Looking for: {first_price_date} (type: {type(first_price_date).__name__})")
    else:
        print("\n  ❌ WARNING: No prediction matrices created!")

    # Validate 100% accuracy
    print("\n4. Validating 100% accuracy...")
    errors = []
    for date in list(prediction_matrices.keys())[:10]:
        pred_matrix = prediction_matrices[date]
        for horizon in range(14):
            variance = np.var(pred_matrix[:, horizon])
            if variance > 0.01:
                errors.append(f"Date {date}, horizon {horizon}: variance = {variance:.6f}")

    if errors:
        print(f"⚠️  WARNING: Found {len(errors)} prediction variances > 0.01")
        for err in errors[:5]:
            print(f"  {err}")
    else:
        print("✓ All predictions have 0 variance (all runs identical)")

    # Set up costs (Small farmer realistic costs)
    costs = {
        'storage_cost_pct_per_day': 0.005,  # 0.005% per day (quality degradation, on-farm storage)
        'transaction_cost_pct': 0.01         # 1% transaction (local intermediary cash payment)
    }

    # Create engine
    engine = SimpleBacktestEngine(prices_df, prediction_matrices, costs)

    # Define strategies
    baseline_strategies = [
        ('Equal Batches', EqualBatchStrategy()),
        ('Price Threshold', PriceThresholdStrategy()),
        ('Moving Average', MovingAverageStrategy())
    ]

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

    # Run baselines
    print("\n" + "="*80)
    print("5. RUNNING BASELINE STRATEGIES")
    print("="*80)

    baseline_results = []
    for name, strategy in baseline_strategies:
        print(f"\n  Running {name}...")
        result = engine.run_backtest(strategy)
        baseline_results.append((name, result))
        print(f"    Net Earnings: ${result['net_earnings']:,.0f}")
        print(f"    Trades: {result['num_trades']}")

    best_baseline = max(baseline_results, key=lambda x: x[1]['net_earnings'])
    print(f"\n  🏆 Best Baseline: {best_baseline[0]} = ${best_baseline[1]['net_earnings']:,.0f}")

    # Run predictions
    print("\n" + "="*80)
    print("6. RUNNING PREDICTION STRATEGIES")
    print("="*80)

    prediction_results = []
    for name, strategy in prediction_strategies:
        print(f"\n  Running {name}...")
        result = engine.run_backtest(strategy)
        prediction_results.append((name, result))
        print(f"    Net Earnings: ${result['net_earnings']:,.0f}")
        print(f"    Trades: {result['num_trades']}")

        improvement = result['net_earnings'] - best_baseline[1]['net_earnings']
        improvement_pct = (improvement / best_baseline[1]['net_earnings']) * 100

        if improvement > 0:
            print(f"    ✓ Beats baseline by ${improvement:,.0f} (+{improvement_pct:.1f}%)")
        else:
            print(f"    ❌ WORSE than baseline by ${-improvement:,.0f} ({improvement_pct:.1f}%)")

    best_prediction = max(prediction_results, key=lambda x: x[1]['net_earnings'])
    print(f"\n  🏆 Best Prediction: {best_prediction[0]} = ${best_prediction[1]['net_earnings']:,.0f}")

    # Final verdict
    print("\n" + "="*80)
    print("7. FINAL VERDICT")
    print("="*80)

    best_pred_earnings = best_prediction[1]['net_earnings']
    best_base_earnings = best_baseline[1]['net_earnings']
    improvement = best_pred_earnings - best_base_earnings
    improvement_pct = (improvement / best_base_earnings) * 100

    print(f"\nBest Baseline:    ${best_base_earnings:,.0f} ({best_baseline[0]})")
    print(f"Best Prediction:  ${best_pred_earnings:,.0f} ({best_prediction[0]})")
    print(f"Improvement:      ${improvement:,.0f} ({improvement_pct:+.1f}%)")

    print("\nValidation Criteria:")
    criterion_1 = improvement > 0
    criterion_2 = improvement_pct > 6
    print(f"  1. Predictions beat baselines: {'✓ PASS' if criterion_1 else '❌ FAIL'}")
    print(f"  2. Improvement >6%: {'✓ PASS' if criterion_2 else '❌ FAIL'}")

    algorithms_valid = criterion_1 and criterion_2

    if algorithms_valid:
        print("\n" + "="*80)
        print("✓✓✓ ALGORITHMS VALIDATED")
        print("="*80)
        print("\nConclusion: Trading algorithms are fundamentally sound.")
        print("If real predictions underperform, focus on:")
        print("  - Improving prediction accuracy")
        print("  - Parameter tuning (diagnostic_16)")
        print("  - Prediction usage refinement")
    else:
        print("\n" + "="*80)
        print("❌❌❌ ALGORITHMS BROKEN")
        print("="*80)
        print("\nConclusion: Fundamental bug in algorithm logic.")
        print("Run diagnostic_17 to debug.")

    # Save results
    print("\n" + "="*80)
    print("8. SAVING RESULTS")
    print("="*80)

    results_data = {
        'execution_time': datetime.now(),
        'commodity': commodity,
        'algorithms_valid': algorithms_valid,
        'best_baseline': {
            'name': best_baseline[0],
            'net_earnings': best_baseline[1]['net_earnings'],
            'trades': best_baseline[1]['num_trades'],
            'full_results': best_baseline[1]
        },
        'best_prediction': {
            'name': best_prediction[0],
            'net_earnings': best_prediction[1]['net_earnings'],
            'trades': best_prediction[1]['num_trades'],
            'full_results': best_prediction[1]
        },
        'improvement': improvement,
        'improvement_pct': improvement_pct,
        'all_baseline_results': baseline_results,
        'all_prediction_results': prediction_results,
        'validation_errors': errors
    }

    with open(output_file, 'wb') as f:
        pickle.dump(results_data, f)

    print(f"✓ Saved results to: {output_file}")

    # Also save summary CSV
    csv_file = f"{volume_path}/diagnostic_100_summary.csv"
    summary_rows = []

    for name, result in baseline_results:
        summary_rows.append({
            'strategy_type': 'Baseline',
            'strategy_name': name,
            'net_earnings': result['net_earnings'],
            'num_trades': result['num_trades'],
            'transaction_costs': result['transaction_costs'],
            'storage_costs': result['storage_costs']
        })

    for name, result in prediction_results:
        summary_rows.append({
            'strategy_type': 'Prediction',
            'strategy_name': name,
            'net_earnings': result['net_earnings'],
            'num_trades': result['num_trades'],
            'transaction_costs': result['transaction_costs'],
            'storage_costs': result['storage_costs']
        })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(csv_file, index=False)
    print(f"✓ Saved summary to: {csv_file}")

    print("\n" + "="*80)
    print("DIAGNOSTIC 100 COMPLETE")
    print("="*80)

    return algorithms_valid


if __name__ == "__main__":
    success = main()
    # Note: Don't call sys.exit() - Databricks interprets it as failure
    # Just let the script complete normally if success=True
    if not success:
        raise RuntimeError("Diagnostic 100 failed - algorithms broken!")
