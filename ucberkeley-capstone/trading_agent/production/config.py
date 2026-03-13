"""
Production Configuration
Central configuration for production trading agent system
Uses updated costs from diagnostic research
"""

import pandas as pd
import os

# =============================================================================
# COMMODITY CONFIGURATIONS
# =============================================================================

COMMODITY_CONFIGS = {
    'coffee': {
        'commodity': 'coffee',
        'harvest_volume': 50,  # tons per year
        'harvest_windows': [(5, 9)],  # May-September
        'storage_cost_pct_per_day': 0.005,   # 0.005% per day (updated from research)
        'transaction_cost_pct': 0.01,        # 0.01% per transaction (updated from research)
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365
    },
    'sugar': {
        'commodity': 'sugar',
        'harvest_volume': 50,
        'harvest_windows': [(10, 12)],  # October-December
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01,
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365
    }
}

# =============================================================================
# STRATEGY PARAMETERS
# =============================================================================

# Baseline strategy parameters (no predictions)
BASELINE_PARAMS = {
    'immediate_sale': {},  # No parameters

    'equal_batch': {
        'batch_size': 0.25,  # Sell in 4 equal batches (25% each)
        'frequency_days': 30  # 30 days between batches
    },

    'price_threshold': {
        'threshold_pct': 0.05  # Sell when price > current + 5%
    },

    'moving_average': {
        'ma_period': 30  # 30-day moving average for crossover
    }
}

# Prediction-based strategy parameters
PREDICTION_PARAMS = {
    'consensus': {
        'storage_cost_pct_per_day': 0.005,  # 0.005% per day (matches commodity config)
        'transaction_cost_pct': 0.01,       # 0.01% per transaction (matches commodity config)
        'consensus_threshold': 0.70,        # 70% agreement to act
        'evaluation_day': 14                # Evaluate at 14-day horizon
    },

    'expected_value': {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01,
        'min_net_benefit_pct': 0.5          # 0.5% minimum net benefit
    },

    'risk_adjusted': {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01,
        'min_return': 0.03,                 # 3% minimum return
        'max_uncertainty_low': 0.05,        # CV < 5% = low risk
        'max_uncertainty_medium': 0.10,     # CV < 10% = medium risk
        'max_uncertainty_high': 0.20        # CV < 20% = high risk
    },

    'price_threshold_predictive': {
        'threshold_pct': 0.05,              # Match PriceThreshold baseline
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    },

    'moving_average_predictive': {
        'ma_period': 30,                    # Match MovingAverage baseline
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    },

    'rolling_horizon_mpc': {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01,
        'horizon_days': 14,                 # 14-day forecast horizon
        'terminal_value_decay': 0.95,       # Discount factor for terminal inventory
        'shadow_price_smoothing': None      # None = simple terminal value (or float 0.1-0.5 for smoothing)
    }
}

# =============================================================================
# DATA PATHS AND TABLES
# =============================================================================

# Unity Catalog paths
OUTPUT_SCHEMA = "commodity.trading_agent"
MARKET_TABLE = "commodity.silver.unified_data"
FORECAST_TABLE = "commodity.forecast.distributions"

# File storage paths - using /dbfs/ prefix for Python file I/O on Databricks
VOLUME_PATH = "/dbfs/production/files"

# =============================================================================
# ANALYSIS CONFIGURATION
# =============================================================================

ANALYSIS_CONFIG = {
    'backtest_start_date': '2022-01-01',  # Start of backtest period
    'synthetic_accuracies': [0.6, 0.7, 0.8, 0.9, 1.0],  # Synthetic accuracy levels
    'n_monte_carlo_runs': 2000,  # Number of Monte Carlo paths
    'forecast_horizon': 14,  # Days ahead to forecast
    'validation_metrics': ['mape', 'rmse', 'mae']  # Metrics for validation
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_model_versions(commodity, spark_session=None):
    """
    Discover available model versions for a commodity from forecast table

    Args:
        commodity: Commodity name (e.g., 'coffee')
        spark_session: SparkSession (optional, will create if not provided)

    Returns:
        list: List of model versions available
    """
    if spark_session is None:
        from pyspark.sql import SparkSession
        spark_session = SparkSession.builder.getOrCreate()

    query = f"""
    SELECT DISTINCT model_version
    FROM {FORECAST_TABLE}
    WHERE commodity = '{commodity.capitalize()}'
    AND is_actuals = FALSE
    ORDER BY model_version
    """

    result_df = spark_session.sql(query).toPandas()

    return result_df['model_version'].tolist()


def load_forecast_data(commodity, model_version, spark_session=None):
    """
    Load forecast prediction data from table for a specific commodity and model

    Args:
        commodity: Commodity name (e.g., 'coffee')
        model_version: Model version (e.g., 'arima_v1')
        spark_session: SparkSession (optional, will create if not provided)

    Returns:
        pd.DataFrame: Wide-format DataFrame with columns:
            - forecast_start_date
            - run_id
            - day_1, day_2, ..., day_14 (predicted prices)
    """
    if spark_session is None:
        from pyspark.sql import SparkSession
        spark_session = SparkSession.builder.getOrCreate()

    # Query to get predictions in wide format
    # Note: Table already has day_1 through day_14 columns, and uses path_id not run_id
    query = f"""
    SELECT
        forecast_start_date,
        path_id as run_id,
        day_1,
        day_2,
        day_3,
        day_4,
        day_5,
        day_6,
        day_7,
        day_8,
        day_9,
        day_10,
        day_11,
        day_12,
        day_13,
        day_14
    FROM {FORECAST_TABLE}
    WHERE commodity = '{commodity.capitalize()}'
        AND model_version = '{model_version}'
        AND is_actuals = FALSE
    ORDER BY forecast_start_date, path_id
    """

    spark_df = spark_session.sql(query)
    predictions_wide = spark_df.toPandas()

    return predictions_wide


def get_data_paths(commodity, model_version):
    """
    Get file paths for a commodity and model version

    Args:
        commodity: Commodity name (e.g., 'coffee')
        model_version: Model version (e.g., 'arima_v1')

    Returns:
        dict: Dictionary of file paths
    """
    return {
        'prediction_matrices_real': f"{VOLUME_PATH}/prediction_matrices_{commodity.lower()}_{model_version}_real.pkl"
    }


def load_price_data(commodity, start_date=None, spark_session=None):
    """
    Load historical price data for a commodity

    Args:
        commodity: Commodity name (e.g., 'coffee')
        start_date: Start date for prices (YYYY-MM-DD), None for all data
        spark_session: SparkSession (optional, will create if not provided)

    Returns:
        pd.DataFrame: DataFrame with columns 'date' and 'price'
    """
    if spark_session is None:
        from pyspark.sql import SparkSession
        spark_session = SparkSession.builder.getOrCreate()

    where_clause = f"WHERE commodity = '{commodity}'"
    if start_date:
        where_clause += f" AND date >= '{start_date}'"

    query = f"""
    SELECT date, price
    FROM {MARKET_TABLE}
    {where_clause}
    ORDER BY date
    """

    spark_df = spark_session.sql(query)
    prices_df = spark_df.toPandas()
    prices_df['date'] = pd.to_datetime(prices_df['date'])

    return prices_df


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'COMMODITY_CONFIGS',
    'BASELINE_PARAMS',
    'PREDICTION_PARAMS',
    'OUTPUT_SCHEMA',
    'MARKET_TABLE',
    'FORECAST_TABLE',
    'VOLUME_PATH',
    'ANALYSIS_CONFIG',
    'get_data_paths',
    'get_model_versions',
    'load_forecast_data',
    'load_price_data'
]
