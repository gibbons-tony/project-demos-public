"""
Trading Strategies for WhatsApp Lambda

Extracted from 03_strategy_implementations.ipynb (Version 3.0).
Implements ExpectedValueStrategy exactly as used in backtesting.

Source: /Users/markgibbons/capstone/ucberkeley-capstone/trading_agent/
        commodity_prediction_analysis/03_strategy_implementations.ipynb
"""

import numpy as np
from typing import Dict, Optional, Tuple


class ExpectedValueStrategy:
    """
    Expected Value Strategy - Best performer for Coffee (+3.4% in backtesting).

    From backtesting notebook 03_strategy_implementations.ipynb:
    - Daily evaluation (not scheduled every 10 days)
    - Storage cost: 0.025% per day (percentage-based)
    - Transaction cost: 0.25% per sale (percentage-based)
    - Cooldown: 7 days between sales
    - Batch sizing: 10-35% based on EV and confidence
    - Technical indicators: RSI, ADX, Coefficient of Variation

    NOTE: In notebook, storage_cost_pct_per_day is the actual percentage (e.g., 0.025),
          not decimal (0.00025). Need to divide by 100 when calculating costs.
    """

    def __init__(
        self,
        storage_cost_pct_per_day: float = 0.025,      # 0.025% per day
        transaction_cost_pct: float = 0.25,           # 0.25% per transaction
        min_ev_improvement: float = 50.0,             # $50/ton minimum
        baseline_batch: float = 0.15,                 # 15% baseline batch
        baseline_frequency: int = 10
    ):
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.min_ev_improvement = min_ev_improvement
        self.baseline_batch = baseline_batch
        self.baseline_frequency = baseline_frequency
        self.cooldown_days = 7
        self.last_sale_day = -self.cooldown_days

    def decide(
        self,
        current_price: float,
        prediction_matrix: np.ndarray,
        inventory: float,
        days_held: int = 0,
        day: int = 0  # Day in simulation (for cooldown tracking)
    ) -> Dict:
        """
        Make trading decision based on expected value calculation.

        Args:
            current_price: Current market price ($/kg)
            prediction_matrix: Monte Carlo predictions (N paths × 14 days)
            inventory: Current inventory (tons)
            days_held: Days since harvest/purchase

        Returns:
            Dict with:
                - action: 'SELL' or 'HOLD'
                - amount: Tons to sell (0 if HOLD)
                - optimal_day: Best day to sell (1-14, 0 if SELL now)
                - expected_gain: Expected gain from waiting ($/ton)
                - total_expected_gain: Total expected gain for inventory
                - reasoning: Human-readable explanation
                - sell_now_value: Value if sell today
                - wait_value: Value if wait for optimal day
        """
        # Calculate median forecasts for each day
        median_forecasts = np.median(prediction_matrix, axis=0)

        # Calculate expected value of selling on each future day
        best_ev = -np.inf
        best_day = 0

        for day in range(14):
            # Expected price on this day
            expected_price = median_forecasts[day]

            # Cumulative storage cost up to this day
            cumulative_storage_cost = current_price * self.storage_cost_pct_per_day * (day + 1)

            # Transaction cost
            transaction_cost = expected_price * self.transaction_cost_pct

            # Net expected value
            ev = expected_price - cumulative_storage_cost - transaction_cost

            if ev > best_ev:
                best_ev = ev
                best_day = day + 1  # Convert to 1-indexed

        # Compare with selling immediately
        immediate_sale_value = current_price - (current_price * self.transaction_cost_pct)

        # Decision threshold
        expected_gain_per_ton = best_ev - immediate_sale_value

        # Calculate total values
        sell_now_total = immediate_sale_value * inventory
        wait_total = best_ev * inventory
        total_expected_gain = expected_gain_per_ton * inventory

        if expected_gain_per_ton > self.min_ev_improvement:
            action = 'HOLD'
            reasoning = f"Expected to gain ${expected_gain_per_ton:.2f}/ton by selling on day {best_day}"
            amount_to_sell = 0
        else:
            action = 'SELL'
            reasoning = f"Immediate sale recommended (expected gain ${expected_gain_per_ton:.2f}/ton < ${self.min_ev_improvement:.0f}/ton threshold)"
            amount_to_sell = inventory
            best_day = 0

        return {
            'action': action,
            'amount': amount_to_sell,
            'optimal_day': best_day,
            'expected_gain_per_ton': expected_gain_per_ton,
            'total_expected_gain': total_expected_gain,
            'reasoning': reasoning,
            'sell_now_value': sell_now_total,
            'wait_value': wait_total
        }


def analyze_forecast(prediction_matrix: np.ndarray, current_price: float) -> Dict:
    """
    Analyze forecast to extract key insights.

    Args:
        prediction_matrix: Monte Carlo predictions (N paths × 14 days)
        current_price: Current market price

    Returns:
        Dict with:
            - price_range: (min, max) tuple for forecast period
            - best_window: (start_day, end_day) tuple for 3-day window
            - best_window_price: Expected price during best window
            - median_by_day: Array of median prices for each day
    """
    # Calculate statistics across all paths for each day
    median_by_day = np.median(prediction_matrix, axis=0)

    # Overall forecast range (10th-90th percentile across all days)
    forecast_min = float(np.percentile(prediction_matrix, 10))
    forecast_max = float(np.percentile(prediction_matrix, 90))

    # Find best sale window (highest median prices, look for 3-day windows)
    window_size = 3
    best_window_start = 0
    best_window_avg = 0

    for start_day in range(len(median_by_day) - window_size + 1):
        window_avg = np.mean(median_by_day[start_day:start_day + window_size])
        if window_avg > best_window_avg:
            best_window_avg = window_avg
            best_window_start = start_day

    best_window_end = best_window_start + window_size - 1

    return {
        'price_range': (forecast_min, forecast_max),
        'best_window': (best_window_start + 1, best_window_end + 1),  # 1-indexed
        'best_window_price': best_window_avg,
        'median_by_day': median_by_day
    }


def calculate_7day_trend(price_history: np.ndarray) -> Tuple[float, str]:
    """
    Calculate 7-day price trend.

    Args:
        price_history: Array of recent prices (at least 8 values)

    Returns:
        (trend_pct, trend_direction) tuple
    """
    if len(price_history) < 2:
        return 0.0, '→'

    prices_7d = price_history[-8:] if len(price_history) >= 8 else price_history

    if len(prices_7d) < 2:
        return 0.0, '→'

    trend_pct = ((prices_7d[-1] - prices_7d[0]) / prices_7d[0]) * 100
    trend_direction = '↑' if trend_pct > 0 else '↓'

    return trend_pct, trend_direction
