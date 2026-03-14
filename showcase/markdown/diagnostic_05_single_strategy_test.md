# Diagnostic 05: Single Strategy Validation Test

**Purpose:** Test corrected Expected Value strategy in isolation

**Test Case:** Coffee synthetic_acc90

**Pass Criteria:**
- Net earnings > $750,000 (beats $727k baseline by $23k+)
- Decision log shows variation based on predictions
- Predictions are used (not defaulting to baseline behavior)


```python
%run ../00_setup_and_config
%run ./diagnostic_04_fixed_strategies  # Import fixed strategy and engine
```


```python
import pandas as pd
import numpy as np
import pickle

print("="*80)
print("DIAGNOSTIC 05: SINGLE STRATEGY VALIDATION TEST")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Validate fixed Expected Value strategy in isolation\n")
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
```

## Step 2: Run Fixed Expected Value Strategy


```python
print("\n" + "="*80)
print("TESTING FIXED EXPECTED VALUE STRATEGY")
print("="*80)

# Create engine
engine = FixedBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)

# Create strategy
strategy = FixedExpectedValueStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    **PREDICTION_PARAMS['expected_value']
)

print(f"\nRunning {strategy.name}...")
results = engine.run(strategy)

# Calculate metrics
total_revenue = sum(t['revenue'] for t in results['trades'])
total_transaction_costs = sum(t['transaction_cost'] for t in results['trades'])
total_storage_costs = results['daily_state']['daily_storage_cost'].sum()
net_earnings = total_revenue - total_transaction_costs - total_storage_costs

print(f"\nResults:")
print(f"  Net earnings: ${net_earnings:,.2f}")
print(f"  Trades: {len(results['trades'])}")
```

## Step 3: Compare to Baseline (Equal Batches)


```python
print("\n" + "="*80)
print("BASELINE COMPARISON")
print("="*80)

# Import baseline strategy from notebook 03
%run ../03_strategy_implementations

# Run Equal Batches baseline
baseline_strategy = EqualBatchesStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    **BASELINE_PARAMS['equal_batches']
)

print(f"\nRunning baseline: {baseline_strategy.name}...")
baseline_results = engine.run(baseline_strategy)

# Calculate baseline metrics
baseline_revenue = sum(t['revenue'] for t in baseline_results['trades'])
baseline_transaction_costs = sum(t['transaction_cost'] for t in baseline_results['trades'])
baseline_storage_costs = baseline_results['daily_state']['daily_storage_cost'].sum()
baseline_earnings = baseline_revenue - baseline_transaction_costs - baseline_storage_costs

print(f"\nBaseline results:")
print(f"  Net earnings: ${baseline_earnings:,.2f}")
print(f"  Trades: {len(baseline_results['trades'])}")
```

## Step 4: Side-by-Side Comparison


```python
print("\n" + "="*80)
print("SIDE-BY-SIDE COMPARISON")
print("="*80)

# Calculate advantage
advantage = net_earnings - baseline_earnings
advantage_pct = 100 * advantage / baseline_earnings if baseline_earnings != 0 else 0

# Create comparison dataframe
comparison = pd.DataFrame([
    {
        'Strategy': baseline_strategy.name,
        'Type': 'Baseline',
        'Net Earnings': baseline_earnings,
        'Trades': len(baseline_results['trades']),
        'Advantage': 0,
        'Advantage %': 0.0
    },
    {
        'Strategy': strategy.name,
        'Type': 'Prediction',
        'Net Earnings': net_earnings,
        'Trades': len(results['trades']),
        'Advantage': advantage,
        'Advantage %': advantage_pct
    }
])

print("\nResults:")
display(comparison)

print(f"\n" + "-"*80)
print(f"Expected Value advantage: ${advantage:+,.2f} ({advantage_pct:+.2f}%)")
print("-"*80)
```

## Step 5: Decision Pattern Analysis


```python
print("\n" + "="*80)
print("DECISION PATTERN ANALYSIS")
print("="*80)

log_df = pd.DataFrame(strategy.decision_log)

if len(log_df) == 0:
    print("\n✗ CRITICAL: No decisions logged!")
else:
    # Overall statistics
    print(f"\nTotal decisions: {len(log_df)}")
    print(f"  With predictions: {len(log_df[log_df['has_predictions']])}")
    print(f"  Without predictions: {len(log_df[~log_df['has_predictions']])}")
    
    # Decision breakdown
    if 'decision' in log_df.columns:
        print(f"\nDecision breakdown:")
        print(log_df['decision'].value_counts())
    
    # Analyze decisions with predictions
    if len(log_df[log_df['has_predictions']]) > 0:
        pred_log = log_df[log_df['has_predictions']].copy()
        
        print(f"\nStatistics (when predictions available):")
        
        if 'expected_return' in pred_log.columns:
            print(f"\nExpected return:")
            print(f"  Mean: {pred_log['expected_return'].mean():.3f}")
            print(f"  Std: {pred_log['expected_return'].std():.3f}")
            print(f"  Min: {pred_log['expected_return'].min():.3f}")
            print(f"  Max: {pred_log['expected_return'].max():.3f}")
        
        if 'net_benefit' in pred_log.columns:
            print(f"\nNet benefit:")
            print(f"  Mean: {pred_log['net_benefit'].mean():.3f}")
            print(f"  Std: {pred_log['net_benefit'].std():.3f}")
            print(f"  Min: {pred_log['net_benefit'].min():.3f}")
            print(f"  Max: {pred_log['net_benefit'].max():.3f}")
        
        # Check variation in decisions
        if 'decision' in pred_log.columns:
            sell_decisions = len(pred_log[pred_log['decision'] == 'SELL'])
            wait_decisions = len(pred_log[pred_log['decision'] == 'WAIT'])
            
            print(f"\nDecision distribution:")
            print(f"  SELL: {sell_decisions} ({100*sell_decisions/len(pred_log):.1f}%)")
            print(f"  WAIT: {wait_decisions} ({100*wait_decisions/len(pred_log):.1f}%)")
            
            if sell_decisions > 0 and wait_decisions > 0:
                ratio = min(sell_decisions, wait_decisions) / max(sell_decisions, wait_decisions)
                print(f"  Balance ratio: {ratio:.2f}")
                
                if ratio > 0.1:
                    print("  ✓ PASS: Good mix of decisions")
                else:
                    print("  ⚠️  Decisions very imbalanced")
            else:
                print("  ✗ FAIL: All decisions identical!")
```

## Step 6: Correlation Analysis


```python
print("\n" + "="*80)
print("CORRELATION ANALYSIS")
print("="*80)

if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    # Check correlation between expected return and decision
    if 'expected_return' in pred_log.columns and 'decision' in pred_log.columns:
        pred_log['decision_numeric'] = (pred_log['decision'] == 'SELL').astype(int)
        
        # Correlation matrix
        corr_cols = ['expected_return', 'decision_numeric']
        if 'net_benefit' in pred_log.columns:
            corr_cols.append('net_benefit')
        
        available_cols = [c for c in corr_cols if c in pred_log.columns]
        
        if len(available_cols) > 1:
            print("\nCorrelation matrix:")
            print(pred_log[available_cols].corr())
            
            # Specific checks
            if 'net_benefit' in pred_log.columns:
                nb_decision_corr = pred_log[['net_benefit', 'decision_numeric']].corr().iloc[0, 1]
                print(f"\nNet benefit vs SELL decision: {nb_decision_corr:.3f}")
                print("(Expected: negative - lower benefit → more selling)")
                
                if nb_decision_corr < -0.3:
                    print("✓ PASS: Strong correlation - predictions driving decisions")
                elif nb_decision_corr < 0:
                    print("⚠️  Weak correlation - predictions have limited impact")
                else:
                    print("✗ FAIL: Wrong direction - logic error?")
else:
    print("\n✗ Cannot perform correlation analysis - no predictions used")
```

## Step 7: Trade Timing Analysis


```python
print("\n" + "="*80)
print("TRADE TIMING ANALYSIS")
print("="*80)

# Compare trade timing between strategies
pred_trades = pd.DataFrame(results['trades'])
baseline_trades = pd.DataFrame(baseline_results['trades'])

print(f"\nTrade counts:")
print(f"  Baseline: {len(baseline_trades)} trades")
print(f"  Fixed strategy: {len(pred_trades)} trades")

if len(pred_trades) > 0 and len(baseline_trades) > 0:
    # Compare average trade day
    print(f"\nAverage trade day:")
    print(f"  Baseline: Day {baseline_trades['day'].mean():.0f}")
    print(f"  Fixed strategy: Day {pred_trades['day'].mean():.0f}")
    
    # Compare average price received
    print(f"\nAverage price received:")
    print(f"  Baseline: ${baseline_trades['price'].mean():.2f}")
    print(f"  Fixed strategy: ${pred_trades['price'].mean():.2f}")
    
    # Calculate weighted average price (by amount)
    baseline_wavg = (baseline_trades['amount'] * baseline_trades['price']).sum() / baseline_trades['amount'].sum()
    pred_wavg = (pred_trades['amount'] * pred_trades['price']).sum() / pred_trades['amount'].sum()
    
    print(f"\nWeighted average price (by volume):")
    print(f"  Baseline: ${baseline_wavg:.2f}")
    print(f"  Fixed strategy: ${pred_wavg:.2f}")
    print(f"  Difference: ${pred_wavg - baseline_wavg:+.2f}")
    
    if pred_wavg > baseline_wavg:
        print("  ✓ Strategy achieving higher average selling price")
    else:
        print("  ⚠️  Strategy achieving lower average selling price")
```

## Step 8: Validation Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 05 VALIDATION SUMMARY")
print("="*80)

# Define pass criteria
checks = {}

# Check 1: Beats baseline
checks['beats_baseline_23k'] = advantage > 23000
checks['beats_baseline'] = advantage > 0

# Check 2: Decision variation
if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    if 'decision' in pred_log.columns:
        sell_count = len(pred_log[pred_log['decision'] == 'SELL'])
        wait_count = len(pred_log[pred_log['decision'] == 'WAIT'])
        checks['decision_variety'] = (sell_count > 0 and wait_count > 0)
    else:
        checks['decision_variety'] = False
else:
    checks['decision_variety'] = False

# Check 3: Predictions used
pred_coverage = 100 * strategy.predictions_received / (strategy.predictions_received + strategy.predictions_missing)
checks['predictions_used'] = pred_coverage > 80

# Check 4: Correlation check
if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    if 'net_benefit' in pred_log.columns and 'decision' in pred_log.columns:
        pred_log['decision_numeric'] = (pred_log['decision'] == 'SELL').astype(int)
        corr = pred_log[['net_benefit', 'decision_numeric']].corr().iloc[0, 1]
        checks['correlation_ok'] = corr < 0  # Should be negative
    else:
        checks['correlation_ok'] = False
else:
    checks['correlation_ok'] = False

print("\nValidation Criteria:")
print(f"  {'✓' if checks['beats_baseline_23k'] else '✗'} Beats baseline by >$23k: ${advantage:+,.2f}")
print(f"  {'✓' if checks['beats_baseline'] else '✗'} Beats baseline (any amount): {advantage > 0}")
print(f"  {'✓' if checks['decision_variety'] else '✗'} Decision variety: {checks['decision_variety']}")
print(f"  {'✓' if checks['predictions_used'] else '✗'} Predictions used (>80%): {pred_coverage:.1f}%")
print(f"  {'✓' if checks['correlation_ok'] else '✗'} Correlation check: {checks['correlation_ok']}")

# Overall verdict
critical_pass = checks['beats_baseline_23k'] and checks['predictions_used']
all_pass = all(checks.values())

print("\n" + "="*80)
if all_pass:
    print("✓✓✓ DIAGNOSTIC 05 FULL PASS")
    print("="*80)
    print("\nConclusion: Fixed strategy validated successfully!")
    print(f"\nExpected Value achieves ${net_earnings:,.2f}")
    print(f"Advantage: ${advantage:+,.2f} ({advantage_pct:+.2f}%)")
    print("\nNext step: Test all strategies (diagnostic_06)")
elif critical_pass:
    print("✓✓ DIAGNOSTIC 05 CRITICAL PASS")
    print("="*80)
    print("\nConclusion: Strategy meets core criteria (beats baseline, uses predictions)")
    print(f"\nAdvantage: ${advantage:+,.2f} ({advantage_pct:+.2f}%)")
    print("\nSome checks failed but core functionality works.")
    print("Next step: Test all strategies (diagnostic_06)")
else:
    print("✗✗✗ DIAGNOSTIC 05 FAIL")
    print("="*80)
    print("\nConclusion: Strategy does not meet validation criteria")
    print(f"\nAdvantage: ${advantage:+,.2f} ({advantage_pct:+.2f}%)")
    
    failed_checks = [k for k, v in checks.items() if not v]
    print(f"\nFailed checks: {', '.join(failed_checks)}")
    print("\nNext step: Review diagnostic_04 fixes and iterate")
```
