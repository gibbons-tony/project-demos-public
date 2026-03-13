"""
Multi-Commodity Runner
Main orchestrator for running backtests across all commodities and models

Replicates notebook 05 workflow in modular, automation-ready format
"""

import pandas as pd
import json
import os
from typing import Dict, List, Any, Optional, Tuple

# Import production modules
from .data_loader import DataLoader
from .strategy_runner import StrategyRunner
from .visualization import VisualizationGenerator
from .result_saver import ResultSaver


class MultiCommodityRunner:
    """Orchestrates backtest execution across all commodity-model combinations"""

    def __init__(
        self,
        spark,
        commodity_configs: Dict[str, Any],
        baseline_params: Dict[str, Any] = None,
        prediction_params: Dict[str, Any] = None,
        volume_path: str = "/Volumes/commodity/trading_agent/files",
        output_schema: str = "commodity.trading_agent",
        use_optimized_params: bool = False,
        optimization_objective: str = 'efficiency',
        run_statistical_tests: bool = True
    ):
        """
        Initialize multi-commodity runner

        Args:
            spark: Spark session
            commodity_configs: Dictionary of commodity configurations
            baseline_params: Baseline strategy parameters (None = auto-load per commodity)
            prediction_params: Prediction strategy parameters (None = auto-load per commodity)
            volume_path: Base path for file storage
            output_schema: Unity Catalog schema for Delta tables
            use_optimized_params: If True, automatically load optimized parameters when available
            optimization_objective: Which optimization objective to use ('efficiency', 'earnings', 'multi')
            run_statistical_tests: If True, run statistical validation after backtests
        """
        self.spark = spark
        self.commodity_configs = commodity_configs
        self.baseline_params = baseline_params
        self.prediction_params = prediction_params
        self.volume_path = volume_path
        self.output_schema = output_schema
        self.use_optimized_params = use_optimized_params
        self.optimization_objective = optimization_objective
        self.run_statistical_tests = run_statistical_tests

        # Initialize sub-modules
        self.data_loader = DataLoader(spark=spark, volume_path=volume_path)
        self.viz_generator = VisualizationGenerator(volume_path=volume_path)
        self.result_saver = ResultSaver(spark=spark)

        # Initialize statistical analyzer (if enabled)
        if self.run_statistical_tests:
            from production.analysis import StatisticalAnalyzer
            self.statistical_analyzer = StatisticalAnalyzer(spark=spark)
        else:
            self.statistical_analyzer = None

        # Storage for all results
        self.all_commodity_results = {}
        self.all_statistical_results = {}

    def run_all_commodities(
        self,
        commodities: Optional[List[str]] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run backtest analysis for all commodities and model versions

        Args:
            commodities: List of commodities to analyze (None = all)
            verbose: Print progress messages

        Returns:
            Dictionary with all results
        """
        # Determine which commodities to process
        if commodities is None:
            commodities = list(self.commodity_configs.keys())

        print("\n" + "=" * 80)
        print("STARTING MULTI-COMMODITY BACKTEST ANALYSIS")
        print("=" * 80)
        print(f"\nCommodities to analyze: {', '.join([c.upper() for c in commodities])}")

        # Process each commodity
        for commodity in commodities:
            self.all_commodity_results[commodity] = {}

            print("\n" + "=" * 80)
            print(f"STARTING ANALYSIS FOR: {commodity.upper()}")
            print("=" * 80)

            # Get commodity configuration
            commodity_config = self.commodity_configs[commodity]

            # Discover all model versions
            model_versions = self._discover_model_versions(commodity)

            if len(model_versions) == 0:
                print(f"\n⚠️  No model versions found for {commodity}")
                continue

            print(f"\n✓ Found {len(model_versions)} model versions for {commodity}")

            # Process each model version
            for model_idx, model_version in enumerate(model_versions, 1):
                print("\n" + "#" * 80)
                print(f"# MODEL {model_idx}/{len(model_versions)}: {commodity.upper()} - {model_version}")
                print("#" * 80)

                try:
                    # Run single commodity-model pair
                    results = self._run_single_commodity_model(
                        commodity, model_version, commodity_config, verbose
                    )

                    # Store results
                    self.all_commodity_results[commodity][model_version] = results

                    print(f"\n✓ Analysis complete for {commodity.upper()} - {model_version}")

                except Exception as e:
                    print(f"\n❌ Error processing {commodity} - {model_version}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

        print("\n" + "=" * 80)
        print("ALL COMMODITY ANALYSES COMPLETE")
        print("=" * 80)

        # Generate cross-commodity comparison
        if verbose:
            self._generate_cross_commodity_comparison()

        # Run statistical validation if enabled
        if self.run_statistical_tests and self.statistical_analyzer is not None:
            print("\n" + "=" * 80)
            print("RUNNING STATISTICAL VALIDATION")
            print("=" * 80)
            self._run_statistical_validation(verbose)

        return self.all_commodity_results

    def _discover_model_versions(self, commodity: str) -> List[str]:
        """
        Discover model versions for a commodity from forecast manifest

        The manifest is created by load_forecast_predictions and contains only
        models that passed quality checks (sufficient coverage and date range).
        This ensures we only backtest models with adequate prediction data.

        Args:
            commodity: Commodity name

        Returns:
            List of model version identifiers from manifest
        """
        manifest_path = os.path.join(self.volume_path, f'forecast_manifest_{commodity}.json')

        try:
            # Read manifest file created by load_forecast_predictions
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Extract model names from manifest
            if 'models' in manifest and manifest['models']:
                model_versions = list(manifest['models'].keys())
                print(f"  ✓ Loaded {len(model_versions)} models from manifest: {model_versions}")
                return model_versions
            else:
                print(f"  ⚠️  Manifest exists but contains no models")
                return []

        except FileNotFoundError:
            print(f"  ⚠️  Manifest not found: {manifest_path}")
            print(f"  ℹ️  Run load_forecast_predictions first to generate manifest")
            return []
        except Exception as e:
            print(f"  ✗ Error reading manifest: {e}")
            print(f"  ℹ️  Falling back to database discovery...")
            # Fallback to old method if manifest can't be read
            synthetic_versions, real_versions = self.data_loader.discover_model_versions(commodity)
            all_versions = list(set(synthetic_versions + real_versions))
            return all_versions

    def _run_single_commodity_model(
        self,
        commodity: str,
        model_version: str,
        commodity_config: Dict[str, Any],
        verbose: bool
    ) -> Dict[str, Any]:
        """
        Run backtest for a single commodity-model pair

        Args:
            commodity: Commodity name
            model_version: Model version
            commodity_config: Commodity configuration
            verbose: Print messages

        Returns:
            Dictionary with all results for this pair
        """
        # Get data paths
        data_paths = self._get_data_paths(commodity, model_version)

        # 1. Load data
        prices, prediction_matrices = self.data_loader.load_commodity_data(
            commodity, model_version, data_paths
        )

        # 2. Load parameters for this commodity-model pair
        baseline_params, prediction_params = self._get_parameters_for_commodity(
            commodity, model_version, verbose
        )

        # 3. Run strategies
        strategy_runner = StrategyRunner(
            prices=prices,
            prediction_matrices=prediction_matrices,
            commodity_config=commodity_config,
            baseline_params=baseline_params,
            prediction_params=prediction_params
        )

        results_dict, metrics_df, metrics_by_year_df, metrics_by_quarter_df, metrics_by_month_df = strategy_runner.run_all_strategies(
            commodity, model_version, verbose
        )

        # 3. Analyze best performers
        analysis = strategy_runner.analyze_best_performers(
            metrics_df, commodity, model_version, verbose
        )

        # 4. Analyze scenarios (if applicable)
        scenario_analysis = strategy_runner.analyze_risk_adjusted_scenarios(
            results_dict, verbose
        )

        # 5. Analyze forced liquidations
        liquidation_analysis = strategy_runner.analyze_forced_liquidations(
            results_dict, commodity_config, verbose
        )

        # 6. Generate visualizations
        baseline_strategies = [
            'Immediate Sale', 'Equal Batches', 'Price Threshold', 'Moving Average'
        ]
        chart_paths = self.viz_generator.generate_all_charts(
            commodity=commodity,
            model_version=model_version,
            results_df=metrics_df,
            results_dict=results_dict,
            prices=prices,
            baseline_strategies=baseline_strategies,
            output_organized=False  # Set to True for Phase 3 organized structure
        )

        # 7. Save results (including year/quarter/month metrics)
        saved_paths = self.result_saver.save_results(
            commodity=commodity,
            model_version=model_version,
            metrics_df=metrics_df,
            results_dict=results_dict,
            data_paths=data_paths,
            metrics_by_year_df=metrics_by_year_df,
            metrics_by_quarter_df=metrics_by_quarter_df,
            metrics_by_month_df=metrics_by_month_df,
            verbose=verbose
        )

        # 8. Validate results
        self.result_saver.validate_results(metrics_df, results_dict)

        # Return comprehensive results
        return {
            'commodity': commodity,
            'model_version': model_version,
            'results_df': metrics_df,
            'results_by_year_df': metrics_by_year_df,
            'results_by_quarter_df': metrics_by_quarter_df,
            'results_by_month_df': metrics_by_month_df,
            'results_dict': results_dict,
            'best_baseline': analysis['best_baseline'],
            'best_prediction': analysis['best_prediction'],
            'best_overall': analysis['best_overall'],
            'earnings_diff': analysis['earnings_diff'],
            'pct_diff': analysis['pct_diff'],
            'prices': prices,
            'config': commodity_config,
            'scenario_analysis': scenario_analysis,
            'liquidation_analysis': liquidation_analysis,
            'chart_paths': chart_paths,
            'saved_paths': saved_paths
        }

    def _generate_cross_commodity_comparison(self) -> None:
        """Generate cross-commodity/model comparison analysis"""
        print("\n" + "=" * 80)
        print("CROSS-MODEL AND CROSS-COMMODITY COMPARISON")
        print("=" * 80)

        # Create consolidated DataFrames
        comparison_df = self.result_saver.create_consolidated_summary(
            self.all_commodity_results, verbose=True
        )

        detailed_df = self.result_saver.create_detailed_results_df(
            self.all_commodity_results
        )

        # Save comparison results
        self.result_saver.save_cross_commodity_results(
            comparison_df, detailed_df, self.volume_path, verbose=True
        )

        # Generate comparison charts
        chart_paths = self.viz_generator.generate_cross_commodity_comparison(
            comparison_df, self.volume_path
        )

        print("\n✓ Cross-commodity/model analysis complete")

    def _get_parameters_for_commodity(
        self,
        commodity: str,
        model_version: str,
        verbose: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Get strategy parameters for a commodity-model pair.

        Intelligently loads from optimized parameters if available and enabled,
        otherwise falls back to defaults or passed-in parameters.

        Args:
            commodity: Commodity name
            model_version: Model version
            verbose: Print parameter source info

        Returns:
            Tuple of (baseline_params, prediction_params)
        """
        # If parameters were explicitly provided in constructor, use those
        if self.baseline_params is not None and self.prediction_params is not None:
            if verbose:
                print(f"\nUsing explicitly provided parameters for {commodity}/{model_version}")
            return self.baseline_params, self.prediction_params

        # Otherwise, use ParameterManager for intelligent loading
        if self.use_optimized_params:
            from production.parameter_manager import get_params_for_backtest

            if verbose:
                print(f"\nLoading parameters for {commodity}/{model_version}...")
                print(f"  Optimization objective: {self.optimization_objective}")
                print(f"  Parameter source: AUTO (optimized if available, else default)")

            params = get_params_for_backtest(
                commodity=commodity,
                model_version=model_version,
                optimization_objective=self.optimization_objective,
                source='auto',
                verbose=verbose
            )

            return params['baseline'], params['prediction']

        else:
            # Use defaults from config
            from production.config import BASELINE_PARAMS, PREDICTION_PARAMS

            if verbose:
                print(f"\nUsing default parameters for {commodity}/{model_version}")

            return BASELINE_PARAMS.copy(), PREDICTION_PARAMS.copy()

    def _get_data_paths(self, commodity: str, model_version: str) -> Dict[str, Any]:
        """
        Generate data paths for a commodity-model pair

        Args:
            commodity: Commodity name
            model_version: Model version

        Returns:
            Dictionary of data paths
        """
        # Clean model version for file/table names
        model_suffix = f"_{model_version.replace('.', '_')}" if model_version else ""

        return {
            # Delta tables
            'historical_prices': f'{self.output_schema}.historical_prices_{commodity.lower()}',
            'predictions': f'{self.output_schema}.predictions_{commodity.lower()}{model_suffix}',
            'prices_prepared': f'{self.output_schema}.prices_prepared_{commodity.lower()}',
            'predictions_prepared': f'{self.output_schema}.predictions_prepared_{commodity.lower()}{model_suffix}',
            'results': f'{self.output_schema}.results_{commodity.lower()}{model_suffix}',

            # Binary files
            'prediction_matrices': f'{self.volume_path}/prediction_matrices_{commodity.lower()}{model_suffix}.pkl',
            'prediction_matrices_real': f'{self.volume_path}/prediction_matrices_{commodity.lower()}{model_suffix}_real.pkl',
            'results_detailed': f'{self.volume_path}/results_detailed_{commodity.lower()}{model_suffix}.pkl',

            # Images
            'cumulative_returns': f'{self.volume_path}/cumulative_returns_{commodity.lower()}{model_suffix}.png',

            # CSV exports
            'final_summary': f'{self.volume_path}/final_summary_{commodity.lower()}{model_suffix}.csv'
        }

    def _run_statistical_validation(self, verbose: bool = True) -> None:
        """Run statistical validation for all commodity-model combinations"""
        for commodity in self.all_commodity_results:
            for model_version in self.all_commodity_results[commodity]:
                try:
                    if verbose:
                        print(f"\n{'#' * 80}")
                        print(f"# Statistical Tests: {commodity.upper()} - {model_version}")
                        print(f"{'#' * 80}")

                    # Run full statistical analysis
                    stats_results = self.statistical_analyzer.run_full_analysis(
                        commodity=commodity,
                        model_version=model_version,
                        primary_baseline="Immediate Sale",
                        verbose=verbose
                    )

                    # Save results
                    self.statistical_analyzer.save_results(
                        results=stats_results,
                        save_to_delta=True
                    )

                    # Store in memory
                    if commodity not in self.all_statistical_results:
                        self.all_statistical_results[commodity] = {}
                    self.all_statistical_results[commodity][model_version] = stats_results

                except Exception as e:
                    print(f"\n⚠️  Error running statistical tests for {commodity}/{model_version}: {e}")
                    import traceback
                    traceback.print_exc()

        print(f"\n✓ Statistical validation complete for {len(self.all_statistical_results)} commodities")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for all processed commodities

        Returns:
            Dictionary with summary information
        """
        summary = {
            'total_commodities': len(self.all_commodity_results),
            'total_combinations': sum(
                len(models) for models in self.all_commodity_results.values()
            ),
            'commodities': list(self.all_commodity_results.keys()),
            'statistical_tests_run': len(self.all_statistical_results) > 0
        }

        # Add per-commodity counts
        for commodity, model_data in self.all_commodity_results.items():
            summary[f'{commodity}_models'] = len(model_data)

        # Add statistical summary if available
        if self.all_statistical_results:
            summary['statistical_summary'] = {}
            for commodity, models in self.all_statistical_results.items():
                summary['statistical_summary'][commodity] = {
                    'models_tested': len(models),
                    'models': list(models.keys())
                }

        return summary


def main():
    """
    Example usage - can be called from Databricks notebook or as script

    Usage in notebook:
        from production.runners.multi_commodity_runner import main
        results = main()
    """
    # Import all parameters from production.config
    from production.config import COMMODITY_CONFIGS, BASELINE_PARAMS, PREDICTION_PARAMS

    # Initialize runner (assuming spark is available)
    runner = MultiCommodityRunner(
        spark=spark,  # noqa: F821 (spark session from Databricks)
        commodity_configs=COMMODITY_CONFIGS,
        baseline_params=BASELINE_PARAMS,
        prediction_params=PREDICTION_PARAMS
    )

    # Run all commodities
    results = runner.run_all_commodities()

    # Print summary
    summary = runner.get_summary()
    print("\n" + "=" * 80)
    print("EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Total commodities processed: {summary['total_commodities']}")
    print(f"Total commodity-model combinations: {summary['total_combinations']}")

    return results


if __name__ == "__main__":
    main()
