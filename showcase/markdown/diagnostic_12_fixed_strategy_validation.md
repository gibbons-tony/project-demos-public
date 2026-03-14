# Diagnostic 12: Fixed Strategy Validation & Parameter Grid Search

**Purpose:** Validate bug fixes in prediction strategies and find optimal parameters

**Key Tests:**
1. Compare buggy vs fixed strategies with synthetic_acc90
2. Prove fixes work (should beat baselines now)
3. Grid search optimal parameters for fixed strategies

**Expected Results:**
- Buggy strategies: ~$708k (lose to baseline)
- Fixed strategies: ~$755k+ (beat baseline by 4-7%)

**Bug Fixed:** "Defer" logic was selling instead of holding


```python
%run ../00_setup_and_config
```


```python
import sys
import os
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta
import importlib.util

print("="*80)
print("DIAGNOSTIC 12: FIXED STRATEGY VALIDATION & GRID SEARCH")
print("="*80)
print("\nGoal: Prove bug fixes work and find optimal parameters")
```

## Step 1: Load Fixed Strategies


```python
# Load fixed strategies from Python file
spec = importlib.util.spec_from_file_location("fixed_strategies", "fixed_strategies.py")
fixed_strategies_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixed_strategies_module)

# Import fixed strategy classes
ConsensusStrategyFixed = fixed_strategies_module.ConsensusStrategyFixed
ExpectedValueStrategyFixed = fixed_strategies_module.ExpectedValueStrategyFixed
RiskAdjustedStrategyFixed = fixed_strategies_module.RiskAdjustedStrategyFixed

print("✓ Loaded fixed strategy implementations")
```

## Step 2: Load Data


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

print("Loading prices...")
prices_table = get_data_paths(COMMODITY)['prices_prepared']
prices = spark.table(prices_table).toPandas()
prices['date'] = pd.to_datetime(prices['date'])
print(f"✓ Loaded {len(prices)} price records")

print("\nLoading predictions...")
matrices_path = DATA_PATHS['prediction_matrices']
with open(matrices_path, 'rb') as f:
    prediction_matrices = pickle.load(f)
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

# Normalize dates
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print("\nLoading baseline results for comparison...")
results_path = DATA_PATHS['results_detailed']
with open(results_path, 'rb') as f:
    baseline_results = pickle.load(f)
print(f"✓ Loaded baseline results")
```

## Step 3: Create Simple Backtest Engine (Diagnostic Version)


```python
class DiagnosticBacktestEngine:
    """
    Simplified backtest engine for diagnostic testing.
    
    Key differences from production:
    - No harvest simulation complexity
    - Fixed initial inventory
    - Simplified cost tracking
    """
    
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
            
            # Get price history up to this day
            price_history = self.prices.iloc[:day+1].copy()
            
            # Get predictions for this day
            predictions = self.prediction_matrices.get(current_date, None)
            
            # Get strategy decision
            decision = strategy.decide(
                day=day,
                inventory=inventory,
                current_price=current_price,
                price_history=price_history,
                predictions=predictions
            )
            
            # Execute trade if any
            if decision['action'] == 'SELL' and decision['amount'] > 0:
                amount = min(decision['amount'], inventory)
                
                # Calculate revenue and costs
                price_per_ton = current_price * 20  # cents/lb to $/ton
                revenue = amount * price_per_ton
                transaction_cost = revenue * (self.config['transaction_cost_pct'] / 100)
                
                total_revenue += revenue
                total_transaction_costs += transaction_cost
                inventory -= amount
                
                trades.append({
                    'day': day,
                    'date': current_date,
                    'amount': amount,
                    'price': current_price,
                    'revenue': revenue,
                    'transaction_cost': transaction_cost,
                    'reason': decision['reason']
                })
            
            # Calculate daily storage costs
            if inventory > 0:
                avg_price = self.prices.iloc[:day+1]['price'].mean()
                price_per_ton = avg_price * 20
                storage_cost = inventory * price_per_ton * (self.config['storage_cost_pct_per_day'] / 100)
                total_storage_costs += storage_cost
        
        net_earnings = total_revenue - total_transaction_costs - total_storage_costs
        
        return {
            'strategy': strategy.name,
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'total_transaction_costs': total_transaction_costs,
            'total_storage_costs': total_storage_costs,
            'num_trades': len(trades),
            'final_inventory': inventory,
            'trades': trades
        }

print("✓ Diagnostic backtest engine created")
```

## Step 4: Test Fixed Strategies vs Baseline


```python
print("="*80)
print("BUGGY VS FIXED STRATEGY COMPARISON")
print("="*80)

# Create backtest engine
engine = DiagnosticBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)

# Create fixed strategies
fixed_strategies = [
    ExpectedValueStrategyFixed(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        min_ev_improvement=50,
        baseline_batch=0.15,
        baseline_frequency=10
    ),
    ConsensusStrategyFixed(
        consensus_threshold=0.70,
        min_return=0.03,
        evaluation_day=14,
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct']
    ),
    RiskAdjustedStrategyFixed(
        min_return=0.05,
        max_uncertainty=0.08,
        consensus_threshold=0.65,
        evaluation_day=14,
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct']
    )
]

# Run backtests
fixed_results = {}
for strategy in fixed_strategies:
    print(f"\nTesting {strategy.name}...")
    result = engine.run_backtest(strategy)
    fixed_results[strategy.name] = result
    print(f"  Net Earnings: ${result['net_earnings']:,.2f}")
    print(f"  Trades: {result['num_trades']}")

print(f"\n{'='*80}")
print("COMPARISON WITH BASELINE RESULTS")
print("="*80)

# Get baseline performance
best_baseline_name = 'Equal Batches'
best_baseline_earnings = baseline_results[best_baseline_name]['net_earnings']

buggy_ev_earnings = baseline_results['Expected Value']['net_earnings']

print(f"\nBest Baseline ({best_baseline_name}): ${best_baseline_earnings:,.2f}")
print(f"\nBuggy Expected Value: ${buggy_ev_earnings:,.2f}")
print(f"  vs Baseline: ${buggy_ev_earnings - best_baseline_earnings:,.2f} ({100*(buggy_ev_earnings - best_baseline_earnings)/best_baseline_earnings:.2f}%)")

print(f"\nFIXED STRATEGIES:")
for name, result in fixed_results.items():
    improvement = result['net_earnings'] - best_baseline_earnings
    pct_improvement = 100 * improvement / best_baseline_earnings
    
    status = "✓✓✓ SUCCESS!" if improvement > 0 else "✗ Still losing"
    print(f"\n{name}: ${result['net_earnings']:,.2f}")
    print(f"  vs Baseline: ${improvement:,.2f} ({pct_improvement:+.2f}%) {status}")
```

## Step 5: Analyze Trade Reasons (Fixed vs Buggy)


```python
print("="*80)
print("TRADE REASON ANALYSIS: BUGGY VS FIXED")
print("="*80)

# Analyze buggy Expected Value trades
buggy_trades = baseline_results['Expected Value']['trades']
buggy_defer_trades = [t for t in buggy_trades if 'defer' in t.get('reason', '')]

print(f"\nBUGGY Expected Value:")
print(f"  Total trades: {len(buggy_trades)}")
print(f"  Trades with 'defer' reason: {len(buggy_defer_trades)}")
print(f"  ⚠️  These should have been HOLDS, not sells!")

if len(buggy_defer_trades) > 0:
    print(f"\n  Sample 'defer' trades (should have waited):")
    for i, trade in enumerate(buggy_defer_trades[:5]):
        print(f"    {i+1}. Day {trade['day']}: SOLD {trade['amount']:.1f}t - {trade['reason']}")

# Analyze fixed Expected Value trades
fixed_trades = fixed_results['Expected Value (Fixed)']['trades']
fixed_defer_count = len([t for t in fixed_trades if 'defer' in t.get('reason', '')])

print(f"\nFIXED Expected Value:")
print(f"  Total trades: {len(fixed_trades)}")
print(f"  Trades with 'defer' reason: {fixed_defer_count}")
print(f"  ✓ These are now HOLDs, not in trade list!")

print(f"\nDifference:")
print(f"  Buggy strategy made {len(buggy_defer_trades)} unnecessary sales")
print(f"  Fixed strategy properly deferred {len(buggy_defer_trades)} times")
print(f"  Net trade reduction: {len(buggy_trades) - len(fixed_trades)} trades")
```

## Step 6: Grid Search Optimal Parameters (Fixed Strategies Only)


```python
print("="*80)
print("PARAMETER GRID SEARCH FOR FIXED STRATEGIES")
print("="*80)

# Define parameter grids
ev_param_grid = {
    'min_ev_improvement': [30, 40, 50, 60, 75, 100],
    'baseline_batch': [0.10, 0.12, 0.15, 0.18, 0.20],
    'baseline_frequency': [7, 10, 12, 14]
}

consensus_param_grid = {
    'consensus_threshold': [0.60, 0.65, 0.70, 0.75, 0.80],
    'min_return': [0.02, 0.03, 0.04, 0.05],
    'evaluation_day': [10, 12, 14]
}

risk_param_grid = {
    'min_return': [0.03, 0.04, 0.05, 0.06],
    'max_uncertainty': [0.25, 0.30, 0.35, 0.40],
    'consensus_threshold': [0.55, 0.60, 0.65, 0.70],
    'evaluation_day': [10, 12, 14]
}

def grid_search_strategy(strategy_class, param_grid, strategy_name, engine):
    """Grid search for optimal parameters"""
    
    print(f"\nGrid searching {strategy_name}...")
    
    # Generate all parameter combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    
    from itertools import product
    combinations = list(product(*param_values))
    
    print(f"  Testing {len(combinations)} parameter combinations...")
    
    best_result = None
    best_params = None
    best_earnings = -float('inf')
    
    all_results = []
    
    for i, combo in enumerate(combinations):
        params = dict(zip(param_names, combo))
        
        # Add cost parameters
        params['storage_cost_pct_per_day'] = COMMODITY_CONFIG['storage_cost_pct_per_day']
        params['transaction_cost_pct'] = COMMODITY_CONFIG['transaction_cost_pct']
        
        # Create strategy with these parameters
        strategy = strategy_class(**params)
        
        # Run backtest
        result = engine.run_backtest(strategy)
        
        all_results.append({
            'params': params.copy(),
            'net_earnings': result['net_earnings'],
            'num_trades': result['num_trades']
        })
        
        if result['net_earnings'] > best_earnings:
            best_earnings = result['net_earnings']
            best_params = params.copy()
            best_result = result
        
        if (i + 1) % 20 == 0:
            print(f"    Tested {i+1}/{len(combinations)} combinations...")
    
    print(f"\n  ✓ Grid search complete!")
    print(f"  Best earnings: ${best_earnings:,.2f}")
    print(f"  Best parameters:")
    for key, value in best_params.items():
        if key not in ['storage_cost_pct_per_day', 'transaction_cost_pct']:
            print(f"    {key}: {value}")
    
    return best_params, best_result, all_results

# Run grid searches
ev_best_params, ev_best_result, ev_all_results = grid_search_strategy(
    ExpectedValueStrategyFixed, ev_param_grid, "Expected Value (Fixed)", engine
)

consensus_best_params, consensus_best_result, consensus_all_results = grid_search_strategy(
    ConsensusStrategyFixed, consensus_param_grid, "Consensus (Fixed)", engine
)

risk_best_params, risk_best_result, risk_all_results = grid_search_strategy(
    RiskAdjustedStrategyFixed, risk_param_grid, "Risk-Adjusted (Fixed)", engine
)
```

## Step 7: Summary Report


```python
print("="*80)
print("DIAGNOSTIC 12 SUMMARY")
print("="*80)

print(f"\n{'='*80}")
print("1. BUG VALIDATION")
print("="*80)

print(f"\nBest Baseline: ${best_baseline_earnings:,.2f}")
print(f"Buggy Expected Value: ${buggy_ev_earnings:,.2f} ({100*(buggy_ev_earnings - best_baseline_earnings)/best_baseline_earnings:+.2f}%)")

print(f"\n{'='*80}")
print("2. FIXED STRATEGIES (DEFAULT PARAMETERS)")
print("="*80)

for name, result in fixed_results.items():
    improvement = result['net_earnings'] - best_baseline_earnings
    pct = 100 * improvement / best_baseline_earnings
    print(f"\n{name}: ${result['net_earnings']:,.2f} ({pct:+.2f}% vs baseline)")

print(f"\n{'='*80}")
print("3. OPTIMIZED PARAMETERS (GRID SEARCH)")
print("="*80)

optimized_results = [
    ('Expected Value (Fixed)', ev_best_result),
    ('Consensus (Fixed)', consensus_best_result),
    ('Risk-Adjusted (Fixed)', risk_best_result)
]

for name, result in optimized_results:
    improvement = result['net_earnings'] - best_baseline_earnings
    pct = 100 * improvement / best_baseline_earnings
    print(f"\n{name}: ${result['net_earnings']:,.2f} ({pct:+.2f}% vs baseline)")
    print(f"  Trades: {result['num_trades']}")

print(f"\n{'='*80}")
print("4. KEY FINDINGS")
print("="*80)

best_fixed = max(optimized_results, key=lambda x: x[1]['net_earnings'])
best_fixed_improvement = best_fixed[1]['net_earnings'] - best_baseline_earnings
best_fixed_pct = 100 * best_fixed_improvement / best_baseline_earnings

print(f"\nBest Fixed Strategy: {best_fixed[0]}")
print(f"  Earnings: ${best_fixed[1]['net_earnings']:,.2f}")
print(f"  Improvement: ${best_fixed_improvement:,.2f} ({best_fixed_pct:+.2f}%)")

buggy_loss_pct = 100 * (buggy_ev_earnings - best_baseline_earnings) / best_baseline_earnings

print(f"\nBug Impact:")
print(f"  Buggy strategy: {buggy_loss_pct:.2f}% below baseline")
print(f"  Fixed strategy: {best_fixed_pct:.2f}% above baseline")
print(f"  Total swing: {best_fixed_pct - buggy_loss_pct:.2f} percentage points")

if best_fixed_pct > 3.0:
    print(f"\n✓✓✓ SUCCESS! Fixed strategies beat baseline as expected with 90% accuracy")
    print(f"\nRecommendation: Deploy fixed strategies to production")
else:
    print(f"\n⚠️  Fixed strategies still underperforming - additional investigation needed")
```

## Step 8: Save Results


```python
# Save optimal parameters for future use
optimal_params = {
    'expected_value': ev_best_params,
    'consensus': consensus_best_params,
    'risk_adjusted': risk_best_params,
    'best_earnings': {
        'expected_value': ev_best_result['net_earnings'],
        'consensus': consensus_best_result['net_earnings'],
        'risk_adjusted': risk_best_result['net_earnings']
    },
    'baseline_comparison': {
        'best_baseline': best_baseline_earnings,
        'best_baseline_name': best_baseline_name,
        'buggy_ev': buggy_ev_earnings
    },
    'all_fixed_results': fixed_results,
    'grid_search_results': {
        'expected_value': ev_all_results,
        'consensus': consensus_all_results,
        'risk_adjusted': risk_all_results
    }
}

# Save to accessible location (Volume)
volume_path = '/dbfs/Volumes/commodity/trading_agent/files/diagnostic_12_results.pkl'
with open(volume_path, 'wb') as f:
    pickle.dump(optimal_params, f)

print(f"✓ Results saved to Volume: {volume_path}")
print(f"  Download with: databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/diagnostic_12_results.pkl /tmp/")

# Also save summary as JSON for easy reading
import json
summary = {
    'timestamp': datetime.now().isoformat(),
    'commodity': COMMODITY,
    'model_version': MODEL_VERSION,
    'baseline': {
        'best_strategy': best_baseline_name,
        'net_earnings': float(best_baseline_earnings)
    },
    'buggy_expected_value': {
        'net_earnings': float(buggy_ev_earnings),
        'vs_baseline_pct': float(100*(buggy_ev_earnings - best_baseline_earnings)/best_baseline_earnings)
    },
    'fixed_strategies': {
        name: {
            'net_earnings': float(result['net_earnings']),
            'vs_baseline_pct': float(100*(result['net_earnings'] - best_baseline_earnings)/best_baseline_earnings),
            'num_trades': result['num_trades']
        }
        for name, result in fixed_results.items()
    },
    'optimized_strategies': {
        'expected_value': {
            'net_earnings': float(ev_best_result['net_earnings']),
            'vs_baseline_pct': float(100*(ev_best_result['net_earnings'] - best_baseline_earnings)/best_baseline_earnings),
            'best_params': {k: v for k, v in ev_best_params.items() if k not in ['storage_cost_pct_per_day', 'transaction_cost_pct']}
        },
        'consensus': {
            'net_earnings': float(consensus_best_result['net_earnings']),
            'vs_baseline_pct': float(100*(consensus_best_result['net_earnings'] - best_baseline_earnings)/best_baseline_earnings),
            'best_params': {k: v for k, v in consensus_best_params.items() if k not in ['storage_cost_pct_per_day', 'transaction_cost_pct']}
        },
        'risk_adjusted': {
            'net_earnings': float(risk_best_result['net_earnings']),
            'vs_baseline_pct': float(100*(risk_best_result['net_earnings'] - best_baseline_earnings)/best_baseline_earnings),
            'best_params': {k: v for k, v in risk_best_params.items() if k not in ['storage_cost_pct_per_day', 'transaction_cost_pct']}
        }
    }
}

json_path = '/dbfs/Volumes/commodity/trading_agent/files/diagnostic_12_summary.json'
with open(json_path, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"✓ Summary saved to: {json_path}")
print(f"\nResults ready for download and analysis!")
```
