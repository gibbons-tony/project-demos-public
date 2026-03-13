# Trading Strategy Algorithm Issues

**Date:** 2025-11-22
**Status:** 🚨 **CRITICAL BUGS IDENTIFIED**
**Priority Context:** See [MASTER_SYSTEM_PLAN.md](../MASTER_SYSTEM_PLAN.md) for current priorities and dependencies

---

## Executive Summary

At **90% prediction accuracy**, trading strategies **underperform baselines by 2-3%**. This indicates logic bugs or implementation issues in the trading algorithms.

**Expected:** 90% accuracy should WIN by 10-20%
**Actual:** LOSE by 2-3%
**Diagnosis:** Trading logic is broken

---

## Critical Test Results: 90% Accuracy

### Coffee (90% Accuracy Synthetic)
- Best Baseline: Equal Batches = $727,037
- Best Prediction: Expected Value = $708,017
- Advantage: **-$19,020 (-2.6%)** ❌

### Sugar (90% Accuracy Synthetic)
- Best Baseline: Immediate Sale = $50,071
- Best Prediction: Consensus = $49,351
- Advantage: **-$720 (-1.4%)** ❌

**Verdict:** Predictions lose money even at 90% accuracy → **Trading logic is broken**

---

## Critical Findings

### Finding 1: Non-Monotonic Performance

Performance does NOT improve consistently as accuracy increases:

| Accuracy | Coffee Advantage | Sugar Advantage | Expected | Status |
|----------|------------------|-----------------|----------|--------|
| 60% | -2.6% | -1.4% | ~0% | ❌ FAIL |
| 70% | -2.6% | -1.4% | +2-5% | ❌ FAIL |
| 80% | -2.7% | -1.4% | +5-10% | ❌ FAIL |
| **90%** | **-2.6%** | **-1.4%** | **+10-20%** | ❌ **FAIL** |

**Coffee:** -$18,931 → -$19,220 → -$19,902 → -$19,020 (fluctuates, no trend)
**Sugar:** -$711 → -$692 → -$692 → -$720 (no clear improvement)

### Finding 2: Real Models Show Identical Results

Out of 13 real forecast models for Coffee:
- **Only 3 unique earnings values**
- **23% uniqueness ratio** (expected: ~90%+)
- Multiple models returning **exact same numbers**

**Example:**
- arima_v1, prophet_v1, xgboost, random_walk → ALL produce Expected Value: $751,640.64
- **This is statistically impossible** if predictions differ

**Diagnosis:** Strategies may be ignoring predictions entirely

### Finding 3: Matched Pair Strategies Show Minimal Difference

**Coffee 90% Accuracy:**
- Moving Average (Baseline): $713,903
- Moving Average Predictive: $706,031
- **Difference: -$7,872**

**Expected:** Predictive should be +$20k-$50k better with 90% accuracy
**Actual:** It's WORSE by $8k

**Diagnosis:** Prediction overlay is not working correctly

---

## Debugging Roadmap

### Step 1: Add Debug Logging (CRITICAL)

```python
def should_sell(self, day, inventory, price, predictions, technical_indicators):
    # ADD THIS:
    print(f"Day {day}: price={price:.2f}, pred_matrix shape={predictions.shape if predictions is not None else None}")

    if predictions is not None and len(predictions) > 0:
        future_prices = predictions[:, :self.horizon]
        print(f"  Sample predictions: {future_prices[0, :5]}")  # First 5 days
```

### Step 2: Validate Prediction Matrix Access

```python
# In run() method where predictions are retrieved:
current_date = row['date']
pred_matrix = self.prediction_matrices.get(current_date, None)

# ADD THIS:
if pred_matrix is not None:
    print(f"Date {current_date}: predictions available, shape={pred_matrix.shape}")
else:
    print(f"Date {current_date}: NO PREDICTIONS!")
```

### Step 3: Check Date Alignment

```python
# Before running backtests:
pred_dates = set(prediction_matrices.keys())
price_dates = set(prices['date'].tolist())
overlap = pred_dates.intersection(price_dates)

print(f"Prediction dates: {len(pred_dates)}")
print(f"Price dates: {len(price_dates)}")
print(f"Overlap: {len(overlap)} ({100*len(overlap)/len(pred_dates):.1f}%)")
```

**Expected:** >90% overlap

### Step 4: Validate Strategy Decision Logic

```python
# After calculating expected_return:
print(f"  Expected return: {expected_return:.3%}")
print(f"  Cost to wait: {cost_to_wait:.3%}")
print(f"  Decision: {'SELL' if expected_return > cost_to_wait else 'WAIT'}")
```

**Expected:** Mix of SELL and WAIT decisions based on predictions

---

## Root Cause Hypotheses

### Hypothesis 1: Strategy Implementation Bugs (MOST LIKELY)

**Evidence:**
- Predictions available (notebooks show they're generated)
- Predictions have correct structure (500 runs × 14 days)
- But strategies produce wrong results

**Likely issues:**
1. Predictions indexed incorrectly (date misalignment)
2. Prediction evaluation logic has bugs
3. Cost calculations dominating signal
4. Strategies defaulting to baseline behavior

### Hypothesis 2: Matched Pair Strategies Not Using Predictions

**SMOKING GUN:**

```
Moving Average (Baseline): $713,903.04
Moving Average Predictive: $713,903.04  ← EXACT MATCH!

Price Threshold (Baseline): $704,988.93
Price Threshold Predictive: $704,988.93  ← EXACT MATCH!
```

**This means:**
- The "Predictive" versions return IDENTICAL results to baselines
- The prediction overlay is doing NOTHING
- Implementation is broken

### Hypothesis 3: All Real Models Return Identical Results

**Every real forecast model produces EXACT same earnings:**
- arima_v1, prophet_v1, xgboost, etc. all → Expected Value: $751,640.64

**This is statistically impossible** if predictions are being used. This suggests:
- Predictions are ignored by strategies
- Strategies use only historical price data
- Backtest engine has a bug

---

## Validation Plan

### Quick Fix Validation Test

After fixes, run this test:

1. **Generate new 99% accuracy synthetic predictions**
2. **Run backtest on Coffee only**
3. **Expected result:**
   - Prediction strategies should beat Equal Batches by +$50k-$100k
   - If still negative → more debugging needed
   - If positive → fixes working!

### Post-Fix Verification Checklist

- [ ] 90% accuracy shows strong positive advantage (+10-20%)
- [ ] Monotonic improvement with accuracy (60% < 70% < 80% < 90%)
- [ ] Matched pairs diverge from baselines
- [ ] Real models show diverse earnings (not all identical)
- [ ] Prediction strategies use actual forecast data (debug logs confirm)
- [ ] Date alignment is >90% overlap
- [ ] Decision logs show mix of SELL and WAIT decisions

---

## Summary Table: All Results

### Synthetic Models - Prediction Advantage

| Commodity | Acc 60% | Acc 70% | Acc 80% | Acc 90% | Monotonic? |
|-----------|---------|---------|---------|---------|------------|
| Coffee | -2.6% ❌ | -2.6% ❌ | -2.7% ❌ | -2.6% ❌ | NO ❌ |
| Sugar | -1.4% ❌ | -1.4% ❌ | -1.4% ❌ | -1.4% ❌ | NO ❌ |

### Real Models - Prediction Advantage

| Model | Coffee | Sugar | Notes |
|-------|--------|-------|-------|
| ARIMA v1 | +3.4% ✓ | N/A | Identical to all others |
| Prophet v1 | +3.4% ✓ | -3.4% ❌ | Coffee OK, Sugar bad |
| XGBoost | +3.6% ✓ | -3.4% ❌ | Best for coffee |
| Random Walk | +3.4% ✓ | -3.4% ❌ | Identical to others |
| Naive | -1.7% ❌ | -3.4% ❌ | Similar to synthetic |

---

## Conclusion

The 90% accuracy scenario **should** show obvious predictive advantage, and it doesn't. This confirms there are bugs in how predictions are used by the trading strategies.

**Good news:**
- ✅ Workflow is well-designed
- ✅ Bugs are identifiable
- ✅ Fixes are straightforward

**Bad news:**
- ❌ Current results are invalid
- ❌ Need debugging before decision-making
- ❌ Will require re-running all analyses

---

**Confidence in Diagnosis:** 95%
**Estimated Fix Time:** 2-4 hours of debugging (after automation infrastructure complete)
**Priority:** HIGH - But blocked by Phase 2 (Automation)

**For current priorities and phase dependencies:** See [MASTER_SYSTEM_PLAN.md](../MASTER_SYSTEM_PLAN.md)

---

**Document created:** 2025-11-22
**Last Updated:** 2025-11-24 (Consolidation)
**Status:** DEFER UNTIL PHASE 2 COMPLETE
