"""
Analysis Module for Trading Agent

This module provides functions to run backtest analysis across
multiple commodities and forecast models.
"""

from .model_runner import (
    run_analysis_for_model,
    run_analysis_for_all_models,
    run_analysis_for_all_commodities,
    compare_model_performance
)

__all__ = [
    'run_analysis_for_model',
    'run_analysis_for_all_models',
    'run_analysis_for_all_commodities',
    'compare_model_performance'
]
