#!/usr/bin/env python3
"""
Grid Search for Trading Strategy Parameter Optimization

This script performs a grid search to find optimal parameter values that maximize
net revenue for each trading strategy. It ensures that matched pairs (baseline vs
predictive versions) share the same parameters, differing only in prediction usage.

Usage:
    python parameter_grid_search.py --commodity coffee --model sarimax_auto_weather_v1

Output:
    - optimal_parameters.json: Best parameter values for each strategy
    - grid_search_results.csv: Complete results for all tested combinations
    - grid_search_report.txt: Summary report with recommendations
"""

import sys
import os
import argparse
import json
import itertools
from datetime import datetime
from typing import Dict, List, Tuple, Any
import pandas as pd
import numpy as np

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import strategy classes (will need to be imported from notebook code)
# For now, we'll structure this to work with the existing notebook code


# ==============================================================================
# PARAMETER GRIDS
# ==============================================================================

def get_parameter_grids():
    """
    Define parameter ranges to test for each strategy.

    Returns:
        dict: Parameter grids for each strategy type
    """
    return {
        'immediate_sale': {
            'min_batch_size': [3.0, 5.0, 7.0, 10.0],
            'sale_frequency_days': [5, 7, 10, 14]
        },
        'equal_batch': {
            'batch_size': [0.15, 0.20, 0.25, 0.30, 0.35],
            'frequency_days': [20, 25, 30, 35, 40]
        },
        'price_threshold': {
            # Matched pair parameters (shared with PriceThresholdPredictive)
            'threshold_pct': [0.02, 0.03, 0.05, 0.07, 0.10],
            'batch_fraction': [0.20, 0.25, 0.30, 0.35],
            'max_days_without_sale': [45, 60, 75, 90]
        },
        'moving_average': {
            # Matched pair parameters (shared with MovingAveragePredictive)
            'ma_period': [20, 25, 30, 35, 40],
            'batch_fraction': [0.20, 0.25, 0.30, 0.35],
            'max_days_without_sale': [45, 60, 75, 90]
        },
        'consensus': {
            'consensus_threshold': [0.60, 0.65, 0.70, 0.75, 0.80],
            'min_return': [0.02, 0.03, 0.04, 0.05],
            'evaluation_day': [10, 12, 14]
        },
        'expected_value': {
            'min_ev_improvement': [30, 40, 50, 60, 75],
            'baseline_batch': [0.10, 0.12, 0.15, 0.18, 0.20],
            'baseline_frequency': [7, 10, 12, 14]
        },
        'risk_adjusted': {
            'min_return': [0.02, 0.03, 0.04, 0.05],
            'max_uncertainty': [0.25, 0.30, 0.35, 0.40],
            'consensus_threshold': [0.55, 0.60, 0.65, 0.70],
            'evaluation_day': [10, 12, 14]
        }
    }


def get_fine_grained_grids():
    """
    Define finer-grained parameter ranges for focused search around optimal values.
    Use this after initial grid search identifies promising ranges.

    Returns:
        dict: Fine-grained parameter grids
    """
    return {
        'price_threshold': {
            'threshold_pct': [0.03, 0.04, 0.05, 0.06, 0.07],
            'batch_fraction': [0.22, 0.25, 0.28, 0.30, 0.32],
            'max_days_without_sale': [50, 55, 60, 65, 70]
        },
        'moving_average': {
            'ma_period': [25, 28, 30, 32, 35],
            'batch_fraction': [0.22, 0.25, 0.28, 0.30, 0.32],
            'max_days_without_sale': [50, 55, 60, 65, 70]
        },
        # Add other strategies as needed
    }


# ==============================================================================
# GRID SEARCH ENGINE
# ==============================================================================

class GridSearchEngine:
    """
    Orchestrates grid search across all strategy parameters.
    """

    def __init__(self, backtest_engine, prices, prediction_matrices,
                 commodity_config, use_fine_grain=False):
        """
        Initialize grid search engine.

        Args:
            backtest_engine: BacktestEngine class
            prices: DataFrame with historical prices
            prediction_matrices: Dict of prediction matrices
            commodity_config: Commodity configuration dict
            use_fine_grain: If True, use fine-grained parameter ranges
        """
        self.backtest_engine = backtest_engine
        self.prices = prices
        self.prediction_matrices = prediction_matrices
        self.commodity_config = commodity_config

        # Get parameter grids
        if use_fine_grain:
            self.param_grids = get_fine_grained_grids()
        else:
            self.param_grids = get_parameter_grids()

        # Storage for results
        self.all_results = []
        self.optimal_params = {}

    def run_grid_search(self, strategy_names=None, max_combinations_per_strategy=None):
        """
        Run grid search for specified strategies.

        Args:
            strategy_names: List of strategy names to optimize, or None for all
            max_combinations_per_strategy: Limit number of combinations per strategy

        Returns:
            dict: Optimal parameters for each strategy
        """
        if strategy_names is None:
            strategy_names = list(self.param_grids.keys())

        print("=" * 80)
        print("GRID SEARCH FOR OPTIMAL TRADING PARAMETERS")
        print("=" * 80)
        print(f"\nStrategies to optimize: {', '.join(strategy_names)}")
        print(f"Commodity: {self.commodity_config.get('commodity', 'Unknown')}")
        print(f"Prediction matrices: {len(self.prediction_matrices)} dates")
        print(f"Price history: {len(self.prices)} days")

        # Calculate total combinations
        total_combinations = 0
        for strategy_name in strategy_names:
            if strategy_name in self.param_grids:
                grid = self.param_grids[strategy_name]
                n_combos = np.prod([len(v) for v in grid.values()])
                total_combinations += n_combos
                print(f"\n{strategy_name}:")
                print(f"  Parameters: {list(grid.keys())}")
                print(f"  Combinations: {n_combos:,}")

        print(f"\nTotal combinations to test: {total_combinations:,}")

        if max_combinations_per_strategy:
            print(f"Limited to {max_combinations_per_strategy} per strategy")

        # Run grid search for each strategy
        for strategy_name in strategy_names:
            if strategy_name not in self.param_grids:
                print(f"\n⚠️  No parameter grid defined for {strategy_name}, skipping")
                continue

            print(f"\n{'=' * 80}")
            print(f"OPTIMIZING: {strategy_name.upper()}")
            print(f"{'=' * 80}")

            optimal = self._optimize_strategy(
                strategy_name,
                max_combinations=max_combinations_per_strategy
            )

            self.optimal_params[strategy_name] = optimal

            print(f"\n✓ Optimal parameters for {strategy_name}:")
            print(f"  Net Revenue: ${optimal['net_revenue']:,.2f}")
            print(f"  Parameters: {json.dumps(optimal['params'], indent=4)}")

        # Handle matched pairs (ensure they share same parameters)
        self._enforce_matched_pairs()

        print(f"\n{'=' * 80}")
        print("GRID SEARCH COMPLETE")
        print(f"{'=' * 80}")

        return self.optimal_params

    def _optimize_strategy(self, strategy_name, max_combinations=None):
        """
        Optimize parameters for a single strategy.

        Args:
            strategy_name: Name of strategy to optimize
            max_combinations: Maximum combinations to test (for sampling)

        Returns:
            dict: Optimal parameters and metrics
        """
        grid = self.param_grids[strategy_name]
        param_names = list(grid.keys())
        param_values = list(grid.values())

        # Generate all parameter combinations
        all_combinations = list(itertools.product(*param_values))
        n_combinations = len(all_combinations)

        # Sample if too many combinations
        if max_combinations and n_combinations > max_combinations:
            print(f"  Sampling {max_combinations} of {n_combinations} combinations")
            indices = np.random.choice(n_combinations, max_combinations, replace=False)
            combinations = [all_combinations[i] for i in indices]
        else:
            combinations = all_combinations

        print(f"  Testing {len(combinations)} parameter combinations...")

        best_result = None
        best_revenue = -np.inf

        for i, param_combo in enumerate(combinations, 1):
            # Create parameter dict
            params = dict(zip(param_names, param_combo))

            # Run backtest with these parameters
            try:
                result = self._run_backtest_with_params(strategy_name, params)

                # Track all results
                self.all_results.append({
                    'strategy': strategy_name,
                    'params': params,
                    'net_revenue': result['net_earnings'],
                    'total_revenue': result['total_revenue'],
                    'total_costs': result['total_costs'],
                    'n_trades': result['n_trades'],
                    'avg_sale_price': result['avg_sale_price']
                })

                # Check if best so far
                if result['net_earnings'] > best_revenue:
                    best_revenue = result['net_earnings']
                    best_result = {
                        'params': params,
                        'net_revenue': result['net_earnings'],
                        'metrics': result
                    }

                # Progress update
                if i % 50 == 0 or i == len(combinations):
                    print(f"    Progress: {i}/{len(combinations)} | "
                          f"Best so far: ${best_revenue:,.2f}")

            except Exception as e:
                print(f"    ⚠️  Error with params {params}: {e}")
                continue

        return best_result

    def _run_backtest_with_params(self, strategy_name, params):
        """
        Run backtest for a strategy with specific parameters.

        Args:
            strategy_name: Name of strategy
            params: Parameter dict

        Returns:
            dict: Backtest metrics
        """
        # Import strategy classes (this will need to be adapted to work with notebook code)
        # For now, this is a placeholder structure
        # In practice, you'd instantiate the strategy class with params and run backtest

        # Placeholder - this needs to be implemented based on notebook structure
        # strategy = create_strategy(strategy_name, params, self.commodity_config)
        # engine = self.backtest_engine(self.prices, self.prediction_matrices,
        #                               self.commodity_config)
        # results = engine.run(strategy)
        # metrics = calculate_metrics(results)
        # return metrics

        raise NotImplementedError(
            "Backtest execution needs to be implemented based on notebook structure"
        )

    def _enforce_matched_pairs(self):
        """
        Ensure matched pairs (baseline/predictive) share same parameters.

        Matched pairs:
        - price_threshold <-> price_threshold_predictive
        - moving_average <-> moving_average_predictive
        """
        matched_pairs = [
            ('price_threshold', 'price_threshold_predictive'),
            ('moving_average', 'moving_average_predictive')
        ]

        for baseline, predictive in matched_pairs:
            if baseline in self.optimal_params:
                # Predictive version should use same baseline parameters
                baseline_params = self.optimal_params[baseline]['params'].copy()

                # Note: Predictive versions have additional parameters
                # (storage_cost_pct_per_day, transaction_cost_pct)
                # which come from commodity_config, not from grid search

                print(f"\n⚙️  Enforcing matched pair: {baseline} <-> {predictive}")
                print(f"   Shared parameters: {list(baseline_params.keys())}")

    def save_results(self, output_dir='./grid_search_results'):
        """
        Save grid search results to files.

        Args:
            output_dir: Directory to save results
        """
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save optimal parameters as JSON
        optimal_file = os.path.join(output_dir, f'optimal_parameters_{timestamp}.json')
        with open(optimal_file, 'w') as f:
            # Convert to serializable format
            output = {}
            for strategy, result in self.optimal_params.items():
                output[strategy] = {
                    'params': result['params'],
                    'net_revenue': float(result['net_revenue']),
                    'metrics': {k: float(v) if isinstance(v, (int, float, np.number)) else v
                               for k, v in result['metrics'].items()}
                }
            json.dump(output, f, indent=2)

        print(f"\n✓ Saved optimal parameters: {optimal_file}")

        # Save all results as CSV
        if self.all_results:
            results_df = pd.DataFrame(self.all_results)
            # Flatten params dict into separate columns
            params_df = pd.json_normalize(results_df['params'])
            results_df = pd.concat([
                results_df.drop('params', axis=1),
                params_df
            ], axis=1)

            results_file = os.path.join(output_dir, f'grid_search_results_{timestamp}.csv')
            results_df.to_csv(results_file, index=False)
            print(f"✓ Saved all results: {results_file}")

        # Generate summary report
        self._generate_report(output_dir, timestamp)

    def _generate_report(self, output_dir, timestamp):
        """
        Generate summary report of grid search results.

        Args:
            output_dir: Directory to save report
            timestamp: Timestamp string for filename
        """
        report_file = os.path.join(output_dir, f'grid_search_report_{timestamp}.txt')

        with open(report_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("GRID SEARCH OPTIMIZATION REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Commodity: {self.commodity_config.get('commodity', 'Unknown')}\n")
            f.write(f"Total combinations tested: {len(self.all_results):,}\n\n")

            f.write("=" * 80 + "\n")
            f.write("OPTIMAL PARAMETERS BY STRATEGY\n")
            f.write("=" * 80 + "\n\n")

            for strategy, result in self.optimal_params.items():
                f.write(f"\n{strategy.upper()}\n")
                f.write("-" * 40 + "\n")
                f.write(f"Net Revenue: ${result['net_revenue']:,.2f}\n")
                f.write("Parameters:\n")
                for param, value in result['params'].items():
                    f.write(f"  {param}: {value}\n")
                f.write("\n")

            f.write("\n" + "=" * 80 + "\n")
            f.write("RECOMMENDATIONS\n")
            f.write("=" * 80 + "\n\n")

            f.write("1. Update BASELINE_PARAMS and PREDICTION_PARAMS in notebook:\n")
            f.write("   - Copy optimal parameter values from above\n")
            f.write("   - Ensure matched pairs share same baseline parameters\n\n")

            f.write("2. Validate results:\n")
            f.write("   - Run full backtest with optimal parameters\n")
            f.write("   - Compare to baseline performance\n")
            f.write("   - Check statistical significance\n\n")

            f.write("3. Consider fine-grained search:\n")
            f.write("   - If parameters are at grid boundaries, expand search range\n")
            f.write("   - Use get_fine_grained_grids() for focused optimization\n\n")

        print(f"✓ Saved summary report: {report_file}")


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def create_strategy_with_params(strategy_name, params, commodity_config):
    """
    Create strategy instance with specified parameters.

    Args:
        strategy_name: Name of strategy
        params: Parameter dict
        commodity_config: Commodity configuration

    Returns:
        Strategy instance
    """
    # This function needs to be implemented to instantiate strategy classes
    # with the provided parameters. It should import the strategy classes
    # from the notebook code.

    raise NotImplementedError(
        "Strategy instantiation needs to be implemented based on notebook structure"
    )


def load_optimal_parameters(filepath):
    """
    Load previously saved optimal parameters.

    Args:
        filepath: Path to optimal_parameters.json

    Returns:
        dict: Optimal parameters by strategy
    """
    with open(filepath, 'r') as f:
        return json.load(f)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """
    Main entry point for grid search script.
    """
    parser = argparse.ArgumentParser(
        description='Grid search for optimal trading strategy parameters'
    )
    parser.add_argument(
        '--commodity',
        required=True,
        choices=['coffee', 'sugar'],
        help='Commodity to optimize'
    )
    parser.add_argument(
        '--model',
        default='sarimax_auto_weather_v1',
        help='Model version to use for predictions'
    )
    parser.add_argument(
        '--strategies',
        nargs='+',
        help='Specific strategies to optimize (default: all)'
    )
    parser.add_argument(
        '--max-combinations',
        type=int,
        help='Maximum combinations per strategy (for sampling large grids)'
    )
    parser.add_argument(
        '--fine-grain',
        action='store_true',
        help='Use fine-grained parameter ranges'
    )
    parser.add_argument(
        '--output-dir',
        default='./grid_search_results',
        help='Directory to save results'
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("TRADING STRATEGY PARAMETER OPTIMIZATION")
    print("=" * 80)
    print(f"\nCommodity: {args.commodity}")
    print(f"Model: {args.model}")
    print(f"Strategies: {args.strategies or 'all'}")
    print(f"Fine-grained: {args.fine_grain}")

    # NOTE: The actual implementation requires integration with the notebook code
    # This script provides the structure and framework for grid search
    # You'll need to:
    # 1. Import strategy classes from the notebook
    # 2. Import BacktestEngine and related classes
    # 3. Load data (prices, predictions) from Unity Catalog
    # 4. Implement _run_backtest_with_params() method

    print("\n⚠️  This script requires integration with notebook code.")
    print("See implementation notes in the script for details.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
