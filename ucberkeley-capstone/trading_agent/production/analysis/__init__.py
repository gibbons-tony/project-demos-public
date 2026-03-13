"""
Statistical Analysis Module

Provides statistical validation for trading strategy backtests
"""

from .statistical_tests import (
    test_strategy_vs_baseline,
    bootstrap_confidence_interval,
    run_full_statistical_analysis,
    StatisticalAnalyzer
)

__all__ = [
    'test_strategy_vs_baseline',
    'bootstrap_confidence_interval',
    'run_full_statistical_analysis',
    'StatisticalAnalyzer'
]
