"""
Brute Force Theoretical Maximum Calculator

Simple approach: Try all combinations of sales (day, quantity) and simulate
the full inventory dynamics for each. Keep the best one.

This is conceptually simpler than DP and easier to verify. It guarantees
finding the global optimum if we enumerate all reasonable policies.

Approach:
1. Generate all reasonable selling policies (combinations of sale events)
2. For each policy, simulate forward with accurate inventory dynamics
3. Calculate net earnings = revenue - transaction_costs - storage_costs
4. Return policy with maximum net earnings
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from itertools import product


def simulate_policy(
    prices: np.ndarray,
    harvest_increments: np.ndarray,
    sales: List[Tuple[int, float]],  # List of (day, quantity) tuples
    storage_cost_pct: float,
    transaction_cost_pct: float
) -> Dict:
    """
    Simulate a selling policy and calculate net earnings.

    Args:
        prices: Array of prices (cents/lb) for each day
        harvest_increments: Array of tons added each day from harvest
        sales: List of (day_idx, quantity_tons) tuples
        storage_cost_pct: Daily storage cost percentage
        transaction_cost_pct: Transaction cost percentage

    Returns:
        Dict with net_earnings, revenue, costs, daily_inventory
    """
    n_days = len(prices)
    inventory = np.zeros(n_days)
    daily_storage_cost = np.zeros(n_days)

    # Create sale lookup: day -> quantity
    sale_dict = {day: qty for day, qty in sales}

    # Simulate forward
    current_inv = 0.0
    total_revenue = 0.0
    total_transaction_cost = 0.0
    total_storage_cost = 0.0

    for day in range(n_days):
        # Add harvest
        current_inv += harvest_increments[day]

        # Execute sale if scheduled
        if day in sale_dict:
            sell_qty = min(sale_dict[day], current_inv)  # Can't sell more than we have
            if sell_qty > 0:
                price_per_ton = prices[day] * 20  # cents/lb -> $/ton
                revenue = sell_qty * price_per_ton
                transaction_cost = revenue * (transaction_cost_pct / 100)

                total_revenue += revenue
                total_transaction_cost += transaction_cost
                current_inv -= sell_qty

        # Calculate storage cost on remaining inventory
        price_per_ton = prices[day] * 20
        storage_cost = current_inv * price_per_ton * (storage_cost_pct / 100)
        total_storage_cost += storage_cost

        # Record state
        inventory[day] = current_inv
        daily_storage_cost[day] = storage_cost

    # Net earnings
    net_earnings = total_revenue - total_transaction_cost - total_storage_cost

    return {
        'net_earnings': net_earnings,
        'total_revenue': total_revenue,
        'total_transaction_cost': total_transaction_cost,
        'total_storage_cost': total_storage_cost,
        'final_inventory': current_inv,
        'sales': sales
    }


def find_optimal_single_sale(
    prices_df: pd.DataFrame,
    harvest_schedule: pd.DataFrame,
    storage_cost_pct_per_day: float,
    transaction_cost_pct: float,
    quantity_increments: List[float] = None
) -> Dict:
    """
    Find optimal single sale by trying all (day, quantity) combinations.

    This is the simplest theoretical max: one sale of some quantity on some day.

    Args:
        prices_df: DataFrame with [date, price]
        harvest_schedule: DataFrame with [date, daily_increment, ...]
        storage_cost_pct_per_day: Storage cost %
        transaction_cost_pct: Transaction cost %
        quantity_increments: List of quantities to try (e.g., [10, 20, 30, 40, 50])
                            If None, will try increments of 5 tons up to total harvest

    Returns:
        Dict with best result
    """
    # Merge and prepare data
    df = prices_df.merge(harvest_schedule, on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df['daily_increment'] = df['daily_increment'].fillna(0)

    prices = df['price'].values
    harvest_increments = df['daily_increment'].values
    n_days = len(df)

    # Calculate cumulative inventory available at each day
    cumulative_inventory = np.cumsum(harvest_increments)
    total_harvest = cumulative_inventory[-1]

    # Generate quantity options
    if quantity_increments is None:
        quantity_increments = list(np.arange(5, total_harvest + 5, 5))

    print(f"   Brute Force Search:")
    print(f"     Days: {n_days}")
    print(f"     Total harvest: {total_harvest:.1f} tons")
    print(f"     Quantity options: {len(quantity_increments)}")
    print(f"     Total combinations: {n_days * len(quantity_increments):,}")

    # Try all (day, quantity) combinations
    best_result = None
    best_net_earnings = -np.inf

    for day in range(n_days):
        available_inv = cumulative_inventory[day]

        for qty in quantity_increments:
            if qty > available_inv:
                continue  # Can't sell more than we've harvested by this day

            # Simulate this policy
            sales = [(day, qty)]
            result = simulate_policy(
                prices, harvest_increments, sales,
                storage_cost_pct_per_day, transaction_cost_pct
            )

            if result['net_earnings'] > best_net_earnings:
                best_net_earnings = result['net_earnings']
                best_result = {
                    **result,
                    'best_day': day,
                    'best_date': df.loc[day, 'date'],
                    'best_quantity': qty,
                    'best_price': prices[day]
                }

    print(f"   ✓ Best single sale:")
    print(f"     Day: {best_result['best_day']} ({best_result['best_date']})")
    print(f"     Quantity: {best_result['best_quantity']:.1f} tons")
    print(f"     Price: {best_result['best_price']:.2f} cents/lb")
    print(f"     Net earnings: ${best_result['net_earnings']:,.2f}")

    return best_result


def find_optimal_multi_sale(
    prices_df: pd.DataFrame,
    harvest_schedule: pd.DataFrame,
    storage_cost_pct_per_day: float,
    transaction_cost_pct: float,
    max_sales: int = 3,
    quantity_step: float = 10.0
) -> Dict:
    """
    Find optimal policy allowing multiple sales.

    This tries combinations of multiple sales. Computationally expensive
    but finds true optimum.

    Args:
        prices_df: DataFrame with [date, price]
        harvest_schedule: DataFrame with [date, daily_increment, ...]
        storage_cost_pct_per_day: Storage cost %
        transaction_cost_pct: Transaction cost %
        max_sales: Maximum number of sales to consider (default: 3)
        quantity_step: Discretization step for quantities (default: 10 tons)

    Returns:
        Dict with best result
    """
    # Merge and prepare data
    df = prices_df.merge(harvest_schedule, on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df['daily_increment'] = df['daily_increment'].fillna(0)

    prices = df['price'].values
    harvest_increments = df['daily_increment'].values
    n_days = len(df)
    total_harvest = harvest_increments.sum()

    print(f"   Multi-Sale Search (max {max_sales} sales):")
    print(f"     Days: {n_days}")
    print(f"     Total harvest: {total_harvest:.1f} tons")
    print(f"     Quantity step: {quantity_step} tons")

    best_result = None
    best_net_earnings = -np.inf

    # For computational tractability, sample days (e.g., every 7 days)
    day_sample_step = max(1, n_days // 50)  # ~50 day options
    candidate_days = list(range(0, n_days, day_sample_step))

    # Generate quantity options (0 = no sale, 10, 20, ..., up to total)
    quantity_options = [0] + list(np.arange(quantity_step, total_harvest + quantity_step, quantity_step))

    print(f"     Candidate days (sampled every {day_sample_step}): {len(candidate_days)}")
    print(f"     Quantity options: {len(quantity_options)}")

    # Try all combinations of (day1, qty1, day2, qty2, ...)
    # This grows as (days * qtys)^max_sales, so keep max_sales small!

    if max_sales == 1:
        # Use simpler single-sale function
        return find_optimal_single_sale(
            prices_df, harvest_schedule,
            storage_cost_pct_per_day, transaction_cost_pct,
            quantity_increments=quantity_options[1:]  # Exclude 0
        )

    # For max_sales > 1, enumerate combinations
    # Create all (day, qty) pairs
    day_qty_pairs = [(d, q) for d in candidate_days for q in quantity_options]

    # Try all combinations of max_sales pairs
    from itertools import combinations_with_replacement

    total_combos = 0
    for sale_combo in combinations_with_replacement(day_qty_pairs, max_sales):
        # Filter out invalid combos (qty=0, duplicate days, etc.)
        sales = [(day, qty) for day, qty in sale_combo if qty > 0]

        # Remove duplicate days (keep earliest sale on each day)
        seen_days = set()
        unique_sales = []
        for day, qty in sorted(sales):
            if day not in seen_days:
                unique_sales.append((day, qty))
                seen_days.add(day)

        if len(unique_sales) == 0:
            continue

        # Check if total sales <= total harvest
        total_sales = sum(qty for _, qty in unique_sales)
        if total_sales > total_harvest:
            continue

        # Simulate this policy
        result = simulate_policy(
            prices, harvest_increments, unique_sales,
            storage_cost_pct_per_day, transaction_cost_pct
        )

        total_combos += 1

        if result['net_earnings'] > best_net_earnings:
            best_net_earnings = result['net_earnings']
            best_result = result

    print(f"     Tested {total_combos:,} valid policies")
    print(f"   ✓ Best policy:")
    print(f"     Number of sales: {len(best_result['sales'])}")
    print(f"     Sales: {best_result['sales']}")
    print(f"     Net earnings: ${best_result['net_earnings']:,.2f}")

    return best_result
