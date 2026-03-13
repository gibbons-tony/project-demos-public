"""
Integration Tests for Production Runners
Tests end-to-end workflow across all modules
"""

import pytest
import pandas as pd
import numpy as np
import pickle
import os
from unittest.mock import MagicMock, patch

from production.runners import (
    DataLoader,
    StrategyRunner,
    VisualizationGenerator,
    ResultSaver,
    MultiCommodityRunner
)


class TestSingleCommodityWorkflow:
    """Test complete workflow for single commodity-model pair"""

    def test_end_to_end_single_commodity(self, mock_spark, sample_prices,
                                         sample_predictions, commodity_config,
                                         baseline_params, prediction_params,
                                         temp_volume):
        """Test complete workflow: Load → Run → Visualize → Save"""

        # 1. Setup data
        data_paths = {
            'prices_prepared': 'test.prices_coffee',
            'prediction_matrices': f'{temp_volume}/pred_coffee_test.pkl',
            'results': 'test.results_coffee_test',
            'results_detailed': f'{temp_volume}/results_detailed_coffee_test.pkl'
        }

        # Save prediction matrices
        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(sample_predictions, f)

        # Mock Spark
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Mock createDataFrame for saving
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        # 2. Load Data
        loader = DataLoader(spark=mock_spark)
        prices, matrices = loader.load_commodity_data(
            commodity='coffee',
            model_version='test_model',
            data_paths=data_paths,
            verbose=False
        )

        assert len(prices) == 100
        assert len(matrices) == 10

        # 3. Run Strategies
        runner = StrategyRunner(
            prices=prices,
            prediction_matrices=matrices,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        results_dict, metrics_df = runner.run_all_strategies(
            commodity='coffee',
            model_version='test_model',
            verbose=False
        )

        assert len(results_dict) == 9
        assert len(metrics_df) == 9

        # 4. Generate Visualizations
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_paths = viz_gen.generate_all_charts(
            commodity='coffee',
            model_version='test_model',
            results_df=metrics_df,
            results_dict=results_dict,
            prices=prices,
            baseline_strategies=['Immediate Sale', 'Equal Batch',
                                'Price Threshold', 'Moving Average'],
            verbose=False
        )

        # Verify all 5 charts generated
        assert len(chart_paths) == 5
        assert 'net_earnings' in chart_paths
        assert 'trading_timeline' in chart_paths
        assert 'total_revenue' in chart_paths
        assert 'cumulative_returns' in chart_paths
        assert 'inventory_drawdown' in chart_paths

        # 5. Save Results
        saver = ResultSaver(spark=mock_spark)

        # Validate before saving
        is_valid = saver.validate_results(metrics_df, results_dict)
        assert is_valid

        saved_paths = saver.save_results(
            commodity='coffee',
            model_version='test_model',
            metrics_df=metrics_df,
            results_dict=results_dict,
            data_paths=data_paths,
            verbose=False
        )

        assert 'delta_metrics' in saved_paths
        assert 'pickle_detailed' in saved_paths

        # Verify detailed pickle was saved
        assert os.path.exists(data_paths['results_detailed'])

    def test_workflow_with_minimal_data(self, mock_spark, sample_prices,
                                        minimal_predictions, commodity_config,
                                        baseline_params, prediction_params,
                                        temp_volume):
        """Test workflow with minimal dataset (faster execution)"""

        data_paths = {
            'prices_prepared': 'test.prices_coffee',
            'prediction_matrices': f'{temp_volume}/pred_minimal.pkl',
            'results': 'test.results_minimal',
            'results_detailed': f'{temp_volume}/results_minimal.pkl'
        }

        # Save minimal predictions
        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(minimal_predictions, f)

        # Mock Spark
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        # Execute full pipeline
        loader = DataLoader(spark=mock_spark)
        prices, matrices = loader.load_commodity_data(
            'coffee', 'minimal', data_paths, verbose=False
        )

        runner = StrategyRunner(prices, matrices, commodity_config,
                               baseline_params, prediction_params)
        results_dict, metrics_df = runner.run_all_strategies(
            'coffee', 'minimal', verbose=False
        )

        viz_gen = VisualizationGenerator(volume_path=temp_volume)
        chart_paths = viz_gen.generate_all_charts(
            'coffee', 'minimal', metrics_df, results_dict, prices,
            ['Immediate Sale', 'Equal Batch', 'Price Threshold', 'Moving Average'],
            verbose=False
        )

        saver = ResultSaver(spark=mock_spark)
        saved_paths = saver.save_results(
            'coffee', 'minimal', metrics_df, results_dict, data_paths, verbose=False
        )

        # Verify pipeline completed
        assert len(results_dict) == 9
        assert len(chart_paths) == 5
        assert len(saved_paths) >= 2


class TestMultiCommodityRunner:
    """Test MultiCommodityRunner orchestration"""

    @patch('production.runners.data_loader.DataLoader.discover_model_versions')
    @patch('production.runners.data_loader.DataLoader.load_commodity_data')
    def test_multi_commodity_runner_initialization(self, mock_load, mock_discover,
                                                   mock_spark, commodity_config,
                                                   baseline_params, prediction_params,
                                                   temp_volume):
        """Test MultiCommodityRunner initializes correctly"""

        runner = MultiCommodityRunner(
            spark=mock_spark,
            commodity_configs={'coffee': commodity_config},
            baseline_params=baseline_params,
            prediction_params=prediction_params,
            volume_path=temp_volume,
            output_schema='test'
        )

        assert runner.spark is not None
        assert runner.commodity_configs is not None
        assert runner.baseline_params is not None
        assert runner.prediction_params is not None
        assert runner.data_loader is not None
        assert runner.viz_generator is not None
        assert runner.result_saver is not None

    @patch('production.runners.data_loader.DataLoader.discover_model_versions')
    @patch('production.runners.data_loader.DataLoader.load_commodity_data')
    @patch('production.runners.strategy_runner.StrategyRunner.run_all_strategies')
    @patch('production.runners.visualization.VisualizationGenerator.generate_all_charts')
    @patch('production.runners.result_saver.ResultSaver.save_results')
    def test_run_all_commodities(self, mock_save, mock_viz, mock_run,
                                 mock_load, mock_discover, mock_spark,
                                 sample_prices, sample_predictions,
                                 commodity_config, baseline_params,
                                 prediction_params, temp_volume,
                                 sample_results_dict, sample_metrics_df):
        """Test running all commodities and models"""

        # Setup mocks
        mock_discover.return_value = (['synthetic_90pct'], [])
        mock_load.return_value = (sample_prices, sample_predictions)
        mock_run.return_value = (sample_results_dict, sample_metrics_df)
        mock_viz.return_value = {
            'net_earnings': f'{temp_volume}/chart1.png',
            'trading_timeline': f'{temp_volume}/chart2.png',
            'total_revenue': f'{temp_volume}/chart3.png',
            'cumulative_returns': f'{temp_volume}/chart4.png',
            'inventory_drawdown': f'{temp_volume}/chart5.png'
        }
        mock_save.return_value = {
            'delta_metrics': 'test.results',
            'pickle_detailed': f'{temp_volume}/results.pkl'
        }

        runner = MultiCommodityRunner(
            spark=mock_spark,
            commodity_configs={'coffee': commodity_config},
            baseline_params=baseline_params,
            prediction_params=prediction_params,
            volume_path=temp_volume,
            output_schema='test'
        )

        results = runner.run_all_commodities(verbose=False)

        # Verify results structure
        assert 'coffee' in results
        assert 'synthetic_90pct' in results['coffee']

        # Verify summary
        summary = runner.get_summary()
        assert summary['total_combinations'] == 1
        assert summary['commodities_processed'] == ['coffee']

    def test_run_specific_commodities(self, mock_spark, commodity_config,
                                      baseline_params, prediction_params,
                                      temp_volume):
        """Test running specific subset of commodities"""

        commodity_configs = {
            'coffee': commodity_config,
            'sugar': commodity_config.copy()
        }

        runner = MultiCommodityRunner(
            spark=mock_spark,
            commodity_configs=commodity_configs,
            baseline_params=baseline_params,
            prediction_params=prediction_params,
            volume_path=temp_volume,
            output_schema='test'
        )

        # Should accept commodities filter
        # (actual execution would require full mocking)
        assert runner.commodity_configs is not None
        assert 'coffee' in runner.commodity_configs
        assert 'sugar' in runner.commodity_configs


class TestErrorHandling:
    """Test error handling across modules"""

    def test_handles_missing_prices(self, mock_spark, sample_predictions,
                                    commodity_config, baseline_params,
                                    prediction_params, temp_volume):
        """Test graceful handling of missing price data"""

        # Mock Spark to raise error
        mock_spark.table.side_effect = Exception("Table not found")

        data_paths = {
            'prices_prepared': 'test.nonexistent_table',
            'prediction_matrices': f'{temp_volume}/pred.pkl'
        }

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Failed to load prices"):
            loader.load_commodity_data('coffee', 'test', data_paths)

    def test_handles_missing_predictions(self, mock_spark, sample_prices,
                                         commodity_config, baseline_params,
                                         prediction_params):
        """Test graceful handling of missing prediction matrices"""

        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        data_paths = {
            'prices_prepared': 'test.prices',
            'prediction_matrices': '/nonexistent/path/predictions.pkl'
        }

        loader = DataLoader(spark=mock_spark)

        with pytest.raises(ValueError, match="Failed to load prediction matrices"):
            loader.load_commodity_data('coffee', 'test', data_paths)

    def test_handles_invalid_results(self, mock_spark, sample_prices,
                                     sample_predictions):
        """Test validation detects invalid results"""

        # Create invalid results (missing strategy)
        invalid_metrics = pd.DataFrame({
            'strategy': ['Strategy A'],  # Only 1 strategy (should be 9)
            'net_earnings': [50000.0],
            'type': ['Baseline']
        })

        invalid_results = {
            'Strategy A': {
                'strategy_name': 'Strategy A',
                'trades': [],
                'net_earnings': 50000.0
            }
        }

        saver = ResultSaver(spark=mock_spark)

        is_valid = saver.validate_results(invalid_metrics, invalid_results)
        assert not is_valid


class TestDataIntegrity:
    """Test data integrity across pipeline"""

    def test_data_consistency_through_pipeline(self, mock_spark, sample_prices,
                                               sample_predictions, commodity_config,
                                               baseline_params, prediction_params,
                                               temp_volume):
        """Test data remains consistent through entire pipeline"""

        data_paths = {
            'prices_prepared': 'test.prices_coffee',
            'prediction_matrices': f'{temp_volume}/pred.pkl',
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results.pkl'
        }

        # Save predictions
        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(sample_predictions, f)

        # Mock Spark
        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Load data
        loader = DataLoader(spark=mock_spark)
        prices, matrices = loader.load_commodity_data(
            'coffee', 'test', data_paths, verbose=False
        )

        # Check prices unchanged
        assert len(prices) == len(sample_prices)
        assert prices['date'].iloc[0] == sample_prices['date'].iloc[0]

        # Check matrices unchanged
        assert len(matrices) == len(sample_predictions)
        first_key = list(matrices.keys())[0]
        assert matrices[first_key].shape == (100, 14)

    def test_metrics_match_results(self, sample_results_dict, sample_metrics_df):
        """Test metrics DataFrame matches results dictionary"""

        # Verify all strategies in results have metrics
        for strategy_name in sample_results_dict.keys():
            assert strategy_name in sample_metrics_df['strategy'].values

        # Verify earnings match
        for _, row in sample_metrics_df.iterrows():
            strategy_name = row['strategy']
            if strategy_name in sample_results_dict:
                expected_earnings = sample_results_dict[strategy_name]['net_earnings']
                actual_earnings = row['net_earnings']
                # Allow small floating point differences
                assert abs(expected_earnings - actual_earnings) < 0.01

    def test_round_trip_save_load(self, mock_spark, sample_metrics_df,
                                  sample_results_dict, temp_volume):
        """Test save and load cycle preserves data"""

        data_paths = {
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results_roundtrip.pkl'
        }

        # Mock Spark for Delta save
        mock_sdf = MagicMock()
        mock_writer = MagicMock()
        mock_writer.format.return_value = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.saveAsTable.return_value = None
        mock_sdf.write = mock_writer
        mock_spark.createDataFrame.return_value = mock_sdf

        # Save
        saver = ResultSaver(spark=mock_spark)
        saved_paths = saver.save_results(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            data_paths, verbose=False
        )

        # Verify pickle saved
        assert os.path.exists(data_paths['results_detailed'])

        # Load pickle
        with open(data_paths['results_detailed'], 'rb') as f:
            loaded_results = pickle.load(f)

        # Verify structure preserved
        assert len(loaded_results) == len(sample_results_dict)
        for key in sample_results_dict.keys():
            assert key in loaded_results


class TestPerformance:
    """Test performance and execution time"""

    def test_minimal_data_execution_time(self, mock_spark, sample_prices,
                                         minimal_predictions, commodity_config,
                                         baseline_params, prediction_params,
                                         temp_volume):
        """Test execution completes quickly with minimal data"""
        import time

        data_paths = {
            'prices_prepared': 'test.prices',
            'prediction_matrices': f'{temp_volume}/pred_perf.pkl',
            'results': 'test.results',
            'results_detailed': f'{temp_volume}/results_perf.pkl'
        }

        os.makedirs(temp_volume, exist_ok=True)
        with open(data_paths['prediction_matrices'], 'wb') as f:
            pickle.dump(minimal_predictions, f)

        mock_df = MagicMock()
        mock_df.toPandas.return_value = sample_prices
        mock_spark.table.return_value = mock_df

        # Time the execution
        start = time.time()

        loader = DataLoader(spark=mock_spark)
        prices, matrices = loader.load_commodity_data(
            'coffee', 'test', data_paths, verbose=False
        )

        runner = StrategyRunner(prices, matrices, commodity_config,
                               baseline_params, prediction_params)
        results_dict, metrics_df = runner.run_all_strategies(
            'coffee', 'test', verbose=False
        )

        elapsed = time.time() - start

        # Should complete in reasonable time (< 60 seconds for minimal data)
        assert elapsed < 60.0
        assert len(results_dict) == 9


class TestRegressionAgainstNotebook05:
    """Test results match notebook 05 outputs (when available)"""

    @pytest.mark.skip(reason="Requires reference data from notebook 05")
    def test_matches_notebook_05_earnings(self):
        """Test net earnings match notebook 05 (within tolerance)"""
        # This test would compare production results to saved notebook 05 results
        # Skip for now - implement when reference data available
        pass

    @pytest.mark.skip(reason="Requires reference data from notebook 05")
    def test_matches_notebook_05_trade_counts(self):
        """Test trade counts match notebook 05"""
        # Compare number of trades per strategy
        pass

    @pytest.mark.skip(reason="Requires reference data from notebook 05")
    def test_matches_notebook_05_best_strategies(self):
        """Test best strategy selection matches notebook 05"""
        # Verify same strategies identified as best
        pass


class TestSmokeTest:
    """Smoke tests for Databricks deployment"""

    def test_all_imports_work(self):
        """Test all production modules can be imported"""
        from production.runners import (
            DataLoader,
            StrategyRunner,
            VisualizationGenerator,
            ResultSaver,
            MultiCommodityRunner
        )

        assert DataLoader is not None
        assert StrategyRunner is not None
        assert VisualizationGenerator is not None
        assert ResultSaver is not None
        assert MultiCommodityRunner is not None

    def test_strategy_imports(self):
        """Test all strategy classes can be imported"""
        from production.strategies import (
            ImmediateSaleStrategy,
            EqualBatchStrategy,
            PriceThresholdStrategy,
            MovingAverageStrategy,
            ConsensusStrategy,
            ExpectedValueStrategy,
            RiskAdjustedStrategy,
            PriceThresholdPredictive,
            MovingAveragePredictive
        )

        # Verify all 9 strategies available
        assert ImmediateSaleStrategy is not None
        assert EqualBatchStrategy is not None
        assert PriceThresholdStrategy is not None
        assert MovingAverageStrategy is not None
        assert ConsensusStrategy is not None
        assert ExpectedValueStrategy is not None
        assert RiskAdjustedStrategy is not None
        assert PriceThresholdPredictive is not None
        assert MovingAveragePredictive is not None

    def test_core_engine_import(self):
        """Test backtest engine can be imported"""
        from production.core.backtest_engine import BacktestEngine

        assert BacktestEngine is not None

    def test_config_import(self):
        """Test config can be imported"""
        from production.config import COMMODITY_CONFIGS

        assert COMMODITY_CONFIGS is not None
        assert 'coffee' in COMMODITY_CONFIGS
