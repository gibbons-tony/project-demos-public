# Diagnostic 01: Prediction Loading Validation

**Purpose:** Verify predictions are loaded correctly with proper date alignment

**Test Case:** Coffee synthetic_acc90

**Pass Criteria:**
- Matrix shape: (500, 14)
- Date overlap: >90%
- Values: $200-$400 range for coffee


```python
%run ../00_setup_and_config
```


```python
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

print("="*80)
print("DIAGNOSTIC 01: PREDICTION LOADING VALIDATION")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Verify predictions load correctly and dates align\n")
```

## Step 1: Load Predictions


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)

print("Loading prediction matrices...")
matrices_path = DATA_PATHS['prediction_matrices']
print(f"Path: {matrices_path}")

try:
    with open(matrices_path, 'rb') as f:
        prediction_matrices = pickle.load(f)
    
    print(f"✓ Loaded successfully")
    print(f"  Total matrices: {len(prediction_matrices)}")
    
except Exception as e:
    print(f"✗ ERROR: {e}")
    raise
```

## Step 2: Inspect Prediction Structure


```python
print("\n" + "="*80)
print("PREDICTION STRUCTURE ANALYSIS")
print("="*80)

if len(prediction_matrices) == 0:
    print("\n✗ CRITICAL: No prediction matrices found!")
else:
    # Get sample
    sample_date = list(prediction_matrices.keys())[0]
    sample_matrix = prediction_matrices[sample_date]
    
    print(f"\nSample date: {sample_date}")
    print(f"Date type: {type(sample_date)}")
    print(f"\nMatrix shape: {sample_matrix.shape}")
    print(f"Expected: (500, 14)")
    
    if sample_matrix.shape == (500, 14):
        print("✓ PASS: Correct shape")
    else:
        print(f"✗ FAIL: Wrong shape! Expected (500, 14), got {sample_matrix.shape}")
    
    # Check value ranges
    min_val = sample_matrix.min()
    max_val = sample_matrix.max()
    mean_val = sample_matrix.mean()
    
    print(f"\nValue ranges:")
    print(f"  Min: ${min_val:.2f}")
    print(f"  Max: ${max_val:.2f}")
    print(f"  Mean: ${mean_val:.2f}")
    
    if 200 <= min_val <= 400 and 200 <= max_val <= 600:
        print("✓ PASS: Values in reasonable range for coffee prices")
    else:
        print("⚠️  WARNING: Values outside expected range ($200-$600)")
    
    # Show sample predictions
    print(f"\nSample predictions (first 5 runs, first 7 days):")
    print(sample_matrix[:5, :7])
```

## Step 3: Load Prices and Check Date Types


```python
print("\n" + "="*80)
print("LOADING PRICES")
print("="*80)

# Load prices (same as production workflow)
prices_table = get_data_paths(COMMODITY)['prices_prepared']
print(f"Loading from: {prices_table}")

prices = spark.table(prices_table).toPandas()

print(f"✓ Loaded {len(prices)} price records")
print(f"\nPrice data info:")
print(f"  Columns: {list(prices.columns)}")
print(f"  Date column type (before): {type(prices['date'].iloc[0])}")
print(f"  Sample date: {prices['date'].iloc[0]}")
```

## Step 4: Date Alignment Analysis


```python
print("\n" + "="*80)
print("DATE ALIGNMENT ANALYSIS")
print("="*80)

# Get all dates from each source
pred_dates = list(prediction_matrices.keys())
price_dates = prices['date'].tolist()

print(f"\nPrediction dates:")
print(f"  Total: {len(pred_dates)}")
print(f"  Type: {type(pred_dates[0])}")
print(f"  First: {pred_dates[0]}")
print(f"  Last: {pred_dates[-1]}")

print(f"\nPrice dates:")
print(f"  Total: {len(price_dates)}")
print(f"  Type: {type(price_dates[0])}")
print(f"  First: {price_dates[0]}")
print(f"  Last: {price_dates[-1]}")

# Check if types match
pred_type = type(pred_dates[0])
price_type = type(price_dates[0])

if pred_type != price_type:
    print(f"\n✗ CRITICAL: Date types don't match!")
    print(f"  Predictions: {pred_type}")
    print(f"  Prices: {price_type}")
    print(f"  This will cause 0% overlap!")
else:
    print(f"\n✓ Date types match: {pred_type}")
```

## Step 5: Calculate Overlap (Raw)


```python
print("\n" + "="*80)
print("RAW OVERLAP CALCULATION")
print("="*80)

pred_set = set(pred_dates)
price_set = set(price_dates)
overlap = pred_set.intersection(price_set)

print(f"\nOverlap analysis (raw):")
print(f"  Prediction dates: {len(pred_set)}")
print(f"  Price dates: {len(price_set)}")
print(f"  Matching dates: {len(overlap)}")

if len(pred_set) > 0:
    overlap_pct = 100 * len(overlap) / len(pred_set)
    print(f"  Overlap percentage: {overlap_pct:.1f}%")
    
    if overlap_pct > 90:
        print("  ✓ PASS: >90% overlap")
    elif overlap_pct > 50:
        print("  ⚠️  WARNING: Only {overlap_pct:.1f}% overlap")
    elif overlap_pct == 0:
        print("  ✗ CRITICAL FAIL: 0% overlap - date type mismatch!")
    else:
        print(f"  ✗ FAIL: Only {overlap_pct:.1f}% overlap")
else:
    print("  ✗ FAIL: No prediction dates!")

# Show sample matching dates
if len(overlap) > 0:
    overlap_list = sorted(list(overlap))
    print(f"\nSample matching dates:")
    for date in overlap_list[:5]:
        print(f"  {date}")
```

## Step 6: Try Normalized Dates (Fix Attempt)


```python
print("\n" + "="*80)
print("NORMALIZED DATE COMPARISON")
print("="*80)

print("\nAttempting to normalize both to datetime...")

# Convert prices to datetime
prices_normalized = prices.copy()
prices_normalized['date'] = pd.to_datetime(prices_normalized['date'])

# Convert prediction keys to datetime
prediction_matrices_normalized = {}
for k, v in prediction_matrices.items():
    try:
        k_dt = pd.to_datetime(k)
        prediction_matrices_normalized[k_dt] = v
    except:
        prediction_matrices_normalized[k] = v

# Recalculate overlap
pred_dates_norm = list(prediction_matrices_normalized.keys())
price_dates_norm = prices_normalized['date'].tolist()

pred_set_norm = set(pred_dates_norm)
price_set_norm = set(price_dates_norm)
overlap_norm = pred_set_norm.intersection(price_set_norm)

print(f"\nAfter normalization:")
print(f"  Prediction dates: {len(pred_set_norm)}")
print(f"  Price dates: {len(price_set_norm)}")
print(f"  Matching dates: {len(overlap_norm)}")

if len(pred_set_norm) > 0:
    overlap_pct_norm = 100 * len(overlap_norm) / len(pred_set_norm)
    print(f"  Overlap percentage: {overlap_pct_norm:.1f}%")
    
    if overlap_pct_norm > 90:
        print("  ✓ SUCCESS: >90% overlap after normalization!")
        print("  Fix: Both datasets need datetime conversion")
    elif overlap_pct_norm > 50:
        print(f"  ⚠️  IMPROVED: {overlap_pct_norm:.1f}% overlap (was {overlap_pct:.1f}%)")
    else:
        print(f"  ✗ Still only {overlap_pct_norm:.1f}% overlap")
```

## Step 7: Date Range Comparison


```python
print("\n" + "="*80)
print("DATE RANGE COMPARISON")
print("="*80)

pred_dates_sorted = sorted(pred_dates_norm)
price_dates_sorted = sorted(price_dates_norm)

print(f"\nPrediction date range:")
print(f"  First: {pred_dates_sorted[0]}")
print(f"  Last: {pred_dates_sorted[-1]}")
print(f"  Span: {(pred_dates_sorted[-1] - pred_dates_sorted[0]).days} days")

print(f"\nPrice date range:")
print(f"  First: {price_dates_sorted[0]}")
print(f"  Last: {price_dates_sorted[-1]}")
print(f"  Span: {(price_dates_sorted[-1] - price_dates_sorted[0]).days} days")

# Check for predictions outside price range
pred_before_prices = [d for d in pred_dates_sorted if d < price_dates_sorted[0]]
pred_after_prices = [d for d in pred_dates_sorted if d > price_dates_sorted[-1]]

if len(pred_before_prices) > 0:
    print(f"\n⚠️  {len(pred_before_prices)} predictions before first price date")
if len(pred_after_prices) > 0:
    print(f"⚠️  {len(pred_after_prices)} predictions after last price date")
```

## Step 8: Diagnostic Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 01 SUMMARY")
print("="*80)

# Collect results
results = {
    'prediction_count': len(prediction_matrices),
    'correct_shape': sample_matrix.shape == (500, 14) if len(prediction_matrices) > 0 else False,
    'values_reasonable': 200 <= min_val <= 600 if len(prediction_matrices) > 0 else False,
    'raw_overlap_pct': overlap_pct if len(pred_set) > 0 else 0,
    'norm_overlap_pct': overlap_pct_norm if len(pred_set_norm) > 0 else 0,
    'date_type_match': pred_type == price_type,
}

print("\nTest Results:")
print(f"  ✓ Predictions loaded: {results['prediction_count']} matrices")
print(f"  {'✓' if results['correct_shape'] else '✗'} Matrix shape: {'(500, 14)' if results['correct_shape'] else 'WRONG'}")
print(f"  {'✓' if results['values_reasonable'] else '✗'} Value range: {'reasonable' if results['values_reasonable'] else 'SUSPICIOUS'}")
print(f"  {'✓' if results['date_type_match'] else '✗'} Date types: {'match' if results['date_type_match'] else 'MISMATCH'}")
print(f"  {'✓' if results['raw_overlap_pct'] > 90 else '✗'} Raw overlap: {results['raw_overlap_pct']:.1f}%")
print(f"  {'✓' if results['norm_overlap_pct'] > 90 else '✗'} Normalized overlap: {results['norm_overlap_pct']:.1f}%")

# Overall verdict
print("\n" + "="*80)
if results['norm_overlap_pct'] > 90 and results['correct_shape'] and results['values_reasonable']:
    print("✓✓✓ DIAGNOSTIC 01 PASS")
    print("="*80)
    print("\nConclusion: Predictions load correctly after date normalization")
    print("\nRequired fix: Convert both prices and predictions to datetime")
elif results['raw_overlap_pct'] == 0:
    print("✗✗✗ DIAGNOSTIC 01 CRITICAL FAIL")
    print("="*80)
    print("\nConclusion: Date type mismatch causing 0% overlap")
    print("This is likely THE BUG causing predictions to not work!")
else:
    print("⚠️⚠️⚠️ DIAGNOSTIC 01 PARTIAL FAIL")
    print("="*80)
    print("\nConclusion: Some issues detected, but not critical")
    print("Further investigation needed")

print("\nNext step: diagnostic_02_backtest_trace.ipynb")
```
