"""
Prediction-Based Trading Strategies
Extracted from diagnostics/all_strategies_pct.py (improved version)

Contains 5 prediction strategies:
1. PriceThresholdPredictive - Matched pair (baseline + predictions, 3-tier OVERRIDE/BLEND/BASELINE)
2. MovingAveragePredictive - Matched pair (baseline + predictions, 3-tier OVERRIDE/BLEND/BASELINE)
3. ExpectedValueStrategy - Standalone (EV optimization)
4. ConsensusStrategy - Standalone (ensemble consensus)
5. RiskAdjustedStrategy - Standalone (risk/return optimization)

**CRITICAL IMPROVEMENTS from notebook 03:**
- Three-tier prediction usage (HIGH/MEDIUM/LOW confidence)
- OVERRIDE/BLEND/BASELINE paradigm for matched pairs
- Percentage-based decision framework (scale-invariant)
- Full parameterization for grid search
- Updated cost defaults (0.005% storage, 0.01% transaction)

Academic References:
- Expected Value strategy based on:
  Williams, J. C., & Wright, B. D. (1991). Storage and Commodity Markets.
  Cambridge University Press. ISBN: 9780521326162

- Consensus strategy based on:
  Clemen, R. T. (1989). "Combining forecasts: A review and annotated bibliography."
  International Journal of Forecasting, 5(4), 559-583.

- Risk-Adjusted strategy based on:
  Markowitz, H. (1952). "Portfolio selection." Journal of Finance, 7(1), 77-91.

- Predictive variants (Threshold/MA) extend baseline strategies with forecast confidence:
  Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008) + Williams & Wright (1991)

See docs/STRATEGY_ACADEMIC_REFERENCES.md for complete academic citations.
"""

import numpy as np
from .base import Strategy
from .indicators import calculate_rsi, calculate_adx, calculate_prediction_confidence


# =============================================================================
# MATCHED PAIR: PRICE THRESHOLD PREDICTIVE
# =============================================================================

class PriceThresholdPredictive(Strategy):
    """
    Matched Pair: PriceThreshold + Predictions (REDESIGNED v2)

    MATCHED PAIR PARADIGM:
    - Baseline: PriceThresholdStrategy (no predictions, for comparison)
    - Augmented: This strategy (with prediction override capability)

    THREE-TIER PREDICTION USAGE:
    1. HIGH confidence predictions → OVERRIDE baseline completely
    2. MEDIUM confidence predictions → BLEND baseline + predictions
    3. LOW/NO confidence predictions → FOLLOW baseline exactly

    This design:
    - Preserves matched pair comparison (baseline vs augmented)
    - Leverages predictions fully when confident
    - Degrades gracefully when predictions weak
    - Shows measurable benefit of adding predictions
    """

    def __init__(self,
                 # MATCHED baseline parameters (identical to PriceThresholdStrategy)
                 threshold_pct=0.05,
                 batch_baseline=0.25,
                 batch_overbought_strong=0.35,
                 batch_overbought=0.30,
                 batch_strong_trend=0.20,
                 rsi_overbought=70,
                 rsi_moderate=65,
                 adx_strong=25,
                 cooldown_days=7,
                 max_days_without_sale=60,

                 # PREDICTION parameters
                 storage_cost_pct_per_day=0.005,  # Updated default
                 transaction_cost_pct=0.01,        # Updated default

                 # Confidence thresholds
                 high_confidence_cv=0.05,      # CV < 5% = high confidence
                 medium_confidence_cv=0.15,    # CV < 15% = medium confidence

                 # Override thresholds
                 strong_positive_threshold=2.0,  # >2% net benefit = strong upward
                 strong_negative_threshold=-1.0, # <-1% net benefit = strong downward
                 moderate_threshold=0.5,         # ±0.5% = moderate signal

                 # Batch sizes for prediction-driven actions
                 batch_pred_hold=0.0,           # Hold completely when strong upward signal
                 batch_pred_aggressive=0.40,    # Aggressive sell when strong downward
                 batch_pred_cautious=0.15):     # Cautious sell when uncertain

        super().__init__("Price Threshold Predictive")

        # Baseline parameters (matched to PriceThresholdStrategy)
        self.threshold_pct = threshold_pct
        self.batch_baseline = batch_baseline
        self.batch_overbought_strong = batch_overbought_strong
        self.batch_overbought = batch_overbought
        self.batch_strong_trend = batch_strong_trend
        self.rsi_overbought = rsi_overbought
        self.rsi_moderate = rsi_moderate
        self.adx_strong = adx_strong
        self.cooldown_days = cooldown_days
        self.max_days_without_sale = max_days_without_sale
        self.last_sale_day = 0

        # Prediction parameters
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.high_confidence_cv = high_confidence_cv
        self.medium_confidence_cv = medium_confidence_cv
        self.strong_positive_threshold = strong_positive_threshold
        self.strong_negative_threshold = strong_negative_threshold
        self.moderate_threshold = moderate_threshold
        self.batch_pred_hold = batch_pred_hold
        self.batch_pred_aggressive = batch_pred_aggressive
        self.batch_pred_cautious = batch_pred_cautious

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        """
        DECISION HIERARCHY:
        1. Forced liquidation (always highest priority)
        2. Cooldown check
        3. Prediction signal analysis (if available)
        4. Baseline signal (if no predictions or low confidence)
        """
        if inventory <= 0:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_inventory'}

        forced = self._force_liquidation_check(day, inventory)
        if forced:
            return forced

        days_since_sale = day - self.last_sale_day

        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        # Analyze predictions if available
        if predictions is not None and predictions.size > 0:
            pred_signal = self._analyze_prediction_signal(
                current_price, price_history, predictions
            )

            # HIGH CONFIDENCE → OVERRIDE BASELINE
            if pred_signal['confidence'] == 'HIGH':
                return self._execute_prediction_override(
                    day, inventory, pred_signal, price_history
                )

            # MEDIUM CONFIDENCE → BLEND WITH BASELINE
            elif pred_signal['confidence'] == 'MEDIUM':
                return self._execute_blended_decision(
                    day, inventory, current_price, price_history, pred_signal
                )

        # LOW/NO CONFIDENCE → FOLLOW BASELINE
        return self._execute_baseline_logic(
            day, inventory, current_price, price_history
        )

    def _analyze_prediction_signal(self, current_price, price_history, predictions):
        """
        Analyze predictions to determine:
        1. Direction (upward/downward/neutral)
        2. Magnitude (strong/moderate/weak)
        3. Confidence (high/medium/low)
        """
        # Calculate cost-benefit across all horizons
        net_benefit_pct = self._calculate_net_benefit_pct(current_price, predictions)

        # Calculate prediction confidence (CV)
        cv = calculate_prediction_confidence(
            predictions,
            horizon_day=min(13, predictions.shape[1] - 1)
        )

        # Determine confidence level
        if cv < self.high_confidence_cv:
            confidence = 'HIGH'
        elif cv < self.medium_confidence_cv:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        # Determine direction and magnitude
        if net_benefit_pct > self.strong_positive_threshold:
            direction = 'STRONG_UPWARD'
        elif net_benefit_pct > self.moderate_threshold:
            direction = 'MODERATE_UPWARD'
        elif net_benefit_pct < self.strong_negative_threshold:
            direction = 'STRONG_DOWNWARD'
        elif net_benefit_pct < -self.moderate_threshold:
            direction = 'MODERATE_DOWNWARD'
        else:
            direction = 'NEUTRAL'

        return {
            'confidence': confidence,
            'direction': direction,
            'net_benefit_pct': net_benefit_pct,
            'cv': cv
        }

    def _execute_prediction_override(self, day, inventory, pred_signal, price_history):
        """
        HIGH CONFIDENCE: Predictions override baseline completely
        """
        direction = pred_signal['direction']
        net_benefit = pred_signal['net_benefit_pct']
        cv = pred_signal['cv']

        if direction == 'STRONG_UPWARD':
            # Strong evidence prices will rise → HOLD completely
            batch_size = self.batch_pred_hold
            reason = f'OVERRIDE_hold_strong_upward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'MODERATE_UPWARD':
            # Moderate upward → Small hedge
            batch_size = self.batch_pred_cautious
            reason = f'OVERRIDE_small_hedge_mod_upward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'STRONG_DOWNWARD':
            # Strong evidence prices will fall → SELL aggressively
            batch_size = self.batch_pred_aggressive
            reason = f'OVERRIDE_aggressive_strong_downward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'MODERATE_DOWNWARD':
            # Moderate downward → Sell baseline
            batch_size = self.batch_baseline
            reason = f'OVERRIDE_baseline_mod_downward_net{net_benefit:.2f}%_cv{cv:.2%}'

        else:  # NEUTRAL
            # Unclear signal → Use baseline batch but note override
            batch_size = self.batch_baseline
            reason = f'OVERRIDE_neutral_net{net_benefit:.2f}%_cv{cv:.2%}'

        return self._execute_trade(day, inventory, batch_size, reason)

    def _execute_blended_decision(self, day, inventory, current_price,
                                  price_history, pred_signal):
        """
        MEDIUM CONFIDENCE: Blend baseline signal with prediction signal
        """
        # Calculate what baseline would do
        baseline_action = self._get_baseline_action(current_price, price_history)

        direction = pred_signal['direction']
        net_benefit = pred_signal['net_benefit_pct']

        # Blend logic:
        # - If baseline and predictions agree → follow baseline
        # - If they disagree → moderate the baseline action

        if baseline_action['triggered']:
            # Baseline says SELL
            if direction in ['STRONG_UPWARD', 'MODERATE_UPWARD']:
                # Predictions disagree → reduce sell amount
                batch_size = baseline_action['batch_size'] * 0.5
                reason = f'BLEND_reduce_sell_pred_upward_net{net_benefit:.2f}%'
            else:
                # Predictions agree or neutral → follow baseline
                batch_size = baseline_action['batch_size']
                reason = f'BLEND_follow_baseline_{baseline_action["reason"]}'

        else:
            # Baseline says HOLD
            if direction in ['STRONG_DOWNWARD', 'MODERATE_DOWNWARD']:
                # Predictions disagree → cautious sell
                batch_size = self.batch_pred_cautious
                reason = f'BLEND_cautious_sell_pred_downward_net{net_benefit:.2f}%'
            else:
                # Predictions agree → hold
                return {'action': 'HOLD', 'amount': 0,
                       'reason': f'BLEND_hold_pred_agrees'}

        return self._execute_trade(day, inventory, batch_size, reason)

    def _execute_baseline_logic(self, day, inventory, current_price, price_history):
        """
        Execute IDENTICAL logic to PriceThresholdStrategy (for fair comparison)
        """
        days_since_sale = day - self.last_sale_day

        # Calculate threshold
        if len(price_history) >= 30:
            ma_30 = price_history['price'].tail(30).mean()
            threshold = ma_30 * (1 + self.threshold_pct)
        else:
            threshold = current_price * (1 + self.threshold_pct)

        signal_triggered = current_price > threshold

        if not signal_triggered:
            # Fallback after max days
            if days_since_sale >= self.max_days_without_sale:
                return self._execute_trade(day, inventory, self.batch_baseline,
                                          f'BASELINE_fallback_{days_since_sale}d')
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'BASELINE_below_threshold_{current_price:.2f}<{threshold:.2f}'}

        # Signal triggered → analyze with technical indicators
        batch_size, reason = self._analyze_baseline_technicals(current_price, price_history)
        return self._execute_trade(day, inventory, batch_size, f'BASELINE_{reason}')

    def _get_baseline_action(self, current_price, price_history):
        """
        Calculate what baseline would do (without executing)
        """
        if len(price_history) >= 30:
            ma_30 = price_history['price'].tail(30).mean()
            threshold = ma_30 * (1 + self.threshold_pct)
        else:
            threshold = current_price * (1 + self.threshold_pct)

        if current_price <= threshold:
            return {'triggered': False, 'batch_size': 0, 'reason': 'below_threshold'}

        batch_size, reason = self._analyze_baseline_technicals(current_price, price_history)
        return {'triggered': True, 'batch_size': batch_size, 'reason': reason}

    def _analyze_baseline_technicals(self, current_price, price_history):
        """
        IDENTICAL to PriceThresholdStrategy technical analysis
        """
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, _, _ = calculate_adx(price_history, period=14)

        if rsi > self.rsi_overbought and adx > self.adx_strong:
            batch_size = self.batch_overbought_strong
            reason = f'overbought_strong_rsi{rsi:.0f}_adx{adx:.0f}'
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

    def _calculate_net_benefit_pct(self, current_price, predictions):
        """
        Calculate net benefit as percentage:
        (best_future_value - sell_today_value) / current_price * 100
        """
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

        optimal_ev = max(ev_by_day)
        net_benefit_pct = 100 * (optimal_ev - ev_today) / current_price

        return net_benefit_pct

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = 0


# =============================================================================
# MATCHED PAIR: MOVING AVERAGE PREDICTIVE
# =============================================================================

class MovingAveragePredictive(Strategy):
    """
    Matched Pair: MovingAverage + Predictions (REDESIGNED v2)

    MATCHED PAIR PARADIGM:
    - Baseline: MovingAverageStrategy (no predictions, for comparison)
    - Augmented: This strategy (with prediction override capability)

    THREE-TIER PREDICTION USAGE:
    1. HIGH confidence predictions → OVERRIDE baseline completely
    2. MEDIUM confidence predictions → BLEND baseline + predictions
    3. LOW/NO confidence predictions → FOLLOW baseline exactly

    This design:
    - Preserves matched pair comparison (baseline vs augmented)
    - Leverages predictions fully when confident
    - Degrades gracefully when predictions weak
    - Shows measurable benefit of adding predictions
    """

    def __init__(self,
                 # MATCHED baseline parameters (identical to MovingAverageStrategy)
                 ma_period=30,
                 batch_baseline=0.25,
                 batch_strong_momentum=0.20,
                 batch_overbought_strong=0.35,
                 batch_overbought=0.30,
                 rsi_overbought=70,
                 rsi_min=45,
                 adx_strong=25,
                 adx_weak=20,
                 cooldown_days=7,
                 max_days_without_sale=60,

                 # PREDICTION parameters
                 storage_cost_pct_per_day=0.005,  # Updated default
                 transaction_cost_pct=0.01,        # Updated default

                 # Confidence thresholds
                 high_confidence_cv=0.05,      # CV < 5% = high confidence
                 medium_confidence_cv=0.15,    # CV < 15% = medium confidence

                 # Override thresholds
                 strong_positive_threshold=2.0,  # >2% net benefit = strong upward
                 strong_negative_threshold=-1.0, # <-1% net benefit = strong downward
                 moderate_threshold=0.5,         # ±0.5% = moderate signal

                 # Batch sizes for prediction-driven actions
                 batch_pred_hold=0.0,           # Hold completely when strong upward signal
                 batch_pred_aggressive=0.40,    # Aggressive sell when strong downward
                 batch_pred_cautious=0.15):     # Cautious sell when uncertain

        super().__init__("Moving Average Predictive")

        # Baseline parameters (matched to MovingAverageStrategy)
        self.period = ma_period
        self.batch_baseline = batch_baseline
        self.batch_strong_momentum = batch_strong_momentum
        self.batch_overbought_strong = batch_overbought_strong
        self.batch_overbought = batch_overbought
        self.rsi_overbought = rsi_overbought
        self.rsi_min = rsi_min
        self.adx_strong = adx_strong
        self.adx_weak = adx_weak
        self.cooldown_days = cooldown_days
        self.max_days_without_sale = max_days_without_sale
        self.last_sale_day = 0

        # Prediction parameters
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.high_confidence_cv = high_confidence_cv
        self.medium_confidence_cv = medium_confidence_cv
        self.strong_positive_threshold = strong_positive_threshold
        self.strong_negative_threshold = strong_negative_threshold
        self.moderate_threshold = moderate_threshold
        self.batch_pred_hold = batch_pred_hold
        self.batch_pred_aggressive = batch_pred_aggressive
        self.batch_pred_cautious = batch_pred_cautious

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        """
        DECISION HIERARCHY:
        1. Forced liquidation (always highest priority)
        2. Fallback after max days
        3. Prediction signal analysis (if available)
        4. Baseline MA crossover signal (if no predictions or low confidence)
        """
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

        if days_since_sale < self.cooldown_days:
            return {'action': 'HOLD', 'amount': 0,
                   'reason': f'cooldown_{self.cooldown_days - days_since_sale}d'}

        # Analyze predictions if available
        if predictions is not None and predictions.size > 0:
            pred_signal = self._analyze_prediction_signal(
                current_price, price_history, predictions
            )

            # HIGH CONFIDENCE → OVERRIDE BASELINE
            if pred_signal['confidence'] == 'HIGH':
                return self._execute_prediction_override(
                    day, inventory, pred_signal, price_history
                )

            # MEDIUM CONFIDENCE → BLEND WITH BASELINE
            elif pred_signal['confidence'] == 'MEDIUM':
                return self._execute_blended_decision(
                    day, inventory, current_price, price_history, pred_signal
                )

        # LOW/NO CONFIDENCE → FOLLOW BASELINE
        return self._execute_baseline_logic(
            day, inventory, current_price, price_history
        )

    def _analyze_prediction_signal(self, current_price, price_history, predictions):
        """
        Analyze predictions to determine:
        1. Direction (upward/downward/neutral)
        2. Magnitude (strong/moderate/weak)
        3. Confidence (high/medium/low)
        """
        # Calculate cost-benefit across all horizons
        net_benefit_pct = self._calculate_net_benefit_pct(current_price, predictions)

        # Calculate prediction confidence (CV)
        cv = calculate_prediction_confidence(
            predictions,
            horizon_day=min(13, predictions.shape[1] - 1)
        )

        # Determine confidence level
        if cv < self.high_confidence_cv:
            confidence = 'HIGH'
        elif cv < self.medium_confidence_cv:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        # Determine direction and magnitude
        if net_benefit_pct > self.strong_positive_threshold:
            direction = 'STRONG_UPWARD'
        elif net_benefit_pct > self.moderate_threshold:
            direction = 'MODERATE_UPWARD'
        elif net_benefit_pct < self.strong_negative_threshold:
            direction = 'STRONG_DOWNWARD'
        elif net_benefit_pct < -self.moderate_threshold:
            direction = 'MODERATE_DOWNWARD'
        else:
            direction = 'NEUTRAL'

        return {
            'confidence': confidence,
            'direction': direction,
            'net_benefit_pct': net_benefit_pct,
            'cv': cv
        }

    def _execute_prediction_override(self, day, inventory, pred_signal, price_history):
        """
        HIGH CONFIDENCE: Predictions override baseline completely
        """
        direction = pred_signal['direction']
        net_benefit = pred_signal['net_benefit_pct']
        cv = pred_signal['cv']

        if direction == 'STRONG_UPWARD':
            # Strong evidence prices will rise → HOLD completely
            batch_size = self.batch_pred_hold
            reason = f'OVERRIDE_hold_strong_upward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'MODERATE_UPWARD':
            # Moderate upward → Small hedge
            batch_size = self.batch_pred_cautious
            reason = f'OVERRIDE_small_hedge_mod_upward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'STRONG_DOWNWARD':
            # Strong evidence prices will fall → SELL aggressively
            batch_size = self.batch_pred_aggressive
            reason = f'OVERRIDE_aggressive_strong_downward_net{net_benefit:.2f}%_cv{cv:.2%}'

        elif direction == 'MODERATE_DOWNWARD':
            # Moderate downward → Sell baseline
            batch_size = self.batch_baseline
            reason = f'OVERRIDE_baseline_mod_downward_net{net_benefit:.2f}%_cv{cv:.2%}'

        else:  # NEUTRAL
            # Unclear signal → Use baseline batch but note override
            batch_size = self.batch_baseline
            reason = f'OVERRIDE_neutral_net{net_benefit:.2f}%_cv{cv:.2%}'

        return self._execute_trade(day, inventory, batch_size, reason)

    def _execute_blended_decision(self, day, inventory, current_price,
                                  price_history, pred_signal):
        """
        MEDIUM CONFIDENCE: Blend baseline signal with prediction signal
        """
        # Calculate what baseline would do
        baseline_action = self._get_baseline_action(current_price, price_history)

        direction = pred_signal['direction']
        net_benefit = pred_signal['net_benefit_pct']

        # Blend logic:
        # - If baseline and predictions agree → follow baseline
        # - If they disagree → moderate the baseline action

        if baseline_action['triggered']:
            # Baseline says SELL (downward cross detected)
            if direction in ['STRONG_UPWARD', 'MODERATE_UPWARD']:
                # Predictions disagree → reduce sell amount
                batch_size = baseline_action['batch_size'] * 0.5
                reason = f'BLEND_reduce_sell_pred_upward_net{net_benefit:.2f}%'
            else:
                # Predictions agree or neutral → follow baseline
                batch_size = baseline_action['batch_size']
                reason = f'BLEND_follow_baseline_{baseline_action["reason"]}'

        else:
            # Baseline says HOLD (no crossover or upward cross)
            if direction in ['STRONG_DOWNWARD', 'MODERATE_DOWNWARD']:
                # Predictions disagree → cautious sell
                batch_size = self.batch_pred_cautious
                reason = f'BLEND_cautious_sell_pred_downward_net{net_benefit:.2f}%'
            else:
                # Predictions agree → hold
                return {'action': 'HOLD', 'amount': 0,
                       'reason': f'BLEND_hold_pred_agrees'}

        return self._execute_trade(day, inventory, batch_size, reason)

    def _execute_baseline_logic(self, day, inventory, current_price, price_history):
        """
        Execute IDENTICAL logic to MovingAverageStrategy (for fair comparison)
        """
        recent_prices = price_history['price'].tail(self.period + 1).values
        ma_current = np.mean(recent_prices[-self.period:])
        ma_prev = np.mean(recent_prices[-(self.period+1):-1])
        prev_price = recent_prices[-2]

        # Detect crossover directions
        upward_cross = (prev_price <= ma_prev and current_price > ma_current)
        downward_cross = (prev_price >= ma_prev and current_price < ma_current)

        # Upward crossover: HOLD for higher prices
        if upward_cross:
            return {'action': 'HOLD', 'amount': 0, 'reason': 'BASELINE_upward_crossover_bullish'}

        # Downward crossover: SELL to avoid decline
        if downward_cross:
            batch_size, reason = self._analyze_baseline_technicals(current_price, price_history)
            return self._execute_trade(day, inventory, batch_size, f'BASELINE_{reason}')

        # No crossover: maintain position
        return {'action': 'HOLD', 'amount': 0, 'reason': 'BASELINE_no_crossover'}

    def _get_baseline_action(self, current_price, price_history):
        """
        Calculate what baseline would do (without executing)
        """
        recent_prices = price_history['price'].tail(self.period + 1).values
        ma_current = np.mean(recent_prices[-self.period:])
        ma_prev = np.mean(recent_prices[-(self.period+1):-1])
        prev_price = recent_prices[-2]

        downward_cross = (prev_price >= ma_prev and current_price < ma_current)

        if not downward_cross:
            return {'triggered': False, 'batch_size': 0, 'reason': 'no_downward_cross'}

        batch_size, reason = self._analyze_baseline_technicals(current_price, price_history)
        return {'triggered': True, 'batch_size': batch_size, 'reason': reason}

    def _analyze_baseline_technicals(self, current_price, price_history):
        """
        IDENTICAL to MovingAverageStrategy technical analysis
        """
        prices = price_history['price'].values
        rsi = calculate_rsi(prices, period=14)
        adx, _, _ = calculate_adx(price_history, period=14)

        if adx > self.adx_strong and rsi >= self.rsi_min and rsi <= self.rsi_overbought:
            batch_size = self.batch_strong_momentum
            reason = f'strong_momentum_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > self.rsi_overbought and adx > self.adx_strong:
            batch_size = self.batch_overbought_strong
            reason = f'overbought_strong_rsi{rsi:.0f}_adx{adx:.0f}'
        elif rsi > self.rsi_overbought:
            batch_size = self.batch_overbought
            reason = f'overbought_rsi{rsi:.0f}'
        else:
            batch_size = self.batch_baseline
            reason = f'baseline_rsi{rsi:.0f}_adx{adx:.0f}'

        return batch_size, reason

    def _calculate_net_benefit_pct(self, current_price, predictions):
        """
        Calculate net benefit as percentage:
        (best_future_value - sell_today_value) / current_price * 100
        """
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

        optimal_ev = max(ev_by_day)
        net_benefit_pct = 100 * (optimal_ev - ev_today) / current_price

        return net_benefit_pct

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = 0


# =============================================================================
# STANDALONE: EXPECTED VALUE (from corrected_strategies.py)
# =============================================================================

class ExpectedValueStrategy(Strategy):
    """
    Standalone prediction: Expected value optimization

    PERCENTAGE-BASED decision framework.
    Full parameterization for grid search.
    """

    def __init__(self,
                 storage_cost_pct_per_day,
                 transaction_cost_pct,
                 min_net_benefit_pct=0.5,
                 negative_threshold_pct=-0.3,
                 high_confidence_cv=0.05,
                 medium_confidence_cv=0.10,
                 strong_trend_adx=25,
                 batch_positive_confident=0.0,
                 batch_positive_uncertain=0.10,
                 batch_marginal=0.15,
                 batch_negative_mild=0.25,
                 batch_negative_strong=0.35,
                 cooldown_days=7,
                 baseline_batch=0.15,
                 baseline_frequency=30):

        super().__init__("Expected Value")
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.min_net_benefit_pct = min_net_benefit_pct
        self.negative_threshold_pct = negative_threshold_pct
        self.high_confidence_cv = high_confidence_cv
        self.medium_confidence_cv = medium_confidence_cv
        self.strong_trend_adx = strong_trend_adx
        self.batch_positive_confident = batch_positive_confident
        self.batch_positive_uncertain = batch_positive_uncertain
        self.batch_marginal = batch_marginal
        self.batch_negative_mild = batch_negative_mild
        self.batch_negative_strong = batch_negative_strong
        self.cooldown_days = cooldown_days
        self.baseline_batch = baseline_batch
        self.baseline_frequency = baseline_frequency
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
            if days_since_sale >= self.baseline_frequency:
                return self._execute_trade(day, inventory, self.baseline_batch,
                                          'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_expected_value_pct(
            current_price, price_history, predictions
        )

        return self._execute_trade(day, inventory, batch_size, reason)

    def _analyze_expected_value_pct(self, current_price, price_history, predictions):
        optimal_day, net_benefit_pct = self._find_optimal_sale_day_pct(
            current_price, predictions
        )

        cv_pred = calculate_prediction_confidence(
            predictions,
            horizon_day=min(13, predictions.shape[1]-1)
        )
        adx_pred, _, _ = calculate_adx(price_history, period=min(14, len(price_history)-1))

        if net_benefit_pct > self.min_net_benefit_pct:
            if cv_pred < self.high_confidence_cv and adx_pred > self.strong_trend_adx:
                batch_size = self.batch_positive_confident
                reason = f'net_benefit_{net_benefit_pct:.2f}%_high_conf_hold_to_day{optimal_day}'
            elif cv_pred < self.medium_confidence_cv:
                batch_size = self.batch_positive_uncertain
                reason = f'net_benefit_{net_benefit_pct:.2f}%_med_conf_small_hedge_day{optimal_day}'
            else:
                batch_size = self.batch_marginal
                reason = f'net_benefit_{net_benefit_pct:.2f}%_low_conf_hedge'

        elif net_benefit_pct > 0:
            batch_size = self.batch_marginal
            reason = f'marginal_benefit_{net_benefit_pct:.2f}%_gradual_liquidation'

        elif net_benefit_pct > self.negative_threshold_pct:
            batch_size = self.batch_negative_mild
            reason = f'mild_negative_{net_benefit_pct:.2f}%_avoid_storage'

        else:
            batch_size = self.batch_negative_strong
            reason = f'strong_negative_{net_benefit_pct:.2f}%_sell_to_cut_losses'

        return batch_size, reason

    def _find_optimal_sale_day_pct(self, current_price, predictions):
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
        net_benefit_pct = 100 * (ev_by_day[optimal_day] - ev_today) / current_price

        return optimal_day, net_benefit_pct

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days


# =============================================================================
# CONSENSUS STRATEGY (PERCENTAGE-BASED)
# =============================================================================

class ConsensusStrategy(Strategy):
    """
    Consensus strategy with percentage-based decision framework.

    Decision Logic:
    1. Count % of predictions that are bullish (above min_return)
    2. If consensus >= threshold AND net_benefit_pct > min: HOLD
    3. If bearish consensus: SELL
    4. Batch size modulated by consensus strength

    All thresholds are percentages for scale-invariance.
    """

    def __init__(self,
                 storage_cost_pct_per_day,
                 transaction_cost_pct,
                 # Consensus thresholds
                 consensus_threshold=0.70,           # 70% agreement to act
                 very_strong_consensus=0.85,         # 85% = very strong
                 moderate_consensus=0.60,            # 60% = moderate
                 # Percentage-based decision thresholds
                 min_return=0.03,                    # 3% minimum return
                 min_net_benefit_pct=0.5,            # 0.5% minimum net benefit
                 # Confidence threshold
                 high_confidence_cv=0.05,            # CV < 5% = high confidence
                 # Which day to evaluate
                 evaluation_day=14,
                 # Batch sizing (0.0 to ~0.40)
                 batch_strong_consensus=0.0,         # Hold when very strong consensus
                 batch_moderate=0.15,                # Gradual when moderate
                 batch_weak=0.25,                    # Sell when weak consensus
                 batch_bearish=0.35,                 # Sell aggressively when bearish
                 # Timing
                 cooldown_days=7):

        super().__init__("Consensus")

        # Cost parameters
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct

        # Consensus thresholds
        self.consensus_threshold = consensus_threshold
        self.very_strong_consensus = very_strong_consensus
        self.moderate_consensus = moderate_consensus

        # PERCENTAGE-based decision thresholds
        self.min_return = min_return
        self.min_net_benefit_pct = min_net_benefit_pct

        # Confidence
        self.high_confidence_cv = high_confidence_cv

        # Evaluation parameters
        self.evaluation_day = evaluation_day

        # Batch sizing
        self.batch_strong_consensus = batch_strong_consensus
        self.batch_moderate = batch_moderate
        self.batch_weak = batch_weak
        self.batch_bearish = batch_bearish

        self.cooldown_days = cooldown_days
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
                return self._execute_trade(day, inventory, 0.20, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_consensus_pct(
            current_price, price_history, predictions
        )

        return self._execute_trade(day, inventory, batch_size, reason)

    def _analyze_consensus_pct(self, current_price, price_history, predictions):
        """Calculate consensus and make percentage-based decision"""

        # Evaluate at specific day
        eval_day = min(self.evaluation_day, predictions.shape[1] - 1)
        day_predictions = predictions[:, eval_day]

        # Calculate expected return as percentage
        median_future = np.median(day_predictions)
        expected_return_pct = (median_future - current_price) / current_price

        # Count bullish predictions (those showing sufficient return)
        bullish_count = np.sum(
            (day_predictions - current_price) / current_price > self.min_return
        )
        bullish_pct = bullish_count / len(day_predictions)

        # Calculate confidence
        cv = calculate_prediction_confidence(predictions, eval_day)

        # Calculate net benefit accounting for costs
        days_to_wait = eval_day + 1
        storage_cost_pct = (self.storage_cost_pct_per_day / 100) * days_to_wait
        transaction_cost_pct = self.transaction_cost_pct / 100
        net_benefit_pct = 100 * (expected_return_pct - storage_cost_pct - transaction_cost_pct)

        # Decision based on consensus and net benefit
        if bullish_pct >= self.very_strong_consensus and net_benefit_pct > self.min_net_benefit_pct:
            # Very strong consensus + positive net benefit
            batch_size = self.batch_strong_consensus
            reason = f'very_strong_consensus_{bullish_pct:.0%}_net_{net_benefit_pct:.2f}%_hold'

        elif bullish_pct >= self.consensus_threshold and net_benefit_pct > self.min_net_benefit_pct:
            # Strong consensus + positive net benefit
            if cv < self.high_confidence_cv:
                batch_size = self.batch_strong_consensus
                reason = f'strong_consensus_{bullish_pct:.0%}_high_conf_hold'
            else:
                batch_size = self.batch_moderate
                reason = f'strong_consensus_{bullish_pct:.0%}_med_conf_gradual'

        elif bullish_pct >= self.moderate_consensus:
            # Moderate consensus
            batch_size = self.batch_moderate
            reason = f'moderate_consensus_{bullish_pct:.0%}_gradual'

        elif bullish_pct < (1 - self.consensus_threshold):
            # Bearish consensus (most predictions negative)
            batch_size = self.batch_bearish
            reason = f'bearish_consensus_{bullish_pct:.0%}_sell'

        else:
            # Weak/unclear consensus
            batch_size = self.batch_weak
            reason = f'weak_consensus_{bullish_pct:.0%}_sell'

        return batch_size, reason

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days


# =============================================================================
# RISK-ADJUSTED STRATEGY (PERCENTAGE-BASED)
# =============================================================================

class RiskAdjustedStrategy(Strategy):
    """
    Risk-adjusted strategy with percentage-based framework.

    Decision Logic:
    1. Evaluate expected return as percentage
    2. Measure uncertainty (CV)
    3. If return > threshold AND uncertainty < max AND net_benefit_pct > min: HOLD
    4. Batch size based on risk tier (low/medium/high/very high)

    All thresholds in percentages.
    """

    def __init__(self,
                 storage_cost_pct_per_day,
                 transaction_cost_pct,
                 # Return threshold (percentage)
                 min_return=0.03,                    # 3% minimum return
                 min_net_benefit_pct=0.5,            # 0.5% minimum net benefit
                 # Uncertainty thresholds (CV levels)
                 max_uncertainty_low=0.05,           # CV < 5% = low risk
                 max_uncertainty_medium=0.10,        # CV < 10% = medium risk
                 max_uncertainty_high=0.20,          # CV < 20% = high risk
                 # Trend strength
                 strong_trend_adx=25,
                 # Evaluation day
                 evaluation_day=14,
                 # Batch sizing by risk tier
                 batch_low_risk=0.0,                 # Hold when low risk
                 batch_medium_risk=0.10,             # Small hedge medium risk
                 batch_high_risk=0.25,               # Sell more at high risk
                 batch_very_high_risk=0.35,          # Aggressive at very high risk
                 # Timing
                 cooldown_days=7):

        super().__init__("Risk-Adjusted")

        # Cost parameters
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct

        # PERCENTAGE-based thresholds
        self.min_return = min_return
        self.min_net_benefit_pct = min_net_benefit_pct

        # Uncertainty (risk) thresholds
        self.max_uncertainty_low = max_uncertainty_low
        self.max_uncertainty_medium = max_uncertainty_medium
        self.max_uncertainty_high = max_uncertainty_high

        # Trend
        self.strong_trend_adx = strong_trend_adx

        # Evaluation
        self.evaluation_day = evaluation_day

        # Batch sizing by risk tier
        self.batch_low_risk = batch_low_risk
        self.batch_medium_risk = batch_medium_risk
        self.batch_high_risk = batch_high_risk
        self.batch_very_high_risk = batch_very_high_risk

        self.cooldown_days = cooldown_days
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
                return self._execute_trade(day, inventory, 0.20, 'no_predictions_fallback')
            return {'action': 'HOLD', 'amount': 0, 'reason': 'no_predictions_waiting'}

        batch_size, reason = self._analyze_risk_adjusted_pct(
            current_price, price_history, predictions
        )

        return self._execute_trade(day, inventory, batch_size, reason)

    def _analyze_risk_adjusted_pct(self, current_price, price_history, predictions):
        """Risk-adjusted decision with percentage-based logic"""

        # Evaluate at specific day
        eval_day = min(self.evaluation_day, predictions.shape[1] - 1)
        day_predictions = predictions[:, eval_day]

        # Calculate expected return as percentage
        median_future = np.median(day_predictions)
        expected_return_pct = (median_future - current_price) / current_price

        # Measure uncertainty (risk)
        cv = calculate_prediction_confidence(predictions, eval_day)

        # Calculate net benefit accounting for costs
        days_to_wait = eval_day + 1
        storage_cost_pct = (self.storage_cost_pct_per_day / 100) * days_to_wait
        transaction_cost_pct = self.transaction_cost_pct / 100
        net_benefit_pct = 100 * (expected_return_pct - storage_cost_pct - transaction_cost_pct)

        # Get trend strength
        adx, _, _ = calculate_adx(price_history, period=min(14, len(price_history)-1))

        # Decision based on risk tier and net benefit
        if expected_return_pct >= self.min_return and net_benefit_pct > self.min_net_benefit_pct:
            # Sufficient expected return and net benefit

            if cv < self.max_uncertainty_low and adx > self.strong_trend_adx:
                # Low risk + strong trend: hold all
                batch_size = self.batch_low_risk
                reason = f'low_risk_cv{cv:.2%}_return{expected_return_pct:.2%}_hold'

            elif cv < self.max_uncertainty_medium:
                # Medium risk: small hedge
                batch_size = self.batch_medium_risk
                reason = f'medium_risk_cv{cv:.2%}_return{expected_return_pct:.2%}_small_hedge'

            elif cv < self.max_uncertainty_high:
                # High risk: larger hedge
                batch_size = self.batch_high_risk
                reason = f'high_risk_cv{cv:.2%}_return{expected_return_pct:.2%}_hedge'

            else:
                # Very high risk: sell aggressively
                batch_size = self.batch_very_high_risk
                reason = f'very_high_risk_cv{cv:.2%}_sell'

        else:
            # Insufficient return or negative net benefit
            if net_benefit_pct < 0:
                batch_size = self.batch_very_high_risk
                reason = f'negative_net_benefit_{net_benefit_pct:.2f}%_sell'
            else:
                batch_size = self.batch_high_risk
                reason = f'insufficient_return_{expected_return_pct:.2%}_sell'

        return batch_size, reason

    def _execute_trade(self, day, inventory, batch_size, reason):
        amount = inventory * batch_size
        self.last_sale_day = day
        return {'action': 'SELL', 'amount': amount, 'reason': reason}

    def reset(self):
        super().reset()
        self.last_sale_day = -self.cooldown_days
