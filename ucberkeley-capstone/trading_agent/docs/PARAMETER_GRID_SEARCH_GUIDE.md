# Parameter Grid Search Guide

**Created:** 2025-11-10
**Purpose:** Find optimal trading strategy parameters that maximize net revenue

---

## Overview

The grid search framework tests different parameter combinations for each trading strategy to find values that maximize net revenue. It ensures matched pairs (baseline/predictive versions) share the same parameters, differing only in prediction usage.

### Key Features

- ✅ Tests 100s-1000s of parameter combinations automatically
- ✅ Ensures matched pairs share baseline parameters
- ✅ Generates optimal_parameters.json for production use
- ✅ Provides detailed comparison of all tested combinations
- ✅ Visualizes parameter impact on performance
- ✅ Two-stage optimization (coarse → fine-grained)

---

## Quick Start

### 1. Run Grid Search in Databricks

```python
# Open archive/scripts/parameter_grid_search.py (archived - now using production/optimization/) in Databricks

# Configure
CURRENT_COMMODITY = 'coffee'
CURRENT_MODEL = 'sarimax_auto_weather_v1'
USE_FINE_GRAIN_GRID = False  # Start with coarse search
MAX_COMBINATIONS_PER_STRATEGY = None  # Test all combinations

# Run all cells
# Results saved to: /dbfs/FileStore/optimal_parameters.json
```

### 2. Review Results

```python
# Optimal parameters are displayed at end of notebook
# Check:
# - Net revenue for each strategy
# - Parameter values
# - Number of trades
# - Total costs
```

### 3. Update Main Notebook

Copy optimal parameter values to `trading_prediction_analysis_multi_model.py`:

```python
# Lines 66-79: BASELINE_PARAMS
BASELINE_PARAMS = {
    'equal_batch': {
        'batch_size': <optimal_value>,  # from grid search
        'frequency_days': <optimal_value>
    },
    'price_threshold': {
        'threshold_pct': <optimal_value>
    },
    'moving_average': {
        'ma_period': <optimal_value>
    }
}

# Lines 81-98: PREDICTION_PARAMS
PREDICTION_PARAMS = {
    'consensus': {
        'consensus_threshold': <optimal_value>,
        'min_return': <optimal_value>,
        'evaluation_day': <optimal_value>
    },
    # ... etc
}
```

### 4. Validate

Run full multi-model backtest with new parameters and compare to baseline.

---

## Parameter Grids

### Baseline Strategies

#### ImmediateSaleStrategy
```python
'immediate_sale': {
    'min_batch_size': [3.0, 5.0, 7.0, 10.0],           # Tons
    'sale_frequency_days': [5, 7, 10, 14]              # Days
}
```

**Combinations:** 4 × 4 = 16

#### EqualBatchStrategy
```python
'equal_batch': {
    'batch_size': [0.15, 0.20, 0.25, 0.30, 0.35],      # Fraction
    'frequency_days': [20, 25, 30, 35, 40]             # Days
}
```

**Combinations:** 5 × 5 = 25

#### PriceThresholdStrategy (Matched Pair)
```python
'price_threshold': {
    'threshold_pct': [0.02, 0.03, 0.05, 0.07, 0.10],   # Price > MA threshold
    'batch_fraction': [0.20, 0.25, 0.30, 0.35],        # Sale fraction
    'max_days_without_sale': [45, 60, 75, 90]          # Fallback days
}
```

**Combinations:** 5 × 4 × 4 = 80
**Note:** These parameters are **shared** with PriceThresholdPredictive

#### MovingAverageStrategy (Matched Pair)
```python
'moving_average': {
    'ma_period': [20, 25, 30, 35, 40],                 # MA window (days)
    'batch_fraction': [0.20, 0.25, 0.30, 0.35],        # Sale fraction
    'max_days_without_sale': [45, 60, 75, 90]          # Fallback days
}
```

**Combinations:** 5 × 4 × 4 = 80
**Note:** These parameters are **shared** with MovingAveragePredictive

### Prediction-Based Strategies

#### ConsensusStrategy
```python
'consensus': {
    'consensus_threshold': [0.60, 0.65, 0.70, 0.75, 0.80],  # Bullish paths needed
    'min_return': [0.02, 0.03, 0.04, 0.05],                 # Min expected return
    'evaluation_day': [10, 12, 14]                          # Forecast horizon
}
```

**Combinations:** 5 × 4 × 3 = 60

#### ExpectedValueStrategy
```python
'expected_value': {
    'min_ev_improvement': [30, 40, 50, 60, 75],        # Min $ gain to wait
    'baseline_batch': [0.10, 0.12, 0.15, 0.18, 0.20],  # Baseline sale size
    'baseline_frequency': [7, 10, 12, 14]              # Reference frequency
}
```

**Combinations:** 5 × 5 × 4 = 100

#### RiskAdjustedStrategy
```python
'risk_adjusted': {
    'min_return': [0.02, 0.03, 0.04, 0.05],            # Min expected return
    'max_uncertainty': [0.25, 0.30, 0.35, 0.40],       # Max acceptable CV
    'consensus_threshold': [0.55, 0.60, 0.65, 0.70],   # Bullish threshold
    'evaluation_day': [10, 12, 14]                     # Forecast horizon
}
```

**Combinations:** 4 × 4 × 4 × 3 = 192

### Total Combinations

**Coarse Search:** 16 + 25 + 80 + 80 + 60 + 100 + 192 = **553 combinations**

**Note:** Matched pairs (PriceThreshold/Predictive, MovingAverage/Predictive) are optimized once and parameters shared.

---

## Two-Stage Optimization

### Stage 1: Coarse Search (Broad Sweep)

**Purpose:** Identify promising parameter ranges
**Grid:** Wide ranges with larger steps
**Runtime:** 30-60 minutes for all strategies
**Output:** Rough optimal values

```python
USE_FINE_GRAIN_GRID = False
```

### Stage 2: Fine-Grained Search (Focused)

**Purpose:** Fine-tune around optimal values from Stage 1
**Grid:** Narrow ranges with smaller steps
**Runtime:** 20-40 minutes for focused strategies
**Output:** Precise optimal values

```python
USE_FINE_GRAIN_GRID = True
```

**Example Fine-Grained Grid:**
```python
'price_threshold': {
    'threshold_pct': [0.04, 0.05, 0.06],              # Focused around 0.05
    'batch_fraction': [0.23, 0.25, 0.27],             # Focused around 0.25
    'max_days_without_sale': [55, 60, 65]             # Focused around 60
}
```

**Combinations:** 3 × 3 × 3 = 27 (vs 80 in coarse search)

---

## Matched Pair Constraint

### What Are Matched Pairs?

Some strategies come in baseline/predictive versions that should differ **only** in prediction usage, not in other parameters. This ensures apples-to-apples comparison.

### Pairs

1. **PriceThresholdStrategy ↔ PriceThresholdPredictive**
   - Shared params: `threshold_pct`, `batch_fraction`, `max_days_without_sale`
   - Predictive adds: prediction-based adjustments, cost-benefit analysis

2. **MovingAverageStrategy ↔ MovingAveragePredictive**
   - Shared params: `ma_period`, `batch_fraction`, `max_days_without_sale`
   - Predictive adds: prediction-based adjustments, cost-benefit analysis

### Implementation

The grid search automatically ensures matched pairs use the same baseline parameters:

```python
# After optimization
if 'price_threshold' in optimal_params:
    pt_params = optimal_params['price_threshold']['params']
    # PriceThresholdPredictive will use same threshold_pct, batch_fraction, max_days_without_sale
```

---

## Understanding Results

### Output Files

1. **optimal_parameters.json**
   - Best parameter values for each strategy
   - Net revenue achieved
   - All metrics (revenue, costs, trades, etc.)

2. **grid_search_results_all.csv**
   - All tested combinations
   - Sorted by net revenue
   - Useful for sensitivity analysis

3. **Console Output**
   - Real-time progress
   - Optimal parameters summary
   - Update instructions

### Sample Output

```
================================================================================
OPTIMAL PARAMETERS SUMMARY
================================================================================

PRICE_THRESHOLD
----------------------------------------
Net Revenue: $14,823.45
Total Revenue: $18,234.12
Total Costs: $3,410.67
Trades: 47

Parameters:
  threshold_pct: 0.05
  batch_fraction: 0.30
  max_days_without_sale: 60
```

### Interpreting Results

**High Net Revenue** = Good performance
**Many Trades** = Active strategy (check if too aggressive)
**Few Trades** = Conservative strategy (check if too passive)
**High Costs** = Frequent trading or long storage (may need adjustment)

### Red Flags

⚠️ **Parameter at grid boundary** → Expand search range
⚠️ **Very few trades (< 10)** → Strategy too conservative
⚠️ **Very many trades (> 100)** → Strategy too aggressive, high transaction costs
⚠️ **Costs > 30% of revenue** → Strategy inefficient

---

## Sampling Large Grids

For strategies with many parameters or fine-grained grids, you can sample combinations to reduce runtime:

```python
# Test only 100 random combinations instead of all 192
MAX_COMBINATIONS_PER_STRATEGY = 100
```

**When to Use:**
- Initial exploration
- Very fine-grained grids (> 500 combinations)
- Time constraints

**Trade-off:**
- Faster runtime
- May miss global optimum
- Good for getting "pretty good" parameters quickly

---

## Validation Workflow

### 1. Run Grid Search
```python
# Databricks notebook: parameter_grid_search_notebook.py
# Output: optimal_parameters.json
```

### 2. Review Optimal Parameters
```python
from parameter_config import load_optimal_parameters, print_update_instructions

optimal = load_optimal_parameters('/dbfs/FileStore/optimal_parameters.json')
print_update_instructions(optimal)
```

### 3. Update Main Notebook
```python
# Copy optimal values to BASELINE_PARAMS and PREDICTION_PARAMS
# Lines 66-98 in trading_prediction_analysis_multi_model.py
```

### 4. Run Full Backtest
```python
# Run multi-model notebook with new parameters
# Compare net earnings to baseline (pre-optimization)
```

### 5. Statistical Validation
```python
# Run bootstrap confidence intervals
# Check if improvement is statistically significant
# p-value < 0.05 = significant improvement
```

### 6. Production Deployment
```python
# If validation passes:
# - Commit optimal_parameters.json to git
# - Update operations/daily_recommendations.py
# - Deploy to production
```

---

## Advanced Usage

### Custom Parameter Grids

You can define custom parameter ranges for specific exploration:

```python
# In parameter_grid_search_notebook.py, modify get_parameter_grids()

custom_grid = {
    'price_threshold': {
        'threshold_pct': [0.04, 0.045, 0.05, 0.055, 0.06],  # Very fine-grained
        'batch_fraction': [0.25],  # Fix this parameter
        'max_days_without_sale': [60]  # Fix this parameter
    }
}
```

### Optimize Subset of Strategies

```python
# Only optimize price threshold and moving average
STRATEGIES_TO_OPTIMIZE = ['price_threshold', 'moving_average']
```

### Multi-Commodity Optimization

Run grid search separately for each commodity:

```python
# Coffee optimization
CURRENT_COMMODITY = 'coffee'
# ... run notebook ...
# Output: optimal_parameters_coffee.json

# Sugar optimization
CURRENT_COMMODITY = 'sugar'
# ... run notebook ...
# Output: optimal_parameters_sugar.json
```

### Parameter Sensitivity Analysis

Use `grid_search_results_all.csv` to analyze how each parameter affects performance:

```python
import pandas as pd
import matplotlib.pyplot as plt

results = pd.read_csv('/dbfs/FileStore/grid_search_results_all.csv')

# Filter to one strategy
pt_results = results[results['strategy'] == 'price_threshold']

# Plot net revenue vs threshold_pct
for threshold in pt_results['threshold_pct'].unique():
    subset = pt_results[pt_results['threshold_pct'] == threshold]
    plt.scatter(subset['batch_fraction'], subset['net_revenue'], label=f'threshold={threshold}')

plt.xlabel('batch_fraction')
plt.ylabel('Net Revenue ($)')
plt.legend()
plt.show()
```

---

## Troubleshooting

### Grid Search Takes Too Long

**Solution 1:** Use sampling
```python
MAX_COMBINATIONS_PER_STRATEGY = 100
```

**Solution 2:** Optimize fewer strategies
```python
STRATEGIES_TO_OPTIMIZE = ['price_threshold', 'consensus']
```

**Solution 3:** Use coarser grid
```python
# Reduce number of values per parameter
'threshold_pct': [0.03, 0.05, 0.07]  # 3 values instead of 5
```

### All Strategies Perform Similarly

**Possible causes:**
- Parameter ranges too narrow
- All parameters already near optimal
- Strategy design dominates parameter choice

**Solution:** Expand parameter ranges in next grid search

### Optimal Parameters at Grid Boundaries

**Example:** Best `threshold_pct = 0.10` (the maximum tested)

**Solution:** Expand grid in that direction
```python
'threshold_pct': [0.08, 0.10, 0.12, 0.15, 0.20]  # Extend beyond 0.10
```

### Results Don't Match Expected Behavior

**Check:**
1. Are prices and predictions loading correctly?
2. Is commodity config correct?
3. Are strategy classes implemented as expected?
4. Run single backtest with debug output to verify

---

## Files Reference

### Created Files

| File | Purpose |
|------|---------|
| `parameter_grid_search.py` | Standalone Python script for grid search |
| `archive/scripts/parameter_grid_search.py (archived - now using production/optimization/)` | Databricks notebook version |
| `parameter_config.py` | Utilities for loading and applying optimal parameters |
| `optimal_parameters_template.json` | Template showing expected structure |
| `docs/PARAMETER_GRID_SEARCH_GUIDE.md` | This documentation |

### Output Files

| File | Description |
|------|-------------|
| `/dbfs/FileStore/optimal_parameters.json` | Best parameters for each strategy |
| `/dbfs/FileStore/grid_search_results_all.csv` | All tested combinations |
| Console output | Real-time progress and summary |

---

## Parameter Descriptions

### Baseline Strategy Parameters

| Parameter | Strategy | Description | Typical Range |
|-----------|----------|-------------|---------------|
| `min_batch_size` | ImmediateSale | Minimum tons to trigger sale | 3-10 tons |
| `sale_frequency_days` | ImmediateSale | Days between sales | 5-14 days |
| `batch_size` | EqualBatch | Fraction to sell each time | 0.15-0.35 |
| `frequency_days` | EqualBatch | Days between batch sales | 20-40 days |
| `threshold_pct` | PriceThreshold | Price > MA by X% to sell | 0.02-0.10 (2-10%) |
| `batch_fraction` | PriceThreshold, MovingAverage | Base sale fraction | 0.20-0.35 |
| `max_days_without_sale` | PriceThreshold, MovingAverage | Force sale after X days | 45-90 days |
| `ma_period` | MovingAverage | Moving average window | 20-40 days |

### Prediction Strategy Parameters

| Parameter | Strategy | Description | Typical Range |
|-----------|----------|-------------|---------------|
| `consensus_threshold` | Consensus, RiskAdjusted | Fraction of bullish paths needed | 0.55-0.80 (55-80%) |
| `min_return` | Consensus, RiskAdjusted | Minimum expected return to wait | 0.02-0.05 (2-5%) |
| `evaluation_day` | Consensus, RiskAdjusted | Which forecast day to evaluate | 10-14 days |
| `min_ev_improvement` | ExpectedValue | Min $ gain over selling today | $30-$75 |
| `baseline_batch` | ExpectedValue | Fallback batch size | 0.10-0.20 |
| `baseline_frequency` | ExpectedValue | Reference frequency (not used) | 7-14 days |
| `max_uncertainty` | RiskAdjusted | Max acceptable uncertainty (CV) | 0.25-0.40 (25-40%) |

**Note:** Cost parameters (`storage_cost_pct_per_day`, `transaction_cost_pct`) come from commodity config and are not optimized.

---

## Best Practices

1. **Start with coarse search** - Get rough optimal values first
2. **Validate on hold-out period** - Don't overfit to training data
3. **Check statistical significance** - Ensure improvements aren't due to chance
4. **Monitor matched pairs** - Ensure they differ only in prediction usage
5. **Document parameter changes** - Track why parameters were changed
6. **Re-optimize periodically** - Market conditions change over time
7. **Compare to baseline** - Always measure improvement vs. current params
8. **Check edge cases** - What happens in extreme market conditions?

---

## Next Steps

1. **Run initial grid search** - Use coarse grid for all strategies
2. **Review optimal parameters** - Do they make intuitive sense?
3. **Validate performance** - Run full backtest with optimal params
4. **Fine-tune if needed** - Run fine-grained search for key strategies
5. **Deploy to production** - Update main notebook with optimal values
6. **Monitor performance** - Track actual vs. expected results
7. **Re-optimize quarterly** - Adjust for changing market conditions

---

## Support

- **Grid Search Issues:** Check Databricks logs for errors
- **Parameter Questions:** Review parameter_descriptions in optimal_parameters_template.json
- **Integration Help:** See parameter_config.py for loading utilities

---

Last Updated: 2025-11-10
