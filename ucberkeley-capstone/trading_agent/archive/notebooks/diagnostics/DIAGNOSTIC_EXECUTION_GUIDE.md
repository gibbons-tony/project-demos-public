# Diagnostic Execution Guide

**Status:** Ready to Execute
**Created:** 2025-11-22
**Purpose:** Step-by-step guide for running diagnostic notebooks to identify and fix trading strategy bugs

---

## Overview

I've created 7 diagnostic notebooks to systematically identify and fix the bugs causing prediction strategies to underperform baselines. These notebooks follow a structured approach:

1. **Diagnostics (01-03):** Identify where predictions are lost
2. **Fixes (04):** Implement corrections
3. **Validation (05-07):** Verify fixes work

---

## Quick Start

### Step 1: Sync Notebooks to Databricks

```bash
cd /Users/markgibbons/capstone/ucberkeley-capstone/trading_agent/commodity_prediction_analysis
databricks workspace import-dir . /Workspace/Users/your-email/trading_agent/commodity_prediction_analysis --overwrite
```

### Step 2: Run Notebooks in Order

Open Databricks and run in this exact order:

1. `diagnostic_01_prediction_loading.ipynb`
2. `diagnostic_02_backtest_trace.ipynb`
3. `diagnostic_03_strategy_decisions.ipynb`
4. `diagnostic_04_fixed_strategies.ipynb`
5. `diagnostic_05_single_strategy_test.ipynb`
6. `diagnostic_06_all_strategies_test.ipynb`
7. `diagnostic_07_monotonicity_test.ipynb`

**Attach to cluster:** Same cluster you use for notebooks 00-10

---

## Detailed Notebook Descriptions

### Phase 1: Root Cause Diagnostics

#### diagnostic_01_prediction_loading.ipynb

**Purpose:** Verify predictions load correctly with proper date alignment

**What it does:**
- Loads prediction matrices for coffee synthetic_acc90
- Checks matrix shape (should be 500 x 14)
- Analyzes date types (datetime vs string)
- Calculates date overlap between predictions and prices
- Tests date normalization fix

**Pass criteria:**
- Matrix shape correct (500, 14)
- >90% date overlap after normalization
- Values in reasonable range ($200-$400 for coffee)

**Expected outcome:**
- ✓ PASS if date normalization fixes overlap
- ✗ FAIL if 0% overlap (confirms date type mismatch bug)

**Time:** 2-3 minutes

---

#### diagnostic_02_backtest_trace.ipynb

**Purpose:** Trace prediction flow through backtest engine

**What it does:**
- Creates instrumented backtest engine with logging
- Tracks how many days have predictions available
- Logs sample prediction values
- Counts days with/without predictions during backtest loop

**Pass criteria:**
- >200 days with predictions (harvest season coverage)
- Predictions not None when passed to strategy
- Coverage >80%

**Expected outcome:**
- ✓ PASS if predictions reaching backtest (coverage >80%)
- ✗ FAIL if 0% coverage (predictions not getting to engine)

**Time:** 3-4 minutes

---

#### diagnostic_03_strategy_decisions.ipynb

**Purpose:** Instrument Expected Value strategy to understand decision-making

**What it does:**
- Creates instrumented version of Expected Value strategy
- Logs every decision with full details:
  - Whether predictions received
  - Expected future price calculations
  - Expected return vs cost to wait
  - Net benefit calculations
  - Decision reasoning (SELL vs WAIT)
- Analyzes correlation between predictions and decisions

**Pass criteria:**
- Predictions received on >80% of days
- Mix of SELL and WAIT decisions (not all same)
- Expected returns vary based on predictions
- Negative correlation between net_benefit and SELL decision

**Expected outcome:**
- ✓ PASS if strategy receives and uses predictions
- ✗ FAIL if all decisions identical or no predictions received

**Time:** 3-4 minutes

---

### Phase 2: Fix Implementation

#### diagnostic_04_fixed_strategies.ipynb

**Purpose:** Implement corrected versions of strategies with fixes

**What it does:**
- Loads data with explicit date normalization:
  ```python
  prices['date'] = pd.to_datetime(prices['date'])
  prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}
  ```
- Defines `FixedExpectedValueStrategy` class with:
  - Proper None checking for predictions
  - Correct decision logic
  - Extensive logging
- Defines `FixedBacktestEngine` class with:
  - Date type verification
  - Prediction availability tracking
- Tests fixed strategy on coffee synthetic_acc90

**Pass criteria:**
- Date alignment >90%
- Prediction coverage >80%
- Beats baseline by >$30k
- Mix of SELL/WAIT decisions

**Expected outcome:**
- ✓ PASS if Expected Value beats baseline by >$30k
- ⚠️  PARTIAL if beats baseline but <$30k
- ✗ FAIL if still underperforms

**Time:** 4-5 minutes

---

### Phase 3: Validation

#### diagnostic_05_single_strategy_test.ipynb

**Purpose:** Test corrected Expected Value strategy in isolation

**What it does:**
- Runs fixed Expected Value strategy
- Runs baseline (Equal Batches) for comparison
- Side-by-side comparison of:
  - Net earnings
  - Trade counts
  - Average selling prices
- Decision pattern analysis
- Correlation analysis
- Trade timing analysis

**Pass criteria:**
- Net earnings > $750,000 (beats $727k baseline by $23k+)
- Decision log shows variation based on predictions
- Predictions used (>80% coverage)
- Negative correlation between net_benefit and SELL decision

**Expected outcome:**
- ✓ FULL PASS if all criteria met
- ✓ CRITICAL PASS if beats baseline and uses predictions
- ✗ FAIL if doesn't beat baseline

**Time:** 4-5 minutes

---

#### diagnostic_06_all_strategies_test.ipynb

**Purpose:** Test all 5 prediction strategies with fixes

**What it does:**
- Tests all prediction strategies:
  1. Expected Value
  2. Risk-Adjusted
  3. Consensus
  4. MA Predictive
  5. PT Predictive
- Plus baseline (Equal Batches) for comparison
- Generates results table with:
  - Net earnings
  - Advantage vs baseline
  - Prediction coverage
- Exports results to CSV

**Pass criteria:**
- At least 3 strategies beat baseline
- Expected Value in top 2
- All show positive advantage

**Expected results:**
1. Expected Value: ~$775k (+$48k, +6.6%)
2. Risk-Adjusted: ~$770k (+$43k, +5.9%)
3. Consensus: ~$765k (+$38k, +5.2%)
4. MA Predictive: ~$740k (+$13k, +1.8%)
5. PT Predictive: ~$730k (+$3k, +0.4%)

**Expected outcome:**
- ✓ FULL PASS if 5/5 strategies beat baseline
- ✓ CRITICAL PASS if 3/5 strategies beat baseline
- ✗ FAIL if <3 beat baseline

**Time:** 5-7 minutes

---

#### diagnostic_07_monotonicity_test.ipynb

**Purpose:** Verify performance improves monotonically with accuracy

**What it does:**
- Runs Expected Value strategy on all accuracy levels:
  - synthetic_acc60
  - synthetic_acc70
  - synthetic_acc80
  - synthetic_acc90
- Checks monotonic improvement
- Calculates incremental gains
- Creates visualization (optional)

**Pass criteria:**
- Monotonic increase (60% < 70% < 80% < 90%)
- 90% > 80% by >$10k
- All accuracies ≥70% show positive advantage

**Expected results:**
- 60%: ~$735k (+1.1%)
- 70%: ~$750k (+3.2%)
- 80%: ~$765k (+5.2%)
- 90%: ~$775k (+6.6%)

**Expected outcome:**
- ✓ FULL PASS if perfect monotonic improvement
- ✓ CRITICAL PASS if monotonic and 90% >$30k advantage
- ⚠️  PARTIAL if monotonic but weak advantage
- ✗ FAIL if not monotonic (bug still present)

**Time:** 6-8 minutes

---

## Interpreting Results

### Scenario A: All Diagnostics Pass ✓✓✓

**What it means:**
- Fixes work perfectly
- Predictions now drive strategy decisions
- Performance scales with accuracy

**Next steps:**
1. Review `diagnostic_04_fixed_strategies.ipynb` to understand the fixes
2. I'll create integration proposal documenting exact changes needed for production notebooks
3. Consider creating tuning notebooks (diagnostic_08-10) to optimize parameters

**Expected timeline:** Ready for production integration

---

### Scenario B: Diagnostics 01-03 Fail, But 04-07 Pass ⚠️

**What it means:**
- Original bug confirmed (date type mismatch or similar)
- Fixes in diagnostic_04 resolve the issue
- Fixed strategies work correctly

**Next steps:**
1. Apply fixes from diagnostic_04 to production notebooks (03, 04, 05)
2. Re-run notebooks 01-05
3. Verify production results match diagnostic results

**Expected timeline:** 1-2 hours to integrate fixes

---

### Scenario C: Some Validation Tests Fail (05-07) ✗

**What it means:**
- Fixes partially work but not fully effective
- May need parameter tuning
- Or additional bugs present

**Next steps:**
1. Review which validation tests failed
2. Analyze decision logs in diagnostic_03 and diagnostic_05
3. Iterate on fixes in diagnostic_04
4. Re-run validation tests

**Expected timeline:** 2-4 hours to iterate on fixes

---

### Scenario D: Monotonicity Test Fails (07) ✗

**What it means:**
- Critical failure - predictions not being used correctly
- Original bug not fully fixed

**Next steps:**
1. Re-run diagnostics 01-03 to re-diagnose
2. Review diagnostic_04 fixes
3. Check for additional date handling issues
4. May need to debug strategy implementation directly

**Expected timeline:** 3-6 hours to re-diagnose and fix

---

## Common Issues and Solutions

### Issue 1: Databricks import fails

**Error:** `Cannot import notebook`

**Solution:**
```bash
# Create directory first
databricks workspace mkdirs /Workspace/Users/your-email/trading_agent/commodity_prediction_analysis

# Then import
databricks workspace import diagnostic_01_prediction_loading.ipynb \
  /Workspace/Users/your-email/trading_agent/commodity_prediction_analysis/diagnostic_01_prediction_loading.ipynb \
  --language PYTHON --format JUPYTER
```

### Issue 2: Module not found error

**Error:** `ModuleNotFoundError: No module named 'X'`

**Solution:**
- Ensure you run `%run ./00_setup_and_config` at the top
- Attach to the same cluster as notebooks 00-10
- Check that notebooks 00-10 are in the same directory

### Issue 3: Prediction matrices file not found

**Error:** `FileNotFoundError: prediction_matrices.pkl`

**Solution:**
- Ensure notebook 01 (synthetic predictions) was run successfully
- Check DATA_PATHS in notebook 00 point to correct locations
- Verify model_version (e.g., 'synthetic_acc90') is correct

### Issue 4: Spark table not found

**Error:** `Table not found: commodity.trading_agent.coffee_prices_prepared`

**Solution:**
- Ensure notebook 02 (data preparation) was run
- Check that Databricks catalog is `commodity`
- Verify schema is `trading_agent`

---

## Output Files

After running all diagnostics, you'll have:

**CSV Results:**
- `/tmp/trading_results/diagnostic_06_all_strategies.csv` - All strategy results
- `/tmp/trading_results/diagnostic_07_monotonicity.csv` - Monotonicity test results

**Visualizations (optional):**
- `/tmp/trading_results/diagnostic_07_monotonicity.png` - Monotonicity chart

**Logs:**
- In-notebook output showing detailed diagnostics

---

## Next Steps After Diagnostics

### If Diagnostics Pass:

1. **Review fixes in diagnostic_04**
   - Understand the exact changes made
   - Verify they're appropriate for production

2. **Create integration proposal** (I'll do this)
   - Document exact code changes needed
   - Identify which notebooks to modify
   - Provide before/after comparisons

3. **Optional: Parameter tuning**
   - Create diagnostic_08 (parameter grid search)
   - Optimize strategy parameters
   - Validate on multiple accuracies

4. **Apply to production**
   - Update notebooks 03, 04, 05 with fixes
   - Re-run full workflow
   - Verify production results

### If Diagnostics Fail:

1. **Analyze failure points**
   - Which diagnostic failed?
   - What was the error?
   - Check decision logs

2. **Iterate on fixes**
   - Modify diagnostic_04
   - Re-run validation tests
   - Repeat until passing

3. **Re-diagnose if needed**
   - Run diagnostics 01-03 again
   - Look for additional bugs
   - Check other potential issues

---

## Estimated Total Time

- **Best case (all pass):** 25-35 minutes
- **Typical case (some iteration):** 1-2 hours
- **Worst case (major debugging):** 3-6 hours

---

## Success Criteria Summary

### Must Pass:
- [ ] diagnostic_01: >90% date overlap after normalization
- [ ] diagnostic_02: >80% prediction coverage in backtest
- [ ] diagnostic_03: Mix of SELL/WAIT decisions, negative correlation
- [ ] diagnostic_04: Beats baseline by >$30k
- [ ] diagnostic_05: Meets all validation criteria
- [ ] diagnostic_06: At least 3 strategies beat baseline
- [ ] diagnostic_07: Monotonic improvement with accuracy

### Should Pass:
- [ ] diagnostic_06: Expected Value in top 2 strategies
- [ ] diagnostic_07: 90% accuracy >$40k advantage
- [ ] All strategies show positive advantage

---

## Support

If you encounter issues:

1. **Check logs in notebook output** - Most diagnostic information is printed
2. **Review error messages** - Often indicate exact problem
3. **Consult this guide** - Common issues section
4. **Share results with me** - I can analyze and suggest next steps

---

## File Locations

**Local:**
- `/Users/markgibbons/capstone/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostic_*.ipynb`

**Databricks (after sync):**
- `/Workspace/Users/your-email/trading_agent/commodity_prediction_analysis/diagnostic_*.ipynb`

**Results:**
- `/tmp/trading_results/diagnostic_*.csv`

---

**Ready to start?** Run diagnostic_01 first and work through sequentially.

Good luck! 🚀
