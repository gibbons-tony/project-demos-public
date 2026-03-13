"""
Strategy Parameter Optimizer

Production-ready parameter optimization using Optuna.

Key Features:
- Earnings-based optimization (maximize profit)
- Uses production backtest engine
- Full logging and result tracking

Migrated from diagnostics/run_diagnostic_16.py with modern enhancements.
"""

import pandas as pd
import numpy as np
import sys
from typing import Dict, List, Optional, Callable, Tuple
from datetime import datetime

# Auto-install optuna if needed (for Databricks)
try:
    import optuna
    from optuna.samplers import TPESampler
except ImportError:
    print("Installing optuna...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "optuna", "--quiet"])
    import optuna
    from optuna.samplers import TPESampler

from .search_space import SearchSpaceRegistry


class ParameterOptimizer:
    """
    Optimize strategy parameters using Optuna.

    Optimizes for earnings (profit maximization).
    """

    def __init__(
        self,
        prices_df: pd.DataFrame,
        prediction_matrices: Dict,
        config: Dict,
        backtest_engine_class: Optional[Callable] = None,
        use_production_engine: bool = True,
        fixed_base_params: Optional[Dict[str, Dict]] = None
    ):
        """
        Initialize optimizer.

        Args:
            prices_df: DataFrame with columns ['date', 'price']
            prediction_matrices: Dict mapping date -> prediction matrix (runs × horizons)
            config: Full commodity config dict with:
                - storage_cost_pct_per_day: float
                - transaction_cost_pct: float
                - harvest_volume: float (required for production engine)
                - harvest_windows: list (required for production engine)
                - commodity: str (optional, for production engine)
                - max_holding_days: int (optional)
                - min_inventory_to_trade: float (optional)
            backtest_engine_class: Backtest engine class (overrides use_production_engine if set)
            use_production_engine: If True (default), use production BacktestEngine for accuracy
                                  If False, use SimpleBacktestEngine for speed
            fixed_base_params: Optional dict of fixed base parameters for matched pair optimization.
                              Example: {'price_threshold': {...}, 'moving_average': {...}}
                              Used in Pass 2 to fix base params while optimizing prediction params.

        Note:
            - Production engine recommended for final optimization (more accurate, harvest-aware)
            - Simple engine acceptable for rapid prototyping/testing
            - For matched pair optimization: Pass 1 optimizes base strategies, Pass 2 uses
              fixed_base_params to optimize predictive strategies with same base parameters
        """
        self.prices = prices_df
        self.predictions = prediction_matrices
        self.config = config

        # Determine which engine to use
        if backtest_engine_class is not None:
            # Explicit override
            self.engine_class = backtest_engine_class
        elif use_production_engine:
            # Use production engine for accuracy (default)
            from production.core.backtest_engine import BacktestEngine
            self.engine_class = BacktestEngine
        else:
            # Use simple engine for speed
            self.engine_class = SimpleBacktestEngine

        # Create engine instance
        self.engine = self.engine_class(prices_df, prediction_matrices, config)

        # Search space registry (with optional fixed base params for matched pairs)
        self.search_space = SearchSpaceRegistry(fixed_base_params=fixed_base_params)

    def optimize_strategy(
        self,
        strategy_class: Callable,
        strategy_name: str,
        n_trials: int = 200,
        seed: int = 42,
        show_progress: bool = True
    ) -> Tuple[Dict, float, Optional[optuna.Study]]:
        """
        Optimize parameters for a single strategy.

        Args:
            strategy_class: Strategy class to instantiate
            strategy_name: Name of strategy (for search space lookup)
            n_trials: Number of optimization trials (default: 200)
            seed: Random seed for reproducibility
            show_progress: Show progress bar

        Returns:
            Tuple of (best_params, best_value, study)
            - best_params: Dict of optimal parameters
            - best_value: Best earnings value achieved
            - study: Optuna study object (for further analysis)
        """
        print(f"\n{'='*80}")
        print(f"OPTIMIZING: {strategy_name}")
        print(f"{'='*80}")
        print(f"Objective: earnings (profit maximization)")
        print(f"Trials: {n_trials}")
        print(f"Started: {datetime.now()}")

        # Create study (maximize earnings)
        study = optuna.create_study(
            direction='maximize',
            sampler=TPESampler(seed=seed)
        )

        # Define objective function
        def objective_function(trial):
            # Get parameter suggestions from search space
            params = self.search_space.get_search_space(trial, strategy_name)

            # Add cost parameters for prediction strategies and advanced strategies
            # (baseline strategies don't use these params)
            if strategy_name not in ['immediate_sale', 'equal_batch', 'price_threshold', 'moving_average']:
                params['storage_cost_pct_per_day'] = self.config['storage_cost_pct_per_day']
                params['transaction_cost_pct'] = self.config['transaction_cost_pct']

            try:
                # Instantiate strategy with suggested parameters
                strategy = strategy_class(**params)

                # Run backtest
                result = self.engine.run_backtest(strategy)

                # Return earnings
                return result['net_earnings']

            except Exception as e:
                print(f"  Trial {trial.number} failed: {e}")
                return -1e9  # Return very bad value for failed trials

        # Run optimization
        study.optimize(
            objective_function,
            n_trials=n_trials,
            show_progress_bar=show_progress
        )

        # Extract best results
        best_params = study.best_params
        best_value = study.best_value

        print(f"✓ Optimization complete")
        print(f"  Best earnings: ${best_value:,.2f}")
        print(f"  Trials completed: {len(study.trials)}")
        print(f"Completed: {datetime.now()}")

        return best_params, best_value, study

    def optimize_all_strategies(
        self,
        strategies: List[Tuple[Callable, str]],
        n_trials: int = 200,
        seed: int = 42,
        checkpoint_path: str = None,
        n_parallel: int = 4
    ) -> Dict[str, Tuple[Dict, float]]:
        """
        Optimize parameters for all provided strategies with parallelization and checkpointing.

        Args:
            strategies: List of (strategy_class, strategy_name) tuples
            n_trials: Number of trials per strategy
            seed: Random seed
            checkpoint_path: Path to save/load checkpoint file (enables fault tolerance)
            n_parallel: Number of strategies to optimize in parallel (default: 4)

        Returns:
            Dict mapping strategy_name -> (best_params, best_earnings)
        """
        import pickle
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Load checkpoint if exists
        results = {}
        if checkpoint_path and os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'rb') as f:
                    results = pickle.load(f)
                print(f"✓ Loaded checkpoint with {len(results)} completed strategies")
            except Exception as e:
                print(f"⚠️  Failed to load checkpoint: {e}")
                results = {}

        # Filter out already completed strategies
        remaining_strategies = [
            (cls, name) for cls, name in strategies
            if name not in results
        ]

        if not remaining_strategies:
            print("✓ All strategies already completed (from checkpoint)")
        else:
            print(f"✓ Optimizing {len(remaining_strategies)} strategies in parallel (workers={n_parallel})")

            def optimize_single(strategy_tuple):
                """Optimize a single strategy (for parallel execution)"""
                strategy_class, strategy_name = strategy_tuple
                try:
                    print(f"\n[STARTED] {strategy_name}")
                    best_params, best_value, _ = self.optimize_strategy(
                        strategy_class=strategy_class,
                        strategy_name=strategy_name,
                        n_trials=n_trials,
                        seed=seed
                    )
                    print(f"[COMPLETED] {strategy_name}: ${best_value:,.2f}")
                    return strategy_name, (best_params, best_value), None
                except Exception as e:
                    print(f"[FAILED] {strategy_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    return strategy_name, None, str(e)

            # Parallel execution with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=n_parallel) as executor:
                futures = {
                    executor.submit(optimize_single, s): s
                    for s in remaining_strategies
                }

                for future in as_completed(futures):
                    strategy_name, result, error = future.result()

                    if error is None:
                        results[strategy_name] = result

                        # Save checkpoint after each completed strategy
                        if checkpoint_path:
                            try:
                                os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
                                with open(checkpoint_path, 'wb') as f:
                                    pickle.dump(results, f)
                                print(f"✓ Checkpoint saved ({len(results)}/{len(strategies)} complete)")
                            except Exception as e:
                                print(f"⚠️  Failed to save checkpoint: {e}")

        # Print summary
        print("\n" + "="*80)
        print(f"ALL {len(results)} STRATEGIES OPTIMIZED")
        print("="*80)
        for name, (params, value) in sorted(results.items(), key=lambda x: x[1][1], reverse=True):
            print(f"{name:35s}: ${value:,.2f}")

        return results


class SimpleBacktestEngine:
    """
    Simplified backtest engine for fast parameter optimization.

    This is extracted from diagnostics/run_diagnostic_16.py.
    For production use, consider using production/core/backtest_engine.py instead.
    """

    def __init__(self, prices_df, pred_matrices, config):
        """
        Initialize engine.

        Args:
            prices_df: DataFrame with columns ['date', 'price']
            pred_matrices: Dict mapping date -> prediction matrix
            config: Dict with cost parameters
        """
        self.prices = prices_df
        self.pred = pred_matrices
        self.config = config

    def run_backtest(self, strategy, initial_inventory=50.0):
        """
        Run backtest for a strategy.

        Args:
            strategy: Strategy instance to test
            initial_inventory: Starting inventory in tons

        Returns:
            Dict with:
                - net_earnings: float
                - total_revenue: float
                - transaction_costs: float
                - storage_costs: float
                - num_trades: int
                - final_inventory: float
                - sharpe_ratio: float (if enough trades)
        """
        inventory = initial_inventory
        total_revenue = 0
        trans_costs = 0
        storage_costs = 0
        trades = []
        daily_returns = []

        strategy.reset()
        strategy.set_harvest_start(0)

        for day in range(len(self.prices)):
            date = self.prices.iloc[day]['date']
            price = self.prices.iloc[day]['price']
            hist = self.prices.iloc[:day+1].copy()
            pred = self.pred.get(date)

            # Get strategy decision
            decision = strategy.decide(
                day=day,
                inventory=inventory,
                current_price=price,
                price_history=hist,
                predictions=pred
            )

            # Execute trade if recommended
            if decision['action'] == 'SELL' and decision['amount'] > 0:
                amt = min(decision['amount'], inventory)

                # Calculate revenue and costs
                # Note: price * 20 converts cents/lb to $/ton
                revenue = amt * price * 20
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100

                total_revenue += revenue
                trans_costs += trans_cost
                inventory -= amt

                trades.append({
                    'day': day,
                    'amount': amt,
                    'price': price,
                    'revenue': revenue
                })

                # Track daily return (for Sharpe ratio)
                if len(trades) > 1:
                    prev_price = trades[-2]['price']
                    daily_return = (price - prev_price) / prev_price
                    daily_returns.append(daily_return)

            # Calculate storage costs
            if inventory > 0:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                storage_cost = inventory * avg_price * 20 * self.config['storage_cost_pct_per_day'] / 100
                storage_costs += storage_cost

        # Calculate net earnings
        net_earnings = total_revenue - trans_costs - storage_costs

        # Calculate Sharpe ratio if enough data
        sharpe_ratio = 0.0
        if len(daily_returns) > 1:
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            if std_return > 0:
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252)  # Annualized

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': trans_costs,
            'storage_costs': storage_costs,
            'num_trades': len(trades),
            'final_inventory': inventory,
            'sharpe_ratio': sharpe_ratio
        }
