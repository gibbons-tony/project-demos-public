"""
Baseline Trading Strategies
Extracted from diagnostics/all_strategies_pct.py (improved version)

Contains 4 baseline strategies:
1. ImmediateSaleStrategy - Weekly liquidation (naive baseline, no citation)
2. EqualBatchStrategy - Fixed schedule batches (systematic liquidation heuristic)
3. PriceThresholdStrategy - Price trigger + technical indicators
4. MovingAverageStrategy - MA crossover + technical indicators

Academic References:
- Price Threshold & Moving Average strategies based on:
  Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008). "Can commodity futures
  be profitably traded with quantitative market timing strategies?"
  Journal of Banking & Finance, 32(9), 1810-1819.

- Technical indicators (RSI, ADX) from:
  Wilder, J. Welles (1978). New Concepts in Technical Trading Systems.
  Trend Research.

See docs/STRATEGY_ACADEMIC_REFERENCES.md for complete academic citations.
"""

import numpy as np
from .base import Strategy
from .indicators import calculate_rsi, calculate_adx


class ImmediateSaleStrategy(Strategy):
    """
    Baseline: Immediate weekly sales

    Parameters fully exposed for grid search.
    """

    def __init__(self,
                 min_batch_size=5.0,
                 sale_frequency_days=7):
        super().__init__("Immediate Sale")
        self.min_batch_size = min_batch_size
        self.sale_frequency_days = sale_frequency_days
        self.days_since_last_sale = sale_frequency_days

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        ready_to_sell = (self.days_since_last_sale >= self.sale_frequency_days)
        enough_inventory = (inventory >= self.min_batch_size)

        if ready_to_sell and enough_inventory:
            self.days_since_last_sale = 0
            return {'action': 'SELL', 'amount': inventory,
                   'reason': f'immediate_weekly_sale_{inventory:.1f}t'}

        self.days_since_last_sale += 1
        if not enough_inventory:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'accumulating_need_{self.min_batch_size:.1f}t'}
        else:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'waiting_for_sale_day_{self.days_since_last_sale}'}

    def reset(self):
        super().reset()
        self.days_since_last_sale = self.sale_frequency_days


class EqualBatchStrategy(Strategy):
    """
    Baseline: Equal batches on fixed schedule

    Parameters fully exposed for grid search.
    """

    def __init__(self,
                 batch_size=0.25,
                 frequency_days=30):
        super().__init__("Equal Batches")
        self.batch_size = batch_size
        self.frequency = frequency_days
        self.last_sale_day = -frequency_days

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale >= self.frequency:
            amount = inventory * self.batch_size
            self.last_sale_day = day
            return {'action': 'SELL', 'amount': amount, 'reason': 'scheduled_batch'}

        return {'action': 'HOLD', 'amount': 0, 'reason': 'waiting_for_schedule'}

    def reset(self):
        super().reset()
        self.last_sale_day = -self.frequency


class PriceThresholdStrategy(Strategy):
    """
    Baseline: Price threshold trigger

    PERCENTAGE-BASED:
    - threshold_pct: trigger when price > MA × (1 + threshold_pct)
    - All batch sizes parameterized
    - RSI/ADX thresholds parameterized
    """

    def __init__(self,
                 threshold_pct=0.05,
                 # Batch sizing (fully parameterized)
                 batch_baseline=0.25,
                 batch_overbought_strong=0.35,
                 batch_overbought=0.30,
                 batch_strong_trend=0.20,
                 # RSI/ADX thresholds
                 rsi_overbought=70,
                 rsi_moderate=65,
                 adx_strong=25,
                 # Timing
                 cooldown_days=7,
                 max_days_without_sale=60):

        super().__init__("Price Threshold")
        self.threshold_pct = threshold_pct

        # Batch sizing
        self.batch_baseline = batch_baseline
        self.batch_overbought_strong = batch_overbought_strong
        self.batch_overbought = batch_overbought
        self.batch_strong_trend = batch_strong_trend

        # Technical thresholds
        self.rsi_overbought = rsi_overbought
        self.rsi_moderate = rsi_moderate
        self.adx_strong = adx_strong

        # Timing
        self.cooldown_days = cooldown_days
        self.max_days_without_sale = max_days_without_sale
        self.last_sale_day = 0  # Start from day 0, give strategy 60 days to operate

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        # Calculate threshold based on 30-day MA
        if len(price_history) >= 30:
            ma_30 = price_history['price'].tail(30).mean()
            threshold = ma_30 * (1 + self.threshold_pct)
        else:
            threshold = current_price * (1 + self.threshold_pct)

        signal_triggered = current_price > threshold
        can_trade = days_since_sale >= self.cooldown_days

        if not signal_triggered:
            if days_since_sale >= self.max_days_without_sale:
                return self._execute_trade(day, inventory, self.batch_baseline,
                                          f'fallback_{days_since_sale}d')
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'below_threshold_{current_price:.2f}<{threshold:.2f}'}

        if not can_trade:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        # Analyze with historical indicators
        batch_size, reason = self._analyze_historical(current_price, price_history)
        return self._execute_trade(day, inventory, batch_size, reason)

    def _analyze_historical(self, current_price, price_history):
        """Analyze using historical technical indicators"""
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, _, _ = calculate_adx(price_history, period=14)

        if rsi > self.rsi_overbought and adx > self.adx_strong:
            batch_size = self.batch_overbought_strong
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > self.rsi_overbought:
            batch_size = self.batch_overbought
            reason = f'overbought_rsi{rsi:.0f}'
        elif adx > self.adx_strong and rsi < self.rsi_moderate:
            batch_size = self.batch_strong_trend
            reason = f'strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        else:
            batch_size = self.batch_baseline
            reason = f'baseline_rsi{rsi:.0f}_adx{adx:.0f}'

        return batch_size, reason

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = 0


class MovingAverageStrategy(Strategy):
    """
    Baseline: Moving average crossover

    PERCENTAGE-BASED:
    - All batch sizes parameterized
    - RSI/ADX thresholds parameterized

    CRITICAL FIX: Downward crossover triggers SELL (not upward)
    """

    def __init__(self,
                 ma_period=30,
                 # Batch sizing (fully parameterized)
                 batch_baseline=0.25,
                 batch_strong_momentum=0.20,
                 batch_overbought_strong=0.35,
                 batch_overbought=0.30,
                 # RSI/ADX thresholds
                 rsi_overbought=70,
                 rsi_min=45,
                 adx_strong=25,
                 adx_weak=20,
                 # Timing
                 cooldown_days=7,
                 max_days_without_sale=60):

        super().__init__("Moving Average")
        self.period = ma_period

        # Batch sizing
        self.batch_baseline = batch_baseline
        self.batch_strong_momentum = batch_strong_momentum
        self.batch_overbought_strong = batch_overbought_strong
        self.batch_overbought = batch_overbought

        # Technical thresholds
        self.rsi_overbought = rsi_overbought
        self.rsi_min = rsi_min
        self.adx_strong = adx_strong
        self.adx_weak = adx_weak

        # Timing
        self.cooldown_days = cooldown_days
        self.max_days_without_sale = max_days_without_sale
        self.last_sale_day = 0  # Start from day 0, give strategy 60 days to operate

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale >= self.max_days_without_sale:
            return self._execute_trade(day, inventory, self.batch_baseline,
                                      f'fallback_{days_since_sale}d')

        if len(price_history) < self.period + 1:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'insufficient_history'}

        # Crossover detection
        recent_prices = price_history['price'].tail(self.period + 1).values
        ma_current = np.mean(recent_prices[-self.period:])
        ma_prev = np.mean(recent_prices[-(self.period+1):-1])
        prev_price = recent_prices[-2]

        # Detect both crossover directions
        upward_cross = (prev_price <= ma_prev and current_price > ma_current)
        downward_cross = (prev_price >= ma_prev and current_price < ma_current)
        can_trade = days_since_sale >= self.cooldown_days

        # Upward crossover: Transition from falling to rising - HOLD for higher prices
        if upward_cross:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'upward_crossover_bullish'}

        # Downward crossover: Transition from rising to falling - SELL to avoid decline
        if downward_cross:
            if not can_trade:
                return {'action': 'HOLD', 'amount': 0,
                       'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

            # Analyze with historical indicators
            batch_size, reason = self._analyze_historical(current_price, price_history)
            return self._execute_trade(day, inventory, batch_size, reason)

        # No crossover: Maintain current position
        return {'action': 'HOLD', 'amount': 0, 'reason': 'no_crossover'}

    def _analyze_historical(self, current_price, price_history):
        """Analyze using historical technical indicators"""
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, _, _ = calculate_adx(price_history, period=14)

        if adx > self.adx_strong and rsi >= self.rsi_min and rsi <= self.rsi_overbought:
            batch_size = self.batch_strong_momentum
            reason = f'strong_momentum_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > self.rsi_overbought and adx > self.adx_strong:
            batch_size = self.batch_overbought_strong
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > self.rsi_overbought:
            batch_size = self.batch_overbought
            reason = f'overbought_rsi{rsi:.0f}'
        else:
            batch_size = self.batch_baseline
            reason = f'baseline_crossover_rsi{rsi:.0f}_adx{adx:.0f}'

        return batch_size, reason

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = 0
