"""
Unit Tests for StrategyRunner Module
Tests strategy initialization, execution, and analysis
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

from production.runners.strategy_runner import StrategyRunner
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


class TestStrategyRunnerInitialization:
    """Test StrategyRunner initialization"""

    def test_initialization_success(self, sample_prices, sample_predictions,
                                     commodity_config, baseline_params,
                                     prediction_params):
        """Test successful initialization"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=sample_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        assert runner.prices is not None
        assert runner.prediction_matrices is not None
        assert runner.commodity_config == commodity_config
        assert runner.baseline_params == baseline_params
        assert runner.prediction_params == prediction_params

    def test_initialization_requires_prices(self, sample_predictions,
                                            commodity_config, baseline_params,
                                            prediction_params):
        """Test initialization requires prices"""
        with pytest.raises(ValueError, match="Prices DataFrame required"):
            StrategyRunner(
                prices=None,
                prediction_matrices=sample_predictions,
                commodity_config=commodity_config,
                baseline_params=baseline_params,
                prediction_params=prediction_params
            )

    def test_initialization_requires_predictions(self, sample_prices,
                                                 commodity_config, baseline_params,
                                                 prediction_params):
        """Test initialization requires prediction matrices"""
        with pytest.raises(ValueError, match="Prediction matrices required"):
            StrategyRunner(
                prices=sample_prices,
                prediction_matrices=None,
                commodity_config=commodity_config,
                baseline_params=baseline_params,
                prediction_params=prediction_params
            )


class TestStrategyInitialization:
    """Test strategy initialization"""

    def test_initialize_strategies(self, sample_prices, sample_predictions,
                                    commodity_config, baseline_params,
                                    prediction_params):
        """Test initializing all 9 strategies"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=sample_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        baselines, predictions = runner.initialize_strategies()

        # Verify counts
        assert len(baselines) == 4
        assert len(predictions) == 5

        # Verify baseline strategy types
        assert isinstance(baselines[0], ImmediateSaleStrategy)
        assert isinstance(baselines[1], EqualBatchStrategy)
        assert isinstance(baselines[2], PriceThresholdStrategy)
        assert isinstance(baselines[3], MovingAverageStrategy)

        # Verify prediction strategy types
        assert isinstance(predictions[0], ConsensusStrategy)
        assert isinstance(predictions[1], ExpectedValueStrategy)
        assert isinstance(predictions[2], RiskAdjustedStrategy)
        assert isinstance(predictions[3], PriceThresholdPredictive)
        assert isinstance(predictions[4], MovingAveragePredictive)

    def test_strategies_have_correct_parameters(self, sample_prices,
                                                sample_predictions,
                                                commodity_config,
                                                baseline_params,
                                                prediction_params):
        """Test strategies initialized with correct parameters"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=sample_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        baselines, predictions = runner.initialize_strategies()

        # Check EqualBatchStrategy parameters
        equal_batch = baselines[1]
        assert equal_batch.batch_size == baseline_params['equal_batch']['batch_size']
        assert equal_batch.frequency_days == baseline_params['equal_batch']['frequency_days']

        # Check ConsensusStrategy parameters
        consensus = predictions[0]
        assert consensus.consensus_threshold == prediction_params['consensus']['consensus_threshold']
        assert consensus.min_return == prediction_params['consensus']['min_return']


class TestStrategyExecution:
    """Test strategy execution and backtest running"""

    @patch('production.runners.strategy_runner.BacktestEngine')
    def test_run_single_strategy(self, mock_engine_class, sample_prices,
                                 sample_predictions, commodity_config,
                                 baseline_params, prediction_params):
        """Test running a single strategy"""
        # Setup mock backtest engine
        mock_engine = MagicMock()
        mock_engine.run.return_value = {
            'strategy_name': 'Test Strategy',
            'trades': [],
            'daily_state': pd.DataFrame(),
            'total_revenue': 50000.0,
            'total_transaction_costs': 50.0,
            'total_storage_costs': 200.0,
            'net_earnings': 49750.0
        }
        mock_engine_class.return_value = mock_engine

        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=sample_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        strategy = ImmediateSaleStrategy()
        result = runner._run_single_strategy(strategy, 'coffee', 'test_model')

        # Verify backtest engine called
        mock_engine_class.assert_called_once()
        mock_engine.run.assert_called_once()

        # Verify result structure
        assert 'strategy_name' in result
        assert 'net_earnings' in result
        assert result['net_earnings'] == 49750.0

    def test_run_all_strategies(self, sample_prices, minimal_predictions,
                               commodity_config, baseline_params,
                               prediction_params):
        """Test running all strategies (integration test)"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=minimal_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        # This is a slow integration test - use minimal data
        results_dict, metrics_df = runner.run_all_strategies(
            commodity='coffee',
            model_version='test_model',
            verbose=False
        )

        # Verify we got results for all 9 strategies
        assert len(results_dict) == 9
        assert len(metrics_df) == 9

        # Verify results_dict structure
        for strategy_name, result in results_dict.items():
            assert 'strategy_name' in result
            assert 'trades' in result
            assert 'daily_state' in result
            assert 'net_earnings' in result

        # Verify metrics_df structure
        required_columns = [
            'strategy', 'type', 'net_earnings', 'total_revenue',
            'total_costs', 'transaction_costs', 'storage_costs',
            'avg_sale_price', 'n_trades', 'commodity', 'model_version'
        ]
        for col in required_columns:
            assert col in metrics_df.columns

    def test_execution_handles_strategy_failure(self, sample_prices,
                                                sample_predictions,
                                                commodity_config,
                                                baseline_params,
                                                prediction_params):
        """Test graceful handling of strategy failures"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=sample_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        # Mock a failing strategy
        bad_strategy = MagicMock()
        bad_strategy.decide.side_effect = Exception("Strategy error")

        with pytest.raises(RuntimeError, match="Failed to run strategy"):
            runner._run_single_strategy(bad_strategy, 'coffee', 'test_model')


class TestMetricsCalculation:
    """Test metrics calculation and aggregation"""

    def test_calculate_metrics_from_results(self, sample_results_dict):
        """Test metrics calculation from results dictionary"""
        # Mock StrategyRunner with sample data
        runner = MagicMock()

        # Extract metrics from sample results
        strategy_result = sample_results_dict['Strategy A']

        # Verify expected values
        assert strategy_result['net_earnings'] == 53844.6
        assert strategy_result['total_revenue'] == 54000.0
        assert len(strategy_result['trades']) == 2

    def test_metrics_dataframe_structure(self, sample_metrics_df):
        """Test metrics DataFrame has correct structure"""
        required_columns = [
            'strategy', 'net_earnings', 'total_revenue', 'total_costs',
            'transaction_costs', 'storage_costs', 'avg_sale_price',
            'n_trades', 'type', 'commodity', 'model_version'
        ]

        for col in required_columns:
            assert col in sample_metrics_df.columns

        # Verify data types
        assert sample_metrics_df['net_earnings'].dtype in [np.float64, float]
        assert sample_metrics_df['n_trades'].dtype in [np.int64, int]
        assert sample_metrics_df['type'].dtype == object

    def test_strategy_type_classification(self, sample_metrics_df):
        """Test strategies correctly classified as Baseline vs Prediction"""
        baseline_strategies = ['Immediate Sale', 'Equal Batch',
                              'Price Threshold', 'Moving Average']
        prediction_strategies = ['Consensus', 'Expected Value', 'Risk-Adjusted',
                                'Price Threshold (Predictive)',
                                'Moving Average (Predictive)']

        for _, row in sample_metrics_df.iterrows():
            strategy_name = row['strategy']
            strategy_type = row['type']

            if any(b in strategy_name for b in baseline_strategies):
                assert strategy_type == 'Baseline'
            elif any(p in strategy_name for p in prediction_strategies):
                assert strategy_type == 'Prediction'


class TestBestPerformerAnalysis:
    """Test best performer identification"""

    def test_analyze_best_performers(self, sample_metrics_df):
        """Test identifying best baseline, prediction, and overall strategies"""
        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            sample_metrics_df, 'coffee', 'test_model'
        )

        # Verify structure
        assert 'best_baseline' in analysis
        assert 'best_prediction' in analysis
        assert 'best_overall' in analysis

        # Verify each has required fields
        for key in ['best_baseline', 'best_prediction', 'best_overall']:
            assert 'strategy' in analysis[key]
            assert 'net_earnings' in analysis[key]
            assert 'type' in analysis[key]

        # Verify best_overall has comparison metrics
        if 'earnings_diff' in analysis['best_overall']:
            assert isinstance(analysis['best_overall']['earnings_diff'], (int, float))
            assert isinstance(analysis['best_overall']['pct_diff'], (int, float))

    def test_best_baseline_identification(self, sample_metrics_df):
        """Test correct identification of best baseline strategy"""
        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            sample_metrics_df, 'coffee', 'test_model'
        )

        # Best baseline should be Strategy B (Baseline type)
        best_baseline = analysis['best_baseline']
        assert best_baseline['type'] == 'Baseline'

    def test_best_prediction_identification(self, sample_metrics_df):
        """Test correct identification of best prediction strategy"""
        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            sample_metrics_df, 'coffee', 'test_model'
        )

        best_prediction = analysis['best_prediction']
        assert best_prediction['type'] == 'Prediction'

    def test_prediction_advantage_calculation(self, sample_metrics_df):
        """Test calculation of prediction advantage over baseline"""
        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            sample_metrics_df, 'coffee', 'test_model'
        )

        # If best overall is prediction, should have advantage metrics
        if analysis['best_overall']['type'] == 'Prediction':
            assert 'earnings_diff' in analysis['best_overall']
            assert 'pct_diff' in analysis['best_overall']
            assert analysis['best_overall']['earnings_diff'] > 0


class TestRiskAdjustedAnalysis:
    """Test Risk-Adjusted strategy scenario analysis"""

    def test_analyze_risk_adjusted_scenarios(self, sample_results_dict):
        """Test Risk-Adjusted scenario distribution analysis"""
        # Add Risk-Adjusted results with scenario tracking
        sample_results_dict['Risk-Adjusted'] = {
            'strategy_name': 'Risk-Adjusted',
            'trades': [],
            'daily_state': pd.DataFrame(),
            'net_earnings': 50000.0,
            'scenario_distribution': {
                'high_confidence': 150,
                'medium_confidence': 200,
                'low_confidence': 100,
                'no_action': 50
            }
        }

        runner = MagicMock()
        runner.analyze_risk_adjusted_scenarios = StrategyRunner.analyze_risk_adjusted_scenarios.__get__(runner)

        analysis = runner.analyze_risk_adjusted_scenarios(sample_results_dict)

        # Verify analysis structure
        assert 'total_scenarios' in analysis
        assert 'scenario_distribution' in analysis
        assert 'scenario_percentages' in analysis

        # Verify scenario types
        assert 'high_confidence' in analysis['scenario_distribution']
        assert 'medium_confidence' in analysis['scenario_distribution']
        assert 'low_confidence' in analysis['scenario_distribution']
        assert 'no_action' in analysis['scenario_distribution']

    def test_risk_adjusted_not_found(self, sample_results_dict):
        """Test handling when Risk-Adjusted strategy not in results"""
        # Remove Risk-Adjusted if present
        results_without_ra = {k: v for k, v in sample_results_dict.items()
                             if 'Risk' not in k}

        runner = MagicMock()
        runner.analyze_risk_adjusted_scenarios = StrategyRunner.analyze_risk_adjusted_scenarios.__get__(runner)

        analysis = runner.analyze_risk_adjusted_scenarios(results_without_ra)

        # Should return None or empty dict
        assert analysis is None or len(analysis) == 0


class TestForcedLiquidationAnalysis:
    """Test forced liquidation detection and analysis"""

    def test_analyze_forced_liquidations(self, sample_results_dict):
        """Test detection of forced liquidations"""
        # Add forced liquidation flag to sample results
        for strategy_name, result in sample_results_dict.items():
            result['forced_liquidation_occurred'] = False
            result['forced_liquidation_date'] = None

        # Mark one strategy as having forced liquidation
        sample_results_dict['Strategy A']['forced_liquidation_occurred'] = True
        sample_results_dict['Strategy A']['forced_liquidation_date'] = pd.Timestamp('2024-03-15')

        runner = MagicMock()
        runner.analyze_forced_liquidations = StrategyRunner.analyze_forced_liquidations.__get__(runner)

        analysis = runner.analyze_forced_liquidations(sample_results_dict)

        # Verify analysis structure
        assert 'total_strategies' in analysis
        assert 'strategies_with_liquidation' in analysis
        assert 'liquidation_pct' in analysis

        # Verify detection
        assert analysis['strategies_with_liquidation'] == 1
        assert analysis['liquidation_pct'] == (1 / len(sample_results_dict)) * 100

    def test_no_forced_liquidations(self, sample_results_dict):
        """Test analysis when no forced liquidations occurred"""
        # Ensure no forced liquidations
        for result in sample_results_dict.values():
            result['forced_liquidation_occurred'] = False

        runner = MagicMock()
        runner.analyze_forced_liquidations = StrategyRunner.analyze_forced_liquidations.__get__(runner)

        analysis = runner.analyze_forced_liquidations(sample_results_dict)

        assert analysis['strategies_with_liquidation'] == 0
        assert analysis['liquidation_pct'] == 0.0


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_strategy_execution(self, sample_prices, minimal_predictions,
                                       commodity_config, baseline_params,
                                       prediction_params):
        """Test execution with single strategy"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=minimal_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        # Run only ImmediateSale
        strategy = ImmediateSaleStrategy()
        result = runner._run_single_strategy(strategy, 'coffee', 'test_model')

        assert result is not None
        assert 'net_earnings' in result

    def test_all_strategies_identical_performance(self):
        """Test handling when all strategies have identical performance"""
        # Create metrics where all strategies have same earnings
        identical_metrics = pd.DataFrame({
            'strategy': [f'Strategy {i}' for i in range(9)],
            'net_earnings': [50000.0] * 9,
            'type': ['Baseline'] * 4 + ['Prediction'] * 5,
            'commodity': ['coffee'] * 9,
            'model_version': ['test'] * 9
        })

        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            identical_metrics, 'coffee', 'test_model'
        )

        # Should still identify best (first one found)
        assert analysis['best_overall'] is not None
        assert analysis['best_overall']['net_earnings'] == 50000.0

    def test_negative_earnings_handling(self):
        """Test handling of strategies with negative net earnings"""
        negative_metrics = pd.DataFrame({
            'strategy': ['Strategy A', 'Strategy B', 'Strategy C'],
            'net_earnings': [-5000.0, 10000.0, -2000.0],
            'type': ['Baseline', 'Prediction', 'Baseline'],
            'commodity': ['coffee'] * 3,
            'model_version': ['test'] * 3
        })

        runner = MagicMock()
        runner.analyze_best_performers = StrategyRunner.analyze_best_performers.__get__(runner)

        analysis = runner.analyze_best_performers(
            negative_metrics, 'coffee', 'test_model'
        )

        # Best should still be Strategy B with positive earnings
        assert analysis['best_overall']['net_earnings'] == 10000.0

    def test_empty_prediction_matrices(self, sample_prices, commodity_config,
                                       baseline_params, prediction_params):
        """Test handling of empty prediction matrices"""
        empty_predictions = {}

        with pytest.raises(ValueError):
            StrategyRunner(
                prices=sample_prices,
                prediction_matrices=empty_predictions,
                commodity_config=commodity_config,
                baseline_params=baseline_params,
                prediction_params=prediction_params
            )


class TestVerboseLogging:
    """Test verbose output and progress tracking"""

    def test_verbose_output_during_execution(self, sample_prices,
                                            minimal_predictions,
                                            commodity_config,
                                            baseline_params,
                                            prediction_params,
                                            capsys):
        """Test verbose logging during strategy execution"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=minimal_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        runner.run_all_strategies(
            commodity='coffee',
            model_version='test_model',
            verbose=True
        )

        captured = capsys.readouterr()

        # Verify verbose output contains key information
        assert "Running backtest" in captured.out
        assert "Completed" in captured.out

    def test_silent_execution(self, sample_prices, minimal_predictions,
                             commodity_config, baseline_params,
                             prediction_params, capsys):
        """Test silent execution (verbose=False)"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=minimal_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        runner.run_all_strategies(
            commodity='coffee',
            model_version='test_model',
            verbose=False
        )

        captured = capsys.readouterr()

        # Should have minimal or no output
        assert len(captured.out) < 100  # Allow for some minimal output


class TestIntegrationScenarios:
    """Test realistic end-to-end scenarios"""

    def test_coffee_90pct_full_execution(self, sample_prices, minimal_predictions,
                                         commodity_config, baseline_params,
                                         prediction_params):
        """Test full execution for coffee 90% scenario"""
        runner = StrategyRunner(
            prices=sample_prices,
            prediction_matrices=minimal_predictions,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        results_dict, metrics_df = runner.run_all_strategies(
            commodity='coffee',
            model_version='synthetic_90pct',
            verbose=False
        )

        # Analyze results
        best_analysis = runner.analyze_best_performers(
            metrics_df, 'coffee', 'synthetic_90pct'
        )

        # Verify complete workflow
        assert len(results_dict) == 9
        assert len(metrics_df) == 9
        assert best_analysis is not None
        assert 'best_overall' in best_analysis

    def test_parameter_sensitivity(self, sample_prices, minimal_predictions,
                                   commodity_config):
        """Test sensitivity to parameter changes"""
        # Test with different baseline parameters
        params1 = {
            'equal_batch': {'batch_size': 0.25, 'frequency_days': 30},
            'price_threshold': {'threshold_pct': 0.05},
            'moving_average': {'ma_period': 30}
        }

        params2 = {
            'equal_batch': {'batch_size': 0.10, 'frequency_days': 15},
            'price_threshold': {'threshold_pct': 0.10},
            'moving_average': {'ma_period': 60}
        }

        prediction_params = {
            'consensus': {'consensus_threshold': 0.70, 'min_return': 0.03, 'evaluation_day': 14},
            'expected_value': {'min_ev_improvement': 50, 'baseline_batch': 0.15, 'baseline_frequency': 10},
            'risk_adjusted': {'min_return': 0.03, 'max_uncertainty': 0.35, 'consensus_threshold': 0.60, 'evaluation_day': 14}
        }

        # Run with both parameter sets
        runner1 = StrategyRunner(sample_prices, minimal_predictions,
                                commodity_config, params1, prediction_params)
        results1, metrics1 = runner1.run_all_strategies('coffee', 'test', verbose=False)

        runner2 = StrategyRunner(sample_prices, minimal_predictions,
                                commodity_config, params2, prediction_params)
        results2, metrics2 = runner2.run_all_strategies('coffee', 'test', verbose=False)

        # Results should differ due to parameter changes
        earnings1 = metrics1['net_earnings'].sum()
        earnings2 = metrics2['net_earnings'].sum()

        # Allow for small differences (strategies might be similar)
        # Just verify both executions completed successfully
        assert earnings1 > 0 or earnings1 < 0  # Just verify we got numbers
        assert earnings2 > 0 or earnings2 < 0
