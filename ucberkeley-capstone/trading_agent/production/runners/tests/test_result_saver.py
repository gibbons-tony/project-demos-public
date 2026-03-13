"""
Unit Tests for ResultSaver Module
Tests result persistence to Delta tables and pickle files
"""

import pytest
import pandas as pd
import numpy as np
import pickle
import os
from unittest.mock import MagicMock, patch

from production.runners.result_saver import ResultSaver


class TestResultSaverInitialization:
    """Test ResultSaver initialization"""

    def test_initialization(self, mock_spark):
        """Test successful initialization"""
        saver = ResultSaver(spark=mock_spark)

        assert saver.spark is not None
        assert saver.spark == mock_spark

    def test_initialization_without_spark(self):
        """Test initialization requires Spark session"""
        with pytest.raises(ValueError, match="Spark session required"):
            ResultSaver(spark=None)


class TestMetricsSaving:
    """Test saving metrics to Delta tables"""

    def test_save_metrics_to_delta(self, mock_spark, sample_metrics_df):
        """Test saving metrics DataFrame to Delta table"""
        # Setup mock
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        saver = ResultSaver(spark=mock_spark)

        table_name = saver._save_metrics_to_delta(
            commodity='coffee',
            model_version='test_model',
            metrics_df=sample_metrics_df,
            table_name='test.results_coffee_test',
            verbose=False
        )

        # Verify Spark calls
        mock_spark.createDataFrame.assert_called_once()
        mock_writer.format.assert_called_with('delta')
        mock_writer.mode.assert_called_with('overwrite')
        mock_writer.saveAsTable.assert_called_with('test.results_coffee_test')

        assert table_name == 'test.results_coffee_test'

    def test_save_metrics_validates_columns(self, mock_spark):
        """Test metrics saving validates required columns"""
        # Missing required columns
        bad_df = pd.DataFrame({
            'strategy': ['Strategy A'],
            'wrong_column': [50000]
        })

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(ValueError, match="Missing required columns"):
            saver._save_metrics_to_delta(
                'coffee', 'test', bad_df, 'test.results', verbose=False
            )

    def test_save_metrics_handles_empty_dataframe(self, mock_spark):
        """Test handling of empty metrics DataFrame"""
        empty_df = pd.DataFrame(columns=[
            'strategy', 'net_earnings', 'total_revenue', 'type',
            'commodity', 'model_version'
        ])

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(ValueError, match="Empty metrics DataFrame"):
            saver._save_metrics_to_delta(
                'coffee', 'test', empty_df, 'test.results', verbose=False
            )


class TestDetailedResultsSaving:
    """Test saving detailed results to pickle files"""

    def test_save_detailed_to_pickle(self, sample_results_dict, temp_volume):
        """Test saving results dictionary to pickle"""
        pickle_path = os.path.join(temp_volume, 'results_detailed_test.pkl')

        saver = ResultSaver(spark=MagicMock())

        saved_path = saver._save_detailed_to_pickle(
            commodity='coffee',
            model_version='test_model',
            results_dict=sample_results_dict,
            pickle_path=pickle_path,
            verbose=False
        )

        # Verify file saved
        assert os.path.exists(pickle_path)
        assert saved_path == pickle_path

        # Verify can be loaded
        with open(pickle_path, 'rb') as f:
            loaded_results = pickle.load(f)

        assert len(loaded_results) == len(sample_results_dict)
        for key in sample_results_dict.keys():
            assert key in loaded_results

    def test_save_detailed_creates_directory(self, sample_results_dict,
                                            temp_volume):
        """Test pickle saving creates parent directory if needed"""
        nested_path = os.path.join(temp_volume, 'nested', 'dir', 'results.pkl')

        saver = ResultSaver(spark=MagicMock())

        saved_path = saver._save_detailed_to_pickle(
            'coffee', 'test', sample_results_dict, nested_path, verbose=False
        )

        # Verify directory created and file saved
        assert os.path.exists(os.path.dirname(nested_path))
        assert os.path.exists(nested_path)

    def test_save_detailed_validates_structure(self, temp_volume):
        """Test pickle saving validates results structure"""
        # Invalid structure (missing required fields)
        bad_results = {
            'Strategy A': {
                'wrong_field': 'value'
            }
        }

        pickle_path = os.path.join(temp_volume, 'bad_results.pkl')

        saver = ResultSaver(spark=MagicMock())

        with pytest.raises(ValueError, match="Missing required fields"):
            saver._save_detailed_to_pickle(
                'coffee', 'test', bad_results, pickle_path, verbose=False
            )


class TestFullResultsSaving:
    """Test complete results saving workflow"""

    def test_save_results(self, mock_spark, sample_metrics_df,
                         sample_results_dict, temp_volume):
        """Test saving both metrics and detailed results"""
        # Setup mocks
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results_coffee_test',
            'results_detailed': f'{temp_volume}/results_detailed.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        saved_paths = saver.save_results(
            commodity='coffee',
            model_version='test_model',
            metrics_df=sample_metrics_df,
            results_dict=sample_results_dict,
            data_paths=data_paths,
            verbose=False
        )

        # Verify both saved
        assert 'delta_metrics' in saved_paths
        assert 'pickle_detailed' in saved_paths
        assert os.path.exists(data_paths['results_detailed'])

    def test_save_results_with_validation(self, mock_spark, sample_metrics_df,
                                          sample_results_dict, temp_volume):
        """Test save_results performs validation"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        # Should validate and succeed
        saved_paths = saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=False
        )

        assert saved_paths is not None


class TestResultsValidation:
    """Test results validation"""

    def test_validate_results_success(self, mock_spark, sample_metrics_df,
                                      sample_results_dict):
        """Test validation passes with valid data"""
        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(sample_metrics_df, sample_results_dict)

        assert is_valid is True

    def test_validate_detects_missing_columns(self, mock_spark,
                                              sample_results_dict):
        """Test validation detects missing required columns"""
        bad_df = pd.DataFrame({
            'strategy': ['Strategy A'],
            'wrong_column': [50000]
        })

        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(bad_df, sample_results_dict)

        assert is_valid is False

    def test_validate_detects_null_values(self, mock_spark, sample_results_dict):
        """Test validation detects NULL values in critical columns"""
        df_with_nulls = pd.DataFrame({
            'strategy': ['Strategy A', 'Strategy B'],
            'net_earnings': [50000.0, None],  # NULL value
            'type': ['Baseline', 'Prediction'],
            'commodity': ['coffee', 'coffee'],
            'model_version': ['test', 'test']
        })

        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(df_with_nulls, sample_results_dict)

        assert is_valid is False

    def test_validate_detects_strategy_mismatch(self, mock_spark,
                                                sample_metrics_df):
        """Test validation detects strategy count mismatch"""
        # Results dict with only 1 strategy (should be 9)
        incomplete_results = {
            'Strategy A': {
                'strategy_name': 'Strategy A',
                'trades': [],
                'net_earnings': 50000
            }
        }

        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(sample_metrics_df, incomplete_results)

        assert is_valid is False

    def test_validate_empty_data(self, mock_spark):
        """Test validation handles empty data"""
        empty_df = pd.DataFrame()
        empty_results = {}

        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(empty_df, empty_results)

        assert is_valid is False


class TestResultsLoading:
    """Test loading previously saved results"""

    def test_load_results(self, mock_spark, sample_metrics_df,
                          sample_results_dict, temp_volume):
        """Test loading results from Delta and pickle"""
        # First save results
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results_load',
            'results_detailed': f'{temp_volume}/results_load.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        # Save
        saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=False
        )

        # Mock Spark table read
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_metrics_df
        mock_spark.table.return_value = mock_df

        # Load
        loaded_metrics, loaded_results = saver.load_results(
            commodity='coffee',
            model_version='test',
            data_paths=data_paths,
            verbose=False
        )

        # Verify loaded data
        assert isinstance(loaded_metrics, pd.DataFrame)
        assert isinstance(loaded_results, dict)
        assert len(loaded_metrics) == len(sample_metrics_df)
        assert len(loaded_results) == len(sample_results_dict)

    def test_load_handles_missing_pickle(self, mock_spark):
        """Test loading handles missing pickle file"""
        data_paths = {
            'results': 'test.results',
            'results_detailed': '/nonexistent/path/results.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(FileNotFoundError):
            saver.load_results('coffee', 'test', data_paths)

    def test_load_handles_missing_delta_table(self, mock_spark, temp_volume):
        """Test loading handles missing Delta table"""
        # Create valid pickle
        sample_results = {'Strategy A': {'net_earnings': 50000}}
        pickle_path = os.path.join(temp_volume, 'results.pkl')
        with open(pickle_path, 'wb') as f:
            pickle.dump(sample_results, f)

        data_paths = {
            'results': 'test.nonexistent_table',
            'results_detailed': pickle_path
        }

        # Mock Spark to raise error
        mock_spark.table.side_effect = Exception("Table not found")

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(Exception):
            saver.load_results('coffee', 'test', data_paths)


class TestCrossCommodityResults:
    """Test cross-commodity summary generation"""

    def test_save_cross_commodity_results(self, mock_spark, temp_volume):
        """Test saving cross-commodity comparison"""
        comparison_df = pd.DataFrame({
            'commodity': ['coffee', 'sugar'],
            'model_version': ['synthetic_90pct', 'synthetic_90pct'],
            'best_strategy': ['Consensus', 'Expected Value'],
            'net_earnings': [50000, 35000],
            'prediction_advantage_pct': [15.5, 8.7]
        })

        detailed_df = pd.DataFrame({
            'commodity': ['coffee', 'coffee', 'sugar', 'sugar'],
            'model_version': ['synthetic_90pct'] * 4,
            'strategy': ['Consensus', 'Equal Batch',
                        'Expected Value', 'Immediate Sale'],
            'net_earnings': [50000, 42000, 35000, 32000]
        })

        saver = ResultSaver(spark=mock_spark)

        saved_paths = saver.save_cross_commodity_results(
            comparison_df=comparison_df,
            detailed_df=detailed_df,
            volume_path=temp_volume,
            verbose=False
        )

        # Verify CSVs saved
        assert 'summary_csv' in saved_paths
        assert 'detailed_csv' in saved_paths
        assert os.path.exists(saved_paths['summary_csv'])
        assert os.path.exists(saved_paths['detailed_csv'])

        # Verify can be loaded
        loaded_summary = pd.read_csv(saved_paths['summary_csv'])
        loaded_detailed = pd.read_csv(saved_paths['detailed_csv'])

        assert len(loaded_summary) == 2
        assert len(loaded_detailed) == 4

    def test_cross_commodity_with_single_commodity(self, mock_spark,
                                                   temp_volume):
        """Test cross-commodity results with only one commodity"""
        single_df = pd.DataFrame({
            'commodity': ['coffee'],
            'model_version': ['synthetic_90pct'],
            'best_strategy': ['Consensus'],
            'net_earnings': [50000]
        })

        saver = ResultSaver(spark=mock_spark)

        # Should still save successfully
        saved_paths = saver.save_cross_commodity_results(
            comparison_df=single_df,
            detailed_df=single_df,
            volume_path=temp_volume,
            verbose=False
        )

        assert os.path.exists(saved_paths['summary_csv'])


class TestErrorHandling:
    """Test error handling in result saving"""

    def test_handles_spark_save_failure(self, mock_spark, sample_metrics_df,
                                        sample_results_dict, temp_volume):
        """Test handling of Spark save failures"""
        # Mock Spark to raise error
        mock_spark.createDataFrame.side_effect = Exception("Spark error")

        data_paths = {
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(RuntimeError, match="Failed to save metrics"):
            saver.save_results(
                'coffee', 'test', sample_metrics_df, sample_results_dict,
                data_paths, verbose=False
            )

    def test_handles_pickle_save_failure(self, mock_spark, sample_metrics_df,
                                         sample_results_dict):
        """Test handling of pickle save failures"""
        # Invalid path (no permissions)
        data_paths = {
            'results': 'test.results',
            'results_detailed': '/root/protected/results.pkl'
        }

        # Mock Spark to succeed
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        saver = ResultSaver(spark=mock_spark)

        with pytest.raises(RuntimeError, match="Failed to save detailed results"):
            saver.save_results(
                'coffee', 'test', sample_metrics_df, sample_results_dict,
                data_paths, verbose=False
            )


class TestVerboseLogging:
    """Test verbose output during saving"""

    def test_verbose_output(self, mock_spark, sample_metrics_df,
                           sample_results_dict, temp_volume, capsys):
        """Test verbose logging during result saving"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=True
        )

        captured = capsys.readouterr()

        # Verify verbose output
        assert "Saving" in captured.out or "saved" in captured.out.lower()

    def test_silent_saving(self, mock_spark, sample_metrics_df,
                          sample_results_dict, temp_volume, capsys):
        """Test silent result saving (verbose=False)"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=False
        )

        captured = capsys.readouterr()

        # Should have minimal output
        assert len(captured.out) < 100


class TestIntegrationScenarios:
    """Test realistic result saving scenarios"""

    def test_coffee_90pct_full_save(self, mock_spark, sample_metrics_df,
                                    sample_results_dict, temp_volume):
        """Test complete save workflow for coffee 90%"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'commodity.trading_agent.results_coffee_synthetic_90pct',
            'results_detailed': f'{temp_volume}/results_detailed_coffee_synthetic_90pct.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        # Validate
        is_valid = saver.validate_results(sample_metrics_df, sample_results_dict)
        assert is_valid

        # Save
        saved_paths = saver.save_results(
            commodity='coffee',
            model_version='synthetic_90pct',
            metrics_df=sample_metrics_df,
            results_dict=sample_results_dict,
            data_paths=data_paths,
            verbose=False
        )

        # Verify
        assert len(saved_paths) == 2
        assert os.path.exists(data_paths['results_detailed'])

    def test_multiple_commodity_saves(self, mock_spark, sample_metrics_df,
                                     sample_results_dict, temp_volume):
        """Test saving results for multiple commodities"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        saver = ResultSaver(spark=mock_spark)

        commodities = ['coffee', 'sugar']
        all_saved = []

        for commodity in commodities:
            data_paths = {
                'results': f'test.results_{commodity}',
                'results_detailed': f'{temp_volume}/results_{commodity}.pkl'
            }

            saved_paths = saver.save_results(
                commodity=commodity,
                model_version='test',
                metrics_df=sample_metrics_df,
                results_dict=sample_results_dict,
                data_paths=data_paths,
                verbose=False
            )

            all_saved.append(saved_paths)

        # Verify all saved
        assert len(all_saved) == 2
        for saved_paths in all_saved:
            assert 'delta_metrics' in saved_paths
            assert 'pickle_detailed' in saved_paths

    def test_round_trip_integrity(self, mock_spark, sample_metrics_df,
                                  sample_results_dict, temp_volume):
        """Test data integrity through save/load cycle"""
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        data_paths = {
            'results': 'test.results_roundtrip',
            'results_detailed': f'{temp_volume}/results_roundtrip.pkl'
        }

        saver = ResultSaver(spark=mock_spark)

        # Save
        saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=False
        )

        # Mock load from Delta
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_metrics_df
        mock_spark.table.return_value = mock_df

        # Load
        loaded_metrics, loaded_results = saver.load_results(
            'coffee', 'test', data_paths, verbose=False
        )

        # Verify integrity
        assert len(loaded_metrics) == len(sample_metrics_df)
        assert len(loaded_results) == len(sample_results_dict)

        # Verify specific values preserved
        for strategy_name, original_result in sample_results_dict.items():
            assert strategy_name in loaded_results
            loaded_earnings = loaded_results[strategy_name]['net_earnings']
            original_earnings = original_result['net_earnings']
            # Allow small floating point differences
            assert abs(loaded_earnings - original_earnings) < 0.01
