"""
Production Strategy Implementations
Extracted from diagnostics/all_strategies_pct.py (improved version)

**Complete Strategy Suite:**
- 4 Baseline strategies
- 5 Prediction strategies
- 1 Advanced optimization strategy (Rolling Horizon MPC)
- Technical indicators

Note: Theoretical maximum calculation done via LP optimizer
(see strategies/lp_optimizer.py, not a Strategy class)
"""

from .base import Strategy
from .baseline import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy
)
from .prediction import (
    PriceThresholdPredictive,
    MovingAveragePredictive,
    ExpectedValueStrategy,
    ConsensusStrategy,
    RiskAdjustedStrategy
)
from .rolling_horizon_mpc import RollingHorizonMPC
from .indicators import (
    calculate_rsi,
    calculate_adx,
    calculate_prediction_confidence
)

# Strategy names for statistical testing
STRATEGY_NAMES = [
    'Immediate Sale',
    'Equal Batches',
    'Price Threshold',
    'Moving Average',
    'Price Threshold Predictive',
    'Moving Average Predictive',
    'Expected Value',
    'Consensus',
    'Risk-Adjusted',
    'RollingHorizonMPC'
]

__all__ = [
    # Base
    'Strategy',

    # Baseline strategies (4)
    'ImmediateSaleStrategy',
    'EqualBatchStrategy',
    'PriceThresholdStrategy',
    'MovingAverageStrategy',

    # Prediction strategies (5)
    'PriceThresholdPredictive',
    'MovingAveragePredictive',
    'ExpectedValueStrategy',
    'ConsensusStrategy',
    'RiskAdjustedStrategy',

    # Advanced strategies (limited foresight optimization)
    'RollingHorizonMPC',

    # Indicators
    'calculate_rsi',
    'calculate_adx',
    'calculate_prediction_confidence',

    # Strategy names
    'STRATEGY_NAMES'
]
