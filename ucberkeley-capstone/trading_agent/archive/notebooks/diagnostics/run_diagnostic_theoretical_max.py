"""
Diagnostic: Theoretical Maximum Benchmark

Calculates the BEST possible performance with perfect 14-day foresight using dynamic programming.
Compares actual strategy performance to theoretical maximum to measure efficiency.

Key Questions:
1. With 100% accurate predictions, what's the absolute best we could do?
2. How efficient are our current strategies? (Actual / Theoretical Max)
3. Where are we leaving money on the table?

Output:
- Theoretical maximum net earnings
- Efficiency ratios for each strategy
- Decision-by-decision comparison
- Missed opportunity analysis
"""

import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

# Import strategies
import importlib.util

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics/all_strategies_pct.py',
    'all_strategies_pct.py'
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

# Import strategy classes
ConsensusStrategy = strat.ConsensusStrategy

# Spark import
from pyspark.sql import SparkSession


class TheoreticalMaxCalculator:
    """
    Calculates theoretical maximum performance with perfect foresight using DP.

    Given perfect 14-day predictions, finds optimal selling policy that maximizes net earnings.
    """

    def __init__(self, prices_df, predictions, config):
        """
        Args:
            prices_df: DataFrame with columns ['date', 'price']
            predictions: Dict mapping date -> prediction matrix (runs × horizons)
            config: Dict with 'storage_cost_pct_per_day', 'transaction_cost_pct'
        """
        self.prices = prices_df
        self.predictions = predictions
        self.config = config

        # Discretize inventory levels for DP (every 5% of total)
        self.inventory_levels = np.arange(0, 51, 2.5)  # 0, 2.5, 5.0, ..., 50.0

    def calculate_optimal_policy(self, initial_inventory=50.0):
        """
        Use dynamic programming to find optimal policy.

        Returns:
            - optimal_decisions: List of (day, inventory, amount_sold, price, net_benefit)
            - total_net_earnings: Maximum achievable net earnings
        """
        n_days = len(self.prices)

        # DP table: dp[day][inventory_idx] = max net earnings from day onwards
        # We'll work backwards from last day to first day
        dp = {}
        decisions = {}  # Track optimal decisions: [day][inventory_idx] = amount_to_sell

        # Base case: Last day (force liquidation)
        last_day = n_days - 1
        last_price = self.prices.iloc[last_day]['price']

        dp[last_day] = {}
        decisions[last_day] = {}

        for inv_idx, inventory in enumerate(self.inventory_levels):
            if inventory > 0:
                # Sell everything on last day
                revenue = inventory * last_price * 20
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100
                net = revenue - trans_cost
                dp[last_day][inv_idx] = net
                decisions[last_day][inv_idx] = inventory
            else:
                dp[last_day][inv_idx] = 0
                decisions[last_day][inv_idx] = 0

        # Work backwards from day n-2 to day 0
        for day in range(last_day - 1, -1, -1):
            dp[day] = {}
            decisions[day] = {}

            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']

            # Get predictions for this day (use mean of prediction matrix)
            pred_matrix = self.predictions.get(current_date)
            if pred_matrix is not None:
                # Use mean prediction for each horizon
                future_prices = pred_matrix.mean(axis=0)  # Average across runs
            else:
                # No predictions available, use current price as estimate
                future_prices = np.full(14, current_price)

            # For each inventory level
            for inv_idx, inventory in enumerate(self.inventory_levels):
                if inventory <= 0:
                    dp[day][inv_idx] = 0
                    decisions[day][inv_idx] = 0
                    continue

                # Try all possible sell amounts (discretized)
                best_value = -np.inf
                best_action = 0

                # Possible actions: sell 0%, 10%, 20%, ..., 100% of inventory
                for pct in np.arange(0, 1.01, 0.1):
                    amount_to_sell = inventory * pct

                    if amount_to_sell > 0:
                        # Calculate immediate revenue and costs
                        revenue = amount_to_sell * current_price * 20
                        trans_cost = revenue * self.config['transaction_cost_pct'] / 100
                        immediate_net = revenue - trans_cost
                    else:
                        immediate_net = 0

                    # Calculate remaining inventory and storage cost
                    remaining_inv = inventory - amount_to_sell

                    if remaining_inv > 0 and day < last_day:
                        # Storage cost for holding remaining inventory to next day
                        avg_price = self.prices.iloc[:day+1]['price'].mean()
                        storage_cost = remaining_inv * avg_price * 20 * self.config['storage_cost_pct_per_day'] / 100
                    else:
                        storage_cost = 0

                    # Find closest inventory level for next day
                    if day < last_day:
                        next_inv_idx = np.argmin(np.abs(self.inventory_levels - remaining_inv))
                        future_value = dp[day + 1][next_inv_idx]
                    else:
                        future_value = 0

                    total_value = immediate_net - storage_cost + future_value

                    if total_value > best_value:
                        best_value = total_value
                        best_action = amount_to_sell

                dp[day][inv_idx] = best_value
                decisions[day][inv_idx] = best_action

        # Extract optimal path starting from initial inventory
        optimal_decisions = []
        current_inv = initial_inventory
        total_revenue = 0
        total_transaction_costs = 0
        total_storage_costs = 0

        for day in range(n_days):
            # Find closest inventory level
            inv_idx = np.argmin(np.abs(self.inventory_levels - current_inv))
            amount_to_sell = decisions[day][inv_idx]

            if amount_to_sell > 0:
                price = self.prices.iloc[day]['price']
                revenue = amount_to_sell * price * 20
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100

                total_revenue += revenue
                total_transaction_costs += trans_cost

                current_inv -= amount_to_sell

            # Storage cost
            if current_inv > 0 and day < n_days - 1:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                storage_cost = current_inv * avg_price * 20 * self.config['storage_cost_pct_per_day'] / 100
                total_storage_costs += storage_cost

            optimal_decisions.append({
                'day': day,
                'date': self.prices.iloc[day]['date'],
                'inventory_before': current_inv + (amount_to_sell if amount_to_sell > 0 else 0),
                'amount_sold': amount_to_sell,
                'price': self.prices.iloc[day]['price'],
                'revenue': revenue if amount_to_sell > 0 else 0,
                'inventory_after': current_inv
            })

        total_net_earnings = total_revenue - total_transaction_costs - total_storage_costs

        return {
            'optimal_decisions': optimal_decisions,
            'total_net_earnings': total_net_earnings,
            'total_revenue': total_revenue,
            'total_transaction_costs': total_transaction_costs,
            'total_storage_costs': total_storage_costs,
            'num_trades': sum(1 for d in optimal_decisions if d['amount_sold'] > 0)
        }


def main():
    print("="*80)
    print("DIAGNOSTIC: THEORETICAL MAXIMUM BENCHMARK")
    print("="*80)
    print(f"Started: {datetime.now()}")

    # Configuration
    COMMODITY = 'coffee'
    MODEL_VERSION = 'synthetic_acc100'  # Perfect predictions

    config = {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    }

    # Load data
    print("\n1. Loading data...")
    spark = SparkSession.builder.getOrCreate()

    # Load prices
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = '{COMMODITY}'"
    ).toPandas()
    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
    prices = prices[prices['date'] >= '2022-01-01'].reset_index(drop=True)

    print(f"✓ Loaded {len(prices)} price points")

    # Load predictions
    pred_table = f"commodity.trading_agent.predictions_{COMMODITY}"
    pred_df = spark.table(pred_table).filter(
        f"model_version = '{MODEL_VERSION}'"
    ).toPandas()

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

    print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

    # Calculate theoretical maximum
    print("\n2. Calculating theoretical maximum with DP...")
    calculator = TheoreticalMaxCalculator(prices, prediction_matrices, config)
    optimal_result = calculator.calculate_optimal_policy(initial_inventory=50.0)

    print(f"\n{'='*80}")
    print("THEORETICAL MAXIMUM (Perfect Foresight + Optimal Policy)")
    print(f"{'='*80}")
    print(f"Net Earnings:        ${optimal_result['total_net_earnings']:,.2f}")
    print(f"Total Revenue:       ${optimal_result['total_revenue']:,.2f}")
    print(f"Transaction Costs:   ${optimal_result['total_transaction_costs']:,.2f}")
    print(f"Storage Costs:       ${optimal_result['total_storage_costs']:,.2f}")
    print(f"Number of Trades:    {optimal_result['num_trades']}")

    # Load actual strategy results for comparison
    print("\n3. Loading actual strategy results...")

    # We'll load from diagnostic_100 results
    summary_path = "/Volumes/commodity/trading_agent/files/diagnostic_100_REDESIGNED_summary.csv"
    try:
        actual_results = pd.read_csv(summary_path)

        print(f"\n{'='*80}")
        print("EFFICIENCY COMPARISON (Actual vs Theoretical Maximum)")
        print(f"{'='*80}")
        print(f"\nTheoretical Maximum: ${optimal_result['total_net_earnings']:,.2f}")
        print(f"\nActual Strategies:")

        efficiency_results = []

        for idx, row in actual_results.iterrows():
            strategy = row['strategy']
            actual_earnings = row['net_earnings']
            efficiency = (actual_earnings / optimal_result['total_net_earnings']) * 100

            efficiency_results.append({
                'strategy': strategy,
                'actual_earnings': actual_earnings,
                'theoretical_max': optimal_result['total_net_earnings'],
                'efficiency_pct': efficiency,
                'gap': optimal_result['total_net_earnings'] - actual_earnings
            })

            print(f"  {strategy:30s}: ${actual_earnings:>10,.2f}  ({efficiency:5.1f}% efficient, gap: ${optimal_result['total_net_earnings'] - actual_earnings:,.2f})")

        efficiency_df = pd.DataFrame(efficiency_results)

    except FileNotFoundError:
        print("Warning: Could not load actual strategy results for comparison")
        efficiency_df = pd.DataFrame()

    # Save results
    print("\n4. Saving results...")
    volume_path = "/Volumes/commodity/trading_agent/files"

    # Save optimal decisions
    decisions_df = pd.DataFrame(optimal_result['optimal_decisions'])
    decisions_file = f"{volume_path}/diagnostic_theoretical_max_decisions.csv"
    decisions_df.to_csv(decisions_file, index=False)
    print(f"✓ Saved decisions to: {decisions_file}")

    # Save efficiency comparison
    if not efficiency_df.empty:
        efficiency_file = f"{volume_path}/diagnostic_theoretical_max_efficiency.csv"
        efficiency_df.to_csv(efficiency_file, index=False)
        print(f"✓ Saved efficiency comparison to: {efficiency_file}")

    # Save summary
    summary = {
        'timestamp': datetime.now(),
        'commodity': COMMODITY,
        'model_version': MODEL_VERSION,
        'theoretical_max_earnings': optimal_result['total_net_earnings'],
        'theoretical_max_revenue': optimal_result['total_revenue'],
        'theoretical_max_trades': optimal_result['num_trades'],
        'config': config
    }

    summary_file = f"{volume_path}/diagnostic_theoretical_max_summary.pkl"
    with open(summary_file, 'wb') as f:
        pickle.dump(summary, f)
    print(f"✓ Saved summary to: {summary_file}")

    print(f"\n{'='*80}")
    print("DIAGNOSTIC COMPLETE")
    print(f"Completed: {datetime.now()}")
    print(f"{'='*80}")

    # Key insights
    print("\n📊 KEY INSIGHTS:")
    if not efficiency_df.empty:
        best_strategy = efficiency_df.loc[efficiency_df['efficiency_pct'].idxmax()]
        print(f"\nBest Strategy: {best_strategy['strategy']}")
        print(f"  Efficiency: {best_strategy['efficiency_pct']:.1f}%")
        print(f"  Gap to optimal: ${best_strategy['gap']:,.2f}")

        if best_strategy['efficiency_pct'] > 80:
            print("\n✅ EXCELLENT: Algorithms are >80% efficient")
        elif best_strategy['efficiency_pct'] > 70:
            print("\n✓ GOOD: Algorithms are >70% efficient, room for optimization")
        elif best_strategy['efficiency_pct'] > 60:
            print("\n⚠️ MODERATE: Algorithms are 60-70% efficient, significant room for improvement")
        else:
            print("\n❌ POOR: Algorithms are <60% efficient, fundamental issues with decision logic")

    return True


if __name__ == "__main__":
    success = main()
    if not success:
        raise RuntimeError("Diagnostic failed")
