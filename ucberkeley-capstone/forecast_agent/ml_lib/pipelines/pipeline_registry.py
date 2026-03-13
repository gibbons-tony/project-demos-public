"""
Pipeline registry for all forecasting models.

Single source of truth for model configurations.
Uses builder functions for lazy dependency loading.
"""
from pyspark.ml import Pipeline
from typing import Dict, Any, Callable, Tuple


# =============================================================================
# BUILDER FUNCTIONS (Lazy Loading)
# =============================================================================

def build_naive_baseline_pipeline() -> Pipeline:
    """
    Build naive baseline forecaster pipeline.

    Dependencies: pyspark.ml (built-in)

    Features: None (only uses last observed value)
    """
    from ml_lib.models.baseline import NaiveForecaster

    return Pipeline(stages=[
        NaiveForecaster(inputCol="close", horizon=14)
    ])


def build_linear_weather_min_max_pipeline() -> Pipeline:
    """
    Build linear regression with min/max weather aggregations.

    Dependencies: pyspark.ml (built-in)

    Features:
    - Weather min/max (captures extreme events)
    - GDELT sentiment (weighted aggregation)
    - VIX (volatility)
    """
    from ml_lib.transformers.weather_features import WeatherAggregator
    from ml_lib.transformers.sentiment_features import GdeltAggregator
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import LinearRegression

    # Feature columns
    weather_features = [
        'weather_temp_mean_c_min', 'weather_temp_mean_c_max',
        'weather_precipitation_mm_min', 'weather_precipitation_mm_max',
        'weather_humidity_mean_pct_min', 'weather_humidity_mean_pct_max'
    ]

    gdelt_features = [
        'gdelt_tone_avg',
        'gdelt_tone_polarity'
    ]

    other_features = ['vix']

    all_features = weather_features + gdelt_features + other_features

    return Pipeline(stages=[
        WeatherAggregator(inputCol="weather_data", aggregation="min_max"),
        GdeltAggregator(inputCol="gdelt_themes"),
        VectorAssembler(
            inputCols=all_features,
            outputCol="features",
            handleInvalid="skip"
        ),
        LinearRegression(
            featuresCol="features",
            labelCol="close",
            predictionCol="forecast_day_1",  # Will need to expand for 14 days
            regParam=0.0,
            maxIter=100
        )
    ])


def build_linear_weather_all_pipeline() -> Pipeline:
    """
    Build linear regression with all weather aggregations (mean + min/max).

    Dependencies: pyspark.ml (built-in)

    Features:
    - Weather mean, min, max (24 features)
    - GDELT sentiment
    - VIX
    """
    from ml_lib.transformers.weather_features import WeatherAggregator
    from ml_lib.transformers.sentiment_features import GdeltAggregator
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import LinearRegression

    # All weather aggregations
    weather_fields = [
        'temp_mean_c', 'temp_max_c', 'temp_min_c',
        'precipitation_mm', 'rain_mm', 'snowfall_cm',
        'humidity_mean_pct', 'wind_speed_max_kmh'
    ]

    weather_features = []
    for field in weather_fields:
        weather_features.extend([
            f'weather_{field}_avg',
            f'weather_{field}_min',
            f'weather_{field}_max'
        ])

    gdelt_features = ['gdelt_tone_avg', 'gdelt_tone_polarity']
    other_features = ['vix']

    all_features = weather_features + gdelt_features + other_features

    return Pipeline(stages=[
        WeatherAggregator(inputCol="weather_data", aggregation="all"),
        GdeltAggregator(inputCol="gdelt_themes"),
        VectorAssembler(
            inputCols=all_features,
            outputCol="features",
            handleInvalid="skip"
        ),
        LinearRegression(
            featuresCol="features",
            labelCol="close",
            predictionCol="forecast_day_1",
            regParam=0.0,
            maxIter=100
        )
    ])


def build_ridge_top_regions_pipeline() -> Pipeline:
    """
    Build Ridge regression with top coffee producing regions.

    Dependencies: pyspark.ml (built-in)

    Features:
    - Top 6 coffee regions (individual weather data)
    - GDELT sentiment
    - VIX
    """
    from ml_lib.transformers.weather_features import WeatherRegionSelector
    from ml_lib.transformers.sentiment_features import GdeltAggregator
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import LinearRegression

    # Top regions (defaults in WeatherRegionSelector)
    # This will create ~48 features (6 regions × 8 weather fields)
    regions = [
        'Minas_Gerais_Brazil',
        'Sao_Paulo_Brazil',
        'Antioquia_Colombia',
        'Huila_Colombia',
        'Sidamo_Ethiopia',
        'Central_Highlands_Vietnam'
    ]

    # Generate feature column names
    weather_fields = [
        'temp_mean_c', 'temp_max_c', 'temp_min_c',
        'precipitation_mm', 'rain_mm', 'snowfall_cm',
        'humidity_mean_pct', 'wind_speed_max_kmh'
    ]

    weather_features = []
    for region in regions:
        region_clean = region.replace(' ', '_').replace('-', '_')
        for field in weather_fields:
            weather_features.append(f'weather_{region_clean}_{field}')

    gdelt_features = ['gdelt_tone_avg', 'gdelt_tone_polarity']
    other_features = ['vix']

    all_features = weather_features + gdelt_features + other_features

    return Pipeline(stages=[
        WeatherRegionSelector(inputCol="weather_data", regions=regions),
        GdeltAggregator(inputCol="gdelt_themes"),
        VectorAssembler(
            inputCols=all_features,
            outputCol="features",
            handleInvalid="skip"
        ),
        LinearRegression(
            featuresCol="features",
            labelCol="close",
            predictionCol="forecast_day_1",
            regParam=0.1,  # Ridge regularization
            elasticNetParam=0.0,  # Pure L2
            maxIter=100
        )
    ])


# =============================================================================
# PIPELINE REGISTRY
# =============================================================================

PIPELINE_REGISTRY: Dict[str, Dict[str, Any]] = {
    'naive_baseline': {
        'name': 'Naive Baseline',
        'description': 'Forecast = last observed value. Benchmark for comparison.',
        'builder': build_naive_baseline_pipeline,
        'metadata': {
            'horizon': 14,
            'features': [],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['pyspark.ml'],
            'complexity': 'simple',
            'expected_performance': 'baseline'
        }
    },

    'linear_weather_min_max': {
        'name': 'Linear Regression (Weather Min/Max)',
        'description': 'Linear model with extreme weather events (min/max aggregations) + GDELT sentiment',
        'builder': build_linear_weather_min_max_pipeline,
        'metadata': {
            'horizon': 14,
            'features': ['weather_min_max', 'gdelt', 'vix'],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['pyspark.ml'],
            'complexity': 'simple',
            'expected_performance': 'moderate'
        }
    },

    'linear_weather_all': {
        'name': 'Linear Regression (All Weather Aggregations)',
        'description': 'Linear model with mean + min + max weather aggregations (24 weather features)',
        'builder': build_linear_weather_all_pipeline,
        'metadata': {
            'horizon': 14,
            'features': ['weather_all', 'gdelt', 'vix'],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['pyspark.ml'],
            'complexity': 'moderate',
            'expected_performance': 'moderate'
        }
    },

    'ridge_top_regions': {
        'name': 'Ridge Regression (Top Regions)',
        'description': 'Ridge regression with individual weather data from top 6 coffee regions',
        'builder': build_ridge_top_regions_pipeline,
        'metadata': {
            'horizon': 14,
            'features': ['weather_regions', 'gdelt', 'vix'],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['pyspark.ml'],
            'complexity': 'moderate',
            'expected_performance': 'good'
        }
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_pipeline(model_name: str) -> Tuple[Pipeline, Dict[str, Any]]:
    """
    Get pipeline and metadata by name.

    Args:
        model_name: Name from PIPELINE_REGISTRY

    Returns:
        Tuple of (Pipeline, metadata dict)

    Example:
        pipeline, metadata = get_pipeline('linear_weather_min_max')
        print(metadata['description'])
    """
    if model_name not in PIPELINE_REGISTRY:
        available = ', '.join(PIPELINE_REGISTRY.keys())
        raise ValueError(
            f"Model '{model_name}' not found. Available models: {available}"
        )

    config = PIPELINE_REGISTRY[model_name]
    pipeline = config['builder']()  # Call builder function

    return pipeline, config['metadata']


def list_models() -> None:
    """Print all available models with descriptions."""
    print("Available Models:")
    print("=" * 80)

    for model_name, config in PIPELINE_REGISTRY.items():
        print(f"\n{model_name}:")
        print(f"  Name: {config['name']}")
        print(f"  Description: {config['description']}")
        print(f"  Features: {', '.join(config['metadata']['features'])}")
        print(f"  Complexity: {config['metadata']['complexity']}")
        print(f"  Expected Performance: {config['metadata']['expected_performance']}")
