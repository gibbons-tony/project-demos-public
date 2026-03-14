# Diagnostic 07: Monotonicity Test

**Purpose:** Verify performance improves monotonically with accuracy

**Test:** Run Expected Value strategy on all synthetic accuracies (60%, 70%, 80%, 90%)

**Expected Results:**
- 60%: ~$735k (+1.1%)
- 70%: ~$750k (+3.2%)
- 80%: ~$765k (+5.2%)
- 90%: ~$775k (+6.6%)

**Pass Criteria:**
- Monotonic increase (each > previous)
- 90% > 80% by >$10k
- All positive advantage (except maybe 60%)


```python
%run ../00_setup_and_config
%run ../03_strategy_implementations
%run ./diagnostic_04_fixed_strategies
```


```python
import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt

print("="*80)
print("DIAGNOSTIC 07: MONOTONICITY TEST")
print("="*80)
print("\nTest: Expected Value strategy across all accuracy levels")
print("Goal: Verify performance improves with accuracy\n")
```

## Step 1: Define Test Configuration


```python
COMMODITY = 'coffee'
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

# Test all accuracy levels
ACCURACY_LEVELS = [60, 70, 80, 90]

print(f"Testing commodity: {COMMODITY}")
print(f"Accuracy levels: {ACCURACY_LEVELS}")
print(f"Strategy: Expected Value")
```

## Step 2: Load Prices (Once)


```python
# Load and normalize prices (same for all accuracy levels)
prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
prices['date'] = pd.to_datetime(prices['date'])

print(f"✓ Loaded {len(prices)} price records")
```

## Step 3: Run Strategy for Each Accuracy Level


```python
print("\n" + "="*80)
print("RUNNING ACCURACY SWEEP")
print("="*80)

results_list = []

for accuracy in ACCURACY_LEVELS:
    model_version = f'synthetic_acc{accuracy}'
    print(f"\n{'='*80}")
    print(f"Testing {accuracy}% accuracy ({model_version})")
    print("="*80)
    
    try:
        # Load predictions for this accuracy
        DATA_PATHS = get_data_paths(COMMODITY, model_version)
        
        with open(DATA_PATHS['prediction_matrices'], 'rb') as f:
            prediction_matrices = pickle.load(f)
        
        # Normalize dates
        prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}
        
        print(f"  ✓ Loaded {len(prediction_matrices)} prediction matrices")
        
        # Create engine
        engine = FixedBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)
        
        # Create strategy
        strategy = ExpectedValueStrategy(
            storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
            transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
            **PREDICTION_PARAMS['expected_value']
        )
        
        print(f"  Running {strategy.name}...")
        
        # Run backtest
        result = engine.run(strategy)
        
        # Calculate metrics
        total_revenue = sum(t['revenue'] for t in result['trades'])
        total_transaction_costs = sum(t['transaction_cost'] for t in result['trades'])
        total_storage_costs = result['daily_state']['daily_storage_cost'].sum()
        net_earnings = total_revenue - total_transaction_costs - total_storage_costs
        
        # Store results
        results_list.append({
            'accuracy': accuracy,
            'model_version': model_version,
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
        import traceback
        traceback.print_exc()
        results_list.append({
            'accuracy': accuracy,
            'model_version': model_version,
            'net_earnings': 0,
            'error': str(e)
        })

print("\n✓ All accuracy levels completed")
```

## Step 4: Calculate Baseline Comparison


```python
print("\n" + "="*80)
print("BASELINE COMPARISON")
print("="*80)

# Run baseline (Equal Batches) for reference
# Note: Baseline doesn't use predictions, so same result regardless of accuracy
engine_baseline = FixedBacktestEngine(prices, {}, COMMODITY_CONFIG)

baseline_strategy = EqualBatchesStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    **BASELINE_PARAMS['equal_batches']
)

print(f"\nRunning baseline: {baseline_strategy.name}...")
baseline_result = engine_baseline.run(baseline_strategy)

baseline_revenue = sum(t['revenue'] for t in baseline_result['trades'])
baseline_transaction_costs = sum(t['transaction_cost'] for t in baseline_result['trades'])
baseline_storage_costs = baseline_result['daily_state']['daily_storage_cost'].sum()
baseline_earnings = baseline_revenue - baseline_transaction_costs - baseline_storage_costs

print(f"✓ Baseline net earnings: ${baseline_earnings:,.2f}")

# Add advantage calculations
results_df = pd.DataFrame(results_list)
if 'net_earnings' in results_df.columns:
    results_df['advantage'] = results_df['net_earnings'] - baseline_earnings
    results_df['advantage_pct'] = 100 * results_df['advantage'] / baseline_earnings
```

## Step 5: Display Results


```python
print("\n" + "="*80)
print("MONOTONICITY RESULTS")
print("="*80)

print(f"\nBaseline (Equal Batches): ${baseline_earnings:,.2f}")
print("\nExpected Value by Accuracy:")

display(results_df[[
    'accuracy', 'net_earnings', 'advantage', 'advantage_pct', 'n_trades'
]].sort_values('accuracy'))

# Print formatted summary
print("\nFormatted Summary:")
for idx, row in results_df.sort_values('accuracy').iterrows():
    symbol = '✓' if row['advantage'] > 0 else '✗'
    print(f"  {symbol} {row['accuracy']}%: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
```

## Step 6: Monotonicity Checks


```python
print("\n" + "="*80)
print("MONOTONICITY CHECKS")
print("="*80)

results_sorted = results_df.sort_values('accuracy').copy()

checks = {}

# Check 1: Monotonic increase
is_monotonic = all(
    results_sorted.iloc[i]['net_earnings'] < results_sorted.iloc[i+1]['net_earnings']
    for i in range(len(results_sorted) - 1)
)
checks['monotonic'] = is_monotonic

# Check 2: 90% > 80% by >$10k
if len(results_sorted) >= 4:
    earnings_90 = results_sorted[results_sorted['accuracy'] == 90]['net_earnings'].iloc[0]
    earnings_80 = results_sorted[results_sorted['accuracy'] == 80]['net_earnings'].iloc[0]
    diff_90_80 = earnings_90 - earnings_80
    checks['90_beats_80_by_10k'] = diff_90_80 > 10000
else:
    diff_90_80 = 0
    checks['90_beats_80_by_10k'] = False

# Check 3: All positive advantage (except maybe 60%)
high_accuracy = results_sorted[results_sorted['accuracy'] >= 70]
checks['high_accuracy_positive'] = all(high_accuracy['advantage'] > 0)

# Check 4: 90% beats baseline by >$30k
if len(results_sorted) >= 4:
    adv_90 = results_sorted[results_sorted['accuracy'] == 90]['advantage'].iloc[0]
    checks['90_strong_advantage'] = adv_90 > 30000
else:
    checks['90_strong_advantage'] = False

print("\nValidation Criteria:")
print(f"  {'✓' if checks['monotonic'] else '✗'} Monotonic increase: {checks['monotonic']}")

if not checks['monotonic']:
    print("    Earnings sequence: ", end="")
    for acc, earn in zip(results_sorted['accuracy'], results_sorted['net_earnings']):
        print(f"{acc}%: ${earn:,.0f}, ", end="")
    print()

print(f"  {'✓' if checks['90_beats_80_by_10k'] else '✗'} 90% > 80% by >$10k: ${diff_90_80:,.2f}")
print(f"  {'✓' if checks['high_accuracy_positive'] else '✗'} High accuracy (70%+) all positive: {checks['high_accuracy_positive']}")

if len(results_sorted) >= 4:
    print(f"  {'✓' if checks['90_strong_advantage'] else '✗'} 90% beats baseline by >$30k: ${adv_90:,.2f}")

# Calculate incremental gains
print("\nIncremental gains:")
for i in range(len(results_sorted) - 1):
    curr = results_sorted.iloc[i]
    next_row = results_sorted.iloc[i+1]
    gain = next_row['net_earnings'] - curr['net_earnings']
    gain_pct = 100 * gain / curr['net_earnings'] if curr['net_earnings'] != 0 else 0
    symbol = '✓' if gain > 0 else '✗'
    print(f"  {symbol} {curr['accuracy']}% → {next_row['accuracy']}%: ${gain:+,.2f} ({gain_pct:+.2f}%)")
```

## Step 7: Visualization


```python
print("\n" + "="*80)
print("VISUALIZATION")
print("="*80)

try:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Plot 1: Net Earnings vs Accuracy
    ax1.plot(results_sorted['accuracy'], results_sorted['net_earnings'], 
             marker='o', linewidth=2, markersize=8, label='Expected Value')
    ax1.axhline(y=baseline_earnings, color='r', linestyle='--', 
                linewidth=2, label='Baseline (Equal Batches)')
    ax1.set_xlabel('Prediction Accuracy (%)', fontsize=12)
    ax1.set_ylabel('Net Earnings ($)', fontsize=12)
    ax1.set_title('Net Earnings vs Prediction Accuracy', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=10)
    ax1.set_xticks(ACCURACY_LEVELS)
    
    # Plot 2: Advantage vs Accuracy
    ax2.bar(results_sorted['accuracy'], results_sorted['advantage'], 
            width=5, alpha=0.7, color=['red' if x < 0 else 'green' for x in results_sorted['advantage']])
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax2.set_xlabel('Prediction Accuracy (%)', fontsize=12)
    ax2.set_ylabel('Advantage vs Baseline ($)', fontsize=12)
    ax2.set_title('Prediction Advantage by Accuracy', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(ACCURACY_LEVELS)
    
    plt.tight_layout()
    plt.savefig('/tmp/trading_results/diagnostic_07_monotonicity.png', dpi=150, bbox_inches='tight')
    print("\n✓ Visualization saved to: /tmp/trading_results/diagnostic_07_monotonicity.png")
    plt.show()
    
except Exception as e:
    print(f"\n⚠️  Could not create visualization: {e}")
    print("(This is OK - visualization is optional)")
```

## Step 8: Diagnostic Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 07 SUMMARY")
print("="*80)

# Overall verdict
critical_pass = checks['monotonic'] and checks['90_strong_advantage']
all_pass = all(checks.values())

print("\nMonotonicity Test Results:")

if all_pass:
    print("\n✓✓✓ DIAGNOSTIC 07 FULL PASS")
    print("="*80)
    print("\nConclusion: Perfect monotonic improvement with accuracy!")
    print("\nStrategy correctly uses predictions with performance scaling as expected.")
    
    print("\nPerformance by accuracy:")
    for idx, row in results_sorted.iterrows():
        print(f"  {row['accuracy']}%: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
    
    print("\nNext step: Parameter tuning (diagnostic_08)")
    
elif critical_pass:
    print("\n✓✓ DIAGNOSTIC 07 CRITICAL PASS")
    print("="*80)
    print("\nConclusion: Monotonic improvement confirmed!")
    print("\nCore functionality working - performance improves with accuracy.")
    
    failed_checks = [k for k, v in checks.items() if not v]
    print(f"\nFailed checks: {', '.join(failed_checks)}")
    
    print("\nPerformance by accuracy:")
    for idx, row in results_sorted.iterrows():
        print(f"  {row['accuracy']}%: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
    
    print("\nNext step: Parameter tuning (diagnostic_08)")
    
elif checks['monotonic']:
    print("\n⚠️  DIAGNOSTIC 07 PARTIAL PASS")
    print("="*80)
    print("\nConclusion: Monotonic but weak advantage")
    print("\nPerformance improves with accuracy but not enough to beat baseline strongly.")
    
    print("\nPerformance by accuracy:")
    for idx, row in results_sorted.iterrows():
        print(f"  {row['accuracy']}%: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
    
    print("\nNext step: Parameter tuning may help (diagnostic_08)")
    
else:
    print("\n✗✗✗ DIAGNOSTIC 07 FAIL")
    print("="*80)
    print("\nConclusion: NOT MONOTONIC - predictions not being used correctly")
    
    print("\nPerformance by accuracy:")
    for idx, row in results_sorted.iterrows():
        print(f"  {row['accuracy']}%: ${row['net_earnings']:,.2f} ({row['advantage_pct']:+.2f}%)")
    
    print("\nThis indicates the original bug is still present!")
    print("\nNext step: Review diagnostic_04 fixes and re-run diagnostics 01-03")

# Export results
output_path = '/tmp/trading_results/diagnostic_07_monotonicity.csv'
results_df.to_csv(output_path, index=False)
print(f"\n✓ Results saved to: {output_path}")
```
