"""
Check what profit/earnings data exists in backtest results
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

import pickle
import pandas as pd

print("=" * 80)
print("CHECKING BACKTEST PROFIT DATA")
print("=" * 80)

# Load sample detailed results
pickle_path = "/Volumes/commodity/trading_agent/files/results_detailed_coffee_naive.pkl"

with open(pickle_path, 'rb') as f:
    results = pickle.load(f)

print(f"\nStrategies available: {list(results.keys())}")

# Check strategy data
strategy = 'Consensus'
baseline = 'Immediate Sale'

print("\n" + "=" * 80)
print(f"STRATEGY: {strategy}")
print("=" * 80)

if strategy in results:
    data = results[strategy]

    print("\n1. DAILY STATE DATA:")
    if 'daily_state' in data:
        daily_df = data['daily_state']
        print(f"   Columns: {daily_df.columns.tolist()}")
        print(f"   Rows: {len(daily_df)}")
        print(f"\n   First few rows:")
        print(daily_df.head(10).to_string())

    print("\n2. TRADE DATA:")
    if 'trades' in data:
        trades = data['trades']
        print(f"   Number of trades: {len(trades)}")
        if len(trades) > 0:
            trades_df = pd.DataFrame(trades)
            print(f"   Columns: {trades_df.columns.tolist()}")
            print(f"\n   First few trades:")
            print(trades_df.head().to_string())

    print("\n3. SUMMARY METRICS:")
    for key in ['total_revenue', 'total_storage_costs', 'total_transaction_costs', 'net_earnings']:
        if key in data:
            print(f"   {key}: ${data[key]:,.2f}")

print("\n" + "=" * 80)
print(f"BASELINE: {baseline}")
print("=" * 80)

if baseline in results:
    baseline_data = results[baseline]

    print("\n1. DAILY STATE DATA:")
    if 'daily_state' in baseline_data:
        baseline_daily_df = baseline_data['daily_state']
        print(f"   Columns: {baseline_daily_df.columns.tolist()}")
        print(f"   Rows: {len(baseline_daily_df)}")
        print(f"\n   First few rows:")
        print(baseline_daily_df.head(10).to_string())

    print("\n3. SUMMARY METRICS:")
    for key in ['total_revenue', 'total_storage_costs', 'total_transaction_costs', 'net_earnings']:
        if key in baseline_data:
            print(f"   {key}: ${baseline_data[key]:,.2f}")

print("\n" + "=" * 80)
print("DAILY PROFIT CALCULATION EXAMPLE")
print("=" * 80)

# Show how we can calculate daily profit
if strategy in results and baseline in results:
    strat_daily = results[strategy]['daily_state']
    base_daily = results[baseline]['daily_state']

    # Calculate for first 10 days
    print("\nDay-by-day comparison (first 10 days):")
    print(f"{'Day':<5} {'Date':<12} {'Strategy_Net':<15} {'Baseline_Net':<15} {'Difference':<15}")
    print("-" * 70)

    for i in range(min(10, len(strat_daily))):
        date = strat_daily.iloc[i]['date']

        # Strategy value that day
        strat_inv = strat_daily.iloc[i]['inventory']
        strat_price = strat_daily.iloc[i]['price']
        strat_storage = strat_daily.iloc[i]['cumulative_storage_cost']
        strat_inv_value = strat_inv * strat_price * 20  # Convert to $/ton

        # Baseline value that day
        base_row = base_daily[base_daily['date'] == date]
        if len(base_row) > 0:
            base_row = base_row.iloc[0]
            base_inv = base_row['inventory']
            base_price = base_row['price']
            base_storage = base_row['cumulative_storage_cost']
            base_inv_value = base_inv * base_price * 20

            # Simplified comparison (just inventory value - storage for demo)
            strat_net = strat_inv_value - strat_storage
            base_net = base_inv_value - base_storage
            diff = strat_net - base_net

            print(f"{i:<5} {str(date):<12} ${strat_net:>12,.0f}  ${base_net:>12,.0f}  ${diff:>12,.0f}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("\nThe backtest data includes:")
print("✓ Daily inventory levels")
print("✓ Daily prices")
print("✓ Cumulative storage costs")
print("✓ Trade-level revenue and costs")
print("\nWe CAN calculate daily profit difference:")
print("  Profit = (inventory × price) + revenue_to_date - storage_costs - transaction_costs")
print("\nThis is exactly what we should test!")
