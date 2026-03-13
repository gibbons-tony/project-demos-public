"""
Theoretical Maximum Calculator

Computes the TRUE theoretical maximum net earnings using dynamic programming
with full price visibility and accurate harvest dynamics.

This is NOT a strategy that runs in BacktestEngine - it's a standalone optimizer
that solves the problem exactly:
- Given: prices, harvest schedule, costs
- Find: optimal selling policy that maximizes net earnings
- Constraints: inventory dynamics, age limits, minimum trade sizes

Approach:
- Dynamic Programming with state (day, inventory_level)
- Actions: HOLD or SELL X tons (partial sales allowed)
- Transition: accurate inventory accumulation and drawdown
- Objective: maximize (revenue - transaction_costs - storage_costs)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


def compute_theoretical_maximum(
    prices_df: pd.DataFrame,
    harvest_schedule: pd.DataFrame,
    storage_cost_pct_per_day: float,
    transaction_cost_pct: float,
    min_trade_size: float = 0.1,
    max_age_days: int = 365,
    inventory_discretization: float = 5.0  # Discretize inventory in 5-ton increments
) -> Dict:
    """
    Compute theoretical maximum using dynamic programming.

    Args:
        prices_df: DataFrame with columns [date, price] (cents/lb)
        harvest_schedule: DataFrame with columns [date, daily_increment, is_harvest_day, harvest_year]
        storage_cost_pct_per_day: Daily storage cost as % (e.g., 0.005)
        transaction_cost_pct: Transaction cost as % (e.g., 0.01)
        min_trade_size: Minimum tons to trade (default: 0.1)
        max_age_days: Maximum age before forced sale (default: 365)
        inventory_discretization: Ton increments for DP states (default: 5.0)

    Returns:
        Dict with:
            - max_net_earnings: float
            - optimal_policy: List of (day, action, amount) tuples
            - daily_state: List of daily inventory/revenue states
    """

    # Merge prices and harvest schedule
    df = prices_df.merge(harvest_schedule, on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df['daily_increment'] = df['daily_increment'].fillna(0)

    n_days = len(df)
    prices = df['price'].values  # cents/lb
    harvest_increments = df['daily_increment'].values  # tons per day

    # Determine max possible inventory (cumulative harvest)
    max_inventory = harvest_increments.sum()

    # Discretize inventory levels (to make DP tractable)
    inventory_levels = np.arange(0, max_inventory + inventory_discretization, inventory_discretization)
    n_inventory_states = len(inventory_levels)

    print(f"   DP Setup:")
    print(f"     Days: {n_days}")
    print(f"     Max inventory: {max_inventory:.1f} tons")
    print(f"     Inventory states: {n_inventory_states} (increments of {inventory_discretization} tons)")
    print(f"     Total states: {n_days * n_inventory_states:,}")

    # DP table: dp[day][inv_idx] = (max_value, best_action, sell_amount)
    # best_action: 'HOLD' or 'SELL'
    # sell_amount: tons to sell (0 if HOLD)
    dp = {}
    policy = {}

    # Helper: Find closest inventory index
    def get_inv_idx(inventory):
        """Round inventory to nearest discrete level."""
        idx = np.argmin(np.abs(inventory_levels - inventory))
        return idx

    # Helper: Calculate net value of selling
    def calc_sell_value(day_idx, inventory, sell_amount):
        """Calculate net value from selling sell_amount tons on day_idx."""
        price_per_ton = prices[day_idx] * 20  # Convert cents/lb to $/ton (2000 lbs = 1 ton)
        revenue = sell_amount * price_per_ton
        transaction_cost = revenue * (transaction_cost_pct / 100)
        return revenue - transaction_cost

    # Helper: Calculate storage cost
    def calc_storage_cost(inventory, price_per_ton):
        """Calculate daily storage cost for given inventory."""
        return inventory * price_per_ton * (storage_cost_pct_per_day / 100)

    # ====================
    # BACKWARD INDUCTION
    # ====================

    # Base case: Last day (must sell all inventory)
    last_day = n_days - 1
    for inv_idx in range(n_inventory_states):
        inventory = inventory_levels[inv_idx]
        if inventory > 0:
            # Forced liquidation
            net_value = calc_sell_value(last_day, inventory, inventory)
            dp[(last_day, inv_idx)] = (net_value, 'SELL', inventory)
            policy[(last_day, inv_idx)] = ('SELL', inventory)
        else:
            dp[(last_day, inv_idx)] = (0.0, 'HOLD', 0)
            policy[(last_day, inv_idx)] = ('HOLD', 0)

    # Iterate backward from day n-2 to 0
    for day in range(n_days - 2, -1, -1):
        price_per_ton = prices[day] * 20
        tomorrow_harvest = harvest_increments[day + 1] if day + 1 < n_days else 0

        for inv_idx in range(n_inventory_states):
            current_inventory = inventory_levels[inv_idx]

            # Option 1: HOLD (don't sell)
            # Tomorrow's inventory = current + tomorrow's harvest
            tomorrow_inventory_hold = current_inventory + tomorrow_harvest
            tomorrow_idx_hold = get_inv_idx(tomorrow_inventory_hold)

            # Storage cost for holding today's inventory
            storage_cost_today = calc_storage_cost(current_inventory, price_per_ton)

            # Value of holding = future value - storage cost
            future_value_hold = dp.get((day + 1, tomorrow_idx_hold), (0, 'HOLD', 0))[0]
            value_hold = future_value_hold - storage_cost_today

            # Option 2: SELL (try different sell amounts)
            # We'll check: sell all, sell half, sell in 10-ton increments
            best_sell_value = -np.inf
            best_sell_amount = 0

            if current_inventory >= min_trade_size:
                # Try different sell amounts
                sell_amounts = []

                # Always try selling everything
                sell_amounts.append(current_inventory)

                # Try incremental sales (e.g., 10, 20, 30 tons)
                for sell_amt in np.arange(min_trade_size, current_inventory, 10.0):
                    sell_amounts.append(sell_amt)

                # Try selling half
                if current_inventory / 2 >= min_trade_size:
                    sell_amounts.append(current_inventory / 2)

                for sell_amount in sell_amounts:
                    if sell_amount < min_trade_size:
                        continue
                    if sell_amount > current_inventory:
                        continue

                    # Immediate revenue from sale
                    sale_value = calc_sell_value(day, current_inventory, sell_amount)

                    # Remaining inventory after sale
                    remaining_inventory = current_inventory - sell_amount

                    # Tomorrow's inventory = remaining + tomorrow's harvest
                    tomorrow_inventory_sell = remaining_inventory + tomorrow_harvest
                    tomorrow_idx_sell = get_inv_idx(tomorrow_inventory_sell)

                    # Storage cost on remaining inventory
                    storage_cost_remaining = calc_storage_cost(remaining_inventory, price_per_ton)

                    # Future value
                    future_value_sell = dp.get((day + 1, tomorrow_idx_sell), (0, 'HOLD', 0))[0]

                    # Total value = sale revenue + future value - storage cost
                    total_value_sell = sale_value + future_value_sell - storage_cost_remaining

                    if total_value_sell > best_sell_value:
                        best_sell_value = total_value_sell
                        best_sell_amount = sell_amount

            # Choose best action: HOLD vs SELL
            if best_sell_value > value_hold:
                dp[(day, inv_idx)] = (best_sell_value, 'SELL', best_sell_amount)
                policy[(day, inv_idx)] = ('SELL', best_sell_amount)
            else:
                dp[(day, inv_idx)] = (value_hold, 'HOLD', 0)
                policy[(day, inv_idx)] = ('HOLD', 0)

    # ====================
    # FORWARD SIMULATION
    # ====================

    # Simulate forward using optimal policy to get actual trajectory
    current_inventory = 0.0
    total_revenue = 0.0
    total_transaction_costs = 0.0
    total_storage_costs = 0.0
    trades = []
    daily_states = []

    for day in range(n_days):
        # Add today's harvest
        current_inventory += harvest_increments[day]

        # Look up optimal policy
        inv_idx = get_inv_idx(current_inventory)
        action, sell_amount = policy.get((day, inv_idx), ('HOLD', 0))

        # Calculate storage cost
        price_per_ton = prices[day] * 20
        storage_cost = calc_storage_cost(current_inventory, price_per_ton)
        total_storage_costs += storage_cost

        # Execute action
        if action == 'SELL' and sell_amount > 0:
            revenue = sell_amount * price_per_ton
            transaction_cost = revenue * (transaction_cost_pct / 100)
            total_revenue += revenue
            total_transaction_costs += transaction_cost

            trades.append({
                'day': day,
                'date': df.loc[day, 'date'],
                'price': prices[day],
                'amount': sell_amount,
                'revenue': revenue,
                'transaction_cost': transaction_cost
            })

            current_inventory -= sell_amount

        daily_states.append({
            'day': day,
            'date': df.loc[day, 'date'],
            'price': prices[day],
            'inventory': current_inventory,
            'action': action,
            'sell_amount': sell_amount if action == 'SELL' else 0,
            'storage_cost': storage_cost
        })

    # Final liquidation if any inventory remains
    if current_inventory > min_trade_size:
        print(f"   WARNING: {current_inventory:.2f} tons remaining after simulation (should be 0)")

    # Calculate net earnings
    net_earnings = total_revenue - total_transaction_costs - total_storage_costs

    print(f"   DP Result:")
    print(f"     Net earnings: ${net_earnings:,.2f}")
    print(f"     Total revenue: ${total_revenue:,.2f}")
    print(f"     Transaction costs: ${total_transaction_costs:,.2f}")
    print(f"     Storage costs: ${total_storage_costs:,.2f}")
    print(f"     Number of trades: {len(trades)}")

    return {
        'max_net_earnings': net_earnings,
        'total_revenue': total_revenue,
        'total_transaction_costs': total_transaction_costs,
        'total_storage_costs': total_storage_costs,
        'trades': trades,
        'daily_state': pd.DataFrame(daily_states),
        'policy': policy
    }
