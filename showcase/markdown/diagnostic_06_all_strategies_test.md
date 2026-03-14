# Diagnostic 06: All Strategies Validation Test

**Purpose:** Test all 5 prediction strategies with fixes

**Test Case:** Coffee synthetic_acc90

**Expected Results:**
1. Expected Value: ~$775k (+$48k, +6.6%)
2. Risk-Adjusted: ~$770k (+$43k, +5.9%)
3. Consensus: ~$765k (+$38k, +5.2%)
4. MA Predictive: ~$740k (+$13k, +1.8%)
5. PT Predictive: ~$730k (+$3k, +0.4%)

**Pass Criteria:**
- At least 3 strategies beat baseline
- Expected Value in top 2
- All show positive advantage


```python
%run ../00_setup_and_config
%run ../03_strategy_implementations
%run ./diagnostic_04_fixed_strategies
```


```python
import pandas as pd
import numpy as np
import pickle

print("="*80)
print("DIAGNOSTIC 06: ALL STRATEGIES VALIDATION TEST")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Test all 5 prediction strategies with fixes\n")
```

## Step 1: Load Data (with normalization)


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)

# Load and normalize prices
prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
prices['date'] = pd.to_datetime(prices['date'])

# Load and normalize predictions
with open(DATA_PATHS['prediction_matrices'], 'rb') as f:
    prediction_matrices = pickle.load(f)
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print(f"✓ Loaded {len(prices)} prices")
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

# Create fixed engine
engine = FixedBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)
```

## Step 2: Define All Fixed Strategies


```python
# For this diagnostic, we'll create fixed versions of all prediction strategies
# using the same date normalization approach as FixedExpectedValueStrategy

# Import strategies from notebook 03 - these already exist but may need date fixes
# We'll test them with the FixedBacktestEngine which handles date normalization

strategies_to_test = [
    # Baseline for comparison
    EqualBatchesStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **BASELINE_PARAMS['equal_batches']
    ),
    
    # Prediction strategies
    ExpectedValueStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **PREDICTION_PARAMS['expected_value']
    ),
    
    RiskAdjustedStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **PREDICTION_PARAMS['risk_adjusted']
    ),
    
    ConsensusStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **PREDICTION_PARAMS['consensus']
    ),
    
    MovingAveragePredictiveStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **PREDICTION_PARAMS['ma_predictive']
    ),
    
    PriceThresholdPredictiveStrategy(
        storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
        transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
        **PREDICTION_PARAMS['pt_predictive']
    ),
]

print(f"✓ Defined {len(strategies_to_test)} strategies to test")
for s in strategies_to_test:
    print(f"  - {s.name}")
```

## Step 3: Run All Strategies


```python
print("\n" + "="*80)
print("RUNNING ALL STRATEGIES")
print("="*80)

results_list = []

for strategy in strategies_to_test:
    print(f"\nRunning: {strategy.name}...")
    
    try:
        # Run backtest
        result = engine.run(strategy)
        
        # Calculate metrics
        total_revenue = sum(t['revenue'] for t in result['trades'])
        total_transaction_costs = sum(t['transaction_cost'] for t in result['trades'])
        total_storage_costs = result['daily_state']['daily_storage_cost'].sum()
        net_earnings = total_revenue - total_transaction_costs - total_storage_costs
        
        # Store results
        results_list.append({
            'strategy': strategy.name,
            'type': 'Baseline' if 'Equal Batches' in strategy.name else 'Prediction',
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'n_trades': len(result['trades']),
            'days_with_predictions': result.get('days_with_predictions', 0),
            'days_without_predictions': result.get('days_without_predictions', 0)
        })
        
        print(f"  ✓ Net earnings: ${net_earnings:,.2f}")
        
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        results_list.append({
            'strategy': strategy.name,
            'type': 'Baseline' if 'Equal Batches' in strategy.name else 'Prediction',
            'net_earnings': 0,
            'error': str(e)
        })

print("\n✓ All strategies completed")
```

## Step 4: Compare Results


```python
print("\n" + "="*80)
print("RESULTS COMPARISON")
print("="*80)

results_df = pd.DataFrame(results_list)

# Get baseline earnings
baseline_earnings = results_df[results_df['type'] == 'Baseline']['net_earnings'].iloc[0]

# Calculate advantage
results_df['advantage'] = results_df['net_earnings'] - baseline_earnings
results_df['advantage_pct'] = 100 * results_df['advantage'] / baseline_earnings

# Sort by net earnings (descending)
results_df = results_df.sort_values('net_earnings', ascending=False).reset_index(drop=True)

print("\nAll Results:")
display(results_df[[
    'strategy', 'type', 'net_earnings', 'n_trades', 
    'advantage', 'advantage_pct'
]])

print(f"\nBaseline (Equal Batches): ${baseline_earnings:,.2f}")
```

## Step 5: Prediction Strategy Analysis


```python
print("\n" + "="*80)
print("PREDICTION STRATEGY ANALYSIS")
print("="*80)

pred_results = results_df[results_df['type'] == 'Prediction'].copy()

if len(pred_results) > 0:
    print(f"\nPrediction Strategy Rankings:")
    for idx, row in pred_results.iterrows():
        symbol = '✓' if row['advantage'] > 0 else '✗'
        print(f"  {symbol} {row['strategy']}: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
    
    # Statistics
    print(f"\nStatistics:")
    print(f"  Strategies beating baseline: {len(pred_results[pred_results['advantage'] > 0])} / {len(pred_results)}")
    print(f"  Best advantage: ${pred_results['advantage'].max():,.2f} ({pred_results['advantage_pct'].max():+.2f}%)")
    print(f"  Worst advantage: ${pred_results['advantage'].min():,.2f} ({pred_results['advantage_pct'].min():+.2f}%)")
    print(f"  Mean advantage: ${pred_results['advantage'].mean():,.2f} ({pred_results['advantage_pct'].mean():+.2f}%)")
else:
    print("\n✗ No prediction strategies found!")
```

## Step 6: Prediction Coverage Analysis


```python
print("\n" + "="*80)
print("PREDICTION COVERAGE ANALYSIS")
print("="*80)

if 'days_with_predictions' in results_df.columns:
    pred_results = results_df[results_df['type'] == 'Prediction'].copy()
    
    if len(pred_results) > 0:
        print("\nPrediction coverage by strategy:")
        for idx, row in pred_results.iterrows():
            total_days = row['days_with_predictions'] + row['days_without_predictions']
            if total_days > 0:
                coverage = 100 * row['days_with_predictions'] / total_days
                symbol = '✓' if coverage > 80 else '⚠️'
                print(f"  {symbol} {row['strategy']}: {coverage:.1f}% ({row['days_with_predictions']} / {total_days} days)")
        
        # Overall coverage
        avg_coverage = pred_results.apply(
            lambda r: 100 * r['days_with_predictions'] / (r['days_with_predictions'] + r['days_without_predictions']),
            axis=1
        ).mean()
        
        print(f"\nAverage coverage: {avg_coverage:.1f}%")
        
        if avg_coverage > 80:
            print("✓ PASS: Good prediction coverage")
        else:
            print(f"⚠️  WARNING: Only {avg_coverage:.1f}% coverage")
else:
    print("\n⚠️  Coverage data not available")
```

## Step 7: Validation Checks


```python
print("\n" + "="*80)
print("VALIDATION CHECKS")
print("="*80)

pred_results = results_df[results_df['type'] == 'Prediction'].copy()

checks = {}

# Check 1: At least 3 strategies beat baseline
n_beating = len(pred_results[pred_results['advantage'] > 0])
checks['three_beat_baseline'] = n_beating >= 3

# Check 2: Expected Value in top 2
ev_results = pred_results[pred_results['strategy'].str.contains('Expected Value', na=False)]
if len(ev_results) > 0:
    ev_rank = pred_results[pred_results['strategy'].str.contains('Expected Value', na=False)].index[0]
    checks['ev_in_top2'] = ev_rank <= 1  # Top 2 (0-indexed)
else:
    checks['ev_in_top2'] = False

# Check 3: All show positive advantage
checks['all_positive'] = all(pred_results['advantage'] > 0)

# Check 4: At least one strategy beats baseline by >$30k
checks['strong_advantage'] = pred_results['advantage'].max() > 30000

print("\nValidation Criteria:")
print(f"  {'✓' if checks['three_beat_baseline'] else '✗'} At least 3 strategies beat baseline: {n_beating} / {len(pred_results)}")
print(f"  {'✓' if checks['ev_in_top2'] else '✗'} Expected Value in top 2: {checks['ev_in_top2']}")
print(f"  {'✓' if checks['all_positive'] else '✗'} All show positive advantage: {checks['all_positive']}")
print(f"  {'✓' if checks['strong_advantage'] else '✗'} At least one >$30k advantage: ${pred_results['advantage'].max():,.2f}")

# Overall verdict
critical_pass = checks['three_beat_baseline'] and checks['strong_advantage']
all_pass = all(checks.values())

print("\n" + "="*80)
if all_pass:
    print("✓✓✓ DIAGNOSTIC 06 FULL PASS")
    print("="*80)
    print("\nConclusion: All prediction strategies working correctly!")
    print(f"\nBest strategy: {pred_results.iloc[0]['strategy']}")
    print(f"Advantage: ${pred_results.iloc[0]['advantage']:+,.2f} ({pred_results.iloc[0]['advantage_pct']:+.2f}%)")
    print("\nNext step: Monotonicity test (diagnostic_07)")
elif critical_pass:
    print("✓✓ DIAGNOSTIC 06 CRITICAL PASS")
    print("="*80)
    print("\nConclusion: Core functionality working (multiple strategies beat baseline)")
    print(f"\nStrategies beating baseline: {n_beating} / {len(pred_results)}")
    
    failed_checks = [k for k, v in checks.items() if not v]
    print(f"\nFailed checks: {', '.join(failed_checks)}")
    print("\nNext step: Monotonicity test (diagnostic_07)")
else:
    print("✗✗✗ DIAGNOSTIC 06 FAIL")
    print("="*80)
    print("\nConclusion: Strategies do not meet validation criteria")
    print(f"\nStrategies beating baseline: {n_beating} / {len(pred_results)}")
    print(f"Best advantage: ${pred_results['advantage'].max():,.2f}")
    
    failed_checks = [k for k, v in checks.items() if not v]
    print(f"\nFailed checks: {', '.join(failed_checks)}")
    print("\nNext step: Review strategy implementations and re-run diagnostic_04")
```

## Step 8: Export Results for Further Analysis


```python
print("\n" + "="*80)
print("EXPORTING RESULTS")
print("="*80)

# Save to CSV for easy comparison
output_path = '/tmp/trading_results/diagnostic_06_all_strategies.csv'
results_df.to_csv(output_path, index=False)
print(f"\n✓ Results saved to: {output_path}")

# Display final summary
print("\nFinal Summary:")
print(f"  Total strategies tested: {len(results_df)}")
print(f"  Prediction strategies: {len(pred_results)}")
print(f"  Beating baseline: {n_beating} ({100*n_beating/len(pred_results):.1f}%)")
print(f"  Best advantage: ${pred_results['advantage'].max():,.2f}")
print(f"  Mean advantage: ${pred_results['advantage'].mean():,.2f}")
```
