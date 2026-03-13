"""
Parameter Search Space Definitions

Defines the parameter search spaces for all 10 trading strategies.

Extracted from diagnostics/run_diagnostic_16.py with clean, modular structure.
Each strategy has its own search space function that returns parameter suggestions
for Optuna trials.

Usage:
    space_registry = SearchSpaceRegistry()
    params = space_registry.get_search_space(trial, 'consensus')
"""

from typing import Dict, Any
import optuna


class SearchSpaceRegistry:
    """
    Registry of parameter search spaces for all trading strategies.

    Provides centralized, consistent parameter ranges for optimization across
    all 10 strategies (4 baseline + 5 prediction-based + 1 advanced optimization).

    Supports matched pair optimization where base parameters can be fixed
    for predictive strategies to ensure valid comparisons.
    """

    def __init__(self, fixed_base_params: Dict[str, Dict[str, Any]] = None):
        """
        Initialize search space registry.

        Args:
            fixed_base_params: Optional dict mapping strategy names to fixed parameters.
                Example: {'price_threshold': {'threshold_pct': 0.05, ...}}
                Used for matched pair optimization where base params are pre-optimized.
        """
        self.fixed_base_params = fixed_base_params or {}

    @staticmethod
    def immediate_sale(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Immediate Sale strategy.

        Parameters:
            - min_batch_size: Minimum tons to sell per transaction (3.0-10.0)
            - sale_frequency_days: Days between sales (5-14)
        """
        return {
            'min_batch_size': trial.suggest_float('min_batch_size', 3.0, 10.0),
            'sale_frequency_days': trial.suggest_int('sale_frequency_days', 5, 14)
        }

    @staticmethod
    def equal_batch(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Equal Batch strategy.

        Parameters:
            - batch_size: Fraction of inventory to sell per batch (0.15-0.30)
            - frequency_days: Days between batch sales (20-35)
        """
        return {
            'batch_size': trial.suggest_float('batch_size', 0.15, 0.30),
            'frequency_days': trial.suggest_int('frequency_days', 20, 35)
        }

    @staticmethod
    def price_threshold(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Price Threshold strategy.

        Parameters:
            - threshold_pct: Price threshold as % above MA (0.02-0.07)
            - batch_baseline: Baseline batch size (0.20-0.35)
            - batch_overbought_strong: Batch when strongly overbought (0.30-0.40)
            - batch_overbought: Batch when overbought (0.25-0.35)
            - batch_strong_trend: Batch in strong trend (0.15-0.25)
            - rsi_overbought: RSI overbought threshold (65-75)
            - rsi_moderate: RSI moderate threshold (60-70)
            - adx_strong: ADX strong trend threshold (20-30)
            - cooldown_days: Days between trades (5-10)
            - max_days_without_sale: Force sale after X days (45-75)
        """
        return {
            'threshold_pct': trial.suggest_float('threshold_pct', 0.02, 0.07),
            'batch_baseline': trial.suggest_float('batch_baseline', 0.20, 0.35),
            'batch_overbought_strong': trial.suggest_float('batch_overbought_strong', 0.30, 0.40),
            'batch_overbought': trial.suggest_float('batch_overbought', 0.25, 0.35),
            'batch_strong_trend': trial.suggest_float('batch_strong_trend', 0.15, 0.25),
            'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 75),
            'rsi_moderate': trial.suggest_int('rsi_moderate', 60, 70),
            'adx_strong': trial.suggest_int('adx_strong', 20, 30),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 10),
            'max_days_without_sale': trial.suggest_int('max_days_without_sale', 45, 75)
        }

    @staticmethod
    def moving_average(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Moving Average strategy.

        Parameters:
            - ma_period: Moving average window (20-35 days)
            - batch_baseline: Baseline batch size (0.20-0.30)
            - batch_strong_momentum: Batch in strong momentum (0.15-0.25)
            - batch_overbought: Batch when overbought (0.25-0.35)
            - batch_overbought_strong: Batch when strongly overbought (0.30-0.40)
            - rsi_overbought: RSI overbought threshold (65-75)
            - rsi_min: RSI minimum threshold (40-50)
            - adx_strong: ADX strong trend threshold (20-30)
            - adx_weak: ADX weak trend threshold (15-25)
            - cooldown_days: Days between trades (5-10)
            - max_days_without_sale: Force sale after X days (45-75)
        """
        return {
            'ma_period': trial.suggest_int('ma_period', 20, 35),
            'batch_baseline': trial.suggest_float('batch_baseline', 0.20, 0.30),
            'batch_strong_momentum': trial.suggest_float('batch_strong_momentum', 0.15, 0.25),
            'batch_overbought': trial.suggest_float('batch_overbought', 0.25, 0.35),
            'batch_overbought_strong': trial.suggest_float('batch_overbought_strong', 0.30, 0.40),
            'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 75),
            'rsi_min': trial.suggest_int('rsi_min', 40, 50),
            'adx_strong': trial.suggest_int('adx_strong', 20, 30),
            'adx_weak': trial.suggest_int('adx_weak', 15, 25),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 10),
            'max_days_without_sale': trial.suggest_int('max_days_without_sale', 45, 75)
        }

    def price_threshold_predictive(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Price Threshold Predictive strategy.

        Inherits all parameters from price_threshold, plus prediction parameters.

        For matched pair optimization: If fixed_base_params['price_threshold'] is set,
        uses those values instead of sampling new base parameters.

        Additional Parameters:
            - min_net_benefit_pct: Minimum benefit to act on prediction (0.3-1.0%)
            - high_confidence_cv: CV threshold for high confidence (0.03-0.08)
            - scenario_shift_aggressive: Scenario shift for aggressive (1-2)
            - scenario_shift_conservative: Scenario shift for conservative (1-2)
        """
        # Check if we have fixed base parameters for matched pair optimization
        if 'price_threshold' in self.fixed_base_params:
            # Use pre-optimized base parameters (matched pair mode)
            params = self.fixed_base_params['price_threshold'].copy()
            print(f"  [Matched Pair Mode] Using fixed base params from price_threshold optimization")
        else:
            # Sample new base parameters (independent optimization mode)
            params = SearchSpaceRegistry.price_threshold(trial)

        # Add prediction-specific parameters (always optimized)
        params.update({
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'scenario_shift_aggressive': trial.suggest_int('scenario_shift_aggressive', 1, 2),
            'scenario_shift_conservative': trial.suggest_int('scenario_shift_conservative', 1, 2)
        })

        return params

    def moving_average_predictive(self, trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Moving Average Predictive strategy.

        Inherits all parameters from moving_average, plus prediction parameters.

        For matched pair optimization: If fixed_base_params['moving_average'] is set,
        uses those values instead of sampling new base parameters.

        Additional Parameters:
            - min_net_benefit_pct: Minimum benefit to act on prediction (0.3-1.0%)
            - high_confidence_cv: CV threshold for high confidence (0.03-0.08)
            - scenario_shift_aggressive: Scenario shift for aggressive (1-2)
            - scenario_shift_conservative: Scenario shift for conservative (1-2)
        """
        # Check if we have fixed base parameters for matched pair optimization
        if 'moving_average' in self.fixed_base_params:
            # Use pre-optimized base parameters (matched pair mode)
            params = self.fixed_base_params['moving_average'].copy()
            print(f"  [Matched Pair Mode] Using fixed base params from moving_average optimization")
        else:
            # Sample new base parameters (independent optimization mode)
            params = SearchSpaceRegistry.moving_average(trial)

        # Add prediction-specific parameters (always optimized)
        params.update({
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'scenario_shift_aggressive': trial.suggest_int('scenario_shift_aggressive', 1, 2),
            'scenario_shift_conservative': trial.suggest_int('scenario_shift_conservative', 1, 2)
        })

        return params

    @staticmethod
    def expected_value(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Expected Value strategy.

        Parameters:
            - min_net_benefit_pct: Minimum net benefit % to trade (0.3-1.0%)
            - negative_threshold_pct: Negative EV threshold (-0.5 to -0.1%)
            - high_confidence_cv: CV for high confidence (0.03-0.08)
            - medium_confidence_cv: CV for medium confidence (0.10-0.15)
            - strong_trend_adx: ADX for strong trend (20-25)
            - batch_positive_confident: Batch when positive & confident (0.0-0.05)
            - batch_positive_uncertain: Batch when positive & uncertain (0.10-0.20)
            - batch_marginal: Batch when marginal EV (0.15-0.20)
            - batch_negative_mild: Batch when mildly negative (0.25-0.30)
            - batch_negative_strong: Batch when strongly negative (0.35-0.40)
            - cooldown_days: Days between trades (5-7)
            - baseline_batch: Baseline batch size (0.15-0.20)
            - baseline_frequency: Baseline frequency in days (25-30)
        """
        return {
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'negative_threshold_pct': trial.suggest_float('negative_threshold_pct', -0.5, -0.1),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'medium_confidence_cv': trial.suggest_float('medium_confidence_cv', 0.10, 0.15),
            'strong_trend_adx': trial.suggest_int('strong_trend_adx', 20, 25),
            'batch_positive_confident': trial.suggest_float('batch_positive_confident', 0.0, 0.05),
            'batch_positive_uncertain': trial.suggest_float('batch_positive_uncertain', 0.10, 0.20),
            'batch_marginal': trial.suggest_float('batch_marginal', 0.15, 0.20),
            'batch_negative_mild': trial.suggest_float('batch_negative_mild', 0.25, 0.30),
            'batch_negative_strong': trial.suggest_float('batch_negative_strong', 0.35, 0.40),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7),
            'baseline_batch': trial.suggest_float('baseline_batch', 0.15, 0.20),
            'baseline_frequency': trial.suggest_int('baseline_frequency', 25, 30)
        }

    @staticmethod
    def consensus(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Consensus strategy.

        Parameters:
            - consensus_threshold: Main consensus threshold (0.60-0.75)
            - very_strong_consensus: Very strong consensus (0.80-0.85)
            - moderate_consensus: Moderate consensus (0.55-0.60)
            - min_return: Minimum required return (0.02-0.05)
            - min_net_benefit_pct: Minimum net benefit % (0.3-0.7%)
            - high_confidence_cv: CV for high confidence (0.03-0.08)
            - batch_strong_consensus: Batch when strong consensus (0.0-0.05)
            - batch_moderate: Batch when moderate (0.10-0.20)
            - batch_weak: Batch when weak (0.25-0.30)
            - batch_bearish: Batch when bearish (0.35-0.40)
            - evaluation_day: Day ahead to evaluate (10-14)
            - cooldown_days: Days between trades (5-7)
        """
        return {
            'consensus_threshold': trial.suggest_float('consensus_threshold', 0.60, 0.75),
            'very_strong_consensus': trial.suggest_float('very_strong_consensus', 0.80, 0.85),
            'moderate_consensus': trial.suggest_float('moderate_consensus', 0.55, 0.60),
            'min_return': trial.suggest_float('min_return', 0.02, 0.05),
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 0.7),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'batch_strong_consensus': trial.suggest_float('batch_strong_consensus', 0.0, 0.05),
            'batch_moderate': trial.suggest_float('batch_moderate', 0.10, 0.20),
            'batch_weak': trial.suggest_float('batch_weak', 0.25, 0.30),
            'batch_bearish': trial.suggest_float('batch_bearish', 0.35, 0.40),
            'evaluation_day': trial.suggest_int('evaluation_day', 10, 14),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7)
        }

    @staticmethod
    def risk_adjusted(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Risk-Adjusted strategy.

        Parameters:
            - min_return: Minimum required return (0.02-0.05)
            - min_net_benefit_pct: Minimum net benefit % (0.3-0.7%)
            - max_uncertainty_low: Max CV for low risk (0.03-0.08)
            - max_uncertainty_medium: Max CV for medium risk (0.10-0.20)
            - max_uncertainty_high: Max CV for high risk (0.25-0.35)
            - strong_trend_adx: ADX for strong trend (20-25)
            - batch_low_risk: Batch when low risk (0.0-0.05)
            - batch_medium_risk: Batch when medium risk (0.10-0.15)
            - batch_high_risk: Batch when high risk (0.25-0.30)
            - batch_very_high_risk: Batch when very high risk (0.35-0.40)
            - evaluation_day: Day ahead to evaluate (10-14)
            - cooldown_days: Days between trades (5-7)
        """
        return {
            'min_return': trial.suggest_float('min_return', 0.02, 0.05),
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 0.7),
            'max_uncertainty_low': trial.suggest_float('max_uncertainty_low', 0.03, 0.08),
            'max_uncertainty_medium': trial.suggest_float('max_uncertainty_medium', 0.10, 0.20),
            'max_uncertainty_high': trial.suggest_float('max_uncertainty_high', 0.25, 0.35),
            'strong_trend_adx': trial.suggest_int('strong_trend_adx', 20, 25),
            'batch_low_risk': trial.suggest_float('batch_low_risk', 0.0, 0.05),
            'batch_medium_risk': trial.suggest_float('batch_medium_risk', 0.10, 0.15),
            'batch_high_risk': trial.suggest_float('batch_high_risk', 0.25, 0.30),
            'batch_very_high_risk': trial.suggest_float('batch_very_high_risk', 0.35, 0.40),
            'evaluation_day': trial.suggest_int('evaluation_day', 10, 14),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7)
        }

    @staticmethod
    def rolling_horizon_mpc(trial: optuna.Trial) -> Dict[str, Any]:
        """
        Search space for Rolling Horizon MPC strategy.

        Parameters:
            - horizon_days: Forecast horizon window (7-21 days)
            - terminal_value_decay: Discount factor for terminal inventory (0.85-0.99)
            - shadow_price_smoothing: Exponential smoothing alpha for shadow prices (0.1-0.5 or None)
        """
        # Shadow price smoothing: randomly decide if we use it (50% chance)
        use_shadow_price = trial.suggest_categorical('use_shadow_price', [True, False])

        params = {
            'horizon_days': trial.suggest_int('horizon_days', 7, 21),
            'terminal_value_decay': trial.suggest_float('terminal_value_decay', 0.85, 0.99)
        }

        if use_shadow_price:
            params['shadow_price_smoothing'] = trial.suggest_float('shadow_price_smoothing', 0.1, 0.5)
        else:
            params['shadow_price_smoothing'] = None

        return params

    def get_search_space(self, trial: optuna.Trial, strategy_name: str) -> Dict[str, Any]:
        """
        Get search space for a strategy by name.

        Args:
            trial: Optuna trial object
            strategy_name: Name of strategy (e.g., 'consensus', 'price_threshold')

        Returns:
            Dict of parameter_name -> value

        Raises:
            ValueError: If strategy_name is unknown
        """
        # Static methods (no fixed base params needed)
        static_strategies = {
            'immediate_sale': SearchSpaceRegistry.immediate_sale,
            'equal_batch': SearchSpaceRegistry.equal_batch,
            'price_threshold': SearchSpaceRegistry.price_threshold,
            'moving_average': SearchSpaceRegistry.moving_average,
            'expected_value': SearchSpaceRegistry.expected_value,
            'consensus': SearchSpaceRegistry.consensus,
            'risk_adjusted': SearchSpaceRegistry.risk_adjusted,
            'rolling_horizon_mpc': SearchSpaceRegistry.rolling_horizon_mpc
        }

        # Instance methods (support fixed base params for matched pairs)
        instance_strategies = {
            'price_threshold_predictive': self.price_threshold_predictive,
            'moving_average_predictive': self.moving_average_predictive
        }

        if strategy_name in static_strategies:
            return static_strategies[strategy_name](trial)
        elif strategy_name in instance_strategies:
            return instance_strategies[strategy_name](trial)
        else:
            raise ValueError(
                f"Unknown strategy: {strategy_name}. "
                f"Available: {list(static_strategies.keys()) + list(instance_strategies.keys())}"
            )

    @classmethod
    def get_available_strategies(cls) -> list:
        """
        Get list of all available strategy names.

        Returns:
            List of strategy names
        """
        return [
            'immediate_sale',
            'equal_batch',
            'price_threshold',
            'moving_average',
            'price_threshold_predictive',
            'moving_average_predictive',
            'expected_value',
            'consensus',
            'risk_adjusted',
            'rolling_horizon_mpc'
        ]
