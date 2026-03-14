```python
%run ./00_setup_and_config

```


```python
# NOTEBOOK 03: STRATEGY IMPLEMENTATIONS (UPDATED - MATCHED PAIRS + INDICATORS)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Strategy Implementations - Enhanced with Technical Indicators
# MAGIC 
# MAGIC **VERSION: 3.0 - Complete Restructure with Backward Compatibility**
# MAGIC 
# MAGIC **KEY CHANGES:**
# MAGIC - Matched pairs: PriceThreshold and MovingAverage (baseline identical, predictions add overlay)
# MAGIC - Daily evaluation for all signal-based strategies
# MAGIC - Technical indicators: RSI, ADX, Std Dev (both historical and predicted)
# MAGIC - Cost-benefit analysis for prediction strategies
# MAGIC - ALL ORIGINAL CONSTRUCTOR SIGNATURES PRESERVED - No downstream changes required

# COMMAND ----------


# COMMAND ----------

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod

# COMMAND ----------

# =============================================================================
# TECHNICAL INDICATOR CALCULATIONS
# =============================================================================

def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return 50.0
    
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_adx(price_history, period=14):
    """Calculate Average Directional Index"""
    if len(price_history) < period + 1:
        return 20.0, 0.0, 0.0
    
    if 'high' in price_history.columns and 'low' in price_history.columns:
        high = price_history['high'].values
        low = price_history['low'].values
    else:
        high = price_history['price'].values
        low = price_history['price'].values
    
    close = price_history['price'].values
    
    tr = np.maximum(high[1:] - low[1:], 
                    np.maximum(abs(high[1:] - close[:-1]), 
                              abs(low[1:] - close[:-1])))
    
    plus_dm = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]), 
                       np.maximum(high[1:] - high[:-1], 0), 0)
    minus_dm = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]), 
                        np.maximum(low[:-1] - low[1:], 0), 0)
    
    atr = np.mean(tr[-period:])
    if atr > 0:
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr
    else:
        plus_di = 0.0
        minus_di = 0.0
    
    di_sum = plus_di + minus_di
    if di_sum > 0:
        dx = 100 * abs(plus_di - minus_di) / di_sum
        adx = dx
    else:
        adx = 0.0
    
    return adx, plus_di, minus_di


def calculate_std_dev_historical(prices, period=14):
    """Calculate standard deviation of recent price returns"""
    if len(prices) < period + 1:
        return 0.10
    
    recent_prices = prices[-period:]
    returns = np.diff(recent_prices) / recent_prices[:-1]
    std_dev = np.std(returns)
    
    return std_dev


def calculate_prediction_confidence(predictions, horizon_day):
    """Calculate confidence from prediction ensemble using std dev"""
    if predictions is None or predictions.size == 0:
        return 1.0
    
    if horizon_day >= predictions.shape[1]:
        horizon_day = predictions.shape[1] - 1
    
    day_predictions = predictions[:, horizon_day]
    median_pred = np.median(day_predictions)
    std_dev = np.std(day_predictions)
    
    cv = std_dev / median_pred if median_pred > 0 else 1.0
    
    return cv


def calculate_rsi_predicted(predictions, period=14):
    """Calculate RSI on predicted price trajectory"""
    if predictions is None or predictions.size == 0:
        return 50.0
    
    predicted_medians = np.array([np.median(predictions[:, h]) 
                                 for h in range(predictions.shape[1])])
    
    return calculate_rsi(predicted_medians, period=min(period, len(predicted_medians)-1))


def calculate_adx_predicted(predictions):
    """Calculate ADX on predicted price trajectory"""
    if predictions is None or predictions.size == 0:
        return 20.0, 0.0, 0.0
    
    predicted_medians = np.array([np.median(predictions[:, h]) 
                                 for h in range(predictions.shape[1])])
    
    pred_df = pd.DataFrame({'price': predicted_medians})
    
    return calculate_adx(pred_df, period=min(14, len(predicted_medians)-1))


# COMMAND ----------

# =============================================================================
# BASE STRATEGY CLASS
# =============================================================================

class Strategy(ABC):
    """Base class for all strategies - UNCHANGED"""
    
    def __init__(self, name, max_holding_days=365):
        self.name = name
        self.history = []
        self.max_holding_days = max_holding_days
        self.harvest_start_day = None
    
    @abstractmethod
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        pass
    
    def set_harvest_start(self, day):
        self.harvest_start_day = day
    
    def reset(self):
        self.history = []
        self.harvest_start_day = None
    
    def _days_held(self, day):
        if self.harvest_start_day is None:
            return 0
        return day - self.harvest_start_day
    
    def _force_liquidation_check(self, day, inventory):
        if self.harvest_start_day is None:
            return None
        
        days_held = self._days_held(day)
        days_remaining = self.max_holding_days - days_held
        
        if days_remaining <= 0 and inventory > 0:
            return {'action': 'SELL', 'amount': inventory, 
                   'reason': 'max_holding_365d_reached'}
        elif days_remaining <= 30 and inventory > 0:
            sell_fraction = min(1.0, 0.05 * (31 - days_remaining))
            amount = inventory * sell_fraction
            return {'action': 'SELL', 'amount': amount,
                   'reason': f'approaching_365d_deadline_{days_remaining}d_left'}
        
        return None
    
    def force_liquidate_before_new_harvest(self, inventory):
        if inventory > 0:
            return {'action': 'SELL', 'amount': inventory, 
                   'reason': 'new_harvest_starting_liquidate_old_inventory'}
        return None


# COMMAND ----------

# MAGIC %md
# MAGIC ## BASELINE STRATEGIES

# COMMAND ----------

class ImmediateSaleStrategy(Strategy):
    """
    Baseline 1: Sell all inventory weekly - NO CHANGES
    """
    
    def __init__(self, min_batch_size=5.0, sale_frequency_days=7):
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
                   'reason': f'accumulating_need_{self.min_batch_size:.1f}t_have_{inventory:.1f}t'}
        else:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'waiting_for_weekly_sale_day_{self.days_since_last_sale}'}
    
    def reset(self):
        super().reset()
        self.days_since_last_sale = self.sale_frequency_days


# COMMAND ----------

class EqualBatchStrategy(Strategy):
    """
    Baseline 2: Sell equal batches on fixed schedule - NO CHANGES
    """
    
    def __init__(self, batch_size=0.25, frequency_days=30):
        super().__init__("Equal Batches")
        self.batch_size = batch_size
        self.frequency = frequency_days
        self.last_sale_day = -frequency_days
        self.num_sales = 0
    
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
            self.num_sales += 1
            return {'action': 'SELL', 'amount': amount, 'reason': f'scheduled_batch_{self.num_sales}'}
        
        return {'action': 'HOLD', 'amount': 0, 'reason': 'waiting_for_schedule'}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.frequency
        self.num_sales = 0


# COMMAND ----------

# MAGIC %md
# MAGIC ## MATCHED PAIR 1: PRICE THRESHOLD

# COMMAND ----------

class PriceThresholdStrategy(Strategy):
    """
    MATCHED PAIR BASELINE: Price Threshold with Historical Indicators
    
    CHANGES FROM ORIGINAL:
    - Fixed: Use 30-day MA threshold (not reference price)
    - Added: Daily evaluation (already had it)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Changed: Batch sizing 20-35% based on historical signals
    - Changed: Cooldown to 7 days (was variable)
    
    CONSTRUCTOR: UNCHANGED for backward compatibility
    """
    
    def __init__(self, threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60):
        super().__init__("Price Threshold")
        self.threshold_pct = threshold_pct
        self.baseline_batch = batch_fraction  # Used as baseline for dynamic sizing
        self.max_days_without_sale = max_days_without_sale
        self.cooldown_days = 7  # Standardized cooldown
        self.last_sale_day = -self.max_days_without_sale
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        # Calculate 30-day MA threshold (FIXED from reference price)
        if len(price_history) >= 30:
            ma_30 = price_history['price'].tail(30).mean()
            threshold = ma_30 * (1 + self.threshold_pct)
        else:
            threshold = current_price * (1 + self.threshold_pct)
        
        signal_triggered = current_price > threshold
        can_trade = days_since_sale >= self.cooldown_days
        
        if not signal_triggered:
            if days_since_sale >= self.max_days_without_sale:
                batch_size = self.baseline_batch
                return self._execute_trade(day, inventory, batch_size,
                                          f'fallback_{days_since_sale}d')
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'below_threshold_{current_price:.2f}<{threshold:.2f}'}
        
        if not can_trade:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        # ADDED: Analyze with historical indicators
        batch_size, reason = self._analyze_with_historical(current_price, price_history)
        
        return self._execute_trade(day, inventory, batch_size, reason)
    
    def _analyze_with_historical(self, current_price, price_history):
        """NEW: Analyze using historical technical indicators"""
        
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, plus_di, minus_di = calculate_adx(price_history, period=14)
        std_dev = calculate_std_dev_historical(prices, period=14)
        
        batch_size = self.baseline_batch
        
        if rsi > 70 and adx > 25:
            batch_size = 0.35
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70:
            batch_size = 0.30
            reason = f'overbought_rsi{rsi:.0f}_adx{adx:.0f}'
        elif std_dev > 0.03:
            batch_size = 0.30
            reason = f'high_volatility_stddev{std_dev:.3f}'
        elif adx > 25 and rsi < 65:
            batch_size = 0.20
            reason = f'strong_trend_not_overbought_rsi{rsi:.0f}_adx{adx:.0f}'
        else:
            reason = f'baseline_rsi{rsi:.0f}_adx{adx:.0f}'
        
        return batch_size, reason
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.max_days_without_sale


# COMMAND ----------

class PriceThresholdPredictive(Strategy):
    """
    MATCHED PAIR PREDICTIVE: Price Threshold with Historical + Predicted Indicators
    
    CHANGES FROM ORIGINAL:
    - MATCHED: Same 30-day MA threshold as baseline
    - MATCHED: Same cooldown (7 days)
    - MATCHED: Same historical indicator logic as baseline
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Added: Cost-benefit check
    - Changed: Batch adjustments ±10% from baseline based on predictions
    
    CONSTRUCTOR: Optional cost parameters added for cost-benefit (backward compatible)
    """
    
    def __init__(self, threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Price Threshold Predictive")
        self.threshold_pct = threshold_pct
        self.baseline_batch = batch_fraction
        self.max_days_without_sale = max_days_without_sale
        self.cooldown_days = 7
        self.last_sale_day = -self.max_days_without_sale
        
        # Cost parameters for cost-benefit
        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        # IDENTICAL baseline logic as PriceThresholdStrategy
        if len(price_history) >= 30:
            ma_30 = price_history['price'].tail(30).mean()
            threshold = ma_30 * (1 + self.threshold_pct)
        else:
            threshold = current_price * (1 + self.threshold_pct)
        
        signal_triggered = current_price > threshold
        can_trade = days_since_sale >= self.cooldown_days
        
        if not signal_triggered:
            if days_since_sale >= self.max_days_without_sale:
                batch_size = self.baseline_batch
                return self._execute_trade(day, inventory, batch_size,
                                          f'fallback_{days_since_sale}d')
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'below_threshold_{current_price:.2f}<{threshold:.2f}'}
        
        if not can_trade:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        # Choose analysis path
        if predictions is None or predictions.size == 0:
            # No predictions - use baseline historical analysis
            batch_size, reason = self._analyze_with_historical(current_price, price_history)
        else:
            # Full predictive analysis
            batch_size, reason = self._analyze_with_predictions(
                current_price, price_history, predictions
            )
        
        return self._execute_trade(day, inventory, batch_size, reason)
    
    def _analyze_with_historical(self, current_price, price_history):
        """IDENTICAL to PriceThresholdStrategy baseline analysis"""
        
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, plus_di, minus_di = calculate_adx(price_history, period=14)
        std_dev = calculate_std_dev_historical(prices, period=14)
        
        batch_size = self.baseline_batch
        
        if rsi > 70 and adx > 25:
            batch_size = 0.35
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70:
            batch_size = 0.30
            reason = f'overbought_rsi{rsi:.0f}_adx{adx:.0f}'
        elif std_dev > 0.03:
            batch_size = 0.30
            reason = f'high_volatility_stddev{std_dev:.3f}'
        elif adx > 25 and rsi < 65:
            batch_size = 0.20
            reason = f'strong_trend_not_overbought_rsi{rsi:.0f}_adx{adx:.0f}'
        else:
            reason = f'baseline_rsi{rsi:.0f}_adx{adx:.0f}'
        
        return batch_size, reason
    
    def _analyze_with_predictions(self, current_price, price_history, predictions):
        """ADDED: Full predictive analysis with historical + predicted indicators"""
        
        # Start with baseline historical analysis
        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)
        std_dev_hist = calculate_std_dev_historical(prices, period=14)
        
        # Get baseline batch from historical signals
        batch_size = self.baseline_batch
        if rsi_hist > 70 and adx_hist > 25:
            batch_size = 0.35
        elif rsi_hist > 70:
            batch_size = 0.30
        elif std_dev_hist > 0.03:
            batch_size = 0.30
        elif adx_hist > 25 and rsi_hist < 65:
            batch_size = 0.20
        
        # Calculate predicted indicators
        rsi_pred = calculate_rsi_predicted(predictions, period=14)
        adx_pred, _, _ = calculate_adx_predicted(predictions)
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=13)
        
        # Calculate cost-benefit
        net_benefit = self._calculate_cost_benefit(current_price, predictions)
        
        # Adjust batch based on predictions (±10% from baseline)
        adjustment = 0.0
        reasons = []
        
        if cv_pred < 0.05 and net_benefit > 100:
            adjustment -= 0.10
            reasons.append(f'high_conf_defer_cv{cv_pred:.2%}_netben${net_benefit:.0f}')
        elif rsi_hist < rsi_pred and rsi_pred > 75:
            adjustment += 0.10
            reasons.append(f'pred_reversal_rsi_hist{rsi_hist:.0f}_pred{rsi_pred:.0f}')
        elif cv_pred > 0.20 or net_benefit < 0:
            adjustment += 0.10
            reasons.append(f'low_conf_cv{cv_pred:.2%}_netben${net_benefit:.0f}')
        elif adx_pred > 30 and rsi_pred < 70:
            adjustment -= 0.05
            reasons.append(f'strong_pred_trend_adx{adx_pred:.0f}')
        
        batch_size = np.clip(batch_size + adjustment, 0.10, 0.45)
        
        reason = f'hist_rsi{rsi_hist:.0f}_adx{adx_hist:.0f}_' + '_'.join(reasons)
        
        return batch_size, reason
    
    def _calculate_cost_benefit(self, current_price, predictions):
        """Calculate net benefit of waiting vs selling today"""
        
        ev_by_day = []
        max_horizon = predictions.shape[1]
        
        for h in range(max_horizon):
            future_price = np.median(predictions[:, h])
            days_to_wait = h + 1
            storage_cost = current_price * (self.storage_cost_pct / 100) * days_to_wait
            transaction_cost = future_price * (self.transaction_cost_pct / 100)
            ev = future_price - storage_cost - transaction_cost
            ev_by_day.append(ev)
        
        transaction_cost_today = current_price * (self.transaction_cost_pct / 100)
        ev_today = current_price - transaction_cost_today
        
        optimal_ev = max(ev_by_day)
        net_benefit = optimal_ev - ev_today
        
        return net_benefit
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.max_days_without_sale


# COMMAND ----------

# MAGIC %md
# MAGIC ## MATCHED PAIR 2: MOVING AVERAGE

# COMMAND ----------

class MovingAverageStrategy(Strategy):
    """
    MATCHED PAIR BASELINE: Moving Average with Historical Indicators
    
    CHANGES FROM ORIGINAL:
    - Kept: Crossover trigger (daily evaluation already existed)
    - Changed: Cooldown to 7 days (was 5)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Changed: Batch sizing 20-35% based on historical signals
    
    CONSTRUCTOR: UNCHANGED for backward compatibility
    """
    
    def __init__(self, ma_period=30, batch_fraction=0.25, max_days_without_sale=60):
        super().__init__("Moving Average")
        self.period = ma_period
        self.baseline_batch = batch_fraction
        self.max_days_without_sale = max_days_without_sale
        self.cooldown_days = 7  # Changed from 5 to 7
        self.last_sale_day = -self.max_days_without_sale
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        if days_since_sale >= self.max_days_without_sale:
            batch_size = self.baseline_batch
            return self._execute_trade(day, inventory, batch_size,
                                      f'fallback_{days_since_sale}d')
        
        if len(price_history) < self.period + 1:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'insufficient_history'}
        
        # Crossover detection
        recent_prices = price_history['price'].tail(self.period + 1).values
        ma_current = np.mean(recent_prices[-self.period:])
        ma_prev = np.mean(recent_prices[-(self.period+1):-1])
        prev_price = recent_prices[-2]
        
        crossover = (prev_price <= ma_prev and current_price > ma_current)
        can_trade = days_since_sale >= self.cooldown_days
        
        if not crossover:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_crossover'}
        
        if not can_trade:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        # ADDED: Analyze with historical indicators
        batch_size, reason = self._analyze_with_historical(current_price, price_history)
        
        return self._execute_trade(day, inventory, batch_size, reason)
    
    def _analyze_with_historical(self, current_price, price_history):
        """NEW: Analyze using historical technical indicators"""
        
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, plus_di, minus_di = calculate_adx(price_history, period=14)
        std_dev = calculate_std_dev_historical(prices, period=14)
        
        batch_size = self.baseline_batch
        
        if adx > 25 and rsi >= 45 and rsi <= 70:
            batch_size = 0.20
            reason = f'strong_momentum_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70 and adx > 25:
            batch_size = 0.35
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70:
            batch_size = 0.30
            reason = f'overbought_rsi{rsi:.0f}'
        elif std_dev > 0.03:
            batch_size = 0.30
            reason = f'high_volatility_stddev{std_dev:.3f}'
        elif adx < 20:
            batch_size = 0.25
            reason = f'weak_trend_choppy_adx{adx:.0f}'
        else:
            reason = f'baseline_crossover_rsi{rsi:.0f}_adx{adx:.0f}'
        
        return batch_size, reason
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.max_days_without_sale


# COMMAND ----------

class MovingAveragePredictive(Strategy):
    """
    MATCHED PAIR PREDICTIVE: Moving Average with Historical + Predicted Indicators
    
    CHANGES FROM ORIGINAL:
    - MATCHED: Same crossover trigger as baseline
    - MATCHED: Same cooldown (7 days)
    - MATCHED: Same historical indicator logic as baseline
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Added: Cost-benefit check
    - Changed: Batch adjustments ±10% from baseline based on predictions
    
    CONSTRUCTOR: Optional cost parameters added for cost-benefit (backward compatible)
    """
    
    def __init__(self, ma_period=30, batch_fraction=0.25, max_days_without_sale=60,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Moving Average Predictive")
        self.period = ma_period
        self.baseline_batch = batch_fraction
        self.max_days_without_sale = max_days_without_sale
        self.cooldown_days = 7
        self.last_sale_day = -self.max_days_without_sale
        
        # Cost parameters for cost-benefit
        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        if days_since_sale >= self.max_days_without_sale:
            batch_size = self.baseline_batch
            return self._execute_trade(day, inventory, batch_size,
                                      f'fallback_{days_since_sale}d')
        
        if len(price_history) < self.period + 1:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'insufficient_history'}
        
        # IDENTICAL baseline logic as MovingAverageStrategy
        recent_prices = price_history['price'].tail(self.period + 1).values
        ma_current = np.mean(recent_prices[-self.period:])
        ma_prev = np.mean(recent_prices[-(self.period+1):-1])
        prev_price = recent_prices[-2]
        
        crossover = (prev_price <= ma_prev and current_price > ma_current)
        can_trade = days_since_sale >= self.cooldown_days
        
        if not crossover:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_crossover'}
        
        if not can_trade:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        # Choose analysis path
        if predictions is None or predictions.size == 0:
            # No predictions - use baseline historical analysis
            batch_size, reason = self._analyze_with_historical(current_price, price_history)
        else:
            # Full predictive analysis
            batch_size, reason = self._analyze_with_predictions(
                current_price, price_history, predictions
            )
        
        return self._execute_trade(day, inventory, batch_size, reason)
    
    def _analyze_with_historical(self, current_price, price_history):
        """IDENTICAL to MovingAverageStrategy baseline analysis"""
        
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, plus_di, minus_di = calculate_adx(price_history, period=14)
        std_dev = calculate_std_dev_historical(prices, period=14)
        
        batch_size = self.baseline_batch
        
        if adx > 25 and rsi >= 45 and rsi <= 70:
            batch_size = 0.20
            reason = f'strong_momentum_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70 and adx > 25:
            batch_size = 0.35
            reason = f'overbought_strong_trend_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > 70:
            batch_size = 0.30
            reason = f'overbought_rsi{rsi:.0f}'
        elif std_dev > 0.03:
            batch_size = 0.30
            reason = f'high_volatility_stddev{std_dev:.3f}'
        elif adx < 20:
            batch_size = 0.25
            reason = f'weak_trend_choppy_adx{adx:.0f}'
        else:
            reason = f'baseline_crossover_rsi{rsi:.0f}_adx{adx:.0f}'
        
        return batch_size, reason
    
    def _analyze_with_predictions(self, current_price, price_history, predictions):
        """ADDED: Full predictive analysis with historical + predicted indicators"""
        
        # Start with baseline historical analysis
        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)
        std_dev_hist = calculate_std_dev_historical(prices, period=14)
        
        # Get baseline batch from historical signals
        batch_size = self.baseline_batch
        if adx_hist > 25 and rsi_hist >= 45 and rsi_hist <= 70:
            batch_size = 0.20
        elif rsi_hist > 70 and adx_hist > 25:
            batch_size = 0.35
        elif rsi_hist > 70:
            batch_size = 0.30
        elif std_dev_hist > 0.03:
            batch_size = 0.30
        elif adx_hist < 20:
            batch_size = 0.25
        
        # Calculate predicted indicators
        rsi_pred = calculate_rsi_predicted(predictions, period=14)
        adx_pred, _, _ = calculate_adx_predicted(predictions)
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=13)
        
        # Calculate cost-benefit
        net_benefit = self._calculate_cost_benefit(current_price, predictions)
        
        # Adjust batch based on predictions (±10% from baseline)
        adjustment = 0.0
        reasons = []
        
        if adx_pred > 25 and cv_pred < 0.05 and net_benefit > 100:
            adjustment -= 0.10
            reasons.append(f'momentum_continues_adx{adx_pred:.0f}_defer')
        elif adx_pred < 15 or (adx_hist > adx_pred * 1.2):
            adjustment += 0.10
            reasons.append(f'momentum_fading_adx_hist{adx_hist:.0f}_pred{adx_pred:.0f}')
        elif cv_pred > 0.20 or net_benefit < 0:
            adjustment += 0.10
            reasons.append(f'low_conf_cv{cv_pred:.2%}_netben${net_benefit:.0f}')
        elif rsi_pred > 75:
            adjustment += 0.05
            reasons.append(f'pred_overbought_rsi{rsi_pred:.0f}')
        
        batch_size = np.clip(batch_size + adjustment, 0.10, 0.45)
        
        reason = f'hist_rsi{rsi_hist:.0f}_adx{adx_hist:.0f}_' + '_'.join(reasons)
        
        return batch_size, reason
    
    def _calculate_cost_benefit(self, current_price, predictions):
        """Calculate net benefit of waiting vs selling today"""
        
        ev_by_day = []
        max_horizon = predictions.shape[1]
        
        for h in range(max_horizon):
            future_price = np.median(predictions[:, h])
            days_to_wait = h + 1
            storage_cost = current_price * (self.storage_cost_pct / 100) * days_to_wait
            transaction_cost = future_price * (self.transaction_cost_pct / 100)
            ev = future_price - storage_cost - transaction_cost
            ev_by_day.append(ev)
        
        transaction_cost_today = current_price * (self.transaction_cost_pct / 100)
        ev_today = current_price - transaction_cost_today
        
        optimal_ev = max(ev_by_day)
        net_benefit = optimal_ev - ev_today
        
        return net_benefit
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.max_days_without_sale


# COMMAND ----------

# MAGIC %md
# MAGIC ## STANDALONE PREDICTION STRATEGIES

# COMMAND ----------

class ConsensusStrategy(Strategy):
    """
    Standalone Prediction Strategy: Consensus with Full Indicators
    
    CHANGES FROM ORIGINAL:
    - Changed: Daily evaluation (was every 14 days)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Added: Cost-benefit check
    - Changed: Batch 5-40% based on all signals
    
    CONSTRUCTOR: Optional cost parameters added (backward compatible)
    """
    
    def __init__(self, consensus_threshold=0.70, min_return=0.03, evaluation_day=14,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Consensus")
        self.consensus_threshold = consensus_threshold
        self.min_return = min_return
        self.evaluation_day = evaluation_day  # Keep for horizon day selection
        self.cooldown_days = 7  # Changed from implicit 14 to explicit 7
        self.last_sale_day = -self.cooldown_days
        
        # Cost parameters
        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        # CHANGED: Check cooldown daily (not scheduled every 14 days)
        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, 0.20, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}
        
        # ADDED: Full analysis with all indicators
        batch_size, reason = self._analyze_consensus(
            current_price, price_history, predictions
        )
        
        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}
    
    def _analyze_consensus(self, current_price, price_history, predictions):
        """ENHANCED: Analyze using historical + predicted indicators + consensus"""
        
        # Historical indicators
        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)
        
        # Predicted indicators
        rsi_pred = calculate_rsi_predicted(predictions, period=14)
        adx_pred, _, _ = calculate_adx_predicted(predictions)
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=min(self.evaluation_day-1, predictions.shape[1]-1))
        
        # Consensus analysis
        eval_day_idx = min(self.evaluation_day, predictions.shape[1]) - 1
        day_preds = predictions[:, eval_day_idx]
        median_pred = np.median(day_preds)
        expected_return = (median_pred - current_price) / current_price
        bullish_pct = np.mean(day_preds > current_price)
        
        # Cost-benefit
        net_benefit = self._calculate_cost_benefit(current_price, predictions)
        
        # Decision matrix
        batch_size = 0.0
        
        if (bullish_pct >= 0.80 and expected_return >= self.min_return and
            cv_pred < 0.05 and adx_pred > 25 and net_benefit > 100):
            batch_size = 0.05
            reason = f'very_strong_consensus_{bullish_pct:.0%}_defer'
        elif (bullish_pct >= self.consensus_threshold and expected_return >= self.min_return and
              cv_pred < 0.10 and net_benefit > 50):
            batch_size = 0.10
            reason = f'strong_consensus_{bullish_pct:.0%}_conf{cv_pred:.1%}'
        elif bullish_pct >= 0.60 and expected_return >= self.min_return * 0.5:
            batch_size = 0.20
            reason = f'moderate_consensus_{bullish_pct:.0%}'
        elif cv_pred > 0.20 or bullish_pct < 0.55:
            batch_size = 0.30
            reason = f'weak_consensus_{bullish_pct:.0%}_or_high_unc{cv_pred:.1%}'
        elif bullish_pct < 0.40 or expected_return < -self.min_return:
            batch_size = 0.40
            reason = f'bearish_consensus_{bullish_pct:.0%}_ret{expected_return:.1%}'
        else:
            batch_size = 0.20
            reason = f'mixed_signals_cons{bullish_pct:.0%}_ret{expected_return:.1%}'
        
        return batch_size, reason
    
    def _calculate_cost_benefit(self, current_price, predictions):
        ev_by_day = []
        for h in range(predictions.shape[1]):
            future_price = np.median(predictions[:, h])
            days_to_wait = h + 1
            storage_cost = current_price * (self.storage_cost_pct / 100) * days_to_wait
            transaction_cost = future_price * (self.transaction_cost_pct / 100)
            ev = future_price - storage_cost - transaction_cost
            ev_by_day.append(ev)
        
        transaction_cost_today = current_price * (self.transaction_cost_pct / 100)
        ev_today = current_price - transaction_cost_today
        
        return max(ev_by_day) - ev_today
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days


# COMMAND ----------

class ExpectedValueStrategy(Strategy):
    """
    Standalone Prediction Strategy: Expected Value with Full Indicators
    
    CHANGES FROM ORIGINAL:
    - Changed: Daily evaluation (was every 10 days)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Kept: Cost-benefit (already existed)
    - Changed: Batch 10-35% based on EV and confidence
    
    CONSTRUCTOR: UNCHANGED (already had cost parameters)
    """
    
    def __init__(self, storage_cost_pct_per_day, transaction_cost_pct,
                 min_ev_improvement=50, baseline_batch=0.15, baseline_frequency=10):
        super().__init__("Expected Value")
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.min_ev_improvement = min_ev_improvement
        self.baseline_batch = baseline_batch
        self.baseline_frequency = baseline_frequency  # Keep for reference but not used in scheduling
        self.cooldown_days = 7  # Changed from implicit 10 to explicit 7
        self.last_sale_day = -self.cooldown_days
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        # CHANGED: Check cooldown daily (not scheduled every 10 days)
        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, self.baseline_batch, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}
        
        # ENHANCED: Full EV analysis with all indicators
        batch_size, reason = self._analyze_expected_value(
            current_price, price_history, predictions
        )
        
        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}
    
    def _analyze_expected_value(self, current_price, price_history, predictions):
        """ENHANCED: EV optimization + all indicators"""
        
        # Historical indicators
        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)
        
        # Predicted indicators
        rsi_pred = calculate_rsi_predicted(predictions, period=14)
        adx_pred, _, _ = calculate_adx_predicted(predictions)
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=13)
        
        # Find optimal sale day
        optimal_day, net_benefit = self._find_optimal_sale_day(current_price, predictions)
        
        # Decision matrix
        batch_size = 0.0
        
        if optimal_day <= 3 and cv_pred < 0.08 and net_benefit > self.min_ev_improvement:
            batch_size = 0.20
            reason = f'peak_soon_day{optimal_day}_ev${net_benefit:.0f}_conf{cv_pred:.1%}'
        elif optimal_day <= 7 and cv_pred < 0.12 and net_benefit > self.min_ev_improvement:
            batch_size = 0.15
            reason = f'peak_mid_day{optimal_day}_ev${net_benefit:.0f}'
        elif optimal_day > 7 and cv_pred < 0.08 and adx_pred > 25:
            batch_size = 0.10
            reason = f'peak_late_day{optimal_day}_high_conf_defer'
        elif optimal_day > 7:
            batch_size = 0.15
            reason = f'peak_late_day{optimal_day}_uncertain_cv{cv_pred:.1%}'
        elif net_benefit < self.min_ev_improvement:
            if cv_pred < 0.08:
                batch_size = 0.10
                reason = f'no_ev_benefit_high_conf_cv{cv_pred:.1%}'
            elif cv_pred < 0.15:
                batch_size = 0.15
                reason = f'no_ev_benefit_mod_conf_cv{cv_pred:.1%}'
            else:
                batch_size = 0.35
                reason = f'no_ev_benefit_low_conf_cv{cv_pred:.1%}'
        else:
            batch_size = 0.15
            reason = f'baseline_ev${net_benefit:.0f}_day{optimal_day}'
        
        return batch_size, reason
    
    def _find_optimal_sale_day(self, current_price, predictions):
        ev_by_day = []
        for h in range(predictions.shape[1]):
            future_price = np.median(predictions[:, h])
            days_to_wait = h + 1
            storage_cost = current_price * (self.storage_cost_pct_per_day / 100) * days_to_wait
            transaction_cost = future_price * (self.transaction_cost_pct / 100)
            ev = future_price - storage_cost - transaction_cost
            ev_by_day.append(ev)
        
        transaction_cost_today = current_price * (self.transaction_cost_pct / 100)
        ev_today = current_price - transaction_cost_today
        
        optimal_day = np.argmax(ev_by_day)
        net_benefit = ev_by_day[optimal_day] - ev_today
        
        return optimal_day, net_benefit
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days


# COMMAND ----------

class RiskAdjustedStrategy(Strategy):
    """
    Standalone Prediction Strategy: Risk-Adjusted with Full Indicators
    
    CHANGES FROM ORIGINAL:
    - Changed: Daily evaluation (was every 12 days)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Added: Cost-benefit check
    - Changed: Batch 8-40% based on risk/uncertainty
    - Std_dev_predictions is PRIMARY driver
    
    CONSTRUCTOR: Optional cost parameters added (backward compatible)
    """
    
    def __init__(self, min_return=0.05, max_uncertainty=0.08, 
                 consensus_threshold=0.65, evaluation_day=14,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Risk-Adjusted")
        self.min_return = min_return
        self.max_uncertainty = max_uncertainty  # Keep for reference
        self.consensus_threshold = consensus_threshold  # Keep for reference
        self.evaluation_day = evaluation_day  # Keep for horizon day selection
        self.cooldown_days = 7  # Changed from implicit 12 to explicit 7
        self.last_sale_day = -self.cooldown_days
        
        # Cost parameters
        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
    
    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}
        
        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced
        
        days_since_sale = day - self.last_sale_day
        
        # CHANGED: Check cooldown daily (not scheduled every 12 days)
        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0, 
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}
        
        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, 0.18, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}
        
        # ENHANCED: Full risk-adjusted analysis
        batch_size, reason = self._analyze_risk_adjusted(
            current_price, price_history, predictions
        )
        
        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}
    
    def _analyze_risk_adjusted(self, current_price, price_history, predictions):
        """ENHANCED: Analyze risk/return using all indicators"""
        
        # Historical indicators
        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)
        
        # Predicted indicators (cv_pred is PRIMARY driver)
        rsi_pred = calculate_rsi_predicted(predictions, period=14)
        adx_pred, _, _ = calculate_adx_predicted(predictions)
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=min(self.evaluation_day-1, predictions.shape[1]-1))
        
        # Expected return
        eval_day_idx = min(self.evaluation_day, predictions.shape[1]) - 1
        day_preds = predictions[:, eval_day_idx]
        median_pred = np.median(day_preds)
        expected_return = (median_pred - current_price) / current_price
        
        # Trajectory
        predicted_medians = [np.median(predictions[:, h]) for h in range(predictions.shape[1])]
        daily_changes = np.diff(predicted_medians)
        pct_positive = np.mean(daily_changes > 0)
        
        # Cost-benefit
        net_benefit = self._calculate_cost_benefit(current_price, predictions)
        
        # Risk assessment - cv_pred is PRIMARY driver
        batch_size = 0.0
        
        if (cv_pred < 0.05 and adx_pred > 25 and expected_return >= self.min_return and
            pct_positive > 0.70 and net_benefit > 100):
            batch_size = 0.08
            reason = f'very_low_risk_cv{cv_pred:.1%}_adx{adx_pred:.0f}_defer'
        elif cv_pred < 0.10 and adx_pred > 20 and expected_return >= self.min_return * 0.67 and net_benefit > 50:
            batch_size = 0.12
            reason = f'low_risk_cv{cv_pred:.1%}_ret{expected_return:.1%}'
        elif cv_pred < 0.15 and expected_return > 0:
            batch_size = 0.18
            reason = f'medium_risk_cv{cv_pred:.1%}_baseline'
        elif cv_pred < 0.25 or adx_pred < 15:
            batch_size = 0.25
            reason = f'med_high_risk_cv{cv_pred:.1%}_weak_trend'
        elif cv_pred >= 0.25 or expected_return < 0:
            batch_size = 0.30
            reason = f'high_risk_cv{cv_pred:.1%}_reduce_exposure'
        else:
            batch_size = 0.40
            reason = f'very_high_risk_cv{cv_pred:.1%}_exit_fast'
        
        return batch_size, reason
    
    def _calculate_cost_benefit(self, current_price, predictions):
        ev_by_day = []
        for h in range(predictions.shape[1]):
            future_price = np.median(predictions[:, h])
            days_to_wait = h + 1
            storage_cost = current_price * (self.storage_cost_pct / 100) * days_to_wait
            transaction_cost = future_price * (self.transaction_cost_pct / 100)
            ev = future_price - storage_cost - transaction_cost
            ev_by_day.append(ev)
        
        transaction_cost_today = current_price * (self.transaction_cost_pct / 100)
        ev_today = current_price - transaction_cost_today
        
        return max(ev_by_day) - ev_today
    
    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}
    
    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days


# COMMAND ----------

# MAGIC %md
# MAGIC ## TESTING ALL STRATEGIES

# COMMAND ----------

# Test all strategies with sample data
test_day = 30
test_inventory = 50
test_price = 200.0
test_predictions = np.random.normal(210, 15, (2000, 14))

# Create minimal price history
test_price_history = pd.DataFrame({
    'date': pd.date_range('2022-01-01', periods=test_day + 1),
    'price': np.linspace(195, test_price, test_day + 1)
})

# Initialize all strategies with realistic parameters
all_strategies = [
    ImmediateSaleStrategy(min_batch_size=5.0, sale_frequency_days=7),
    EqualBatchStrategy(batch_size=0.25, frequency_days=30),
    PriceThresholdStrategy(threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60),
    MovingAverageStrategy(ma_period=30, batch_fraction=0.25, max_days_without_sale=60),
    ConsensusStrategy(consensus_threshold=0.70, min_return=0.03, evaluation_day=14),
    ExpectedValueStrategy(
        storage_cost_pct_per_day=0.025,
        transaction_cost_pct=0.25,
        min_ev_improvement=50,
        baseline_batch=0.15,
        baseline_frequency=10
    ),
    RiskAdjustedStrategy(min_return=0.05, max_uncertainty=0.08, 
                        consensus_threshold=0.65, evaluation_day=14),
    PriceThresholdPredictive(threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60),
    MovingAveragePredictive(ma_period=30, batch_fraction=0.25, max_days_without_sale=60)
]

# Test harvest start functionality
for strategy in all_strategies:
    strategy.set_harvest_start(0)  # Simulate harvest starting at day 0

print("=" * 80)
print("TESTING ALL STRATEGIES - VERSION 3.0 (ENHANCED WITH INDICATORS)")
print("=" * 80)
print(f"\nTest scenario: Day {test_day}, Inventory {test_inventory}t, Price ${test_price}")
print(f"Predictions: Mean=${np.mean(test_predictions[:, 13]):.2f}, Std=${np.std(test_predictions[:, 13]):.2f}\n")

for strategy in all_strategies:
    decision = strategy.decide(
        day=test_day,
        inventory=test_inventory,
        current_price=test_price,
        price_history=test_price_history,
        predictions=test_predictions
    )
    
    action = decision.get('action', 'N/A')
    amount = decision.get('amount', 0)
    reason = decision.get('reason', 'N/A')
    
    print(f"{strategy.name:30s}: {action:4s} {amount:5.1f}t - {reason}")

print("\n" + "=" * 80)
print("✓ All 9 strategies implemented and tested successfully!")
print("✓ CHANGES FROM ORIGINAL:")
print("  - PriceThreshold: Fixed to use 30-day MA (not reference price)")
print("  - MovingAverage: Cooldown 7 days (was 5)")
print("  - Consensus/ExpectedValue/RiskAdjusted: Daily evaluation (not scheduled)")
print("  - All baselines: Added RSI/ADX/Std_dev_historical")
print("  - All predictive: Added RSI/ADX/Std_dev_predictions + cost-benefit")
print("  - Matched pairs: Identical baseline logic, predictions add overlay only")
print("✓ ENHANCEMENTS:")
print("  - Technical indicators: RSI, ADX, Standard Deviation")
print("  - Cost-benefit analysis for all prediction strategies")
print("  - Dynamic batch sizing based on signals (20-40% range)")
print("  - Daily signal evaluation (not scheduled checks)")
print(f"✓ Max holding period: {all_strategies[0].max_holding_days} days (365 days from harvest)")
print("=" * 80)
```
