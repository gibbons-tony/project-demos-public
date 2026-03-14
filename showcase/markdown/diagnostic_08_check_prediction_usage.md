# Diagnostic 08: Check if Predictions Are Being Used

**Purpose:** Verify that strategies are receiving predictions (not None)

**Test:** Analyze trade reasons to see if strategies are falling back to baseline

**Key Question:** Are trades marked with 'no_predictions_fallback'?


```python
%run ../00_setup_and_config
```


```python
import pandas as pd
import pickle

print("="*80)
print("DIAGNOSTIC 08: PREDICTION USAGE CHECK")
print("="*80)
print("\nTest: Check if strategies receive predictions or get None")
```

## Step 1: Load Results


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)

print(f"Loading results for {COMMODITY} - {MODEL_VERSION}...")
results_path = DATA_PATHS['results_detailed']

try:
    with open(results_path, 'rb') as f:
        all_results = pickle.load(f)
    print(f"✓ Loaded {len(all_results)} strategy results")
except Exception as e:
    print(f"✗ ERROR: {e}")
    print(f"\nTrying to load from Spark table instead...")
    
    # Fallback: load from Spark table
    results_table = DATA_PATHS['results']
    results_df = spark.table(results_table).toPandas()
    print(f"✓ Loaded from table: {results_table}")
```

## Step 2: Analyze Trade Reasons for Each Strategy


```python
print("\n" + "="*80)
print("TRADE REASON ANALYSIS")
print("="*80)

# Analyze each strategy
for strategy_name, result in all_results.items():
    trades = result['trades']
    
    print(f"\n{strategy_name}:")
    print(f"  Total trades: {len(trades)}")
    
    # Count reasons
    reason_counts = {}
    for trade in trades:
        reason = trade.get('reason', 'unknown')
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    # Display top reasons
    print(f"  Trade reasons:")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])[:10]:
        pct = 100 * count / len(trades) if len(trades) > 0 else 0
        print(f"    {reason}: {count} ({pct:.1f}%)")
    
    # Flag if falling back to baseline
    fallback_count = reason_counts.get('no_predictions_fallback', 0)
    waiting_count = reason_counts.get('no_predictions_waiting', 0)
    
    if fallback_count > 0 or waiting_count > 0:
        print(f"  ⚠️  WARNING: {fallback_count + waiting_count} trades without predictions")
        print(f"     This means predictions are not being passed correctly!")
```

## Step 3: Check Prediction Strategies Specifically


```python
print("\n" + "="*80)
print("PREDICTION STRATEGY ANALYSIS")
print("="*80)

prediction_strategies = ['Expected Value', 'Risk-Adjusted', 'Consensus']

for strategy_name in prediction_strategies:
    if strategy_name in all_results:
        result = all_results[strategy_name]
        trades = result['trades']
        
        # Count prediction-based vs fallback trades
        prediction_based = 0
        fallback = 0
        
        for trade in trades:
            reason = trade.get('reason', '')
            if 'no_predictions' in reason:
                fallback += 1
            else:
                prediction_based += 1
        
        print(f"\n{strategy_name}:")
        print(f"  Prediction-based trades: {prediction_based}")
        print(f"  Fallback trades: {fallback}")
        
        if fallback > prediction_based:
            print(f"  ✗ CRITICAL: More fallback than prediction trades!")
            print(f"     Predictions are NOT being passed correctly")
        elif fallback > 0:
            pct = 100 * fallback / len(trades)
            print(f"  ⚠️  WARNING: {pct:.1f}% trades without predictions")
        else:
            print(f"  ✓ PASS: All trades used predictions")
```

## Step 4: Sample Trade Details


```python
print("\n" + "="*80)
print("SAMPLE TRADE DETAILS (Expected Value)")
print("="*80)

if 'Expected Value' in all_results:
    trades = all_results['Expected Value']['trades']
    
    print(f"\nFirst 10 trades:")
    for i, trade in enumerate(trades[:10]):
        print(f"  {i+1}. Day {trade['day']}: {trade['amount']:.1f}t @ ${trade['price']:.2f} - {trade['reason']}")
    
    if len(trades) > 10:
        print(f"\nLast 5 trades:")
        for i, trade in enumerate(trades[-5:]):
            print(f"  {len(trades)-4+i}. Day {trade['day']}: {trade['amount']:.1f}t @ ${trade['price']:.2f} - {trade['reason']}")
```

## Step 5: Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 08 SUMMARY")
print("="*80)

# Calculate overall statistics
total_fallback = 0
total_trades = 0

for strategy_name in prediction_strategies:
    if strategy_name in all_results:
        trades = all_results[strategy_name]['trades']
        total_trades += len(trades)
        
        for trade in trades:
            if 'no_predictions' in trade.get('reason', ''):
                total_fallback += 1

print(f"\nAcross all prediction strategies:")
print(f"  Total trades: {total_trades}")
print(f"  Trades without predictions: {total_fallback}")

if total_fallback == 0:
    print(f"\n✓✓✓ PASS: Predictions are being passed correctly")
    print(f"\nConclusion: Bug is NOT in prediction passing")
    print(f"Next step: Check decision logic (diagnostic_09)")
elif total_fallback > total_trades * 0.5:
    print(f"\n✗✗✗ CRITICAL FAIL: {100*total_fallback/total_trades:.1f}% trades without predictions")
    print(f"\nConclusion: Predictions are NOT being passed")
    print(f"Bug: Date lookup issue or prediction_matrices not loaded")
else:
    pct = 100 * total_fallback / total_trades
    print(f"\n⚠️⚠️⚠️ PARTIAL: {pct:.1f}% trades without predictions")
    print(f"\nConclusion: Predictions passed sometimes but not always")
    print(f"Bug: Date coverage gaps or intermittent lookup failure")
```
