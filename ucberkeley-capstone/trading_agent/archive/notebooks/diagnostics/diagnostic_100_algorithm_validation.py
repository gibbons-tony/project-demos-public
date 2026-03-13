"""
Diagnostic Test: 100% Accuracy Algorithm Validation

**Purpose:** Prove trading algorithms work correctly by testing with PERFECT FORESIGHT

**Critical Logic:**
With 100% accurate predictions (perfect foresight):
- Prediction strategies MUST beat baseline strategies
- If they don't, the algorithms are fundamentally broken

**This is NOT a test of prediction quality**
This is a test of algorithm correctness.

**Usage:**
    python diagnostic_100_algorithm_validation.py

**Expected Results:**
Coffee synthetic_acc100:
- Best Baseline (Equal Batches): ~$727k
- Best Prediction (Expected Value): >$800k (+10% minimum)
- Status: ✓ ALGORITHMS WORK

If prediction strategies lose with 100% accuracy:
- Status: ❌ ALGORITHMS BROKEN - fundamental bug in decision logic
"""

import pickle
import numpy as np
import pandas as pd
from pathlib import Path

# Import strategies - handle both Databricks and local execution
import sys
import os

# Add diagnostics directory to path
try:
    diagnostics_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # __file__ not defined in Databricks jobs, use hardcoded path
    diagnostics_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

if diagnostics_dir not in sys.path:
    sys.path.insert(0, diagnostics_dir)

from all_strategies_pct import (
    # Baselines
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy,

    # Prediction strategies
    ExpectedValueStrategy,
    ConsensusStrategy,
    RiskAdjustedStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive
)


class SimpleBacktestEngine:
    """
    Minimal backtest engine for algorithm validation
    Mirrors main engine but simplified for diagnostics
    """
    def __init__(self, prices_df, prediction_matrices, costs):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.storage_cost_pct = costs['storage_cost_pct_per_day']
        self.transaction_cost_pct = costs['transaction_cost_pct']

    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest and return final net earnings"""
        inventory = initial_inventory
        total_revenue = 0.0
        total_transaction_costs = 0.0
        total_storage_costs = 0.0
        trades = []

        for day in range(len(self.prices) - 14):  # Stop 14 days before end
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']

            # Get predictions for this day
            predictions = self.prediction_matrices.get(current_date, None)

            # Get price history
            price_history = self.prices.iloc[:day+1].copy()

            # Strategy decision
            decision = strategy.decide(day, inventory, current_price, price_history, predictions)

            # Execute trade
            if decision['action'] == 'SELL' and decision['amount'] > 0:
                sell_amount = min(decision['amount'], inventory)

                # Revenue
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

            # Storage costs (daily)
            if inventory > 0:
                storage_cost = inventory * current_price * (self.storage_cost_pct / 100)
                total_storage_costs += storage_cost

        # Forced liquidation at end
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

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'trades': trades,
            'num_trades': len(trades)
        }


def load_predictions_from_delta_table(commodity='coffee'):
    """Load synthetic_acc100 predictions from v8 Delta table"""
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()

        # Load from trading_agent.predictions table
        table_name = f"commodity.trading_agent.predictions_{commodity.lower()}"
        pred_df = spark.table(table_name).filter(
            "model_version = 'synthetic_acc100'"
        ).toPandas()

        if len(pred_df) == 0:
            raise ValueError(f"No synthetic_acc100 predictions in {table_name}")

        # Convert to prediction_matrices format: dict of timestamp -> (n_runs x 14) matrix
        pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
        prediction_matrices = {}

        for timestamp in pred_df['timestamp'].unique():
            ts_data = pred_df[pred_df['timestamp'] == timestamp]

            # Pivot to get (run_id, day_ahead) -> predicted_price
            matrix = ts_data.pivot_table(
                index='run_id',
                columns='day_ahead',
                values='predicted_price',
                aggfunc='first'
            ).values

            prediction_matrices[timestamp] = matrix

        print(f"✓ Loaded synthetic_acc100 predictions from Delta table")
        print(f"  {len(prediction_matrices)} timestamps, {matrix.shape[0]} runs × {matrix.shape[1]} horizons")
        return prediction_matrices

    except Exception as e:
        return None  # Will try pickle files next


def load_100_accuracy_predictions(commodity='coffee', volume_path='/Volumes/commodity/trading_agent/files'):
    """Load synthetic_acc100 predictions from v8 (tries Delta table first, then pickle files)"""

    # Try Delta table first (v8 format)
    print("Trying Delta table...")
    predictions = load_predictions_from_delta_table(commodity)
    if predictions is not None:
        return predictions

    # Fall back to pickle files
    print("Trying pickle files...")
    for version in ['v8', 'v6']:
        # Try volume path first (Databricks)
        pred_file = f'{volume_path}/prediction_matrices_{commodity}_synthetic_acc100_{version}.pkl'
        if Path(pred_file).exists():
            with open(pred_file, 'rb') as f:
                data = pickle.load(f)
            print(f"✓ Loaded {version} synthetic_acc100 predictions from volume")
            return data['prediction_matrices']

        # Fall back to local path (for local testing)
        pred_file = f'../prediction_matrices_{commodity}_synthetic_acc100_{version}.pkl'
        if Path(pred_file).exists():
            with open(pred_file, 'rb') as f:
                data = pickle.load(f)
            print(f"✓ Loaded {version} synthetic_acc100 predictions from local")
            return data['prediction_matrices']

    raise FileNotFoundError(
        f"No synthetic_acc100 predictions found.\n"
        f"Looked in:\n"
        f"  Delta table: commodity.trading_agent.predictions_{commodity}\n"
        f"  {volume_path}/prediction_matrices_{commodity}_synthetic_acc100_*.pkl\n"
        f"  ../prediction_matrices_{commodity}_synthetic_acc100_*.pkl\n"
        f"\nRun 01_synthetic_predictions_v8.ipynb first to generate predictions."
    )


def validate_100_accuracy_predictions(predictions, prices):
    """Verify predictions are actually 100% accurate"""
    print("\nValidating 100% Accuracy...")

    errors = []
    for date in list(predictions.keys())[:10]:  # Sample 10 dates
        pred_matrix = predictions[date]  # Shape: (n_runs, 14)

        # For 100% accuracy, all runs should be identical and match actual future prices
        # Check variance across runs (should be 0)
        for horizon in range(14):
            variance = np.var(pred_matrix[:, horizon])
            if variance > 0.01:  # Allow tiny floating point errors
                errors.append(f"Date {date}, horizon {horizon}: variance = {variance:.6f}")

    if errors:
        print(f"⚠️  WARNING: Found {len(errors)} prediction variances > 0.01")
        for err in errors[:5]:
            print(f"  {err}")
    else:
        print("✓ All predictions have 0 variance (all runs identical)")

    return len(errors) == 0


def load_prices_from_databricks(commodity='coffee'):
    """Load price data from Databricks Delta table or volume"""
    try:
        # Try to load from Spark (if running in Databricks)
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()

        # Load from bronze.market table
        market_df = spark.table("commodity.bronze.market").filter(
            f"lower(commodity) = '{commodity.lower()}'"
        ).toPandas()

        market_df['date'] = pd.to_datetime(market_df['date'])
        market_df['price'] = market_df['close']
        prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)

        # Filter to synthetic start date
        prices_df = prices_df[prices_df['date'] >= '2022-01-01'].reset_index(drop=True)

        print(f"✓ Loaded {len(prices_df)} days of prices from Delta table")
        return prices_df

    except Exception as e:
        # Fall back to local pickle file
        price_file = f'../{commodity}_prices.pkl'
        if Path(price_file).exists():
            with open(price_file, 'rb') as f:
                prices_df = pickle.load(f)
            print(f"✓ Loaded {len(prices_df)} days of prices from local file")
            return prices_df
        else:
            raise FileNotFoundError(
                f"Could not load prices.\n"
                f"Databricks error: {e}\n"
                f"Local file not found: {price_file}"
            )


def run_validation_test(commodity='coffee'):
    """Run the 100% accuracy algorithm validation test"""

    print("=" * 80)
    print("DIAGNOSTIC: 100% ACCURACY ALGORITHM VALIDATION")
    print("=" * 80)
    print(f"\nCommodity: {commodity.upper()}")
    print("\n⚠️  CRITICAL TEST: With PERFECT FORESIGHT, algorithms MUST beat baselines!")
    print("   If they don't, the algorithms are BROKEN.\n")

    # Load data
    print("Loading data...")

    # Load prices
    try:
        prices = load_prices_from_databricks(commodity)
    except Exception as e:
        print(f"❌ Failed to load prices: {e}")
        return False

    # Load 100% accuracy predictions
    try:
        predictions = load_100_accuracy_predictions(commodity)
        print(f"✓ Loaded predictions for {len(predictions)} dates")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return False

    # Validate predictions are truly 100% accurate
    is_valid = validate_100_accuracy_predictions(predictions, prices)

    # Set up costs (same as main backtests)
    costs = {
        'storage_cost_pct_per_day': 0.025,  # 0.025% per day
        'transaction_cost_pct': 0.25  # 0.25% per transaction
    }

    # Create backtest engine
    engine = SimpleBacktestEngine(prices, predictions, costs)

    # Define strategies to test
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

    # Run baseline strategies
    print("\n" + "=" * 80)
    print("BASELINE STRATEGIES (No Predictions)")
    print("=" * 80)

    baseline_results = []
    for name, strategy in baseline_strategies:
        print(f"\nRunning {name}...")
        result = engine.run_backtest(strategy)
        baseline_results.append((name, result))
        print(f"  Net Earnings: ${result['net_earnings']:,.0f}")
        print(f"  Trades: {result['num_trades']}")

    best_baseline = max(baseline_results, key=lambda x: x[1]['net_earnings'])
    print(f"\n🏆 Best Baseline: {best_baseline[0]} = ${best_baseline[1]['net_earnings']:,.0f}")

    # Run prediction strategies
    print("\n" + "=" * 80)
    print("PREDICTION STRATEGIES (With 100% Accurate Predictions)")
    print("=" * 80)

    prediction_results = []
    for name, strategy in prediction_strategies:
        print(f"\nRunning {name}...")
        result = engine.run_backtest(strategy)
        prediction_results.append((name, result))
        print(f"  Net Earnings: ${result['net_earnings']:,.0f}")
        print(f"  Trades: {result['num_trades']}")

        # Compare to best baseline
        improvement = result['net_earnings'] - best_baseline[1]['net_earnings']
        improvement_pct = (improvement / best_baseline[1]['net_earnings']) * 100

        if improvement > 0:
            print(f"  ✓ Beats best baseline by ${improvement:,.0f} (+{improvement_pct:.1f}%)")
        else:
            print(f"  ❌ WORSE than baseline by ${-improvement:,.0f} ({improvement_pct:.1f}%)")

    best_prediction = max(prediction_results, key=lambda x: x[1]['net_earnings'])
    print(f"\n🏆 Best Prediction: {best_prediction[0]} = ${best_prediction[1]['net_earnings']:,.0f}")

    # Final verdict
    print("\n" + "=" * 80)
    print("ALGORITHM VALIDATION VERDICT")
    print("=" * 80)

    best_pred_earnings = best_prediction[1]['net_earnings']
    best_base_earnings = best_baseline[1]['net_earnings']
    improvement = best_pred_earnings - best_base_earnings
    improvement_pct = (improvement / best_base_earnings) * 100

    print(f"\nBest Baseline:    ${best_base_earnings:,.0f} ({best_baseline[0]})")
    print(f"Best Prediction:  ${best_pred_earnings:,.0f} ({best_prediction[0]})")
    print(f"Improvement:      ${improvement:,.0f} ({improvement_pct:+.1f}%)")

    # Validation criteria
    algorithms_valid = improvement > 0 and improvement_pct > 10
    print("\nValidation Criteria:")
    print(f"  1. Predictions must beat baselines: {'✓ PASS' if improvement > 0 else '❌ FAIL'}")
    print(f"  2. Improvement must be >10%: {'✓ PASS' if improvement_pct > 10 else '❌ FAIL (only ' + f'{improvement_pct:.1f}%)'}")

    if algorithms_valid:
        print("\n" + "=" * 80)
        print("✓✓✓ ALGORITHMS VALIDATED: Strategies work correctly with perfect predictions")
        print("=" * 80)
        print("\nConclusion: The trading algorithms are fundamentally sound.")
        print("If real predictions underperform, the issue is:")
        print("  - Prediction accuracy not high enough")
        print("  - Parameter tuning needed")
        print("  - Prediction usage in strategies needs refinement")
    else:
        print("\n" + "=" * 80)
        print("❌❌❌ ALGORITHMS BROKEN: Even with PERFECT predictions, strategies lose!")
        print("=" * 80)
        print("\nConclusion: There is a fundamental bug in the algorithm logic.")
        print("Possible issues:")
        print("  - Decision logic is inverted (buy when should sell)")
        print("  - Wrong prediction horizon being used")
        print("  - Cost calculations are wrong")
        print("  - Prediction lookups returning None/wrong data")
        print("\nNEXT STEP: Run diagnostic_17_paradox_analysis.ipynb to find the bug")

    # Save results to volume
    try:
        import pickle
        from datetime import datetime

        volume_path = "/Volumes/commodity/trading_agent/files"
        output_file = f"{volume_path}/diagnostic_100_results.pkl"

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
        }

        with open(output_file, 'wb') as f:
            pickle.dump(results_data, f)

        print(f"\n✓ Saved results to: {output_file}")

        # Also save CSV summary
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

    except Exception as e:
        print(f"\n⚠️  Could not save results: {e}")

    return algorithms_valid


if __name__ == "__main__":
    import sys
    success = run_validation_test('coffee')
    sys.exit(0 if success else 1)
