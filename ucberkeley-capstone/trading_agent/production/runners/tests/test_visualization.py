"""
Unit Tests for VisualizationGenerator Module
Tests chart generation and visual outputs
"""

import pytest
import pandas as pd
import numpy as np
import os
from unittest.mock import MagicMock, patch
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for testing


from production.runners.visualization import VisualizationGenerator


class TestVisualizationGeneratorInitialization:
    """Test VisualizationGenerator initialization"""

    def test_initialization(self, temp_volume):
        """Test successful initialization"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        assert viz_gen.volume_path == temp_volume
        assert viz_gen.output_organized is False  # Default

    def test_initialization_with_organized_output(self, temp_volume):
        """Test initialization with organized directory structure"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        assert viz_gen.output_organized is True

    def test_initialization_creates_directories(self, temp_volume):
        """Test initialization creates necessary directories"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        # Verify subdirectories created
        assert os.path.exists(os.path.join(temp_volume, 'performance'))
        assert os.path.exists(os.path.join(temp_volume, 'timelines'))


class TestNetEarningsChart:
    """Test net earnings bar chart generation"""

    def test_generate_net_earnings_chart(self, sample_metrics_df, temp_volume):
        """Test generating net earnings bar chart"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_net_earnings_chart(
            commodity='coffee',
            model_version='test_model',
            metrics_df=sample_metrics_df,
            verbose=False
        )

        # Verify chart saved
        assert chart_path is not None
        assert os.path.exists(chart_path)
        assert chart_path.endswith('.png')
        assert 'net_earnings' in chart_path

    def test_net_earnings_chart_with_organized_output(self, sample_metrics_df,
                                                      temp_volume):
        """Test chart saved to performance/ subdirectory"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_path = viz_gen.generate_net_earnings_chart(
            commodity='coffee',
            model_version='test_model',
            metrics_df=sample_metrics_df,
            verbose=False
        )

        # Verify saved to performance/ subdirectory
        assert 'performance' in chart_path

    def test_net_earnings_chart_handles_empty_data(self, temp_volume):
        """Test handling of empty metrics DataFrame"""
        empty_df = pd.DataFrame(columns=['strategy', 'net_earnings', 'type'])

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        with pytest.raises(ValueError, match="Empty metrics DataFrame"):
            viz_gen.generate_net_earnings_chart(
                'coffee', 'test', empty_df, verbose=False
            )

    def test_net_earnings_chart_file_format(self, sample_metrics_df, temp_volume):
        """Test chart file format and naming"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_net_earnings_chart(
            'coffee', 'synthetic_90pct', sample_metrics_df, verbose=False
        )

        # Verify naming pattern
        assert 'net_earnings' in chart_path
        assert 'coffee' in chart_path
        assert 'synthetic_90pct' in chart_path
        assert chart_path.endswith('.png')


class TestTradingTimelineChart:
    """Test trading timeline scatter plot generation"""

    def test_generate_trading_timeline(self, sample_results_dict,
                                       sample_prices, temp_volume):
        """Test generating trading timeline chart"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_trading_timeline(
            commodity='coffee',
            model_version='test_model',
            results_dict=sample_results_dict,
            prices=sample_prices,
            baseline_strategies=['Strategy B'],
            verbose=False
        )

        # Verify chart saved
        assert chart_path is not None
        assert os.path.exists(chart_path)
        assert 'trading_timeline' in chart_path

    def test_trading_timeline_with_no_trades(self, sample_prices, temp_volume):
        """Test timeline when strategies made no trades"""
        # Create results with no trades
        no_trades_results = {
            'Strategy A': {
                'strategy_name': 'Strategy A',
                'trades': [],  # Empty
                'daily_state': pd.DataFrame({
                    'day': range(100),
                    'date': pd.date_range('2024-01-01', periods=100),
                    'inventory': [50] * 100
                })
            }
        }

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        # Should handle gracefully (empty chart or skip)
        chart_path = viz_gen.generate_trading_timeline(
            'coffee', 'test', no_trades_results, sample_prices,
            baseline_strategies=[], verbose=False
        )

        # Chart should still be created
        assert chart_path is not None
        assert os.path.exists(chart_path)

    def test_trading_timeline_organized_output(self, sample_results_dict,
                                               sample_prices, temp_volume):
        """Test timeline saved to timelines/ subdirectory"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_path = viz_gen.generate_trading_timeline(
            'coffee', 'test', sample_results_dict, sample_prices,
            baseline_strategies=['Strategy B'], verbose=False
        )

        assert 'timelines' in chart_path


class TestTotalRevenueChart:
    """Test total revenue (without costs) chart generation"""

    def test_generate_total_revenue_chart(self, sample_results_dict, temp_volume):
        """Test generating total revenue chart"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_total_revenue_chart(
            commodity='coffee',
            model_version='test_model',
            results_dict=sample_results_dict,
            verbose=False
        )

        # Verify chart saved
        assert chart_path is not None
        assert os.path.exists(chart_path)
        assert 'total_revenue' in chart_path or 'no_costs' in chart_path

    def test_total_revenue_with_organized_output(self, sample_results_dict,
                                                 temp_volume):
        """Test revenue chart saved to performance/ subdirectory"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_path = viz_gen.generate_total_revenue_chart(
            'coffee', 'test', sample_results_dict, verbose=False
        )

        assert 'performance' in chart_path


class TestCumulativeReturnsChart:
    """Test cumulative net revenue (with costs) chart generation"""

    def test_generate_cumulative_returns_chart(self, sample_results_dict,
                                               temp_volume):
        """Test generating cumulative returns chart"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_cumulative_returns_chart(
            commodity='coffee',
            model_version='test_model',
            results_dict=sample_results_dict,
            verbose=False
        )

        # Verify chart saved
        assert chart_path is not None
        assert os.path.exists(chart_path)
        assert 'cumulative' in chart_path or 'returns' in chart_path

    def test_cumulative_returns_organized_output(self, sample_results_dict,
                                                 temp_volume):
        """Test cumulative returns saved to performance/ subdirectory"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_path = viz_gen.generate_cumulative_returns_chart(
            'coffee', 'test', sample_results_dict, verbose=False
        )

        assert 'performance' in chart_path


class TestInventoryDrawdownChart:
    """Test inventory drawdown chart generation"""

    def test_generate_inventory_drawdown_chart(self, sample_results_dict,
                                               temp_volume):
        """Test generating inventory drawdown chart"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_inventory_drawdown_chart(
            commodity='coffee',
            model_version='test_model',
            results_dict=sample_results_dict,
            verbose=False
        )

        # Verify chart saved
        assert chart_path is not None
        assert os.path.exists(chart_path)
        assert 'inventory' in chart_path or 'drawdown' in chart_path

    def test_inventory_drawdown_organized_output(self, sample_results_dict,
                                                 temp_volume):
        """Test inventory chart saved to timelines/ subdirectory"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_path = viz_gen.generate_inventory_drawdown_chart(
            'coffee', 'test', sample_results_dict, verbose=False
        )

        assert 'timelines' in chart_path


class TestGenerateAllCharts:
    """Test generating all charts at once"""

    def test_generate_all_charts(self, sample_metrics_df, sample_results_dict,
                                 sample_prices, temp_volume):
        """Test generating all 5 chart types"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_paths = viz_gen.generate_all_charts(
            commodity='coffee',
            model_version='test_model',
            results_df=sample_metrics_df,
            results_dict=sample_results_dict,
            prices=sample_prices,
            baseline_strategies=['Strategy B'],
            verbose=False
        )

        # Verify all 5 charts generated
        assert len(chart_paths) == 5
        assert 'net_earnings' in chart_paths
        assert 'trading_timeline' in chart_paths
        assert 'total_revenue' in chart_paths
        assert 'cumulative_returns' in chart_paths
        assert 'inventory_drawdown' in chart_paths

        # Verify all files exist
        for chart_type, path in chart_paths.items():
            assert os.path.exists(path), f"Chart {chart_type} not found at {path}"

    def test_generate_all_charts_with_organized_output(self, sample_metrics_df,
                                                       sample_results_dict,
                                                       sample_prices,
                                                       temp_volume):
        """Test all charts with organized directory structure"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_paths = viz_gen.generate_all_charts(
            'coffee', 'test', sample_metrics_df, sample_results_dict,
            sample_prices, ['Strategy B'], verbose=False
        )

        # Verify charts distributed across subdirectories
        performance_charts = [p for p in chart_paths.values() if 'performance' in p]
        timeline_charts = [p for p in chart_paths.values() if 'timelines' in p]

        assert len(performance_charts) > 0
        assert len(timeline_charts) > 0


class TestCrossCommodityComparison:
    """Test cross-commodity comparison charts"""

    def test_generate_cross_commodity_comparison(self, temp_volume):
        """Test generating cross-commodity comparison charts"""
        # Create sample comparison DataFrame
        comparison_df = pd.DataFrame({
            'commodity': ['coffee', 'coffee', 'sugar', 'sugar'],
            'model_version': ['synthetic_90pct', 'synthetic_80pct',
                             'synthetic_90pct', 'synthetic_80pct'],
            'best_strategy': ['Consensus', 'Expected Value',
                             'Risk-Adjusted', 'Consensus'],
            'net_earnings': [50000, 45000, 35000, 32000],
            'prediction_advantage_pct': [15.5, 12.3, 8.7, 6.5]
        })

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_paths = viz_gen.generate_cross_commodity_comparison(
            comparison_df,
            verbose=False
        )

        # Verify comparison charts generated
        assert isinstance(chart_paths, dict)
        assert len(chart_paths) > 0

        # Verify files exist
        for chart_path in chart_paths.values():
            assert os.path.exists(chart_path)

    def test_cross_commodity_with_single_commodity(self, temp_volume):
        """Test cross-commodity charts with only one commodity"""
        single_commodity_df = pd.DataFrame({
            'commodity': ['coffee'],
            'model_version': ['synthetic_90pct'],
            'best_strategy': ['Consensus'],
            'net_earnings': [50000],
            'prediction_advantage_pct': [15.5]
        })

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        # Should handle single commodity gracefully
        chart_paths = viz_gen.generate_cross_commodity_comparison(
            single_commodity_df,
            verbose=False
        )

        assert chart_paths is not None


class TestChartCustomization:
    """Test chart styling and customization"""

    def test_chart_dimensions(self, sample_metrics_df, temp_volume):
        """Test charts have reasonable dimensions"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_net_earnings_chart(
            'coffee', 'test', sample_metrics_df, verbose=False
        )

        # Verify file size indicates actual chart (not empty)
        file_size = os.path.getsize(chart_path)
        assert file_size > 1000  # At least 1KB

    def test_chart_format(self, sample_metrics_df, temp_volume):
        """Test charts saved in correct format"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_path = viz_gen.generate_net_earnings_chart(
            'coffee', 'test', sample_metrics_df, verbose=False
        )

        # Verify PNG format
        assert chart_path.endswith('.png')

        # Verify file is valid PNG (starts with PNG signature)
        with open(chart_path, 'rb') as f:
            header = f.read(8)
            assert header[:4] == b'\x89PNG'


class TestErrorHandling:
    """Test error handling in visualization"""

    def test_handles_missing_columns(self, temp_volume):
        """Test handling of DataFrame missing required columns"""
        bad_df = pd.DataFrame({
            'wrong_column': ['Strategy A'],
            'other_column': [50000]
        })

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        with pytest.raises(ValueError):
            viz_gen.generate_net_earnings_chart(
                'coffee', 'test', bad_df, verbose=False
            )

    def test_handles_invalid_path(self):
        """Test handling of invalid volume path"""
        viz_gen = VisualizationGenerator(volume_path='/nonexistent/path')

        # Should raise error when trying to save
        with pytest.raises(Exception):
            viz_gen.generate_net_earnings_chart(
                'coffee', 'test', pd.DataFrame(), verbose=False
            )

    def test_handles_corrupt_data(self, temp_volume):
        """Test handling of corrupt result data"""
        corrupt_results = {
            'Strategy A': {
                'trades': 'invalid',  # Should be list
                'daily_state': 'invalid'  # Should be DataFrame
            }
        }

        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        with pytest.raises(Exception):
            viz_gen.generate_trading_timeline(
                'coffee', 'test', corrupt_results, pd.DataFrame(),
                baseline_strategies=[], verbose=False
            )


class TestVerboseLogging:
    """Test verbose output during chart generation"""

    def test_verbose_output(self, sample_metrics_df, temp_volume, capsys):
        """Test verbose logging during chart generation"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        viz_gen.generate_net_earnings_chart(
            'coffee', 'test', sample_metrics_df, verbose=True
        )

        captured = capsys.readouterr()

        # Verify some output produced
        assert len(captured.out) > 0

    def test_silent_generation(self, sample_metrics_df, temp_volume, capsys):
        """Test silent chart generation (verbose=False)"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        viz_gen.generate_net_earnings_chart(
            'coffee', 'test', sample_metrics_df, verbose=False
        )

        captured = capsys.readouterr()

        # Should have minimal or no output
        assert len(captured.out) < 100


class TestIntegrationScenarios:
    """Test realistic visualization scenarios"""

    def test_coffee_90pct_full_visualization(self, sample_metrics_df,
                                             sample_results_dict,
                                             sample_prices, temp_volume):
        """Test complete visualization for coffee 90% scenario"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        chart_paths = viz_gen.generate_all_charts(
            commodity='coffee',
            model_version='synthetic_90pct',
            results_df=sample_metrics_df,
            results_dict=sample_results_dict,
            prices=sample_prices,
            baseline_strategies=['Strategy B'],
            verbose=False
        )

        # Verify all charts created
        assert len(chart_paths) == 5

        # Verify realistic file sizes
        for chart_path in chart_paths.values():
            file_size = os.path.getsize(chart_path)
            assert file_size > 1000  # At least 1KB
            assert file_size < 10_000_000  # Less than 10MB

    def test_multiple_commodities_visualization(self, sample_metrics_df,
                                                sample_results_dict,
                                                sample_prices, temp_volume):
        """Test generating charts for multiple commodities"""
        viz_gen = VisualizationGenerator(volume_path=temp_volume)

        # Generate for coffee
        coffee_paths = viz_gen.generate_all_charts(
            'coffee', 'synthetic_90pct', sample_metrics_df,
            sample_results_dict, sample_prices, ['Strategy B'],
            verbose=False
        )

        # Generate for sugar (reuse same data for test)
        sugar_paths = viz_gen.generate_all_charts(
            'sugar', 'synthetic_90pct', sample_metrics_df,
            sample_results_dict, sample_prices, ['Strategy B'],
            verbose=False
        )

        # Verify separate files created
        assert len(coffee_paths) == 5
        assert len(sugar_paths) == 5

        # Verify different filenames
        for coffee_path in coffee_paths.values():
            assert 'coffee' in coffee_path

        for sugar_path in sugar_paths.values():
            assert 'sugar' in sugar_path

    def test_organized_output_structure(self, sample_metrics_df,
                                        sample_results_dict,
                                        sample_prices, temp_volume):
        """Test Phase 3 organized directory structure"""
        viz_gen = VisualizationGenerator(
            volume_path=temp_volume,
            output_organized=True
        )

        chart_paths = viz_gen.generate_all_charts(
            'coffee', 'synthetic_90pct', sample_metrics_df,
            sample_results_dict, sample_prices, ['Strategy B'],
            verbose=False
        )

        # Verify subdirectories exist
        assert os.path.exists(os.path.join(temp_volume, 'performance'))
        assert os.path.exists(os.path.join(temp_volume, 'timelines'))

        # Verify charts in correct subdirectories
        performance_dir = os.path.join(temp_volume, 'performance')
        timelines_dir = os.path.join(temp_volume, 'timelines')

        performance_charts = [
            f for f in os.listdir(performance_dir)
            if f.endswith('.png')
        ]
        timeline_charts = [
            f for f in os.listdir(timelines_dir)
            if f.endswith('.png')
        ]

        assert len(performance_charts) > 0
        assert len(timeline_charts) > 0
