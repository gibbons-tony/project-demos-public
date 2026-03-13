"""
Data Access Layer for Trading Agent

This module provides functions to load forecast data from Databricks Unity Catalog.
"""

from .forecast_loader import (
    get_available_models,
    get_available_commodities,
    load_forecast_distributions,
    load_forecast_distributions_all_models,
    transform_to_prediction_matrices,
    load_actuals_from_distributions
)

__all__ = [
    'get_available_models',
    'get_available_commodities',
    'load_forecast_distributions',
    'load_forecast_distributions_all_models',
    'transform_to_prediction_matrices',
    'load_actuals_from_distributions'
]
