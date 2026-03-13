"""
Linear Programming Optimizer for Theoretical Maximum

Formulates the optimal liquidation problem as a Linear Program and solves exactly.

This is the OPTIMAL approach based on academic literature:
- "Optimal Commodity Trading with a Capacitated Storage Asset" (Management Science, 2010)
- Deterministic inventory liquidation with perfect price foresight

Mathematical Formulation:
  Decision Variables:
    - sell[t] ≥ 0: tons to sell on day t

  Objective: Maximize
    sum_t [ sell[t] * price[t] * (1 - trans_cost%) ]
    - sum_t [ inventory[t] * price[t] * storage_cost% ]

  Constraints:
    - inventory[t] = inventory[t-1] + harvest[t] - sell[t]  (inventory balance)
    - sell[t] <= inventory[t-1] + harvest[t]                (can't sell more than you have)
    - inventory[T] = 0                                      (liquidate all by end)
    - sell[t], inventory[t] >= 0                            (non-negativity)

Since this is a Linear Program with a few thousand variables (~1000 days × 2 variables/day),
standard LP solvers (like scipy.optimize.linprog or PuLP with CBC) can solve it quickly.
"""

import numpy as np
import pandas as pd
from typing import Dict
from scipy.optimize import linprog


def solve_optimal_liquidation_lp(
    prices_df: pd.DataFrame,
    harvest_schedule: pd.DataFrame,
    storage_cost_pct_per_day: float,
    transaction_cost_pct: float
) -> Dict:
    """
    Solve the optimal liquidation problem using Linear Programming.

    Args:
        prices_df: DataFrame with [date, price] (cents/lb)
        harvest_schedule: DataFrame with [date, daily_increment, ...]
        storage_cost_pct_per_day: Storage cost % per day
        transaction_cost_pct: Transaction cost %

    Returns:
        Dict with optimal policy and net earnings
    """
    print(f"   Linear Programming Formulation:")

    # Merge and prepare data
    df = prices_df.merge(harvest_schedule, on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df['daily_increment'] = df['daily_increment'].fillna(0)

    prices = df['price'].values  # cents/lb
    harvest = df['daily_increment'].values  # tons
    n_days = len(df)

    print(f"     Days: {n_days}")
    print(f"     Total harvest: {harvest.sum():.1f} tons")

    # Convert prices to $/ton
    price_per_ton = prices * 20  # 2000 lbs = 1 ton

    # ====================
    # DECISION VARIABLES
    # ====================
    # Variables: [sell[0], sell[1], ..., sell[T-1], inv[0], inv[1], ..., inv[T-1]]
    # Total: 2 * n_days variables

    var_sell_start = 0
    var_inv_start = n_days

    # ====================
    # OBJECTIVE FUNCTION (MINIMIZE NEGATIVE NET EARNINGS)
    # ====================
    # Maximize: revenue - transaction_costs - storage_costs
    # Scipy minimizes, so we minimize the negative

    c = np.zeros(2 * n_days)

    # Revenue - transaction costs: sell[t] * price[t] * (1 - trans_cost%)
    revenue_coeff = price_per_ton * (1 - transaction_cost_pct / 100)
    c[var_sell_start:var_inv_start] = -revenue_coeff  # Negative because minimizing

    # Storage costs: inventory[t] * price[t] * storage_cost%
    storage_coeff = price_per_ton * (storage_cost_pct_per_day / 100)
    c[var_inv_start:] = storage_coeff  # Positive (cost, we want to minimize)

    # ====================
    # CONSTRAINTS (A_eq * x = b_eq)
    # ====================
    # Inventory balance: inventory[t] = inventory[t-1] + harvest[t] - sell[t]
    # Rearranged: inventory[t] - inventory[t-1] + sell[t] = harvest[t]

    A_eq = []
    b_eq = []

    for t in range(n_days):
        row = np.zeros(2 * n_days)

        # sell[t] coefficient: +1
        row[var_sell_start + t] = 1

        # inventory[t] coefficient: +1
        row[var_inv_start + t] = 1

        # inventory[t-1] coefficient: -1
        if t > 0:
            row[var_inv_start + t - 1] = -1

        A_eq.append(row)
        b_eq.append(harvest[t])

    A_eq = np.array(A_eq)
    b_eq = np.array(b_eq)

    # Final constraint: inventory[T-1] = 0 (liquidate all)
    final_inv_row = np.zeros(2 * n_days)
    final_inv_row[var_inv_start + n_days - 1] = 1
    A_eq = np.vstack([A_eq, final_inv_row])
    b_eq = np.append(b_eq, 0)

    # ====================
    # BOUNDS (NON-NEGATIVITY)
    # ====================
    # All variables >= 0
    bounds = [(0, None) for _ in range(2 * n_days)]

    # ====================
    # SOLVE LP
    # ====================
    print(f"     Decision variables: {2 * n_days:,}")
    print(f"     Equality constraints: {len(b_eq)}")
    print(f"     Solving LP...")

    result = linprog(
        c=c,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method='highs',  # Use HiGHS solver (fastest for this size)
        options={'disp': False}
    )

    if not result.success:
        raise RuntimeError(f"LP solver failed: {result.message}")

    print(f"     ✓ Solver converged in {result.nit} iterations")

    # Extract solution
    sell_solution = result.x[var_sell_start:var_inv_start]
    inv_solution = result.x[var_inv_start:]

    # Calculate net earnings (negative of objective value)
    net_earnings = -result.fun

    # Extract trades (days where sell > 0.01 tons)
    trades = []
    for t in range(n_days):
        if sell_solution[t] > 0.01:  # Threshold to filter numerical noise
            price = prices[t]
            sell_amt = sell_solution[t]
            revenue = sell_amt * price_per_ton[t]
            transaction_cost = revenue * (transaction_cost_pct / 100)

            trades.append({
                'day': t,
                'date': df.loc[t, 'date'],
                'price': price,
                'amount': sell_amt,
                'revenue': revenue,
                'transaction_cost': transaction_cost
            })

    # Calculate total costs
    total_revenue = sum(t['revenue'] for t in trades)
    total_transaction_costs = sum(t['transaction_cost'] for t in trades)
    total_storage_costs = np.sum(inv_solution * storage_coeff)

    # Daily state
    daily_states = []
    for t in range(n_days):
        daily_states.append({
            'day': t,
            'date': df.loc[t, 'date'],
            'price': prices[t],
            'inventory': inv_solution[t],
            'sell_amount': sell_solution[t],
            'storage_cost': inv_solution[t] * storage_coeff[t]
        })

    print(f"   ✓ Optimal Solution:")
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
        'sell_schedule': sell_solution,
        'inventory_schedule': inv_solution
    }
