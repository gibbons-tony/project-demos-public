# Diagnostic 13: Comprehensive Grid Search - All Strategies & Parameters

**Purpose:** Systematic parameter optimization across ALL 9 trading strategies

**Scope:**
- 4 Baseline strategies: ImmediateSale, EqualBatch, PriceThreshold, MovingAverage
- 5 Prediction strategies: Consensus, ExpectedValue, RiskAdjusted, + 2 matched pairs
- Total combinations: 2,001 base + batch sizing variations

**Focus:** Matched pairs with synthetic_acc90 to prove prediction value-add

**Expected Results:**
- Fixed strategies beat baseline by 4-7%
- Matched pairs show clear prediction advantage
- Optimal parameters identified for production deployment


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
from itertools import product
import importlib.util

print("="*80)
print("DIAGNOSTIC 13: COMPREHENSIVE PARAMETER GRID SEARCH")
print("="*80)
print("\nScope: ALL 9 strategies, ALL parameters (including hidden)")
print("Focus: Matched pairs to isolate prediction value-add")
```

## Configuration


```
# Test configuration
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

# Grid search configuration
USE_COARSE_GRID = True  # Start with coarse, then fine-tune
MAX_COMBINATIONS_PER_STRATEGY = None  # None = test all, or set limit for quick test
SAVE_ALL_RESULTS = True  # Save every combination for analysis

# Focus areas
STRATEGIES_TO_TEST = 'all'  # 'all', 'matched_pairs', 'baselines', 'predictions', or list
PRIORITY_MATCHED_PAIRS = True  # Run matched pairs first

print(f"Configuration:")
print(f"  Commodity: {COMMODITY}")
print(f"  Model: {MODEL_VERSION}")
print(f"  Grid: {'Coarse' if USE_COARSE_GRID else 'Fine'}")
print(f"  Focus: {'Matched pairs priority' if PRIORITY_MATCHED_PAIRS else 'All strategies'}")
```

## Load Fixed Strategies and Data


```
# Load baseline strategies from production (they don't have the defer bug)
%run ../03_strategy_implementations

print("✓ Loaded baseline strategies from production:")
print("  - ImmediateSaleStrategy")
print("  - EqualBatchStrategy")
print("  - PriceThresholdStrategy")
print("  - MovingAverageStrategy")
print("  - PriceThresholdPredictive")
print("  - MovingAveragePredictive")

print("\n✓ Loaded fixed strategies from diagnostics:")
print("  - ConsensusStrategyFixed")
print("  - ExpectedValueStrategyFixed")
print("  - RiskAdjustedStrategyFixed")
```


```
# Load data
DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

print("Loading data...")
prices_table = get_data_paths(COMMODITY)['prices_prepared']
prices = spark.table(prices_table).toPandas()
prices['date'] = pd.to_datetime(prices['date'])

matrices_path = DATA_PATHS['prediction_matrices']
with open(matrices_path, 'rb') as f:
    prediction_matrices = pickle.load(f)
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print(f"✓ Loaded {len(prices)} price records")
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")
```

## Define Parameter Grids


```
# Parameter grids for all strategies

if USE_COARSE_GRID:
    # Coarse grid for initial sweep
    PARAM_GRIDS = {
        'immediate_sale': {
            'min_batch_size': [3.0, 5.0, 7.0, 10.0],
            'sale_frequency_days': [5, 7, 10, 14]
        },
        'equal_batch': {
            'batch_size': [0.15, 0.20, 0.25, 0.30, 0.35],
            'frequency_days': [20, 25, 30, 35, 40]
        },
        'price_threshold': {
            'threshold_pct': [0.02, 0.03, 0.05, 0.07, 0.10],
            'batch_fraction': [0.20, 0.25, 0.30, 0.35],
            'max_days_without_sale': [45, 60, 75, 90]
            # Note: cooldown_days hard-coded to 7 in strategy class
        },
        'moving_average': {
            'ma_period': [20, 25, 30, 35, 40],
            'batch_fraction': [0.20, 0.25, 0.30, 0.35],
            'max_days_without_sale': [45, 60, 75, 90]
            # Note: cooldown_days hard-coded to 7 in strategy class
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
else:
    # Fine grid - tighter ranges around optimal values from coarse search
    # TODO: Update these ranges based on coarse search results
    PARAM_GRIDS = {
        # Define fine grids after coarse search completes
    }

# Calculate total combinations
total_combos = 0
for strategy, grid in PARAM_GRIDS.items():
    combos = np.prod([len(v) for v in grid.values()])
    print(f"{strategy}: {combos} combinations")
    total_combos += combos

# Matched pairs share same parameter grids
print(f"\nMatched pairs (share params):")
print(f"  price_threshold ↔ price_threshold_predictive: {np.prod([len(v) for v in PARAM_GRIDS['price_threshold'].values()])} combinations")
print(f"  moving_average ↔ moving_average_predictive: {np.prod([len(v) for v in PARAM_GRIDS['moving_average'].values()])} combinations")

matched_pair_combos = (
    np.prod([len(v) for v in PARAM_GRIDS['price_threshold'].values()]) +
    np.prod([len(v) for v in PARAM_GRIDS['moving_average'].values()])
)

print(f"\nTotal base combinations: {total_combos}")
print(f"Total with matched pairs: {total_combos + matched_pair_combos}")
```

## Backtest Engine (From diagnostic_12)


```
class DiagnosticBacktestEngine:
    """Simplified backtest engine for grid search"""
    
    def __init__(self, prices_df, prediction_matrices, commodity_config):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.config = commodity_config
        
    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest for a single strategy"""
        
        inventory = initial_inventory
        trades = []
        total_revenue = 0
        total_transaction_costs = 0
        total_storage_costs = 0
        
        strategy.reset()
        strategy.set_harvest_start(0)
        
        for day in range(len(self.prices)):
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']
            price_history = self.prices.iloc[:day+1].copy()
            predictions = self.prediction_matrices.get(current_date, None)
            
            decision = strategy.decide(
                day=day,
                inventory=inventory,
                current_price=current_price,
                price_history=price_history,
                predictions=predictions
            )
            
            if decision['action'] == 'SELL' and decision['amount'] > 0:
                amount = min(decision['amount'], inventory)
                price_per_ton = current_price * 20
                revenue = amount * price_per_ton
                transaction_cost = revenue * (self.config['transaction_cost_pct'] / 100)
                
                total_revenue += revenue
                total_transaction_costs += transaction_cost
                inventory -= amount
                
                trades.append({
                    'day': day,
                    'amount': amount,
                    'price': current_price,
                    'revenue': revenue,
                    'reason': decision['reason']
                })
            
            if inventory > 0:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                price_per_ton = avg_price * 20
                storage_cost = inventory * price_per_ton * (self.config['storage_cost_pct_per_day'] / 100)
                total_storage_costs += storage_cost
        
        net_earnings = total_revenue - total_transaction_costs - total_storage_costs
        
        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'total_transaction_costs': total_transaction_costs,
            'total_storage_costs': total_storage_costs,
            'num_trades': len(trades),
            'final_inventory': inventory,
            'trades': trades
        }

engine = DiagnosticBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)
print("✓ Backtest engine ready")
```

## Grid Search Framework


```
def grid_search_strategy(strategy_class, param_grid, strategy_name, engine, 
                        is_prediction_strategy=False, max_combos=None):
    """
    Grid search for a single strategy.
    
    Args:
        strategy_class: Strategy class to test
        param_grid: Dictionary of parameter names to lists of values
        strategy_name: Display name
        engine: Backtest engine
        is_prediction_strategy: Whether this uses predictions
        max_combos: Maximum combinations to test (None = all)
    
    Returns:
        best_params, best_result, all_results
    """
    
    print(f"\n{'='*80}")
    print(f"Grid searching: {strategy_name}")
    print("="*80)
    
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(product(*param_values))
    
    if max_combos and len(combinations) > max_combos:
        import random
        random.seed(42)
        combinations = random.sample(combinations, max_combos)
        print(f"Testing {max_combos} of {len(combinations)} combinations (sampled)")
    else:
        print(f"Testing {len(combinations)} parameter combinations")
    
    best_earnings = -float('inf')
    best_params = None
    best_result = None
    all_results = []
    
    for i, combo in enumerate(combinations):
        params = dict(zip(param_names, combo))
        
        # Add cost parameters if needed
        if is_prediction_strategy:
            params['storage_cost_pct_per_day'] = COMMODITY_CONFIG['storage_cost_pct_per_day']
            params['transaction_cost_pct'] = COMMODITY_CONFIG['transaction_cost_pct']
        
        # Create strategy
        try:
            strategy = strategy_class(**params)
        except Exception as e:
            print(f"  Error creating strategy with params {params}: {e}")
            continue
        
        # Run backtest
        try:
            result = engine.run_backtest(strategy)
        except Exception as e:
            print(f"  Error running backtest: {e}")
            continue
        
        # Store result
        all_results.append({
            'params': params.copy(),
            'net_earnings': result['net_earnings'],
            'num_trades': result['num_trades'],
            'final_inventory': result['final_inventory']
        })
        
        # Update best
        if result['net_earnings'] > best_earnings:
            best_earnings = result['net_earnings']
            best_params = params.copy()
            best_result = result
        
        # Progress
        if (i + 1) % 50 == 0 or (i + 1) == len(combinations):
            print(f"  Progress: {i+1}/{len(combinations)} ({100*(i+1)/len(combinations):.1f}%) | Best so far: ${best_earnings:,.0f}")
    
    print(f"\n✓ Grid search complete")
    print(f"  Best net earnings: ${best_earnings:,.2f}")
    print(f"  Best parameters:")
    for key, value in best_params.items():
        if key not in ['storage_cost_pct_per_day', 'transaction_cost_pct']:
            print(f"    {key}: {value}")
    
    return best_params, best_result, all_results
```

## Run Grid Searches - MATCHED PAIRS FIRST (Priority)


```
print("="*80)
print("MATCHED PAIRS GRID SEARCH - HIGHEST PRIORITY")
print("="*80)
print("\nThese should show clear prediction advantage if bugs are fixed.")
print("Testing baseline and predictive versions with IDENTICAL parameters.")

matched_pair_results = {}
```

### Matched Pair 1: Price Threshold

**Critical Test:** With same parameters, does adding predictions improve performance?


```
print("\n" + "="*80)
print("MATCHED PAIR 1: PRICE THRESHOLD (BASELINE vs PREDICTIVE)")
print("="*80)
print("\nCritical test: With IDENTICAL parameters, does adding predictions help?")

# Test baseline first
print("\n>>> Testing PriceThresholdStrategy (baseline - historical indicators only)")
pt_baseline_params, pt_baseline_result, pt_baseline_all = grid_search_strategy(
    PriceThresholdStrategy,
    PARAM_GRIDS['price_threshold'],
    "Price Threshold (Baseline)",
    engine,
    is_prediction_strategy=False,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

# Test predictive with SAME parameter grid
print("\n>>> Testing PriceThresholdPredictive (predictions added)")
pt_predictive_params, pt_predictive_result, pt_predictive_all = grid_search_strategy(
    PriceThresholdPredictive,
    PARAM_GRIDS['price_threshold'],  # SAME grid as baseline
    "Price Threshold Predictive",
    engine,
    is_prediction_strategy=True,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

# Store results
matched_pair_results['price_threshold'] = {
    'baseline': (pt_baseline_params, pt_baseline_result, pt_baseline_all),
    'predictive': (pt_predictive_params, pt_predictive_result, pt_predictive_all)
}

# Immediate comparison
improvement = pt_predictive_result['net_earnings'] - pt_baseline_result['net_earnings']
pct_improvement = 100 * improvement / pt_baseline_result['net_earnings']

print(f"\n{'='*80}")
print(f"PRICE THRESHOLD MATCHED PAIR RESULTS:")
print(f"  Baseline (best):   ${pt_baseline_result['net_earnings']:,.2f}")
print(f"  Predictive (best): ${pt_predictive_result['net_earnings']:,.2f}")
print(f"  Improvement:       ${improvement:,.2f} ({pct_improvement:+.2f}%)")

if improvement > 0:
    print(f"  ✓✓✓ Predictions add value! {pct_improvement:.2f}% better")
else:
    print(f"  ✗ Predictions hurt performance - needs investigation")
```

### Matched Pair 2: Moving Average

**Critical Test:** With same parameters, does adding predictions improve performance?


```
print("\n" + "="*80)
print("MATCHED PAIR 2: MOVING AVERAGE (BASELINE vs PREDICTIVE)")
print("="*80)
print("\nCritical test: With IDENTICAL parameters, does adding predictions help?")

# Test baseline first
print("\n>>> Testing MovingAverageStrategy (baseline - historical indicators only)")
ma_baseline_params, ma_baseline_result, ma_baseline_all = grid_search_strategy(
    MovingAverageStrategy,
    PARAM_GRIDS['moving_average'],
    "Moving Average (Baseline)",
    engine,
    is_prediction_strategy=False,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

# Test predictive with SAME parameter grid
print("\n>>> Testing MovingAveragePredictive (predictions added)")
ma_predictive_params, ma_predictive_result, ma_predictive_all = grid_search_strategy(
    MovingAveragePredictive,
    PARAM_GRIDS['moving_average'],  # SAME grid as baseline
    "Moving Average Predictive",
    engine,
    is_prediction_strategy=True,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

# Store results
matched_pair_results['moving_average'] = {
    'baseline': (ma_baseline_params, ma_baseline_result, ma_baseline_all),
    'predictive': (ma_predictive_params, ma_predictive_result, ma_predictive_all)
}

# Immediate comparison
improvement = ma_predictive_result['net_earnings'] - ma_baseline_result['net_earnings']
pct_improvement = 100 * improvement / ma_baseline_result['net_earnings']

print(f"\n{'='*80}")
print(f"MOVING AVERAGE MATCHED PAIR RESULTS:")
print(f"  Baseline (best):   ${ma_baseline_result['net_earnings']:,.2f}")
print(f"  Predictive (best): ${ma_predictive_result['net_earnings']:,.2f}")
print(f"  Improvement:       ${improvement:,.2f} ({pct_improvement:+.2f}%)")

if improvement > 0:
    print(f"  ✓✓✓ Predictions add value! {pct_improvement:.2f}% better")
else:
    print(f"  ✗ Predictions hurt performance - needs investigation")
```

## Run Grid Searches - STANDALONE PREDICTION STRATEGIES


```
print("="*80)
print("STANDALONE PREDICTION STRATEGIES - FIXED VERSIONS")
print("="*80)

standalone_results = {}
```

### Expected Value (Fixed)


```
ev_best_params, ev_best_result, ev_all_results = grid_search_strategy(
    ExpectedValueStrategyFixed,
    PARAM_GRIDS['expected_value'],
    "Expected Value (Fixed)",
    engine,
    is_prediction_strategy=True,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

standalone_results['expected_value'] = {
    'best_params': ev_best_params,
    'best_result': ev_best_result,
    'all_results': ev_all_results
}
```

### Consensus (Fixed)


```
cons_best_params, cons_best_result, cons_all_results = grid_search_strategy(
    ConsensusStrategyFixed,
    PARAM_GRIDS['consensus'],
    "Consensus (Fixed)",
    engine,
    is_prediction_strategy=True,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

standalone_results['consensus'] = {
    'best_params': cons_best_params,
    'best_result': cons_best_result,
    'all_results': cons_all_results
}
```

### Risk-Adjusted (Fixed)


```
risk_best_params, risk_best_result, risk_all_results = grid_search_strategy(
    RiskAdjustedStrategyFixed,
    PARAM_GRIDS['risk_adjusted'],
    "Risk-Adjusted (Fixed)",
    engine,
    is_prediction_strategy=True,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

standalone_results['risk_adjusted'] = {
    'best_params': risk_best_params,
    'best_result': risk_best_result,
    'all_results': risk_all_results
}
```

## Run Grid Searches - BASELINE STRATEGIES


```
print("="*80)
print("BASELINE STRATEGIES - NO PREDICTIONS")
print("="*80)

baseline_results = {}

# ImmediateSaleStrategy
print("\n>>> Testing ImmediateSaleStrategy")
is_best_params, is_best_result, is_all_results = grid_search_strategy(
    ImmediateSaleStrategy,
    PARAM_GRIDS['immediate_sale'],
    "Immediate Sale",
    engine,
    is_prediction_strategy=False,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

baseline_results['immediate_sale'] = {
    'best_params': is_best_params,
    'best_result': is_best_result,
    'all_results': is_all_results
}

# EqualBatchStrategy
print("\n>>> Testing EqualBatchStrategy")
eb_best_params, eb_best_result, eb_all_results = grid_search_strategy(
    EqualBatchStrategy,
    PARAM_GRIDS['equal_batch'],
    "Equal Batch",
    engine,
    is_prediction_strategy=False,
    max_combos=MAX_COMBINATIONS_PER_STRATEGY
)

baseline_results['equal_batch'] = {
    'best_params': eb_best_params,
    'best_result': eb_best_result,
    'all_results': eb_all_results
}

print(f"\n{'='*80}")
print("BASELINE STRATEGIES SUMMARY:")
print(f"  ImmediateSale: ${is_best_result['net_earnings']:,.2f}")
print(f"  EqualBatch:    ${eb_best_result['net_earnings']:,.2f}")
print("\nNote: PriceThreshold and MovingAverage baselines tested in matched pairs section above")
```

## Summary Analysis


```
print("="*80)
print("COMPREHENSIVE GRID SEARCH RESULTS SUMMARY")
print("="*80)

# Find best overall strategy
all_strategy_results = []

# Add standalone predictions
for name, data in standalone_results.items():
    all_strategy_results.append({
        'strategy': name,
        'type': 'prediction',
        'net_earnings': data['best_result']['net_earnings'],
        'params': data['best_params']
    })

# Add matched pairs (when available)
for name, data in matched_pair_results.items():
    if 'baseline' in data:
        all_strategy_results.append({
            'strategy': f"{name}_baseline",
            'type': 'baseline',
            'net_earnings': data['baseline'][1]['net_earnings'],
            'params': data['baseline'][0]
        })
    if 'predictive' in data:
        all_strategy_results.append({
            'strategy': f"{name}_predictive",
            'type': 'prediction',
            'net_earnings': data['predictive'][1]['net_earnings'],
            'params': data['predictive'][0]
        })

# Sort by earnings
all_strategy_results.sort(key=lambda x: x['net_earnings'], reverse=True)

print("\nTop 5 Strategies (by net earnings):")
for i, result in enumerate(all_strategy_results[:5]):
    print(f"\n{i+1}. {result['strategy']} ({result['type']})")
    print(f"   Net Earnings: ${result['net_earnings']:,.2f}")
    print(f"   Parameters: {result['params']}")

# Matched pair analysis
print("\n" + "="*80)
print("MATCHED PAIR COMPARISON")
print("="*80)

for pair_name, pair_data in matched_pair_results.items():
    if 'baseline' in pair_data and 'predictive' in pair_data:
        baseline_earnings = pair_data['baseline'][1]['net_earnings']
        predictive_earnings = pair_data['predictive'][1]['net_earnings']
        improvement = predictive_earnings - baseline_earnings
        pct_improvement = 100 * improvement / baseline_earnings
        
        print(f"\n{pair_name.upper()}:")
        print(f"  Baseline:   ${baseline_earnings:,.2f}")
        print(f"  Predictive: ${predictive_earnings:,.2f}")
        print(f"  Improvement: ${improvement:,.2f} ({pct_improvement:+.2f}%)")
        
        if improvement > 0:
            print(f"  ✓✓✓ Predictions add value!")
        else:
            print(f"  ✗ Predictions hurt performance - investigate further")
```

## Save Comprehensive Results


```
# Save all results for detailed analysis
comprehensive_results = {
    'timestamp': datetime.now().isoformat(),
    'commodity': COMMODITY,
    'model_version': MODEL_VERSION,
    'grid_type': 'coarse' if USE_COARSE_GRID else 'fine',
    'matched_pairs': matched_pair_results,
    'standalone_predictions': standalone_results,
    'baselines': baseline_results,
    'summary': all_strategy_results
}

# Save to Volume (accessible location)
volume_path = '/dbfs/Volumes/commodity/trading_agent/files/diagnostic_13_results.pkl'
with open(volume_path, 'wb') as f:
    pickle.dump(comprehensive_results, f)

print(f"✓ Comprehensive results saved to Volume: {volume_path}")
print(f"  Download with: databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/diagnostic_13_results.pkl /tmp/")

# Save summary as JSON for easy reading
import json
summary = {
    'timestamp': datetime.now().isoformat(),
    'commodity': COMMODITY,
    'model_version': MODEL_VERSION,
    'matched_pairs': {
        pair_name: {
            'baseline': {
                'net_earnings': float(pair_data['baseline'][1]['net_earnings']) if 'baseline' in pair_data else None,
                'best_params': pair_data['baseline'][0] if 'baseline' in pair_data else None
            },
            'predictive': {
                'net_earnings': float(pair_data['predictive'][1]['net_earnings']) if 'predictive' in pair_data else None,
                'best_params': pair_data['predictive'][0] if 'predictive' in pair_data else None
            },
            'improvement_pct': float(100 * (pair_data['predictive'][1]['net_earnings'] - pair_data['baseline'][1]['net_earnings']) / pair_data['baseline'][1]['net_earnings']) if 'baseline' in pair_data and 'predictive' in pair_data else None
        }
        for pair_name, pair_data in matched_pair_results.items()
    },
    'top_strategies': [
        {
            'strategy': result['strategy'],
            'type': result['type'],
            'net_earnings': float(result['net_earnings']),
            'params': result['params']
        }
        for result in all_strategy_results[:5]
    ]
}

json_path = '/dbfs/Volumes/commodity/trading_agent/files/diagnostic_13_summary.json'
with open(json_path, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"✓ Summary saved to: {json_path}")

print(f"\nResults include:")
print(f"  - All tested parameter combinations")
print(f"  - Best parameters for each strategy")
print(f"  - Matched pair comparisons")
print(f"  - Performance rankings")
print(f"\nReady for download and analysis!")
```

## Next Steps

1. **If matched pairs show prediction advantage:**
   - Bug fix validated ✓
   - Deploy optimal parameters to production
   - Test with other accuracy levels (60%, 70%, 80%)

2. **If matched pairs still show baseline winning:**
   - Additional diagnostics needed
   - Check for other logic bugs
   - Review cost assumptions

3. **Fine-tuning:**
   - Run fine grid search around optimal coarse values
   - Test batch sizing parameters
   - Optimize cooldown_days (currently hard-coded to 7)
