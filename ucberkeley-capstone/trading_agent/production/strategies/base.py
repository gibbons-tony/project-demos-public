"""
Base Strategy Class
Extracted from diagnostics/all_strategies_pct.py (improved version)

Clean, minimal base class with essential functionality.
"""

from abc import ABC, abstractmethod


class Strategy(ABC):
    """Base class for all trading strategies"""

    def __init__(self, name):
        self.name = name
        self.harvest_start = None

    @abstractmethod
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        """
        Make trading decision for current day.

        Args:
            day: Current day index
            inventory: Current inventory (tons)
            current_price: Current price (cents/lb)
            price_history: DataFrame with columns ['date', 'price']
            predictions: Optional numpy array (n_paths, n_horizons)

        Returns:
            dict with keys: action ('SELL'/'HOLD'), amount (tons), reason (str)
        """
        pass

    def reset(self):
        """Reset strategy state"""
        self.harvest_start = None

    def set_harvest_start(self, day):
        """Set the day when harvest started"""
        self.harvest_start = day

    def force_liquidate_before_new_harvest(self, inventory):
        """
        Force liquidation of old inventory before new harvest arrives.
        Called by backtest engine when harvest window starts.

        Returns:
            dict with trade decision or None
        """
        if inventory > 0:
            return {'action': 'SELL', 'amount': inventory,
                   'reason': 'new_harvest_starting_liquidate_old_inventory'}
        return None

    def _force_liquidation_check(self, day, inventory):
        """
        Force liquidation approaching day 365.

        Rules:
        - At 365 days: Force sell all remaining inventory
        - At 345-364 days: Gradual liquidation (5% per day)

        Returns:
            dict with trade decision or None
        """
        if self.harvest_start is not None:
            days_since_harvest = day - self.harvest_start
            if days_since_harvest >= 365:
                return {'action': 'SELL', 'amount': inventory,
                       'reason': 'forced_liquidation_365d'}
            elif days_since_harvest >= 345:
                days_left = 365 - days_since_harvest
                return {'action': 'SELL', 'amount': inventory * 0.05,
                       'reason': f'approaching_365d_deadline_{days_left}d_left'}
        return None
