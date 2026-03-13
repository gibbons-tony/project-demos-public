# Trading Strategy Debugging Plan

**Test Case:** Coffee synthetic_acc90 (90% accuracy - should be obvious win)
**Current State:** Losing -$19k (-2.6%) vs baseline
**Goal:** Get predictions to beat baseline by +$50k-$100k (+7-14%)
**Approach:** Create diagnostic notebooks (don't modify existing workflow)

---

## Execution Constraints

**✅ Allowed:**
- Create new diagnostic notebooks
- Read existing notebooks
- Analyze outputs
- Create test scripts

**❌ Not Allowed:**
- Modify existing notebooks (00-10)
- Change production workflow
- Edit strategy implementations directly

**Strategy:** Create parallel diagnostic notebooks that:
1. Load same data as production
2. Add extensive logging
3. Test modified strategies
4. Validate fixes before proposing changes

---

## Phase 1: Diagnostic - Find Where Predictions Are Lost

**Duration:** 1 hour
**Deliverable:** Diagnostic report identifying exact bug location

### Diagnostic 1.1: Prediction Loading Validation

**Create:** `diagnostic_01_prediction_loading.ipynb`

**Purpose:** Verify predictions are loaded correctly with proper date alignment

**Key Checks:**
1. Prediction matrix structure (should be 500 runs × 14 days)
2. Date type consistency (datetime vs string)
3. Date alignment between predictions and prices (>90% overlap)
4. Prediction value ranges (should be realistic prices)

**Pass Criteria:**
- Matrix shape correct
- >90% date overlap
- Values in range $200-$400 for coffee

---

### Diagnostic 1.2: Backtest Engine Trace

**Create:** `diagnostic_02_backtest_trace.ipynb`

**Purpose:** Trace prediction flow through backtest engine

**Key Checks:**
1. How many days have predictions available?
2. Are predictions reaching the strategy's should_sell() method?
3. Sample prediction values on key dates

**Pass Criteria:**
- >200 days with predictions (harvest season coverage)
- Predictions not None when passed to strategy
- Values look reasonable

---

### Diagnostic 1.3: Strategy Decision Logic Trace

**Create:** `diagnostic_03_strategy_decisions.ipynb`

**Purpose:** Instrument Expected Value strategy to log all decision-making

**Key Checks:**
1. Is strategy receiving predictions or None?
2. What are the actual expected_return calculations?
3. Why is it choosing SELL vs WAIT?
4. Are costs being calculated correctly?

**Pass Criteria:**
- Predictions received on >80% of days
- Mix of SELL and WAIT decisions
- Expected returns vary based on predictions
- Correlation between predictions and decisions

---

## Phase 2: Fix Implementation

**Duration:** 2 hours
**Deliverable:** Working strategy implementation in test notebook

### Fix 2.1: Create Test Notebook with Corrections

**Create:** `diagnostic_04_fixed_strategies.ipynb`

**Purpose:** Implement corrected versions of strategies based on diagnostics

**Approach:**
1. Copy strategy class definitions
2. Add fixes identified in Phase 1
3. Add extensive logging
4. Test on Coffee synthetic_acc90

**Common Fixes to Try:**

```python
# Fix A: Date alignment
prices['date'] = pd.to_datetime(prices['date'])
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

# Fix B: Ensure predictions passed to strategy
# In backtest loop:
prediction_matrix = prediction_matrices.get(current_date, None)
# Verify not None before passing

# Fix C: Check decision logic
# Expected Value should:
# - If future_price > current_price significantly → WAIT
# - If future_price <= current_price → SELL NOW
```

---

### Fix 2.2: Validate Single Strategy

**Create:** `diagnostic_05_single_strategy_test.ipynb`

**Purpose:** Test corrected Expected Value strategy in isolation

**Test:**
1. Run only Expected Value on Coffee synthetic_acc90
2. Compare to baseline (Equal Batches)
3. Verify decision log shows predictions being used

**Pass Criteria:**
- Net earnings > $750,000 (beats $727k baseline by $23k+)
- Decision log shows variation based on predictions
- Correlation between predictions and decisions < 0.95

---

## Phase 3: Validation

**Duration:** 30 minutes
**Deliverable:** Confirmation that fixes work

### Validation 3.1: All Prediction Strategies

**Create:** `diagnostic_06_all_strategies_test.ipynb`

**Purpose:** Test all 5 prediction strategies with fixes

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

---

### Validation 3.2: Monotonicity Test

**Create:** `diagnostic_07_monotonicity_test.ipynb`

**Purpose:** Verify performance improves with accuracy

**Test:**
Run Expected Value on all accuracies: 60%, 70%, 80%, 90%

**Expected Results:**
- 60%: ~$735k (+1.1%)
- 70%: ~$750k (+3.2%)
- 80%: ~$765k (+5.2%)
- 90%: ~$775k (+6.6%)

**Pass Criteria:**
- Monotonic increase (each > previous)
- 90% > 80% by >$10k
- All positive advantage (except maybe 60%)

---

## Phase 4: Fine-Tuning

**Duration:** 1-2 hours
**Deliverable:** Optimized parameters

### Tune 4.1: Parameter Grid Search

**Create:** `diagnostic_08_parameter_tuning.ipynb`

**Purpose:** Optimize strategy parameters using 90% accuracy as training set

**Parameters to Tune:**

**Expected Value:**
- evaluation_day: [3, 5, 7, 10, 14]
- min_return: [0.02, 0.03, 0.04, 0.05]

**Consensus:**
- consensus_threshold: [0.60, 0.65, 0.70, 0.75, 0.80]
- min_return: [0.02, 0.03, 0.04, 0.05, 0.06]

**Risk-Adjusted:**
- Adjust batch sizes: [conservative, baseline, aggressive]

**Method:**
- Grid search on Coffee synthetic_acc90
- Select parameters maximizing net earnings
- Validate on other accuracies

---

## Phase 5: Cross-Validation

**Duration:** 30 minutes
**Deliverable:** Confirmation that tuning generalizes

### Cross-Val 5.1: Lower Accuracies

**Create:** `diagnostic_09_cross_validation.ipynb`

**Purpose:** Verify optimized parameters work across all accuracies

**Test:**
1. Run optimized Expected Value on 60%, 70%, 80%, 90%
2. Check monotonicity
3. Verify all (or most) show positive advantage

**Pass Criteria:**
- Monotonic improvement
- 80%+ shows strong advantage (>$30k)
- 70%+ shows moderate advantage (>$15k)

---

### Cross-Val 5.2: Sugar Commodity

**Create:** `diagnostic_10_sugar_validation.ipynb`

**Purpose:** Verify fixes work for Sugar too

**Test:**
Run optimized strategies on Sugar synthetic_acc90

**Pass Criteria:**
- At least one strategy beats baseline
- 90% accuracy better than lower accuracies
- Positive trend with accuracy

---

## Phase 6: Production Integration Proposal

**Duration:** 1 hour
**Deliverable:** Recommended changes to production notebooks

### Integration 6.1: Document Required Changes

**Create:** `PRODUCTION_CHANGES_PROPOSAL.md`

**Document:**
1. Exact code changes needed in each notebook
2. Before/after comparisons
3. Expected impact on results
4. Risk assessment

**Notebooks to Change:**
- `03_strategy_implementations.ipynb` - Fix strategy logic
- `04_backtesting_engine.ipynb` - Fix date alignment (if needed)
- `05_strategy_comparison.ipynb` - Fix data loading (if needed)

**Format:**
```markdown
## Change 1: Date Alignment (05_strategy_comparison.ipynb)

### Current Code (Line 45):
```python
prices = spark.table(...).toPandas()
```

### Proposed Fix:
```python
prices = spark.table(...).toPandas()
prices['date'] = pd.to_datetime(prices['date'])  # ADD THIS
```

### Rationale:
Ensures date types match between prices and predictions.

### Risk: LOW
- Simple type conversion
- No logic changes
- Easily reversible
```

---

## Success Metrics

### Phase 1 Success (Diagnostics):
- [ ] Identified exact location where predictions are lost/misused
- [ ] Documented root cause with evidence
- [ ] Created reproduction case

### Phase 2 Success (Fixes):
- [ ] Expected Value beats baseline by >$30k on Coffee 90%
- [ ] Decision logs show predictions driving decisions
- [ ] Correlation check passes (predictions used, not ignored)

### Phase 3 Success (Validation):
- [ ] 3+ strategies beat baseline
- [ ] Monotonic improvement (60% < 70% < 80% < 90%)
- [ ] 90% shows +$40k-$60k advantage

### Phase 4 Success (Tuning):
- [ ] Optimized parameters improve results by >10%
- [ ] Tuning generalizes to other accuracies
- [ ] Parameter choices are justifiable

### Phase 5 Success (Cross-Val):
- [ ] Tuning works on all accuracies
- [ ] Tuning works on Sugar
- [ ] No overfitting detected

### Phase 6 Success (Integration):
- [ ] Clear change proposal documented
- [ ] Changes are minimal and low-risk
- [ ] Expected impact quantified

---

## Rollback Strategy

If diagnostic uncovers unfixable issues:

**Plan B:** Document that current strategies are fundamentally flawed and recommend:
1. Simplified strategies (fewer parameters)
2. Different approach (machine learning-based decisions)
3. Hybrid approach (combine baseline + predictions)

---

## Execution Timeline

### Session 1 (2-3 hours):
- Create diagnostic notebooks 01-03
- Run diagnostics
- Identify root cause

### Session 2 (2-3 hours):
- Create fix notebook 04-05
- Implement corrections
- Validate single strategy

### Session 3 (2 hours):
- Create validation notebooks 06-07
- Test all strategies
- Verify monotonicity

### Session 4 (1-2 hours):
- Create tuning notebook 08
- Optimize parameters
- Document findings

### Session 5 (1 hour):
- Create cross-val notebooks 09-10
- Final validation
- Create integration proposal

---

## Deliverables

### Diagnostic Notebooks:
1. `diagnostic_01_prediction_loading.ipynb`
2. `diagnostic_02_backtest_trace.ipynb`
3. `diagnostic_03_strategy_decisions.ipynb`
4. `diagnostic_04_fixed_strategies.ipynb`
5. `diagnostic_05_single_strategy_test.ipynb`
6. `diagnostic_06_all_strategies_test.ipynb`
7. `diagnostic_07_monotonicity_test.ipynb`
8. `diagnostic_08_parameter_tuning.ipynb`
9. `diagnostic_09_cross_validation.ipynb`
10. `diagnostic_10_sugar_validation.ipynb`

### Documentation:
1. `DIAGNOSTIC_REPORT.md` - Findings from Phase 1
2. `FIX_VALIDATION_REPORT.md` - Results from Phases 2-3
3. `TUNING_REPORT.md` - Optimization results from Phase 4
4. `PRODUCTION_CHANGES_PROPOSAL.md` - Integration plan

---

## Getting Started

**Next Steps:**
1. Create `diagnostic_01_prediction_loading.ipynb`
2. Run on Coffee synthetic_acc90
3. Analyze output
4. Document findings
5. Proceed to diagnostic_02

**Ready to begin?** Start with Phase 1, Diagnostic 1.1.
