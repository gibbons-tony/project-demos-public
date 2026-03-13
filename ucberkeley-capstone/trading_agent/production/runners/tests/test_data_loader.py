"""
Unit Tests for DataLoader Module
Tests data loading, validation, and model discovery
"""

import pytest
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from unittest.mock import MagicMock, patch
import os

from production.runners.data_loader import DataLoader


class TestDataLoaderBasic:
    """Basic functionality tests"""

    def test_initialization(self, mock_spark):
        """Test DataLoader initializes correctly"""
        loader = DataLoader(spark=mock_spark)
        assert loader.spark is not None
        assert loader.spark == mock_spark

    def test_initialization_without_spark(self):
        """Test DataLoader requires Spark session"""
        with pytest.raises(ValueError, match="Spark session required"):
            DataLoader(spark=None)


class TestLoadPrices:
    """Test price data loading from Delta tables"""

    def test_load_prices_from_delta(self, mock_spark, sample_prices):
        """Test loading prices from Delta table"""
        # Setup mock
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        loader = DataLoader(spark=mock_spark)
        data_paths = {'prices_prepared': 'test.prices_coffee'}

        prices = loader._load_prices(data_paths)

        # Verify
        assert isinstance(prices, pd.DataFrame)
        assert len(prices) == 100
        assert 'date' in prices.columns
        assert 'price' in prices.columns
        mock_spark.table.assert_called_once_with('test.prices_coffee')

    def test_load_prices_validates_columns(self, mock_spark):
        """Test price loading validates required columns"""
        # Mock DataFrame missing 'price' column
        bad_df = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'wrong_column': np.random.uniform(100, 110, 10)
        })

        mock_df = MagicMock()
        mock_df.toPandas.return_value = bad_df
        mock_spark.table.return_value = mock_df

        loader = DataLoader(spark=mock_spark)
        data_paths = {'prices_prepared': 'test.prices_coffee'}

        with pytest.raises(ValueError, match="Missing required columns"):
            loader._load_prices(data_paths)

    def test_load_prices_handles_missing_table(self, mock_spark):
        """Test graceful handling of missing Delta table"""
        mock_spark.table.side_effect = Exception("Table not found")

        loader = DataLoader(spark=mock_spark)
        data_paths = {'prices_prepared': 'test.nonexistent_table'}

        with pytest.raises(ValueError, match="Failed to load prices"):
            loader._load_prices(data_paths)


class TestLoadPredictionMatrices:
    """Test prediction matrix loading from pickle files"""

    def test_load_prediction_matrices(self, sample_predictions, temp_volume):
        """Test loading prediction matrices from pickle"""
        # Save sample predictions to pickle
        pickle_path = os.path.join(temp_volume, 'predictions.pkl')
        with open(pickle_path, 'wb') as f:
            pickle.dump(sample_predictions, f)

        loader = DataLoader(spark=MagicMock())
        data_paths = {'prediction_matrices': pickle_path}

        matrices = loader._load_prediction_matrices('test_model', data_paths)

        # Verify
        assert isinstance(matrices, dict)
        assert len(matrices) == 10  # 10 dates

        # Check structure
        first_key = list(matrices.keys())[0]
        assert isinstance(first_key, pd.Timestamp)
        assert matrices[first_key].shape == (100, 14)  # 100 runs, 14 horizons

    def test_load_prediction_matrices_validates_structure(self, temp_volume):
        """Test prediction matrix validation"""
        # Create invalid structure (wrong dimensions)
        bad_matrices = {
            pd.Timestamp('2024-01-10'): np.random.uniform(90, 110, (100,))  # Missing horizons dimension
        }

        pickle_path = os.path.join(temp_volume, 'bad_predictions.pkl')
        with open(pickle_path, 'wb') as f:
            pickle.dump(bad_matrices, f)

        loader = DataLoader(spark=MagicMock())
        data_paths = {'prediction_matrices': pickle_path}

        with pytest.raises(ValueError, match="Invalid prediction matrix shape"):
            loader._load_prediction_matrices('test_model', data_paths)

    def test_load_prediction_matrices_handles_missing_file(self, temp_volume):
        """Test graceful handling of missing pickle file"""
        loader = DataLoader(spark=MagicMock())
        data_paths = {'prediction_matrices': '/nonexistent/path/predictions.pkl'}

        with pytest.raises(ValueError, match="Failed to load prediction matrices"):
            loader._load_prediction_matrices('test_model', data_paths)

    def test_load_prediction_matrices_handles_corrupted_file(self, temp_volume):
        """Test handling of corrupted pickle file"""
        # Create corrupted file
        pickle_path = os.path.join(temp_volume, 'corrupted.pkl')
        with open(pickle_path, 'w') as f:
            f.write("This is not a valid pickle file")

        loader = DataLoader(spark=MagicMock())
        data_paths = {'prediction_matrices': pickle_path}

        with pytest.raises(ValueError, match="Failed to load prediction matrices"):
            loader._load_prediction_matrices('test_model', data_paths)


class TestDataValidation:
    """Test data quality validation"""

    def test_validate_data_alignment_success(self, mock_spark, sample_prices, sample_predictions):
        """Test validation passes with properly aligned data"""
        loader = DataLoader(spark=mock_spark)

        # Should not raise exception
        loader._validate_data(sample_prices, sample_predictions, 'test_model')

    def test_validate_data_detects_no_overlap(self, mock_spark):
        """Test validation detects completely misaligned dates"""
        # Prices from Jan 2024
        prices = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'price': np.random.uniform(100, 110, 100)
        })

        # Predictions from Jan 2025 (no overlap)
        predictions = {
            pd.Timestamp('2025-01-10'): np.random.uniform(90, 110, (100, 14))
        }

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Insufficient date overlap"):
            loader._validate_data(prices, predictions, 'test_model')

    def test_validate_data_detects_poor_overlap(self, mock_spark):
        """Test validation detects insufficient overlap (< 50%)"""
        # 100 days of prices
        prices = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'price': np.random.uniform(100, 110, 100)
        })

        # Only 2 prediction dates overlap (< 50% of 10 dates)
        predictions = {
            pd.Timestamp('2024-01-10'): np.random.uniform(90, 110, (100, 14)),
            pd.Timestamp('2024-01-15'): np.random.uniform(90, 110, (100, 14)),
            pd.Timestamp('2025-02-01'): np.random.uniform(90, 110, (100, 14)),
            pd.Timestamp('2025-02-05'): np.random.uniform(90, 110, (100, 14))
        }

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Insufficient date overlap"):
            loader._validate_data(prices, predictions, 'test_model')

    def test_validate_data_detects_empty_prices(self, mock_spark, sample_predictions):
        """Test validation detects empty price DataFrame"""
        empty_prices = pd.DataFrame(columns=['date', 'price'])

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Prices DataFrame is empty"):
            loader._validate_data(empty_prices, sample_predictions, 'test_model')

    def test_validate_data_detects_empty_predictions(self, mock_spark, sample_prices):
        """Test validation detects empty prediction matrices"""
        empty_predictions = {}

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Prediction matrices are empty"):
            loader._validate_data(sample_prices, empty_predictions, 'test_model')


class TestFullDataLoad:
    """Test complete data loading workflow"""

    def test_load_commodity_data_success(self, mock_spark, sample_prices,
                                          sample_predictions, temp_volume,
                                          sample_data_paths):
        """Test successful end-to-end data loading"""
        # Setup mocks
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Save predictions to pickle
        pickle_path = sample_data_paths['prediction_matrices']
        os.makedirs(os.path.dirname(pickle_path), exist_ok=True)
        with open(pickle_path, 'wb') as f:
            pickle.dump(sample_predictions, f)

        loader = DataLoader(spark=mock_spark)

        prices, matrices = loader.load_commodity_data(
            commodity='coffee',
            model_version='test_model',
            data_paths=sample_data_paths
        )

        # Verify outputs
        assert isinstance(prices, pd.DataFrame)
        assert isinstance(matrices, dict)
        assert len(prices) == 100
        assert len(matrices) == 10

    def test_load_commodity_data_with_verbose(self, mock_spark, sample_prices,
                                               sample_predictions, temp_volume,
                                               sample_data_paths, capsys):
        """Test verbose logging during data load"""
        # Setup mocks
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Save predictions
        pickle_path = sample_data_paths['prediction_matrices']
        os.makedirs(os.path.dirname(pickle_path), exist_ok=True)
        with open(pickle_path, 'wb') as f:
            pickle.dump(sample_predictions, f)

        loader = DataLoader(spark=mock_spark)

        loader.load_commodity_data(
            commodity='coffee',
            model_version='test_model',
            data_paths=sample_data_paths,
            verbose=True
        )

        captured = capsys.readouterr()
        assert "Loading data for coffee" in captured.out
        assert "Successfully loaded" in captured.out


class TestModelVersionDiscovery:
    """Test model version discovery functionality"""

    def test_discover_model_versions_synthetic(self, mock_spark):
        """Test discovery of synthetic model versions"""
        # Mock query result
        mock_result = pd.DataFrame({
            'model_version': ['synthetic_90pct', 'synthetic_80pct', 'synthetic_70pct']
        })

        mock_df = MagicMock()
        mock_df.toPandas.return_value = mock_result
        mock_spark.sql.return_value = mock_df

        loader = DataLoader(spark=mock_spark)

        synthetic, real = loader.discover_model_versions('coffee')

        assert len(synthetic) == 3
        assert 'synthetic_90pct' in synthetic
        assert 'synthetic_80pct' in synthetic
        assert len(real) == 0

    def test_discover_model_versions_real(self, mock_spark):
        """Test discovery of real model versions"""
        # Mock query result with real versions
        mock_result = pd.DataFrame({
            'model_version': ['real_xgboost_v1', 'real_lstm_v2']
        })

        mock_df = MagicMock()
        mock_df.toPandas.return_value = mock_result
        mock_spark.sql.return_value = mock_df

        loader = DataLoader(spark=mock_spark)

        synthetic, real = loader.discover_model_versions('coffee')

        assert len(synthetic) == 0
        assert len(real) == 2
        assert 'real_xgboost_v1' in real
        assert 'real_lstm_v2' in real

    def test_discover_model_versions_mixed(self, mock_spark):
        """Test discovery of mixed synthetic and real versions"""
        mock_result = pd.DataFrame({
            'model_version': ['synthetic_90pct', 'real_xgboost_v1', 'synthetic_80pct']
        })

        mock_df = MagicMock()
        mock_df.toPandas.return_value = mock_result
        mock_spark.sql.return_value = mock_df

        loader = DataLoader(spark=mock_spark)

        synthetic, real = loader.discover_model_versions('coffee')

        assert len(synthetic) == 2
        assert len(real) == 1
        assert 'synthetic_90pct' in synthetic
        assert 'real_xgboost_v1' in real

    def test_discover_model_versions_none_found(self, mock_spark):
        """Test handling when no model versions found"""
        mock_result = pd.DataFrame(columns=['model_version'])

        mock_df = MagicMock()
        mock_df.toPandas.return_value = mock_result
        mock_spark.sql.return_value = mock_df

        loader = DataLoader(spark=mock_spark)

        synthetic, real = loader.discover_model_versions('coffee')

        assert len(synthetic) == 0
        assert len(real) == 0


class TestDataSummary:
    """Test data summary generation"""

    def test_get_data_summary(self, mock_spark, sample_prices, sample_predictions):
        """Test summary statistics generation"""
        loader = DataLoader(spark=mock_spark)

        summary = loader.get_data_summary(sample_prices, sample_predictions)

        # Verify summary structure
        assert 'prices' in summary
        assert 'prediction_matrices' in summary
        assert 'alignment' in summary

        # Verify prices summary
        assert summary['prices']['n_days'] == 100
        assert 'date_range' in summary['prices']
        assert 'price_range' in summary['prices']

        # Verify predictions summary
        assert summary['prediction_matrices']['n_dates'] == 10
        assert summary['prediction_matrices']['n_runs'] == 100
        assert summary['prediction_matrices']['n_horizons'] == 14

        # Verify alignment
        assert 'overlap_pct' in summary['alignment']
        assert summary['alignment']['overlap_pct'] >= 0
        assert summary['alignment']['overlap_pct'] <= 100

    def test_get_data_summary_minimal_predictions(self, mock_spark, sample_prices,
                                                   minimal_predictions):
        """Test summary with minimal prediction set"""
        loader = DataLoader(spark=mock_spark)

        summary = loader.get_data_summary(sample_prices, minimal_predictions)

        # Verify predictions summary with smaller dataset
        assert summary['prediction_matrices']['n_dates'] == 3
        assert summary['prediction_matrices']['n_runs'] == 10
        assert summary['prediction_matrices']['n_horizons'] == 14


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_handles_prices_with_nulls(self, mock_spark, sample_predictions):
        """Test handling of prices with NULL values"""
        prices_with_nulls = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'price': [100.0] * 50 + [None] * 50  # Half nulls
        })

        mock_df = MagicMock()
        mock_df.toPandas.return_value = prices_with_nulls
        mock_spark.table.return_value = mock_df

        loader = DataLoader(spark=mock_spark)
        data_paths = {'prices_prepared': 'test.prices_coffee'}

        with pytest.raises(ValueError, match="contains NULL values"):
            loader._load_prices(data_paths)

    def test_handles_single_date_predictions(self, mock_spark, sample_prices):
        """Test handling of single prediction date"""
        single_prediction = {
            pd.Timestamp('2024-01-10'): np.random.uniform(90, 110, (100, 14))
        }

        loader = DataLoader(spark=mock_spark)

        # Should still validate successfully if date overlaps
        loader._validate_data(sample_prices, single_prediction, 'test_model')

    def test_handles_large_prediction_matrices(self, mock_spark, sample_prices):
        """Test handling of large prediction matrices (500 runs)"""
        large_predictions = {
            pd.Timestamp('2024-01-10'): np.random.uniform(90, 110, (500, 14))
        }

        loader = DataLoader(spark=mock_spark)

        # Should validate successfully
        loader._validate_data(sample_prices, large_predictions, 'test_model')

        summary = loader.get_data_summary(sample_prices, large_predictions)
        assert summary['prediction_matrices']['n_runs'] == 500

    def test_handles_different_horizon_counts(self, mock_spark, sample_prices):
        """Test detection of inconsistent horizon counts"""
        # Create predictions with different horizon counts
        inconsistent_predictions = {
            pd.Timestamp('2024-01-10'): np.random.uniform(90, 110, (100, 14)),
            pd.Timestamp('2024-01-15'): np.random.uniform(90, 110, (100, 10))  # Wrong!
        }

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Inconsistent horizon count"):
            loader._validate_data(sample_prices, inconsistent_predictions, 'test_model')


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""

    def test_coffee_synthetic_90pct_scenario(self, mock_spark, sample_prices,
                                              sample_predictions, temp_volume):
        """Test realistic coffee synthetic 90% accuracy scenario"""
        # Setup data paths
        data_paths = {
            'prices_prepared': 'commodity.prices.coffee',
            'prediction_matrices': f'{temp_volume}/prediction_matrices_coffee_synthetic_90pct.pkl'
        }

        # Setup mocks
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Save predictions
        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(sample_predictions, f)

        loader = DataLoader(spark=mock_spark)

        # Execute full load
        prices, matrices = loader.load_commodity_data(
            commodity='coffee',
            model_version='synthetic_90pct',
            data_paths=data_paths,
            verbose=True
        )

        # Get summary
        summary = loader.get_data_summary(prices, matrices)

        # Verify realistic outputs
        assert len(prices) == 100
        assert len(matrices) == 10
        assert summary['prices']['n_days'] == 100
        assert summary['prediction_matrices']['n_dates'] == 10
        assert summary['alignment']['overlap_pct'] >= 50.0

    def test_sugar_real_model_scenario(self, mock_spark, temp_volume):
        """Test realistic sugar real model scenario"""
        # Create realistic sugar data (longer time series)
        sugar_prices = pd.DataFrame({
            'date': pd.date_range('2020-01-01', periods=365),
            'price': 15 + np.cumsum(np.random.normal(0, 0.5, 365))
        })

        # Real model predictions (fewer dates, more runs)
        sugar_predictions = {
            pd.Timestamp(date): np.random.uniform(14, 18, (500, 14))
            for date in pd.date_range('2020-06-01', periods=20, freq='7D')
        }

        data_paths = {
            'prices_prepared': 'commodity.prices.sugar',
            'prediction_matrices': f'{temp_volume}/prediction_matrices_sugar_real_xgboost.pkl'
        }

        # Setup mocks
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sugar_prices
        mock_spark.table.return_value = mock_df

        # Save predictions
        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(sugar_predictions, f)

        loader = DataLoader(spark=mock_spark)

        prices, matrices = loader.load_commodity_data(
            commodity='sugar',
            model_version='real_xgboost',
            data_paths=data_paths
        )

        summary = loader.get_data_summary(prices, matrices)

        # Verify
        assert len(prices) == 365
        assert len(matrices) == 20
        assert summary['prediction_matrices']['n_runs'] == 500
