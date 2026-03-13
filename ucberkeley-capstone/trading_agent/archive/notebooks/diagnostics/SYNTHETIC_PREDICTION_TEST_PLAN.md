# Synthetic Prediction Testing Plan

**Date:** 2025-11-22
**Status:** ACTIVE INVESTIGATION
**Problem:** Synthetic predictions with 90% accuracy produce WORSE results than no-prediction baselines

---

## Problem Statement

### Expected Behavior
With 90% accurate predictions, trading strategies should:
- Beat baseline strategies by **+$30k to $50k** (+4% to +7%)
- Show **monotonic improvement**: 60% < 70% < 80% < 90% accuracy
- Make **prediction-informed decisions** that outperform simple rules

### Actual Behavior
**Coffee synthetic_acc90:**
- Best Baseline (Equal Batches): $727,037
- Best Prediction (Expected Value): $708,017
- **Result: -$19,020 (-2.6%)** ❌

**This is impossible if predictions are being used correctly.**

---

## Testing Strategy: Top-to-Bottom Validation

We will systematically test each layer of the system from data input through final decision-making.

### Layer 1: Data Layer
**Question:** Are predictions generated correctly and accessible?

**Tests:**
- ✅ **diagnostic_01** - Verify prediction matrices load with correct shape
- ✅ **diagnostic_01** - Verify date alignment between predictions and prices
- 🔲 **diagnostic_08** - Verify predictions are not None when looked up

**Pass Criteria:**
- Prediction matrices: 951 dates × 500 runs × 14 horizons
- Date overlap: 100% (all prediction dates exist in price data)
- Synthetic accuracy: Measured correlation with actual prices = 90% ±2%

**If FAIL:** Bug is in prediction generation (notebook 01)
**If PASS:** Move to Layer 2

---

### Layer 2: Data Passing Layer
**Question:** Are predictions being passed from backtest engine to strategies?

**Tests:**
- ✅ **diagnostic_08** - Analyze trade reasons for 'no_predictions_fallback' **[COMPLETED - PASSED]**
  - **Result:** 0% trades without predictions (0/207)
  - **Finding:** All trades show prediction-based reasons
  - **Conclusion:** Predictions ARE being passed correctly
- ~~🔲 **diagnostic_09**~~ - Not needed (Layer 2 passed)
- ~~🔲 **diagnostic_10**~~ - Not needed (Layer 2 passed)

**Pass Criteria:**
- ✅ <5% of trades should have 'no_predictions_fallback' reason (ACHIEVED: 0%)
- ✅ prediction_matrices.get(current_date) returns non-None for ≥95% of trading days
- ✅ Date types match exactly (both pandas.Timestamp)

**Result:** ✅ PASSED - Move to Layer 3

---

### Layer 3: Strategy Decision Layer
**Question:** Are strategies using predictions correctly in their decision logic?

**Tests:**
- 🔲 **diagnostic_11** - Trace Expected Value calculation step-by-step
- 🔲 **diagnostic_12** - Verify prediction array slicing (correct horizon used)
- 🔲 **diagnostic_13** - Compare EV decisions with manually calculated EV
- 🔲 **diagnostic_14** - Check if batch sizes correlate with prediction confidence

**Pass Criteria:**
- Expected Value calculation matches hand-calculated values
- Strategy uses correct prediction horizon (day 14 for 2-week forecasts)
- Batch sizes increase when predictions show strong upward trend
- Batch sizes decrease when predictions show downward trend

**If FAIL:** Bug is in strategy decision logic
**If PASS:** Move to Layer 4

---

### Layer 4: Trade Execution Layer
**Question:** Are calculated decisions being executed correctly?

**Tests:**
- 🔲 **diagnostic_15** - Verify decisions translate to trades correctly
- 🔲 **diagnostic_16** - Check inventory tracking across trades
- 🔲 **diagnostic_17** - Validate cost calculations (storage + transaction)

**Pass Criteria:**
- When strategy returns {'action': 'SELL', 'amount': X}, trade occurs for amount X
- Inventory decreases by exact trade amount
- Costs are calculated correctly (percentage-based on price)

**If FAIL:** Bug is in backtest engine trade execution
**If PASS:** Move to Layer 5

---

### Layer 5: Results Aggregation Layer
**Question:** Are results being calculated and stored correctly?

**Tests:**
- 🔲 **diagnostic_18** - Recalculate net_earnings from trades manually
- 🔲 **diagnostic_19** - Verify all costs are included in final total
- 🔲 **diagnostic_20** - Compare stored results with fresh calculation

**Pass Criteria:**
- Manual calculation matches stored net_earnings ±$1
- All trades accounted for in revenue calculation
- All storage days accounted for in cost calculation

**If FAIL:** Bug is in results calculation or storage
**If PASS:** Problem is elsewhere (parameter tuning, strategy design)

---

## Detailed Test Specifications

### Test 08: Check Prediction Usage
**File:** `diagnostic_08_check_prediction_usage.ipynb`
**Status:** ✅ CREATED

**What it does:**
- Loads results for coffee synthetic_acc90
- Analyzes trade reasons for each strategy
- Counts trades with 'no_predictions_fallback' vs prediction-based reasons
- Flags if >5% trades are fallback

**Expected outcome:**
- If predictions are passed correctly: 0-5% fallback trades
- If predictions are NOT passed: 50-100% fallback trades

**Interpretation:**
- High fallback % → Layer 2 bug (data passing)
- Low fallback % → Layer 3 bug (decision logic)

---

### Test 09: Instrument Backtest Engine
**File:** `diagnostic_09_backtest_instrumentation.ipynb` (TO CREATE)

**What it does:**
- Creates InstrumentedBacktestEngine with logging
- Logs every prediction lookup: date, result (None or matrix)
- Tracks prediction availability for each trading day
- Reports % of days with successful prediction lookups

**Expected outcome:**
- ≥95% of trading days should have predictions
- Log should show prediction matrix shapes when found
- Log should identify which specific dates return None

**What to check:**
```python
for each day:
    current_date = prices['date'][day]
    predictions = prediction_matrices.get(current_date, None)

    if predictions is None:
        LOG: "Day {day}, Date {current_date}: NO PREDICTIONS"
    else:
        LOG: "Day {day}, Date {current_date}: Predictions shape {predictions.shape}"
```

---

### Test 10: Date Key Validation
**File:** `diagnostic_10_date_key_validation.ipynb` (TO CREATE)

**What it does:**
- Loads prediction_matrices dictionary
- Loads prices DataFrame
- Compares date formats, types, and values character-by-character
- Tests dictionary lookup with actual price dates

**Expected outcome:**
```python
# Should work:
for date in prices['date']:
    pred = prediction_matrices.get(date, None)
    assert pred is not None, f"Missing predictions for {date}"
```

**What to check:**
- Are prediction keys: datetime, date, string, Timestamp?
- Are price dates: datetime, date, string, Timestamp?
- Do types match exactly?
- Do lookups work when types are converted?

---

### Test 11: Expected Value Calculation Trace
**File:** `diagnostic_11_ev_calculation_trace.ipynb` (TO CREATE)

**What it does:**
- Takes a single day's data (price, predictions, inventory)
- Manually calculates expected value step-by-step
- Compares with strategy's calculation
- Shows all intermediate values

**Example:**
```python
Day 100:
  Current price: $220.00
  Predictions (500 runs, day 14):
    Mean: $235.00
    Median: $234.50
    Std: $15.00

  Expected Value Calculation:
    If sell today: $220 × inventory - costs = $X
    If wait 14 days: $235 (expected) × inventory - storage - costs = $Y
    EV improvement: $Y - $X = $Z

  Strategy decision:
    Min EV improvement threshold: $50
    Calculated EV improvement: $Z
    Decision: SELL if Z < 50, WAIT if Z >= 50
```

**Expected outcome:**
- Manual calculation matches strategy's calculation
- Decisions make sense given the numbers

---

### Test 12: Prediction Horizon Check
**File:** `diagnostic_12_horizon_check.ipynb` (TO CREATE)

**What it does:**
- Verifies strategies use the correct prediction horizon
- For 14-day forecast: should use predictions[:, 13] (0-indexed)
- Checks if using wrong slice like predictions[:, 0] (today) or predictions[:, 7] (wrong day)

**Expected outcome:**
```python
# Correct:
future_prices = predictions[:, 13]  # Day 14 (2 weeks out)

# Incorrect (bugs):
future_prices = predictions[:, 0]   # Day 0 (today - useless!)
future_prices = predictions[:, 6]   # Day 7 (1 week - wrong horizon)
```

---

### Test 13: Decision Logic Validation
**File:** `diagnostic_13_decision_validation.ipynb` (TO CREATE)

**What it does:**
- For 100 random days, calculate what decision SHOULD be made
- Compare with what decision WAS made
- Identify any systematic errors

**Example scenario:**
```
Day 50:
  Price: $200
  Predicted (14d): $250 (mean), $10 (std)

Expected decision:
  - 90% accuracy means prediction is reliable
  - $250 > $200 by 25% - strong upward signal
  - Should WAIT to sell later at higher price

Actual decision:
  - Strategy chose: SELL
  - Reason: ???

→ BUG: Strategy is not responding to predictions correctly
```

---

### Test 14: Prediction Correlation Check
**File:** `diagnostic_14_prediction_correlation.ipynb` (TO CREATE)

**What it does:**
- For each trade, record:
  - Predicted future price
  - Actual future price (14 days later)
  - Decision made (SELL vs WAIT)
- Calculate correlation between predictions and decisions
- Check if good predictions lead to better decisions

**Expected outcome:**
- When predicted_price > current_price, strategy should WAIT more often
- When predicted_price < current_price, strategy should SELL more often
- Correlation should be positive and significant

**If correlation is near zero:** Strategy is ignoring predictions!

---

## Test Execution Order

### Phase 1: Data Validation (Run First)
1. ✅ diagnostic_01 (already run - PASSED)
2. 🔲 diagnostic_08 - Check if predictions are passed
3. 🔲 diagnostic_10 - Validate date keys

**Stop if:** Predictions are not being passed (high fallback %)
**Continue to Phase 2 if:** Predictions are being passed correctly

---

### Phase 2: Decision Logic Validation
4. 🔲 diagnostic_11 - Trace EV calculations
5. 🔲 diagnostic_12 - Check prediction horizon
6. 🔲 diagnostic_13 - Validate decisions
7. 🔲 diagnostic_14 - Check prediction correlation

**Stop if:** Logic bug found in decision-making
**Continue to Phase 3 if:** Decisions look correct

---

### Phase 3: Execution Validation
8. 🔲 diagnostic_15 - Verify trade execution
9. 🔲 diagnostic_16 - Check inventory tracking
10. 🔲 diagnostic_17 - Validate cost calculations

**Stop if:** Bug found in execution
**Continue to Phase 4 if:** Execution is correct

---

### Phase 4: Results Validation
11. 🔲 diagnostic_18 - Recalculate results manually
12. 🔲 diagnostic_19 - Verify cost accounting
13. 🔲 diagnostic_20 - Compare results

---

## Success Criteria for Each Phase

### Phase 1 Success:
- [x] Prediction matrices load correctly
- [x] Dates align 100%
- [ ] <5% trades have 'no_predictions_fallback'
- [ ] Date type lookups work correctly

### Phase 2 Success:
- [ ] EV calculations are mathematically correct
- [ ] Strategies use correct prediction horizon (day 14)
- [ ] Decisions correlate positively with predictions
- [ ] Batch sizes respond to prediction confidence

### Phase 3 Success:
- [ ] Decisions translate to correct trades
- [ ] Inventory tracking is accurate
- [ ] Costs are calculated correctly

### Phase 4 Success:
- [ ] Manual results match stored results
- [ ] All trades and costs accounted for

---

## Expected Bug Locations (Ranked by Likelihood)

### 1. Prediction Horizon Bug (HIGH PROBABILITY)
**Hypothesis:** Strategy is using wrong prediction slice
```python
# Wrong (using today's price):
future_price = predictions[:, 0]

# Wrong (using wrong day):
future_price = predictions[:, 6]  # Day 7 instead of 14

# Correct:
future_price = predictions[:, 13]  # Day 14 (0-indexed)
```

**Test with:** diagnostic_12

---

### 2. Decision Logic Inverted (MEDIUM PROBABILITY)
**Hypothesis:** Strategy logic is backwards
```python
# Wrong:
if predicted_price > current_price:
    return SELL  # Should WAIT!

# Correct:
if predicted_price > current_price:
    return WAIT  # Expect price to rise
```

**Test with:** diagnostic_11, diagnostic_13

---

### 3. Prediction Lookup Failure (MEDIUM PROBABILITY)
**Hypothesis:** Dictionary lookup returns None due to date type mismatch in production
```python
# Diagnostic 01 showed dates match, but maybe in actual execution they don't
```

**Test with:** diagnostic_08, diagnostic_09, diagnostic_10

---

### 4. Cost Calculation Error (LOW PROBABILITY)
**Hypothesis:** Costs are too high for prediction strategies
- But diagnostics showed costs are ~2%, not enough to explain -2.6% gap

**Test with:** diagnostic_17, diagnostic_18

---

## Validation After Fixes

Once bug is identified and fixed (in diagnostics folder), validate with:

### Validation Test 1: Monotonicity
Run all 4 synthetic accuracies (60%, 70%, 80%, 90%) and verify:
```
Results should be:
60% accuracy: ≈ baseline (±$5k)
70% accuracy: +$10-20k vs baseline
80% accuracy: +$20-40k vs baseline
90% accuracy: +$30-50k vs baseline
```

**Pass:** Clear upward trend
**Fail:** Random or downward trend

---

### Validation Test 2: Absolute Performance
With 90% accuracy:
```
Expected Value strategy should:
- Beat Equal Batches baseline by >$30k
- Net earnings: $755k - $775k (not $708k)
```

**Pass:** Prediction strategy is best performer
**Fail:** Baseline still wins

---

### Validation Test 3: Decision Correlation
```
Correlation between:
- Prediction signal strength
- Decision aggressiveness (batch size)

Should be: r > 0.6 (strong positive)
```

**Pass:** Strategies respond to predictions
**Fail:** Strategies ignore predictions

---

## Files Created

### Existing:
- ✅ `diagnostic_01_prediction_loading.ipynb` - Date alignment (PASSED)
- ✅ `diagnostic_02_backtest_trace.ipynb` - Backtest tracing (FAILED - my bug)
- ✅ `diagnostic_03_strategy_decisions.ipynb` - Strategy instrumentation (FAILED - my bug)
- ✅ `diagnostic_04_fixed_strategies.ipynb` - Fixed implementations (FAILED - my bug)
- ✅ `diagnostic_08_check_prediction_usage.ipynb` - Trade reason analysis (READY)

### To Create (Priority Order):
1. 🔲 `diagnostic_09_backtest_instrumentation.ipynb` - Log prediction lookups
2. 🔲 `diagnostic_10_date_key_validation.ipynb` - Validate dictionary lookups
3. 🔲 `diagnostic_11_ev_calculation_trace.ipynb` - Trace EV math
4. 🔲 `diagnostic_12_horizon_check.ipynb` - Verify prediction horizon
5. 🔲 `diagnostic_13_decision_validation.ipynb` - Validate decision logic
6. 🔲 `diagnostic_14_prediction_correlation.ipynb` - Check prediction usage

---

## Next Steps

### Immediate (NOW):
1. Run **diagnostic_08** in Databricks
2. Check results: Are predictions being passed?
   - If NO → Create diagnostic_09, diagnostic_10
   - If YES → Create diagnostic_11, diagnostic_12

### After Identifying Bug:
1. Document exact bug location and nature
2. Create fixed version in diagnostics folder
3. Test fixed version with all 4 accuracy levels
4. Validate monotonicity and absolute performance
5. Document required changes to production code

### Final Deliverable:
**BUG_REPORT.md** containing:
- Exact bug location (file, function, line)
- Root cause explanation
- Proof of bug (diagnostic outputs)
- Required fix (code changes)
- Validation results (showing fix works)

---

**Test Plan Owner:** Claude Code
**Execution:** User (Mark) in Databricks
**Timeline:** Complete within 1 session
**Success Metric:** Identify root cause and demonstrate fix
