"""
Shared Test Fixtures for Runners Module
Provides reusable test data and mock objects
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import tempfile
import shutil


@pytest.fixture
def sample_prices():
    """
    Generate 100 days of sample price data

    Returns:
        DataFrame with columns ['date', 'price']
    """
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    # Generate realistic price movement (random walk with drift)
    prices = 100 + np.cumsum(np.random.normal(0.5, 2, 100))

    return pd.DataFrame({
        'date': dates,
        'price': prices
    })


@pytest.fixture
def sample_predictions():
    """
    Generate sample prediction matrices for 10 dates

    Returns:
        Dict mapping {timestamp: numpy_array(100 runs, 14 horizons)}
    """
    dates = pd.date_range('2024-01-10', periods=10, freq='D')

    prediction_matrices = {}
    for date in dates:
        # 100 runs × 14 day horizons
        # Generate predictions around base price with noise
        base_price = 100
        predictions = base_price + np.random.normal(0, 10, (100, 14))
        prediction_matrices[pd.Timestamp(date)] = predictions

    return prediction_matrices


@pytest.fixture
def minimal_predictions():
    """
    Minimal prediction matrix for quick tests (3 dates, 10 runs, 14 horizons)

    Returns:
        Dict mapping {timestamp: numpy_array(10 runs, 14 horizons)}
    """
    dates = pd.date_range('2024-01-10', periods=3, freq='D')

    return {
        pd.Timestamp(date): np.random.uniform(90, 110, (10, 14))
        for date in dates
    }


@pytest.fixture
def commodity_config():
    """
    Sample commodity configuration (coffee)

    Returns:
        Dict with commodity parameters
    """
    return {
        'commodity': 'coffee',
        'harvest_volume': 50,
        'harvest_windows': [(5, 9)],  # May-September
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01,
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365
    }


@pytest.fixture
def baseline_params():
    """
    Baseline strategy parameters

    Returns:
        Dict with baseline strategy configs
    """
    return {
        'equal_batch': {
            'batch_size': 0.25,
            'frequency_days': 30
        },
        'price_threshold': {
            'threshold_pct': 0.05
        },
        'moving_average': {
            'ma_period': 30
        }
    }


@pytest.fixture
def prediction_params():
    """
    Prediction strategy parameters

    Returns:
        Dict with prediction strategy configs
    """
    return {
        'consensus': {
            'consensus_threshold': 0.70,
            'min_return': 0.03,
            'evaluation_day': 14
        },
        'expected_value': {
            'min_ev_improvement': 50,
            'baseline_batch': 0.15,
            'baseline_frequency': 10
        },
        'risk_adjusted': {
            'min_return': 0.03,
            'max_uncertainty': 0.35,
            'consensus_threshold': 0.60,
            'evaluation_day': 14
        }
    }


@pytest.fixture
def mock_spark():
    """
    Mock Spark session for testing

    Returns:
        MagicMock with basic Spark functionality
    """
    spark = MagicMock()

    # Mock table method to return DataFrames
    def mock_table(table_name):
        mock_df = MagicMock()
        mock_df.toPandas.return_value = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'price': np.random.uniform(90, 110, 100)
        })
        return mock_df

    spark.table = MagicMock(side_effect=mock_table)

    # Mock createDataFrame
    def mock_create_dataframe(pandas_df):
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        return mock_sdf

    spark.createDataFrame = MagicMock(side_effect=mock_create_dataframe)

    return spark


@pytest.fixture
def temp_volume():
    """
    Temporary directory for volume operations

    Yields:
        Path to temporary directory

    Cleanup:
        Removes directory after test
    """
    temp_dir = tempfile.mkdtemp(prefix='test_volume_')
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_data_paths(temp_volume):
    """
    Generate sample data paths using temp directory

    Args:
        temp_volume: Temporary directory fixture

    Returns:
        Dict with data paths
    """
    return {
        'prices_prepared': 'test.prices_coffee',
        'prediction_matrices': f'{temp_volume}/prediction_matrices_coffee_test.pkl',
        'prediction_matrices_real': f'{temp_volume}/prediction_matrices_coffee_test_real.pkl',
        'results': 'test.results_coffee_test',
        'results_detailed': f'{temp_volume}/results_detailed_coffee_test.pkl'
    }


@pytest.fixture
def sample_results_dict():
    """
    Sample results dictionary from strategy execution

    Returns:
        Dict with mock strategy results
    """
    # Create sample trades
    sample_trades = [
        {
            'day': 10,
            'date': pd.Timestamp('2024-01-10'),
            'price': 105.0,
            'price_per_ton': 2100.0,
            'amount': 10.0,
            'revenue': 21000.0,
            'transaction_cost': 2.1,
            'net_revenue': 20997.9,
            'reason': 'price_threshold_triggered'
        },
        {
            'day': 40,
            'date': pd.Timestamp('2024-02-09'),
            'price': 110.0,
            'price_per_ton': 2200.0,
            'amount': 15.0,
            'revenue': 33000.0,
            'transaction_cost': 3.3,
            'net_revenue': 32996.7,
            'reason': 'moving_average_crossover'
        }
    ]

    # Create daily state
    daily_state = pd.DataFrame({
        'day': range(100),
        'date': pd.date_range('2024-01-01', periods=100),
        'inventory': 50 - np.cumsum([0.25 if i % 10 == 0 else 0 for i in range(100)]),
        'daily_storage_cost': np.random.uniform(0.5, 2.0, 100)
    })

    return {
        'Strategy A': {
            'strategy_name': 'Strategy A',
            'trades': sample_trades,
            'daily_state': daily_state,
            'total_revenue': 54000.0,
            'total_transaction_costs': 5.4,
            'total_storage_costs': 150.0,
            'net_earnings': 53844.6
        },
        'Strategy B': {
            'strategy_name': 'Strategy B',
            'trades': sample_trades[:1],  # Fewer trades
            'daily_state': daily_state,
            'total_revenue': 21000.0,
            'total_transaction_costs': 2.1,
            'total_storage_costs': 200.0,
            'net_earnings': 20797.9
        }
    }


@pytest.fixture
def sample_metrics_df():
    """
    Sample metrics DataFrame

    Returns:
        DataFrame with strategy metrics
    """
    return pd.DataFrame({
        'strategy': ['Strategy A', 'Strategy B', 'Strategy C'],
        'net_earnings': [53844.6, 20797.9, 45000.0],
        'total_revenue': [54000.0, 21000.0, 45500.0],
        'total_costs': [155.4, 202.1, 500.0],
        'transaction_costs': [5.4, 2.1, 4.5],
        'storage_costs': [150.0, 200.0, 495.5],
        'avg_sale_price': [108.0, 105.0, 107.5],
        'n_trades': [2, 1, 3],
        'type': ['Prediction', 'Baseline', 'Prediction'],
        'commodity': ['coffee', 'coffee', 'coffee'],
        'model_version': ['test_v1', 'test_v1', 'test_v1']
    })


# Utility functions for tests
def assert_dataframe_columns(df, required_columns):
    """Assert DataFrame has required columns"""
    missing = set(required_columns) - set(df.columns)
    assert len(missing) == 0, f"Missing columns: {missing}"


def assert_numeric_close(actual, expected, tolerance=0.01):
    """Assert numeric values are close within tolerance"""
    assert abs(actual - expected) / abs(expected) < tolerance, \
        f"Values not close: {actual} vs {expected} (tolerance={tolerance})"
