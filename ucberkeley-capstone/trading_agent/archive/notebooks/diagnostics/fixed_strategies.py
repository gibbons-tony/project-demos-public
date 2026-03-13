"""
Fixed Trading Strategies - Bug Corrections

**Purpose:** Corrected implementations of prediction strategies that were selling
when they should be holding (deferring).

**Key Fixes:**
1. ExpectedValueStrategy: "defer" logic now returns batch_size=0.0 (HOLD) instead of 0.10 (SELL)
2. ConsensusStrategy: "defer" logic now returns batch_size=0.0 (HOLD) instead of 0.05 (SELL)
3. RiskAdjustedStrategy: "defer" logic now returns batch_size=0.0 (HOLD) instead of 0.08 (SELL)

**Bug Description:**
Original code set non-zero batch_size with reasons like "peak_late_day13_high_conf_defer",
which caused the strategy to SELL when it calculated that WAITING would be optimal.

**Testing:** Use diagnostic_12_fixed_strategy_comparison.ipynb to validate improvements.
"""

import numpy as np
import pandas as pd
from abc import ABC, abstractmethod


# =============================================================================
# TECHNICAL INDICATOR CALCULATIONS (unchanged from original)
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


# =============================================================================
# BASE STRATEGY CLASS (unchanged)
# =============================================================================

class Strategy(ABC):
    """Base class for all strategies"""

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


# =============================================================================
# FIXED: CONSENSUS STRATEGY
# =============================================================================

class ConsensusStrategyFixed(Strategy):
    """
    FIXED: Consensus Strategy

    BUG FIX: Lines that say "defer" now return batch_size=0.0 to HOLD instead of selling

    Original bug:
        batch_size = 0.05 with reason "very_strong_consensus_80%_defer"
    Fixed:
        batch_size = 0.0 with reason "very_strong_consensus_80%_defer"
    """

    def __init__(self, consensus_threshold=0.70, min_return=0.03, evaluation_day=14,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Consensus (Fixed)")
        self.consensus_threshold = consensus_threshold
        self.min_return = min_return
        self.evaluation_day = evaluation_day
        self.cooldown_days = 7
        self.last_sale_day = -self.cooldown_days

        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, 0.20, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_consensus(
            current_price, price_history, predictions
        )

        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}

    def _analyze_consensus(self, current_price, price_history, predictions):
        """Analyze using historical + predicted indicators + consensus"""

        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)

        cv_pred = calculate_prediction_confidence(predictions, horizon_day=min(self.evaluation_day-1, predictions.shape[1]-1))

        eval_day_idx = min(self.evaluation_day, predictions.shape[1]) - 1
        day_preds = predictions[:, eval_day_idx]
        median_pred = np.median(day_preds)
        expected_return = (median_pred - current_price) / current_price
        bullish_pct = np.mean(day_preds > current_price)

        net_benefit = self._calculate_cost_benefit(current_price, predictions)

        batch_size = 0.0

        # FIXED: Very strong consensus → HOLD (batch_size = 0.0, not 0.05)
        if (bullish_pct >= 0.80 and expected_return >= self.min_return and
            cv_pred < 0.05 and net_benefit > 100):
            batch_size = 0.0  # FIX: Was 0.05, now 0.0 to actually defer
            reason = f'very_strong_consensus_{bullish_pct:.0%}_defer'
        # FIXED: Strong consensus → HOLD (batch_size = 0.0, not 0.10)
        elif (bullish_pct >= self.consensus_threshold and expected_return >= self.min_return and
              cv_pred < 0.10 and net_benefit > 50):
            batch_size = 0.0  # FIX: Was 0.10, now 0.0 to defer
            reason = f'strong_consensus_{bullish_pct:.0%}_conf{cv_pred:.1%}_defer'
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


# =============================================================================
# FIXED: EXPECTED VALUE STRATEGY
# =============================================================================

class ExpectedValueStrategyFixed(Strategy):
    """
    FIXED: Expected Value Strategy

    BUG FIX: Lines that say "defer" now return batch_size=0.0 to HOLD instead of selling

    Original bug:
        batch_size = 0.10 with reason "peak_late_day13_high_conf_defer"
    Fixed:
        batch_size = 0.0 with reason "peak_late_day13_high_conf_defer"
    """

    def __init__(self, storage_cost_pct_per_day, transaction_cost_pct,
                 min_ev_improvement=50, baseline_batch=0.15, baseline_frequency=10):
        super().__init__("Expected Value (Fixed)")
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.min_ev_improvement = min_ev_improvement
        self.baseline_batch = baseline_batch
        self.baseline_frequency = baseline_frequency
        self.cooldown_days = 7
        self.last_sale_day = -self.cooldown_days

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, self.baseline_batch, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_expected_value(
            current_price, price_history, predictions
        )

        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}

    def _analyze_expected_value(self, current_price, price_history, predictions):
        """EV optimization + all indicators"""

        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)

        cv_pred = calculate_prediction_confidence(predictions, horizon_day=13)
        adx_pred, _, _ = calculate_adx(pd.DataFrame({'price': [np.median(predictions[:, h]) for h in range(predictions.shape[1])]}))

        optimal_day, net_benefit = self._find_optimal_sale_day(current_price, predictions)

        batch_size = 0.0

        if optimal_day <= 3 and cv_pred < 0.08 and net_benefit > self.min_ev_improvement:
            batch_size = 0.20
            reason = f'peak_soon_day{optimal_day}_ev${net_benefit:.0f}_conf{cv_pred:.1%}'
        elif optimal_day <= 7 and cv_pred < 0.12 and net_benefit > self.min_ev_improvement:
            batch_size = 0.15
            reason = f'peak_mid_day{optimal_day}_ev${net_benefit:.0f}'
        # FIXED: Peak is late → HOLD (batch_size = 0.0, not 0.10)
        elif optimal_day > 7 and cv_pred < 0.08 and adx_pred > 25:
            batch_size = 0.0  # FIX: Was 0.10, now 0.0 to actually defer
            reason = f'peak_late_day{optimal_day}_high_conf_defer'
        elif optimal_day > 7:
            batch_size = 0.0  # FIX: Was 0.15, now 0.0 to defer when peak is late
            reason = f'peak_late_day{optimal_day}_uncertain_cv{cv_pred:.1%}_defer'
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


# =============================================================================
# FIXED: RISK-ADJUSTED STRATEGY
# =============================================================================

class RiskAdjustedStrategyFixed(Strategy):
    """
    FIXED: Risk-Adjusted Strategy

    BUG FIX: Lines that say "defer" now return batch_size=0.0 to HOLD instead of selling

    Original bug:
        batch_size = 0.08 with reason "very_low_risk_cv3.4%_adx26_defer"
    Fixed:
        batch_size = 0.0 with reason "very_low_risk_cv3.4%_adx26_defer"
    """

    def __init__(self, min_return=0.05, max_uncertainty=0.08,
                 consensus_threshold=0.65, evaluation_day=14,
                 storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25):
        super().__init__("Risk-Adjusted (Fixed)")
        self.min_return = min_return
        self.max_uncertainty = max_uncertainty
        self.consensus_threshold = consensus_threshold
        self.evaluation_day = evaluation_day
        self.cooldown_days = 7
        self.last_sale_day = -self.cooldown_days

        self.storage_cost_pct = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        if predictions is None or predictions.size == 0:
            if days_since_sale >= 30:
                return self._execute_trade(day, inventory, 0.18, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_risk_adjusted(
            current_price, price_history, predictions
        )

        if batch_size > 0:
            return self._execute_trade(day, inventory, batch_size, reason)
        else:
            return {'action': 'HOLD', 'amount': 0, 'reason': reason}

    def _analyze_risk_adjusted(self, current_price, price_history, predictions):
        """Analyze risk/return using all indicators"""

        prices = price_history['price'].values
        rsi_hist = calculate_rsi(prices, period=14)
        adx_hist, _, _ = calculate_adx(price_history, period=14)

        adx_pred, _, _ = calculate_adx(pd.DataFrame({'price': [np.median(predictions[:, h]) for h in range(predictions.shape[1])]}))
        cv_pred = calculate_prediction_confidence(predictions, horizon_day=min(self.evaluation_day-1, predictions.shape[1]-1))

        eval_day_idx = min(self.evaluation_day, predictions.shape[1]) - 1
        day_preds = predictions[:, eval_day_idx]
        median_pred = np.median(day_preds)
        expected_return = (median_pred - current_price) / current_price

        predicted_medians = [np.median(predictions[:, h]) for h in range(predictions.shape[1])]
        daily_changes = np.diff(predicted_medians)
        pct_positive = np.mean(daily_changes > 0)

        net_benefit = self._calculate_cost_benefit(current_price, predictions)

        batch_size = 0.0

        # FIXED: Very low risk → HOLD (batch_size = 0.0, not 0.08)
        if (cv_pred < 0.05 and adx_pred > 25 and expected_return >= self.min_return and
            pct_positive > 0.70 and net_benefit > 100):
            batch_size = 0.0  # FIX: Was 0.08, now 0.0 to defer
            reason = f'very_low_risk_cv{cv_pred:.1%}_adx{adx_pred:.0f}_defer'
        # FIXED: Low risk → HOLD (batch_size = 0.0, not 0.12)
        elif cv_pred < 0.10 and adx_pred > 20 and expected_return >= self.min_return * 0.67 and net_benefit > 50:
            batch_size = 0.0  # FIX: Was 0.12, now 0.0 to defer
            reason = f'low_risk_cv{cv_pred:.1%}_ret{expected_return:.1%}_defer'
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
