"""
Diagnostic 17: Trade-by-Trade Paradox Analysis
Investigates why prediction strategies underperform baselines
Requires diagnostic_16 to run first to generate optimized parameters
"""

import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

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
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive

# Spark import
from pyspark.sql import SparkSession


class DetailedEngine:
    """Enhanced backtest engine with detailed daily logging"""
    def __init__(self, prices_df, pred_matrices, config):
        self.prices = prices_df
        self.pred = pred_matrices
        self.config = config

    def run_backtest_detailed(self, strategy, inv=50.0):
        """Run backtest with detailed trade and daily logging"""
        inventory = inv
        trades = []
        daily_log = []
        total_revenue = 0
        total_transaction_costs = 0
        total_storage_costs = 0

        strategy.reset()
        strategy.set_harvest_start(0)

        for day in range(len(self.prices)):
            date = self.prices.iloc[day]['date']
            price = self.prices.iloc[day]['price']
            hist = self.prices.iloc[:day+1].copy()
            pred = self.pred.get(date)

            # Get decision
            dec = strategy.decide(
                day=day,
                inventory=inventory,
                current_price=price,
                price_history=hist,
                predictions=pred
            )

            # Calculate daily storage cost
            daily_storage = 0
            if inventory > 0:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                daily_storage = inventory * avg_price * 20 * self.config['storage_cost_pct_per_day'] / 100
                total_storage_costs += daily_storage

            # Process trade
            trade_revenue = 0
            trade_cost = 0
            trade_amount = 0

            if dec['action'] == 'SELL' and dec['amount'] > 0:
                trade_amount = min(dec['amount'], inventory)
                trade_revenue = trade_amount * price * 20
                trade_cost = trade_revenue * self.config['transaction_cost_pct'] / 100

                total_revenue += trade_revenue
                total_transaction_costs += trade_cost
                inventory -= trade_amount

                trades.append({
                    'day': day,
                    'date': date,
                    'price': price,
                    'amount': trade_amount,
                    'revenue': trade_revenue,
                    'transaction_cost': trade_cost,
                    'reason': dec.get('reason', 'Unknown')
                })

            # Log daily state
            daily_log.append({
                'day': day,
                'date': date,
                'price': price,
                'inventory': inventory,
                'action': dec['action'],
                'trade_amount': trade_amount,
                'trade_revenue': trade_revenue,
                'trade_cost': trade_cost,
                'daily_storage': daily_storage,
                'cumulative_revenue': total_revenue,
                'cumulative_trans_cost': total_transaction_costs,
                'cumulative_storage': total_storage_costs,
                'net_earnings': total_revenue - total_transaction_costs - total_storage_costs
            })

        return {
            'net_earnings': total_revenue - total_transaction_costs - total_storage_costs,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'num_trades': len(trades),
            'final_inventory': inventory,
            'trades': trades,
            'daily_log': daily_log
        }


def analyze_cost_breakdown(baseline_res, pred_res, name):
    """Analyze and return cost breakdown comparison"""
    analysis = {
        'strategy_name': name,
        'rev_diff': pred_res['total_revenue'] - baseline_res['total_revenue'],
        'trans_diff': pred_res['transaction_costs'] - baseline_res['transaction_costs'],
        'stor_diff': pred_res['storage_costs'] - baseline_res['storage_costs'],
        'net_diff': pred_res['net_earnings'] - baseline_res['net_earnings'],
        'baseline_net': baseline_res['net_earnings'],
        'pred_net': pred_res['net_earnings'],
        'baseline_trades': baseline_res['num_trades'],
        'pred_trades': pred_res['num_trades']
    }

    # Find primary driver
    impacts = {
        'Revenue': analysis['rev_diff'],
        'Transaction costs': -analysis['trans_diff'],
        'Storage costs': -analysis['stor_diff']
    }
    primary = max(impacts.items(), key=lambda x: abs(x[1]))
    analysis['primary_driver'] = primary[0]
    analysis['primary_impact'] = abs(primary[1])

    return analysis


def main():
    print("="*80)
    print("DIAGNOSTIC 17: TRADE-BY-TRADE PARADOX ANALYSIS")
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

    # Load optimized parameters from diagnostic_16
    print("\n2. Loading optimized parameters from diagnostic_16...")
    volume_path = "/Volumes/commodity/trading_agent/files"
    params_file = f"{volume_path}/diagnostic_16_best_params.pkl"

    try:
        with open(params_file, 'rb') as f:
            best_params = pickle.load(f)
        print(f"✓ Loaded parameters for {len(best_params)} strategies")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"\nERROR: {params_file} not found!\n"
            f"Please run diagnostic_16 first to generate optimized parameters.\n"
        )

    # Create detailed engine
    engine = DetailedEngine(prices, prediction_matrices, config)
    print("✓ Enhanced backtest engine ready")

    # Run matched pair comparisons
    print("\n" + "="*80)
    print("3. MATCHED PAIR 1: Price Threshold")
    print("="*80)

    pt_baseline = PriceThresholdStrategy(**best_params['price_threshold'])
    pt_baseline_results = engine.run_backtest_detailed(pt_baseline)

    pt_pred = PriceThresholdPredictive(**best_params['price_threshold_predictive'])
    pt_pred_results = engine.run_backtest_detailed(pt_pred)

    print(f"\nBaseline:    Net=${pt_baseline_results['net_earnings']:,.2f}, Trades={pt_baseline_results['num_trades']}")
    print(f"Predictive:  Net=${pt_pred_results['net_earnings']:,.2f}, Trades={pt_pred_results['num_trades']}")
    print(f"Difference:  ${pt_pred_results['net_earnings'] - pt_baseline_results['net_earnings']:,.2f}")

    print("\n" + "="*80)
    print("4. MATCHED PAIR 2: Moving Average")
    print("="*80)

    ma_baseline = MovingAverageStrategy(**best_params['moving_average'])
    ma_baseline_results = engine.run_backtest_detailed(ma_baseline)

    ma_pred = MovingAveragePredictive(**best_params['moving_average_predictive'])
    ma_pred_results = engine.run_backtest_detailed(ma_pred)

    print(f"\nBaseline:    Net=${ma_baseline_results['net_earnings']:,.2f}, Trades={ma_baseline_results['num_trades']}")
    print(f"Predictive:  Net=${ma_pred_results['net_earnings']:,.2f}, Trades={ma_pred_results['num_trades']}")
    print(f"Difference:  ${ma_pred_results['net_earnings'] - ma_baseline_results['net_earnings']:,.2f}")

    # Analyze cost breakdowns
    print("\n" + "="*80)
    print("5. COST BREAKDOWN ANALYSIS")
    print("="*80)

    pt_analysis = analyze_cost_breakdown(pt_baseline_results, pt_pred_results, 'Price Threshold')
    ma_analysis = analyze_cost_breakdown(ma_baseline_results, ma_pred_results, 'Moving Average')

    print(f"\nPrice Threshold:")
    print(f"  Primary driver: {pt_analysis['primary_driver']} (${pt_analysis['primary_impact']:,.2f})")
    print(f"  Revenue diff:   ${pt_analysis['rev_diff']:,.2f}")
    print(f"  Trans diff:     ${pt_analysis['trans_diff']:,.2f}")
    print(f"  Storage diff:   ${pt_analysis['stor_diff']:,.2f}")

    print(f"\nMoving Average:")
    print(f"  Primary driver: {ma_analysis['primary_driver']} (${ma_analysis['primary_impact']:,.2f})")
    print(f"  Revenue diff:   ${ma_analysis['rev_diff']:,.2f}")
    print(f"  Trans diff:     ${ma_analysis['trans_diff']:,.2f}")
    print(f"  Storage diff:   ${ma_analysis['stor_diff']:,.2f}")

    # Inventory analysis
    print("\n" + "="*80)
    print("6. INVENTORY ANALYSIS")
    print("="*80)

    pt_baseline_daily = pd.DataFrame(pt_baseline_results['daily_log'])
    pt_pred_daily = pd.DataFrame(pt_pred_results['daily_log'])
    ma_baseline_daily = pd.DataFrame(ma_baseline_results['daily_log'])
    ma_pred_daily = pd.DataFrame(ma_pred_results['daily_log'])

    print(f"\nPrice Threshold avg inventory:")
    print(f"  Baseline:   {pt_baseline_daily['inventory'].mean():.2f}")
    print(f"  Predictive: {pt_pred_daily['inventory'].mean():.2f}")
    print(f"  Difference: {pt_pred_daily['inventory'].mean() - pt_baseline_daily['inventory'].mean():.2f}")

    print(f"\nMoving Average avg inventory:")
    print(f"  Baseline:   {ma_baseline_daily['inventory'].mean():.2f}")
    print(f"  Predictive: {ma_pred_daily['inventory'].mean():.2f}")
    print(f"  Difference: {ma_pred_daily['inventory'].mean() - ma_baseline_daily['inventory'].mean():.2f}")

    # Save results
    print("\n" + "="*80)
    print("7. SAVING RESULTS")
    print("="*80)

    results_data = {
        'execution_time': datetime.now(),
        'commodity': COMMODITY,
        'model_version': MODEL_VERSION,
        'config': config,
        'price_threshold': {
            'baseline': pt_baseline_results,
            'predictive': pt_pred_results,
            'analysis': pt_analysis
        },
        'moving_average': {
            'baseline': ma_baseline_results,
            'predictive': ma_pred_results,
            'analysis': ma_analysis
        }
    }

    # Save full results pickle
    results_file = f"{volume_path}/diagnostic_17_results.pkl"
    with open(results_file, 'wb') as f:
        pickle.dump(results_data, f)
    print(f"✓ Saved full results to: {results_file}")

    # Save summary CSV
    csv_file = f"{volume_path}/diagnostic_17_summary.csv"
    summary_rows = [
        {
            'strategy': 'Price Threshold',
            'baseline_net': pt_analysis['baseline_net'],
            'pred_net': pt_analysis['pred_net'],
            'difference': pt_analysis['net_diff'],
            'primary_driver': pt_analysis['primary_driver'],
            'primary_impact': pt_analysis['primary_impact'],
            'baseline_trades': pt_analysis['baseline_trades'],
            'pred_trades': pt_analysis['pred_trades']
        },
        {
            'strategy': 'Moving Average',
            'baseline_net': ma_analysis['baseline_net'],
            'pred_net': ma_analysis['pred_net'],
            'difference': ma_analysis['net_diff'],
            'primary_driver': ma_analysis['primary_driver'],
            'primary_impact': ma_analysis['primary_impact'],
            'baseline_trades': ma_analysis['baseline_trades'],
            'pred_trades': ma_analysis['pred_trades']
        }
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(csv_file, index=False)
    print(f"✓ Saved summary to: {csv_file}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print("\nFindings:")
    print(f"  Price Threshold: Predictive WORSE by ${pt_analysis['net_diff']:,.2f}")
    print(f"  Moving Average:  Predictive WORSE by ${ma_analysis['net_diff']:,.2f}")

    print("\nRecommendations:")
    print("  1. Review prediction confidence thresholds")
    print("  2. Examine scenario shifting logic")
    print("  3. Validate net benefit calculations")
    print("  4. Consider whether 90% accuracy is sufficient")

    print("\n" + "="*80)
    print("DIAGNOSTIC 17 COMPLETE")
    print(f"Completed: {datetime.now()}")
    print("="*80)

    return True


if __name__ == "__main__":
    success = main()
    # Note: Don't call sys.exit() - Databricks interprets it as failure
    # Just let the script complete normally if success=True
    if not success:
        raise RuntimeError("Diagnostic 17 failed")
