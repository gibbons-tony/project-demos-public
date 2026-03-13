"""
Diagnostic 16: Optuna Parameter Optimization for All 9 Strategies
Runs 200 trials per strategy to find optimal parameters
Saves results to diagnostic_16_best_params.pkl for use by diagnostic_17
"""

import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

# Handle Databricks path
# Import strategies using importlib to avoid notebook import issues
import importlib.util

# Try multiple paths to find all_strategies_pct.py
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),  # Same directory as this script
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics/all_strategies_pct.py',
    '/Workspace/Users/gibbons_tony@berkeley.edu/all_strategies_pct.py',
    'all_strategies_pct.py'  # Fallback to relative path
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        print(f"Found all_strategies_pct.py at: {path}")
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find all_strategies_pct.py. Tried: {possible_paths}")

spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

# Import strategy classes from the loaded module
ImmediateSaleStrategy = strat.ImmediateSaleStrategy
EqualBatchStrategy = strat.EqualBatchStrategy
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive
ExpectedValueStrategy = strat.ExpectedValueStrategy
ConsensusStrategy = strat.ConsensusStrategy
RiskAdjustedStrategy = strat.RiskAdjustedStrategy

# Import optuna
try:
    import optuna
    from optuna.samplers import TPESampler
except ImportError:
    print("Installing optuna...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "optuna", "--quiet"])
    import optuna
    from optuna.samplers import TPESampler

# Spark import
from pyspark.sql import SparkSession


class SimpleBacktestEngine:
    """Simplified backtest engine for parameter optimization"""
    def __init__(self, prices_df, pred_matrices, config):
        self.prices = prices_df
        self.pred = pred_matrices
        self.config = config

    def run_backtest(self, strategy, initial_inventory=50.0):
        inventory = initial_inventory
        total_revenue = 0
        trans_costs = 0
        storage_costs = 0
        trades = []

        strategy.reset()
        strategy.set_harvest_start(0)

        for day in range(len(self.prices)):
            date = self.prices.iloc[day]['date']
            price = self.prices.iloc[day]['price']
            hist = self.prices.iloc[:day+1].copy()
            pred = self.pred.get(date)

            decision = strategy.decide(
                day=day,
                inventory=inventory,
                current_price=price,
                price_history=hist,
                predictions=pred
            )

            if decision['action'] == 'SELL' and decision['amount'] > 0:
                amt = min(decision['amount'], inventory)
                # Scale to tons (assuming price is per ton)
                revenue = amt * price * 20
                trans_cost = revenue * self.config['transaction_cost_pct'] / 100
                total_revenue += revenue
                trans_costs += trans_cost
                inventory -= amt
                trades.append({'day': day, 'amount': amt, 'price': price})

            # Storage costs
            if inventory > 0:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                storage_costs += inventory * avg_price * 20 * self.config['storage_cost_pct_per_day'] / 100

        net_earnings = total_revenue - trans_costs - storage_costs

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': trans_costs,
            'storage_costs': storage_costs,
            'num_trades': len(trades),
            'final_inventory': inventory
        }


def get_search_space(trial, strategy_name):
    """Define search space for each strategy"""

    if strategy_name == 'immediate_sale':
        return {
            'min_batch_size': trial.suggest_float('min_batch_size', 3.0, 10.0),
            'sale_frequency_days': trial.suggest_int('sale_frequency_days', 5, 14)
        }

    elif strategy_name == 'equal_batch':
        return {
            'batch_size': trial.suggest_float('batch_size', 0.15, 0.30),
            'frequency_days': trial.suggest_int('frequency_days', 20, 35)
        }

    elif strategy_name == 'price_threshold':
        return {
            'threshold_pct': trial.suggest_float('threshold_pct', 0.02, 0.07),
            'batch_baseline': trial.suggest_float('batch_baseline', 0.20, 0.35),
            'batch_overbought_strong': trial.suggest_float('batch_overbought_strong', 0.30, 0.40),
            'batch_overbought': trial.suggest_float('batch_overbought', 0.25, 0.35),
            'batch_strong_trend': trial.suggest_float('batch_strong_trend', 0.15, 0.25),
            'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 75),
            'rsi_moderate': trial.suggest_int('rsi_moderate', 60, 70),
            'adx_strong': trial.suggest_int('adx_strong', 20, 30),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 10),
            'max_days_without_sale': trial.suggest_int('max_days_without_sale', 45, 75)
        }

    elif strategy_name == 'moving_average':
        return {
            'ma_period': trial.suggest_int('ma_period', 20, 35),
            'batch_baseline': trial.suggest_float('batch_baseline', 0.20, 0.30),
            'batch_strong_momentum': trial.suggest_float('batch_strong_momentum', 0.15, 0.25),
            'batch_overbought': trial.suggest_float('batch_overbought', 0.25, 0.35),
            'batch_overbought_strong': trial.suggest_float('batch_overbought_strong', 0.30, 0.40),
            'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 75),
            'rsi_min': trial.suggest_int('rsi_min', 40, 50),
            'adx_strong': trial.suggest_int('adx_strong', 20, 30),
            'adx_weak': trial.suggest_int('adx_weak', 15, 25),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 10),
            'max_days_without_sale': trial.suggest_int('max_days_without_sale', 45, 75)
        }

    elif strategy_name == 'price_threshold_predictive':
        params = get_search_space(trial, 'price_threshold')
        params.update({
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'scenario_shift_aggressive': trial.suggest_int('scenario_shift_aggressive', 1, 2),
            'scenario_shift_conservative': trial.suggest_int('scenario_shift_conservative', 1, 2)
        })
        return params

    elif strategy_name == 'moving_average_predictive':
        params = get_search_space(trial, 'moving_average')
        params.update({
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'scenario_shift_aggressive': trial.suggest_int('scenario_shift_aggressive', 1, 2),
            'scenario_shift_conservative': trial.suggest_int('scenario_shift_conservative', 1, 2)
        })
        return params

    elif strategy_name == 'expected_value':
        return {
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 1.0),
            'negative_threshold_pct': trial.suggest_float('negative_threshold_pct', -0.5, -0.1),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'medium_confidence_cv': trial.suggest_float('medium_confidence_cv', 0.10, 0.15),
            'strong_trend_adx': trial.suggest_int('strong_trend_adx', 20, 25),
            'batch_positive_confident': trial.suggest_float('batch_positive_confident', 0.0, 0.05),
            'batch_positive_uncertain': trial.suggest_float('batch_positive_uncertain', 0.10, 0.20),
            'batch_marginal': trial.suggest_float('batch_marginal', 0.15, 0.20),
            'batch_negative_mild': trial.suggest_float('batch_negative_mild', 0.25, 0.30),
            'batch_negative_strong': trial.suggest_float('batch_negative_strong', 0.35, 0.40),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7),
            'baseline_batch': trial.suggest_float('baseline_batch', 0.15, 0.20),
            'baseline_frequency': trial.suggest_int('baseline_frequency', 25, 30)
        }

    elif strategy_name == 'consensus':
        return {
            'consensus_threshold': trial.suggest_float('consensus_threshold', 0.60, 0.75),
            'very_strong_consensus': trial.suggest_float('very_strong_consensus', 0.80, 0.85),
            'moderate_consensus': trial.suggest_float('moderate_consensus', 0.55, 0.60),
            'min_return': trial.suggest_float('min_return', 0.02, 0.05),
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 0.7),
            'high_confidence_cv': trial.suggest_float('high_confidence_cv', 0.03, 0.08),
            'batch_strong_consensus': trial.suggest_float('batch_strong_consensus', 0.0, 0.05),
            'batch_moderate': trial.suggest_float('batch_moderate', 0.10, 0.20),
            'batch_weak': trial.suggest_float('batch_weak', 0.25, 0.30),
            'batch_bearish': trial.suggest_float('batch_bearish', 0.35, 0.40),
            'evaluation_day': trial.suggest_int('evaluation_day', 10, 14),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7)
        }

    elif strategy_name == 'risk_adjusted':
        return {
            'min_return': trial.suggest_float('min_return', 0.02, 0.05),
            'min_net_benefit_pct': trial.suggest_float('min_net_benefit_pct', 0.3, 0.7),
            'max_uncertainty_low': trial.suggest_float('max_uncertainty_low', 0.03, 0.08),
            'max_uncertainty_medium': trial.suggest_float('max_uncertainty_medium', 0.10, 0.20),
            'max_uncertainty_high': trial.suggest_float('max_uncertainty_high', 0.25, 0.35),
            'strong_trend_adx': trial.suggest_int('strong_trend_adx', 20, 25),
            'batch_low_risk': trial.suggest_float('batch_low_risk', 0.0, 0.05),
            'batch_medium_risk': trial.suggest_float('batch_medium_risk', 0.10, 0.15),
            'batch_high_risk': trial.suggest_float('batch_high_risk', 0.25, 0.30),
            'batch_very_high_risk': trial.suggest_float('batch_very_high_risk', 0.35, 0.40),
            'evaluation_day': trial.suggest_int('evaluation_day', 10, 14),
            'cooldown_days': trial.suggest_int('cooldown_days', 5, 7)
        }

    raise ValueError(f'Unknown strategy: {strategy_name}')


def optimize_strategy(strategy_class, strategy_name, engine, config, n_trials=200):
    """Optimize a single strategy using Optuna"""
    print(f"\n{'='*80}")
    print(f"{strategy_name}: {n_trials} trials")
    print(f"{'='*80}")

    # Create pure in-memory study
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))

    def objective(trial):
        params = get_search_space(trial, strategy_name)

        # Add costs for prediction strategies
        if strategy_name not in ['immediate_sale', 'equal_batch', 'price_threshold', 'moving_average']:
            params['storage_cost_pct_per_day'] = config['storage_cost_pct_per_day']
            params['transaction_cost_pct'] = config['transaction_cost_pct']

        try:
            strategy = strategy_class(**params)
            result = engine.run_backtest(strategy)
            return result['net_earnings']
        except Exception as e:
            print(f"  Trial failed: {e}")
            return -1e9

    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    print(f'✓ Best value: ${study.best_value:,.2f}')

    return study.best_params, study.best_value


def main():
    print("="*80)
    print("DIAGNOSTIC 16: OPTUNA PARAMETER OPTIMIZATION")
    print("="*80)
    print(f"Started: {datetime.now()}")

    # Configuration
    COMMODITY = 'coffee'
    MODEL_VERSION = 'synthetic_acc90'

    config = {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    }

    # Load data
    print("\n1. Loading data...")
    spark = SparkSession.builder.getOrCreate()

    # Load prices
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = '{COMMODITY}'"
    ).toPandas()
    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
    prices = prices[prices['date'] >= '2022-01-01'].reset_index(drop=True)

    print(f"✓ Loaded {len(prices)} price points")

    # Load predictions
    pred_table = f"commodity.trading_agent.predictions_{COMMODITY}"
    pred_df = spark.table(pred_table).filter(
        f"model_version = '{MODEL_VERSION}'"
    ).toPandas()

    # Convert to matrix format
    pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
    prediction_matrices = {}

    for timestamp in pred_df['timestamp'].unique():
        ts_data = pred_df[pred_df['timestamp'] == timestamp]
        matrix = ts_data.pivot_table(
            index='run_id',
            columns='day_ahead',
            values='predicted_price',
            aggfunc='first'
        ).values
        # Normalize to date-only for consistent dictionary lookups
        date_key = pd.Timestamp(timestamp).normalize()
        prediction_matrices[date_key] = matrix

    print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

    # Create engine
    engine = SimpleBacktestEngine(prices, prediction_matrices, config)
    print("✓ Backtest engine ready")

    # Define strategies to optimize
    strategies = [
        (ImmediateSaleStrategy, 'immediate_sale'),
        (EqualBatchStrategy, 'equal_batch'),
        (PriceThresholdStrategy, 'price_threshold'),
        (MovingAverageStrategy, 'moving_average'),
        (PriceThresholdPredictive, 'price_threshold_predictive'),
        (MovingAveragePredictive, 'moving_average_predictive'),
        (ExpectedValueStrategy, 'expected_value'),
        (ConsensusStrategy, 'consensus'),
        (RiskAdjustedStrategy, 'risk_adjusted')
    ]

    # Optimize all strategies
    print("\n2. Optimizing all 9 strategies...")
    results = {}

    for i, (strategy_class, strategy_name) in enumerate(strategies, 1):
        print(f"\n[{i}/9] Optimizing {strategy_name}...")
        best_params, best_value = optimize_strategy(
            strategy_class, strategy_name, engine, config, n_trials=200
        )
        results[strategy_name] = (best_params, best_value)

    # Summary
    print("\n" + "="*80)
    print("ALL 9 STRATEGIES OPTIMIZED")
    print("="*80)
    for name, (params, value) in sorted(results.items(), key=lambda x: x[1][1], reverse=True):
        print(f'{name:35s}: ${value:,.2f}')

    # Prepare parameters for diagnostic 17
    best_params = {name: params for name, (params, value) in results.items()}

    # Add cost parameters to predictive strategies
    for strategy in ['price_threshold_predictive', 'moving_average_predictive',
                     'expected_value', 'consensus', 'risk_adjusted']:
        if strategy in best_params:
            best_params[strategy]['storage_cost_pct_per_day'] = config['storage_cost_pct_per_day']
            best_params[strategy]['transaction_cost_pct'] = config['transaction_cost_pct']

    # Save results
    print("\n3. Saving results...")
    volume_path = "/Volumes/commodity/trading_agent/files"

    # Save parameters pickle
    params_file = f"{volume_path}/diagnostic_16_best_params.pkl"
    with open(params_file, 'wb') as f:
        pickle.dump(best_params, f)
    print(f"✓ Saved parameters to: {params_file}")

    # Save full results
    results_file = f"{volume_path}/diagnostic_16_results.pkl"
    results_data = {
        'execution_time': datetime.now(),
        'commodity': COMMODITY,
        'model_version': MODEL_VERSION,
        'config': config,
        'results': results,
        'best_params': best_params
    }
    with open(results_file, 'wb') as f:
        pickle.dump(results_data, f)
    print(f"✓ Saved full results to: {results_file}")

    # Save CSV summary
    csv_file = f"{volume_path}/diagnostic_16_summary.csv"
    summary_rows = []
    for name, (params, value) in results.items():
        summary_rows.append({
            'strategy_name': name,
            'best_net_earnings': value,
            'num_params': len(params)
        })
    summary_df = pd.DataFrame(summary_rows).sort_values('best_net_earnings', ascending=False)
    summary_df.to_csv(csv_file, index=False)
    print(f"✓ Saved summary to: {csv_file}")

    print("\n" + "="*80)
    print("DIAGNOSTIC 16 COMPLETE")
    print(f"Completed: {datetime.now()}")
    print("="*80)
    print("\nNext: Run diagnostic_17_paradox_analysis to analyze trade-by-trade differences")

    return True


if __name__ == "__main__":
    success = main()
    # Note: Don't call sys.exit() - Databricks interprets it as failure
    # Just let the script complete normally if success=True
    if not success:
        raise RuntimeError("Diagnostic 16 failed")
