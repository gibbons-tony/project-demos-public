# Diagnostic 17: Why Do Predictions Hurt Performance?

**The Paradox:** 95% accurate predictions make net earnings WORSE

**Findings from Diagnostic 16:**
- price_threshold (baseline): $239,921
- price_threshold_predictive: $238,040 (WORSE by $1,882)
- moving_average (baseline): $226,755
- moving_average_predictive: $225,949 (WORSE by $806)

**This notebook investigates:**
1. Trade-by-trade comparison
2. Cost breakdown (transaction vs storage)
3. Prediction usage patterns
4. Scenario shifting behavior
5. Net benefit calculation accuracy


```
%run ../00_setup_and_config
```


```
import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime
import importlib.util

print('='*80)
print('DIAGNOSTIC 17: PREDICTION PARADOX INVESTIGATION')
print('='*80)
```

## Load Strategies


```
if 'all_strategies_pct' in sys.modules:
    del sys.modules['all_strategies_pct']

spec = importlib.util.spec_from_file_location('all_strategies_pct', 'all_strategies_pct.py')
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive

print('✓ Loaded strategies')
```

## Load Data


```
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

COMMODITY_CONFIG['storage_cost_pct_per_day'] = 0.005
COMMODITY_CONFIG['transaction_cost_pct'] = 0.01

prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
prices['date'] = pd.to_datetime(prices['date'])

with open(DATA_PATHS['prediction_matrices'], 'rb') as f:
    prediction_matrices = pickle.load(f)
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print(f'✓ Loaded {len(prices)} prices, {len(prediction_matrices)} matrices')
```

## Load Best Parameters from Diagnostic 16


```
params_file = 'diagnostic_16_best_params.pkl'

if os.path.exists(params_file):
    with open(params_file, 'rb') as f:
        best_params = pickle.load(f)
    print(f'✓ Loaded optimized parameters from {params_file}')
    print(f'  Found {len(best_params)} strategies')
    
    # Display key strategies we'll analyze
    for strategy in ['price_threshold', 'price_threshold_predictive', 'moving_average', 'moving_average_predictive']:
        if strategy in best_params:
            print(f'  - {strategy}: {len(best_params[strategy])} parameters')
else:
    raise FileNotFoundError(
        f"\n\n{'='*80}\n"
        f"ERROR: {params_file} not found!\n\n"
        f"Please run diagnostic_16_optuna_complete.ipynb first to generate\n"
        f"the optimized parameters. That notebook will save them to:\n"
        f"  {params_file}\n\n"
        f"Then this notebook will automatically load them.\n"
        f"{'='*80}"
    )
```

## Enhanced Backtest Engine with Detailed Logging


```
class DetailedEngine:
    def __init__(self, prices_df, pred_matrices, config):
        self.prices = prices_df
        self.pred = pred_matrices
        self.config = config
    
    def run_backtest_detailed(self, strategy, inv=50.0):
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

engine = DetailedEngine(prices, prediction_matrices, COMMODITY_CONFIG)
print('✓ Enhanced engine ready')
```

## Run Matched Pair Comparisons


```
print('\n' + '='*80)
print('MATCHED PAIR 1: Price Threshold')
print('='*80)

pt_baseline = PriceThresholdStrategy(**best_params['price_threshold'])
pt_baseline_results = engine.run_backtest_detailed(pt_baseline)

pt_pred = PriceThresholdPredictive(**best_params['price_threshold_predictive'])
pt_pred_results = engine.run_backtest_detailed(pt_pred)

print('\nBaseline:')
print(f"  Net Earnings:     ${pt_baseline_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${pt_baseline_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${pt_baseline_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${pt_baseline_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {pt_baseline_results['num_trades']}")
print(f"  Final Inventory:  {pt_baseline_results['final_inventory']:.2f}")

print('\nPredictive:')
print(f"  Net Earnings:     ${pt_pred_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${pt_pred_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${pt_pred_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${pt_pred_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {pt_pred_results['num_trades']}")
print(f"  Final Inventory:  {pt_pred_results['final_inventory']:.2f}")

print('\nDifference (Predictive - Baseline):')
print(f"  Net Earnings:     ${pt_pred_results['net_earnings'] - pt_baseline_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${pt_pred_results['total_revenue'] - pt_baseline_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${pt_pred_results['transaction_costs'] - pt_baseline_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${pt_pred_results['storage_costs'] - pt_baseline_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {pt_pred_results['num_trades'] - pt_baseline_results['num_trades']}")
```


```
print('\n' + '='*80)
print('MATCHED PAIR 2: Moving Average')
print('='*80)

ma_baseline = MovingAverageStrategy(**best_params['moving_average'])
ma_baseline_results = engine.run_backtest_detailed(ma_baseline)

ma_pred = MovingAveragePredictive(**best_params['moving_average_predictive'])
ma_pred_results = engine.run_backtest_detailed(ma_pred)

print('\nBaseline:')
print(f"  Net Earnings:     ${ma_baseline_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${ma_baseline_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${ma_baseline_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${ma_baseline_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {ma_baseline_results['num_trades']}")
print(f"  Final Inventory:  {ma_baseline_results['final_inventory']:.2f}")

print('\nPredictive:')
print(f"  Net Earnings:     ${ma_pred_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${ma_pred_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${ma_pred_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${ma_pred_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {ma_pred_results['num_trades']}")
print(f"  Final Inventory:  {ma_pred_results['final_inventory']:.2f}")

print('\nDifference (Predictive - Baseline):')
print(f"  Net Earnings:     ${ma_pred_results['net_earnings'] - ma_baseline_results['net_earnings']:,.2f}")
print(f"  Total Revenue:    ${ma_pred_results['total_revenue'] - ma_baseline_results['total_revenue']:,.2f}")
print(f"  Trans Costs:      ${ma_pred_results['transaction_costs'] - ma_baseline_results['transaction_costs']:,.2f}")
print(f"  Storage Costs:    ${ma_pred_results['storage_costs'] - ma_baseline_results['storage_costs']:,.2f}")
print(f"  Num Trades:       {ma_pred_results['num_trades'] - ma_baseline_results['num_trades']}")
```

## Trade-by-Trade Comparison


```
# Convert to DataFrames for comparison
pt_baseline_trades = pd.DataFrame(pt_baseline_results['trades'])
pt_pred_trades = pd.DataFrame(pt_pred_results['trades'])

print('\n' + '='*80)
print('PRICE THRESHOLD: Trade Comparison')
print('='*80)

print(f'\nBaseline: {len(pt_baseline_trades)} trades')
if len(pt_baseline_trades) > 0:
    print(pt_baseline_trades.head(10))
    print(f'\nAvg trade size: {pt_baseline_trades["amount"].mean():.2f}')
    print(f'Avg trade revenue: ${pt_baseline_trades["revenue"].mean():,.2f}')

print(f'\nPredictive: {len(pt_pred_trades)} trades')
if len(pt_pred_trades) > 0:
    print(pt_pred_trades.head(10))
    print(f'\nAvg trade size: {pt_pred_trades["amount"].mean():.2f}')
    print(f'Avg trade revenue: ${pt_pred_trades["revenue"].mean():,.2f}')
```


```
ma_baseline_trades = pd.DataFrame(ma_baseline_results['trades'])
ma_pred_trades = pd.DataFrame(ma_pred_results['trades'])

print('\n' + '='*80)
print('MOVING AVERAGE: Trade Comparison')
print('='*80)

print(f'\nBaseline: {len(ma_baseline_trades)} trades')
if len(ma_baseline_trades) > 0:
    print(ma_baseline_trades.head(10))
    print(f'\nAvg trade size: {ma_baseline_trades["amount"].mean():.2f}')
    print(f'Avg trade revenue: ${ma_baseline_trades["revenue"].mean():,.2f}')

print(f'\nPredictive: {len(ma_pred_trades)} trades')
if len(ma_pred_trades) > 0:
    print(ma_pred_trades.head(10))
    print(f'\nAvg trade size: {ma_pred_trades["amount"].mean():.2f}')
    print(f'Avg trade revenue: ${ma_pred_trades["revenue"].mean():,.2f}')
```

## Daily State Comparison

Look at inventory levels over time to understand storage cost differences


```
pt_baseline_daily = pd.DataFrame(pt_baseline_results['daily_log'])
pt_pred_daily = pd.DataFrame(pt_pred_results['daily_log'])

print('\n' + '='*80)
print('PRICE THRESHOLD: Inventory Over Time')
print('='*80)

print('\nBaseline inventory stats:')
print(pt_baseline_daily['inventory'].describe())

print('\nPredictive inventory stats:')
print(pt_pred_daily['inventory'].describe())

print('\nDays with inventory > 40:')
print(f"  Baseline:   {(pt_baseline_daily['inventory'] > 40).sum()} days")
print(f"  Predictive: {(pt_pred_daily['inventory'] > 40).sum()} days")

print('\nDays with inventory > 30:')
print(f"  Baseline:   {(pt_baseline_daily['inventory'] > 30).sum()} days")
print(f"  Predictive: {(pt_pred_daily['inventory'] > 30).sum()} days")
```


```
ma_baseline_daily = pd.DataFrame(ma_baseline_results['daily_log'])
ma_pred_daily = pd.DataFrame(ma_pred_results['daily_log'])

print('\n' + '='*80)
print('MOVING AVERAGE: Inventory Over Time')
print('='*80)

print('\nBaseline inventory stats:')
print(ma_baseline_daily['inventory'].describe())

print('\nPredictive inventory stats:')
print(ma_pred_daily['inventory'].describe())

print('\nDays with inventory > 40:')
print(f"  Baseline:   {(ma_baseline_daily['inventory'] > 40).sum()} days")
print(f"  Predictive: {(ma_pred_daily['inventory'] > 40).sum()} days")

print('\nDays with inventory > 30:')
print(f"  Baseline:   {(ma_baseline_daily['inventory'] > 30).sum()} days")
print(f"  Predictive: {(ma_pred_daily['inventory'] > 30).sum()} days")
```

## Cost Breakdown Analysis


```
def cost_breakdown(baseline_res, pred_res, name):
    print(f'\n{"="*80}')
    print(f'{name}: Cost Breakdown')
    print('='*80)
    
    # Revenue comparison
    rev_diff = pred_res['total_revenue'] - baseline_res['total_revenue']
    print(f'\nRevenue Difference: ${rev_diff:,.2f}')
    if abs(rev_diff) > 1:
        print(f"  {'Predictive sold MORE' if rev_diff > 0 else 'Predictive sold LESS'}")
    
    # Transaction cost comparison
    trans_diff = pred_res['transaction_costs'] - baseline_res['transaction_costs']
    print(f'\nTransaction Cost Difference: ${trans_diff:,.2f}')
    if abs(trans_diff) > 1:
        print(f"  {'Predictive paid MORE in transaction fees' if trans_diff > 0 else 'Predictive paid LESS in transaction fees'}")
        print(f"  This is {abs(trans_diff / baseline_res['transaction_costs'] * 100):.1f}% {'more' if trans_diff > 0 else 'less'}")
    
    # Storage cost comparison
    stor_diff = pred_res['storage_costs'] - baseline_res['storage_costs']
    print(f'\nStorage Cost Difference: ${stor_diff:,.2f}')
    if abs(stor_diff) > 1:
        print(f"  {'Predictive paid MORE in storage' if stor_diff > 0 else 'Predictive paid LESS in storage'}")
        print(f"  This is {abs(stor_diff / baseline_res['storage_costs'] * 100):.1f}% {'more' if stor_diff > 0 else 'less'}")
    
    # Net earnings
    net_diff = pred_res['net_earnings'] - baseline_res['net_earnings']
    print(f'\nNet Earnings Difference: ${net_diff:,.2f}')
    
    # Attribution
    print(f'\nPerformance Attribution:')
    print(f"  Revenue impact:      {'+' if rev_diff > 0 else ''}{rev_diff:,.2f}")
    print(f"  Transaction impact:  {'-' if trans_diff > 0 else '+'}{abs(trans_diff):,.2f}")
    print(f"  Storage impact:      {'-' if stor_diff > 0 else '+'}{abs(stor_diff):,.2f}")
    print(f"  Net impact:          {'+' if net_diff > 0 else ''}{net_diff:,.2f}")
    
    # What drove the difference?
    print(f'\nPrimary Driver:')
    impacts = {
        'Revenue': rev_diff,
        'Transaction costs': -trans_diff,
        'Storage costs': -stor_diff
    }
    primary = max(impacts.items(), key=lambda x: abs(x[1]))
    print(f"  {primary[0]} had the biggest impact (${abs(primary[1]):,.2f})")

cost_breakdown(pt_baseline_results, pt_pred_results, 'PRICE THRESHOLD')
cost_breakdown(ma_baseline_results, ma_pred_results, 'MOVING AVERAGE')
```

## Hypothesis Testing

Based on the analysis above, let's test specific hypotheses about why predictions hurt performance


```
print('\n' + '='*80)
print('HYPOTHESIS TESTING')
print('='*80)

print('\n1. Hypothesis: Predictions cause DELAYED selling, increasing storage costs')
print('   Test: Compare average inventory levels')
print(f'\n   Price Threshold:')
print(f'     Baseline avg inventory:   {pt_baseline_daily["inventory"].mean():.2f}')
print(f'     Predictive avg inventory: {pt_pred_daily["inventory"].mean():.2f}')
print(f'     Difference: {pt_pred_daily["inventory"].mean() - pt_baseline_daily["inventory"].mean():.2f}')

print(f'\n   Moving Average:')
print(f'     Baseline avg inventory:   {ma_baseline_daily["inventory"].mean():.2f}')
print(f'     Predictive avg inventory: {ma_pred_daily["inventory"].mean():.2f}')
print(f'     Difference: {ma_pred_daily["inventory"].mean() - ma_baseline_daily["inventory"].mean():.2f}')

print('\n2. Hypothesis: Predictions cause MORE FREQUENT trading, increasing transaction costs')
print('   Test: Compare number of trades')
print(f'\n   Price Threshold:')
print(f'     Baseline trades:   {pt_baseline_results["num_trades"]}')
print(f'     Predictive trades: {pt_pred_results["num_trades"]}')
print(f'     Difference: {pt_pred_results["num_trades"] - pt_baseline_results["num_trades"]}')

print(f'\n   Moving Average:')
print(f'     Baseline trades:   {ma_baseline_results["num_trades"]}')
print(f'     Predictive trades: {ma_pred_results["num_trades"]}')
print(f'     Difference: {ma_pred_results["num_trades"] - ma_baseline_results["num_trades"]}')

print('\n3. Hypothesis: Predictions cause selling at WORSE prices')
print('   Test: Compare average selling price')
if len(pt_baseline_trades) > 0 and len(pt_pred_trades) > 0:
    print(f'\n   Price Threshold:')
    print(f'     Baseline avg price:   ${pt_baseline_trades["price"].mean():.4f}')
    print(f'     Predictive avg price: ${pt_pred_trades["price"].mean():.4f}')
    print(f'     Difference: ${pt_pred_trades["price"].mean() - pt_baseline_trades["price"].mean():.4f}')

if len(ma_baseline_trades) > 0 and len(ma_pred_trades) > 0:
    print(f'\n   Moving Average:')
    print(f'     Baseline avg price:   ${ma_baseline_trades["price"].mean():.4f}')
    print(f'     Predictive avg price: ${ma_pred_trades["price"].mean():.4f}')
    print(f'     Difference: ${ma_pred_trades["price"].mean() - ma_baseline_trades["price"].mean():.4f}')
```

## Summary and Conclusions


```
print('\n' + '='*80)
print('SUMMARY: Why Predictions Hurt Performance')
print('='*80)

print('\n📊 FINDINGS:')
print('\n1. Price Threshold Strategy:')
print(f"   - Predictive WORSE by ${pt_pred_results['net_earnings'] - pt_baseline_results['net_earnings']:,.2f}")
print(f"   - Storage cost diff: ${pt_pred_results['storage_costs'] - pt_baseline_results['storage_costs']:,.2f}")
print(f"   - Transaction cost diff: ${pt_pred_results['transaction_costs'] - pt_baseline_results['transaction_costs']:,.2f}")
print(f"   - Revenue diff: ${pt_pred_results['total_revenue'] - pt_baseline_results['total_revenue']:,.2f}")

print('\n2. Moving Average Strategy:')
print(f"   - Predictive WORSE by ${ma_pred_results['net_earnings'] - ma_baseline_results['net_earnings']:,.2f}")
print(f"   - Storage cost diff: ${ma_pred_results['storage_costs'] - ma_baseline_results['storage_costs']:,.2f}")
print(f"   - Transaction cost diff: ${ma_pred_results['transaction_costs'] - ma_baseline_results['transaction_costs']:,.2f}")
print(f"   - Revenue diff: ${ma_pred_results['total_revenue'] - ma_baseline_results['total_revenue']:,.2f}")

print('\n🔍 ROOT CAUSES:')
print('   (Analysis above reveals which specific cost component is responsible)')

print('\n💡 RECOMMENDATIONS:')
print('   1. Review prediction confidence thresholds')
print('   2. Examine scenario shifting logic')
print('   3. Validate net benefit calculations')
print('   4. Consider whether 95% accuracy is the right metric')
print('   5. Test prediction strategies with different cost assumptions')

print('\n' + '='*80)
```
