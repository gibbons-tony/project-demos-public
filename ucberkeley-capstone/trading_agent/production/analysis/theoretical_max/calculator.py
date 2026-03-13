"""
Theoretical Maximum Calculator

Calculates the BEST possible performance with perfect 14-day foresight using dynamic programming.
Provides upper bound for strategy performance.

Algorithm:
    - Dynamic programming with discretized inventory levels
    - Works backwards from last day to first day
    - At each state (day, inventory), tries all possible sell amounts
    - Considers storage costs, transaction costs, and future value
    - Returns optimal policy and maximum achievable earnings

Usage:
    calculator = TheoreticalMaxCalculator(prices, predictions, config)
    result = calculator.calculate_optimal_policy(initial_inventory=50.0)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple


class TheoreticalMaxCalculator:
    """
    Calculates theoretical maximum performance with perfect foresight using DP.

    Given perfect 14-day predictions, finds optimal selling policy that maximizes net earnings
    while accounting for storage costs, transaction costs, and market dynamics.

    Attributes:
        prices (pd.DataFrame): Price data with columns ['date', 'price']
        predictions (Dict): Mapping from date -> prediction matrix (runs × horizons)
        config (Dict): Configuration with 'storage_cost_pct_per_day', 'transaction_cost_pct'
        inventory_levels (np.ndarray): Discretized inventory levels for DP
    """

    def __init__(
        self,
        prices_df: pd.DataFrame,
        predictions: Dict[pd.Timestamp, np.ndarray],
        config: Dict,
        inventory_granularity: float = 2.5
    ):
        """
        Initialize calculator.

        Args:
            prices_df: DataFrame with columns ['date', 'price']
            predictions: Dict mapping date -> prediction matrix (runs × horizons)
            config: Dict with cost parameters:
                - storage_cost_pct_per_day: float (e.g., 0.005 = 0.005% per day)
                - transaction_cost_pct: float (e.g., 0.01 = 0.01% per transaction)
            inventory_granularity: float (default 2.5) - step size for inventory discretization

        Raises:
            ValueError: If required config keys are missing
        """
        # Validate config
        required_keys = ['storage_cost_pct_per_day', 'transaction_cost_pct']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

        self.prices = prices_df.copy().sort_values('date').reset_index(drop=True)
        self.predictions = predictions
        self.config = config

        # Discretize inventory levels (0 to 50 tons in steps)
        # Using 2.5 ton increments for reasonable computation time
        self.inventory_levels = np.arange(0, 51, inventory_granularity)

        # Constants
        self.PRICE_MULTIPLIER = 20  # Convert cents/lb to $/ton

    def calculate_optimal_policy(
        self,
        initial_inventory: float = 50.0
    ) -> Dict:
        """
        Use dynamic programming to find optimal selling policy.

        Algorithm:
            1. Initialize DP table: dp[day][inventory_idx] = max net earnings from day onwards
            2. Base case (last day): Force liquidation of all remaining inventory
            3. Work backwards: For each (day, inventory) state:
                - Try all possible sell amounts (0%, 10%, 20%, ..., 100%)
                - Calculate immediate revenue, costs, and future value
                - Keep action that maximizes total value
            4. Extract optimal path from initial state

        Args:
            initial_inventory: float (default 50.0) - starting inventory in tons

        Returns:
            Dict with:
                - optimal_decisions: List[Dict] - day-by-day optimal actions
                - total_net_earnings: float - maximum achievable net earnings
                - total_revenue: float - gross revenue from all sales
                - total_transaction_costs: float - cumulative transaction costs
                - total_storage_costs: float - cumulative storage costs
                - num_trades: int - number of non-zero sales
        """
        n_days = len(self.prices)

        # DP table: dp[day][inventory_idx] = max net earnings from day onwards
        dp = {}
        decisions = {}  # Track optimal decisions: [day][inventory_idx] = amount_to_sell

        # ----------------------------------------------------------------------
        # Base Case: Last Day (Force Liquidation)
        # ----------------------------------------------------------------------
        last_day = n_days - 1
        last_price = self.prices.iloc[last_day]['price']

        dp[last_day] = {}
        decisions[last_day] = {}

        for inv_idx, inventory in enumerate(self.inventory_levels):
            if inventory > 0:
                # Sell everything on last day
                revenue = inventory * last_price * self.PRICE_MULTIPLIER
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100
                net = revenue - trans_cost
                dp[last_day][inv_idx] = net
                decisions[last_day][inv_idx] = inventory
            else:
                dp[last_day][inv_idx] = 0
                decisions[last_day][inv_idx] = 0

        # ----------------------------------------------------------------------
        # Backward Induction: Days n-2 to 0
        # ----------------------------------------------------------------------
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

                    # Calculate immediate revenue and costs
                    if amount_to_sell > 0:
                        revenue = amount_to_sell * current_price * self.PRICE_MULTIPLIER
                        trans_cost = revenue * self.config['transaction_cost_pct'] / 100
                        immediate_net = revenue - trans_cost
                    else:
                        immediate_net = 0

                    # Calculate remaining inventory and storage cost
                    remaining_inv = inventory - amount_to_sell

                    if remaining_inv > 0 and day < last_day:
                        # Storage cost for holding remaining inventory to next day
                        avg_price = self.prices.iloc[:day+1]['price'].mean()
                        storage_cost = (
                            remaining_inv
                            * avg_price
                            * self.PRICE_MULTIPLIER
                            * self.config['storage_cost_pct_per_day'] / 100
                        )
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

        # ----------------------------------------------------------------------
        # Extract Optimal Path
        # ----------------------------------------------------------------------
        optimal_decisions = []
        current_inv = initial_inventory
        total_revenue = 0
        total_transaction_costs = 0
        total_storage_costs = 0

        for day in range(n_days):
            # Find closest inventory level
            inv_idx = np.argmin(np.abs(self.inventory_levels - current_inv))
            amount_to_sell = decisions[day][inv_idx]

            revenue = 0
            trans_cost = 0

            if amount_to_sell > 0:
                price = self.prices.iloc[day]['price']
                revenue = amount_to_sell * price * self.PRICE_MULTIPLIER
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100

                total_revenue += revenue
                total_transaction_costs += trans_cost

                current_inv -= amount_to_sell

            # Storage cost
            storage_cost = 0
            if current_inv > 0 and day < n_days - 1:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                storage_cost = (
                    current_inv
                    * avg_price
                    * self.PRICE_MULTIPLIER
                    * self.config['storage_cost_pct_per_day'] / 100
                )
                total_storage_costs += storage_cost

            optimal_decisions.append({
                'day': day,
                'date': self.prices.iloc[day]['date'],
                'inventory_before': current_inv + (amount_to_sell if amount_to_sell > 0 else 0),
                'amount_sold': amount_to_sell,
                'price': self.prices.iloc[day]['price'],
                'revenue': revenue,
                'transaction_cost': trans_cost,
                'storage_cost': storage_cost,
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

    def get_summary_stats(self, optimal_result: Dict) -> pd.DataFrame:
        """
        Get summary statistics from optimal policy result.

        Args:
            optimal_result: Dict returned from calculate_optimal_policy()

        Returns:
            pd.DataFrame with summary metrics
        """
        decisions = pd.DataFrame(optimal_result['optimal_decisions'])

        summary = {
            'Total Net Earnings': optimal_result['total_net_earnings'],
            'Total Revenue': optimal_result['total_revenue'],
            'Total Transaction Costs': optimal_result['total_transaction_costs'],
            'Total Storage Costs': optimal_result['total_storage_costs'],
            'Number of Trades': optimal_result['num_trades'],
            'Avg Sale Price': decisions[decisions['amount_sold'] > 0]['price'].mean(),
            'Days to Liquidate': len(decisions[decisions['inventory_after'] > 0]),
            'Max Daily Sale': decisions['amount_sold'].max(),
            'Avg Daily Sale (when selling)': decisions[decisions['amount_sold'] > 0]['amount_sold'].mean()
        }

        return pd.DataFrame([summary])
