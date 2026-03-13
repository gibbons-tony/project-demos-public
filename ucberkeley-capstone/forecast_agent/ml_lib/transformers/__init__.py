"""
ML transformers for feature engineering and imputation.

Available transformers:
- WeatherAggregator: Aggregate weather_data arrays (min/max/mean strategies)
- WeatherRegionExpander: Expand weather into per-region columns
- WeatherRegionSelector: Expand weather for selected regions only
- ImputationTransformer: Impute NULLs with time-series aware strategies
"""
from forecast_agent.ml_lib.transformers.weather_features import (
    WeatherAggregator,
    WeatherRegionExpander,
    WeatherRegionSelector
)
from forecast_agent.ml_lib.transformers.imputation import (
    ImputationTransformer,
    create_production_imputer,
    get_default_imputation_config,
    get_gdelt_date_conditional_config
)

__all__ = [
    # Weather transformers
    'WeatherAggregator',
    'WeatherRegionExpander',
    'WeatherRegionSelector',

    # Imputation
    'ImputationTransformer',
    'create_production_imputer',
    'get_default_imputation_config',
    'get_gdelt_date_conditional_config',
]
