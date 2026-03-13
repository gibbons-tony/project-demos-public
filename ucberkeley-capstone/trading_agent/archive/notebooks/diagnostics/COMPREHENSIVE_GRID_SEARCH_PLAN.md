# Comprehensive Grid Search Plan

**Created:** 2025-11-22
**Purpose:** Complete parameter optimization across ALL strategies

---

## Problem with Original diagnostic_12

**Issues:**
- Only covered 3 prediction strategies (Expected Value, Consensus, Risk-Adjusted)
- Missed 4 baseline strategies completely
- Missed 2 predictive overlay strategies
- Didn't test cooldown_days parameter
- Hard-coded many parameters that should be searched

---

## Complete Strategy Inventory

### Baseline Strategies (4)

**1. ImmediateSaleStrategy**
```python
def __init__(self, min_batch_size=5.0, sale_frequency_days=7)
```
**Tunable Parameters:**
- `min_batch_size`: Minimum tons needed to trade (default: 5.0)
- `sale_frequency_days`: Days between sales (default: 7)

**2. EqualBatchStrategy**
```python
def __init__(self, batch_size=0.25, frequency_days=30)
```
**Tunable Parameters:**
- `batch_size`: Fraction of inventory to sell (default: 0.25 = 25%)
- `frequency_days`: Days between sales (default: 30)

**3. PriceThresholdStrategy**
```python
def __init__(self, threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60)
```
**Tunable Parameters:**
- `threshold_pct`: Price must exceed MA by this % (default: 0.05 = 5%)
- `batch_fraction`: Fraction to sell when triggered (default: 0.25)
- `max_days_without_sale`: Fallback if no trigger (default: 60)
- **Hidden:** `cooldown_days` = 7 (hard-coded in class)

**4. MovingAverageStrategy**
```python
def __init__(self, ma_period=30, batch_fraction=0.25, max_days_without_sale=60)
```
**Tunable Parameters:**
- `ma_period`: Moving average window in days (default: 30)
- `batch_fraction`: Fraction to sell on crossover (default: 0.25)
- `max_days_without_sale`: Fallback if no crossover (default: 60)
- **Hidden:** `cooldown_days` = 7 (hard-coded in class)

---

### Prediction Strategies (5)

**5. ConsensusStrategy**
```python
def __init__(self, consensus_threshold=0.70, min_return=0.03, evaluation_day=14,
             storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25)
```
**Tunable Parameters:**
- `consensus_threshold`: % of paths that must be bullish (default: 0.70)
- `min_return`: Minimum expected return to wait (default: 0.03 = 3%)
- `evaluation_day`: Which forecast day to use (default: 14)
- **Hidden:** `cooldown_days` = 7 (hard-coded in class)

**6. ExpectedValueStrategy**
```python
def __init__(self, storage_cost_pct_per_day, transaction_cost_pct,
             min_ev_improvement=50, baseline_batch=0.15, baseline_frequency=10)
```
**Tunable Parameters:**
- `min_ev_improvement`: Min $ gain to defer sale (default: 50)
- `baseline_batch`: Batch size for fallback (default: 0.15)
- `baseline_frequency`: Reference frequency in days (default: 10)
- **Hidden:** `cooldown_days` = 7 (hard-coded in class)

**7. RiskAdjustedStrategy**
```python
def __init__(self, min_return=0.05, max_uncertainty=0.08,
             consensus_threshold=0.65, evaluation_day=14,
             storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25)
```
**Tunable Parameters:**
- `min_return`: Minimum expected return (default: 0.05 = 5%)
- `max_uncertainty`: Max acceptable CV (default: 0.08 = 8%)
- `consensus_threshold`: Bullish threshold (default: 0.65)
- `evaluation_day`: Which forecast day to use (default: 14)
- **Hidden:** `cooldown_days` = 7 (hard-coded in class)

**8. PriceThresholdPredictive**
```python
def __init__(self, threshold_pct=0.05, batch_fraction=0.25, max_days_without_sale=60,
             storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25)
```
**Tunable Parameters:**
- Same as PriceThresholdStrategy (matched pair)
- **Must share exact same params for fair comparison**

**9. MovingAveragePredictive**
```python
def __init__(self, ma_period=30, batch_fraction=0.25, max_days_without_sale=60,
             storage_cost_pct_per_day=0.025, transaction_cost_pct=0.25)
```
**Tunable Parameters:**
- Same as MovingAverageStrategy (matched pair)
- **Must share exact same params for fair comparison**

---

## Hard-Coded Parameters That Should Be Searched

### Cooldown Days
Currently hard-coded to **7 days** in all strategies. Should test:
- 3 days (more aggressive trading)
- 5 days (moderate)
- 7 days (current default)
- 10 days (conservative)
- 14 days (very conservative)

### Batch Sizing in Decision Logic
Many strategies use hard-coded batch sizes in their decision matrices:

**ExpectedValueStrategy._analyze_expected_value():**
```python
if optimal_day <= 3:
    batch_size = 0.20  # ← Hard-coded
elif optimal_day <= 7:
    batch_size = 0.15  # ← Hard-coded
elif optimal_day > 7:
    batch_size = 0.10  # ← Hard-coded (BUG: should be 0.0)
```

These should be parameterized as:
- `batch_size_peak_soon` (default: 0.20)
- `batch_size_peak_mid` (default: 0.15)
- `batch_size_peak_late` (default: 0.0 after fix)

**ConsensusStrategy._analyze_consensus():**
```python
if very_strong_consensus:
    batch_size = 0.05  # ← Hard-coded
elif strong_consensus:
    batch_size = 0.10  # ← Hard-coded
elif moderate:
    batch_size = 0.20  # ← Hard-coded
```

Should be:
- `batch_size_very_strong` (default: 0.0 after fix)
- `batch_size_strong` (default: 0.0 after fix)
- `batch_size_moderate` (default: 0.20)

**RiskAdjustedStrategy._analyze_risk_adjusted():**
```python
if very_low_risk:
    batch_size = 0.08  # ← Hard-coded
elif low_risk:
    batch_size = 0.12  # ← Hard-coded
elif medium_risk:
    batch_size = 0.18  # ← Hard-coded
```

Should be:
- `batch_size_very_low_risk` (default: 0.0 after fix)
- `batch_size_low_risk` (default: 0.0 after fix)
- `batch_size_medium_risk` (default: 0.18)

---

## Comprehensive Parameter Grid

### Grid Size Estimation

**Baseline Strategies:**
1. ImmediateSale: 4 × 4 = 16 combinations
2. EqualBatch: 5 × 5 = 25 combinations
3. PriceThreshold: 5 × 4 × 4 × 5 = 400 combinations (added cooldown)
4. MovingAverage: 5 × 4 × 4 × 5 = 400 combinations (added cooldown)

**Prediction Strategies:**
5. Consensus: 5 × 4 × 3 × 5 = 300 combinations (added cooldown)
6. ExpectedValue: 5 × 5 × 4 × 5 = 500 combinations (added cooldown)
7. RiskAdjusted: 4 × 4 × 4 × 3 × 5 = 960 combinations (added cooldown)

**Matched Pairs:**
8. PriceThresholdPredictive: Use same grid as PriceThreshold (400)
9. MovingAveragePredictive: Use same grid as MovingAverage (400)

**Total: 2,001 base parameter combinations**

**With batch sizing variations:**
- ExpectedValue: +3 batch params × 3 values each = ×27 multiplier
- Consensus: +3 batch params × 3 values each = ×27 multiplier
- RiskAdjusted: +3 batch params × 3 values each = ×27 multiplier

**Full comprehensive grid: ~40,000+ combinations**

---

## Recommended Search Strategy

### Stage 1: Coarse Grid (Baseline + Standard Params)
Test 2,001 combinations with default batch sizing to establish baseline performance.

**Estimated runtime:** 2-4 hours

### Stage 2: Fine Grid (Top Performers)
For top 3 strategies from Stage 1, search batch sizing parameters:
- 3 strategies × 27 batch combos × ~100 parameter combos = ~8,100 combinations

**Estimated runtime:** 1-2 hours

### Stage 3: Ultra-Fine Grid (Winner)
For best strategy from Stage 2, search tight ranges around optimal:
- ±10% around each parameter
- Smaller step sizes
- ~500 combinations

**Estimated runtime:** 30 minutes

**Total: 4-7 hours for complete search**

---

## Proposed Parameter Grids

### ImmediateSaleStrategy
```python
{
    'min_batch_size': [3.0, 5.0, 7.0, 10.0],
    'sale_frequency_days': [5, 7, 10, 14]
}
# Combinations: 16
```

### EqualBatchStrategy
```python
{
    'batch_size': [0.15, 0.20, 0.25, 0.30, 0.35],
    'frequency_days': [20, 25, 30, 35, 40]
}
# Combinations: 25
```

### PriceThresholdStrategy
```python
{
    'threshold_pct': [0.02, 0.03, 0.05, 0.07, 0.10],
    'batch_fraction': [0.20, 0.25, 0.30, 0.35],
    'max_days_without_sale': [45, 60, 75, 90],
    'cooldown_days': [3, 5, 7, 10, 14]
}
# Combinations: 400
```

### MovingAverageStrategy
```python
{
    'ma_period': [20, 25, 30, 35, 40],
    'batch_fraction': [0.20, 0.25, 0.30, 0.35],
    'max_days_without_sale': [45, 60, 75, 90],
    'cooldown_days': [3, 5, 7, 10, 14]
}
# Combinations: 400
```

### ConsensusStrategy (Fixed)
```python
{
    'consensus_threshold': [0.60, 0.65, 0.70, 0.75, 0.80],
    'min_return': [0.02, 0.03, 0.04, 0.05],
    'evaluation_day': [10, 12, 14],
    'cooldown_days': [3, 5, 7, 10, 14]
}
# Combinations: 300
```

### ExpectedValueStrategy (Fixed)
```python
{
    'min_ev_improvement': [30, 40, 50, 60, 75],
    'baseline_batch': [0.10, 0.12, 0.15, 0.18, 0.20],
    'baseline_frequency': [7, 10, 12, 14],
    'cooldown_days': [3, 5, 7, 10, 14]
}
# Combinations: 500
```

### RiskAdjustedStrategy (Fixed)
```python
{
    'min_return': [0.02, 0.03, 0.04, 0.05],
    'max_uncertainty': [0.25, 0.30, 0.35, 0.40],
    'consensus_threshold': [0.55, 0.60, 0.65, 0.70],
    'evaluation_day': [10, 12, 14],
    'cooldown_days': [3, 5, 7, 10, 14]
}
# Combinations: 960
```

---

## Implementation Requirements

### Must Support:
1. **All 9 strategies** (not just 3)
2. **Matched pair constraints** (PriceThreshold/Predictive share params)
3. **Hidden parameters** (cooldown_days, batch sizing)
4. **Multi-stage optimization** (coarse → fine → ultra-fine)
5. **Result persistence** (save all combinations, not just best)
6. **Visualization** (heatmaps showing parameter sensitivity)

### Must Avoid:
1. **Redundant computation** (cache backtest results)
2. **Memory issues** (stream results to disk)
3. **Fixed vs buggy confusion** (clearly label which version)

---

## Deliverable

Create `diagnostic_13_comprehensive_grid_search.ipynb` that:
1. Tests ALL 9 strategies
2. Searches ALL parameters (including hidden ones)
3. Uses fixed strategy implementations
4. Saves comprehensive results for analysis
5. Identifies global optimal strategy + parameters
6. Generates sensitivity visualizations

**Expected outcome:**
Find the combination that beats baseline by maximum margin with synthetic_acc90.

---

## Success Criteria

**Stage 1 Success:**
- All 2,001 baseline combinations tested
- Top 5 strategies identified
- Parameter sensitivity understood

**Stage 2 Success:**
- Batch sizing optimized for top strategies
- Best strategy beats baseline by >5%
- Parameters make intuitive sense

**Stage 3 Success:**
- Global optimal found
- Beats baseline by >6%
- Monotonic improvement across accuracy levels (60% → 90%)

---

**Next Step:** Implement diagnostic_13 with comprehensive grid search framework
