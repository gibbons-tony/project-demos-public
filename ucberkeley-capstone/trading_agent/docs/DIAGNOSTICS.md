# Master Diagnostic Plan - Trading Strategy Testing

**Created:** 2025-11-24
**Status:** ACTIVE - Consolidated from multiple previous docs
**Purpose:** Single source of truth for all diagnostic testing workflows

---

## 🎯 Current State - What Actually Exists

### Active Diagnostic Files

| File | Purpose | Status | Dependencies |
|------|---------|--------|--------------|
| `diagnostic_16_optuna_with_params.ipynb` | Grid search optimization | ✓ Working | Requires `all_strategies_pct.py` |
| `diagnostic_17_paradox_analysis.ipynb` | Trade-by-trade analysis | ✓ Working | Requires `diagnostic_16_best_params.pkl` |
| `diagnostic_100_algorithm_validation.py` | 100% accuracy validation | ⚠️ New | Requires synthetic_acc100 predictions |

### Support Files

| File | Purpose | Used By |
|------|---------|---------|
| `all_strategies_pct.py` | All 10 strategy implementations | diagnostic_16, diagnostic_17, diagnostic_100 |
| `test_all_strategies.py` | Quick smoke tests | Manual testing |
| `cost_config_small_farmer.py` | Cost configurations | Strategies |
| `diagnostic_16_best_params.pkl` | **OUTPUT** from diagnostic_16 | **INPUT** to diagnostic_17 |

### Documentation

**This file** (`DIAGNOSTICS.md`) is the single source of truth for all diagnostic testing workflows.

Previously scattered across multiple files - now consolidated here.

---

## 🔄 The Diagnostic Workflow - How Everything Connects

### Phase 1: Generate Synthetic Predictions (Main Notebooks)

**Location:** Parent folder (`../01_synthetic_predictions_v8.ipynb`)

**What it does:**
- Generates predictions at multiple accuracy levels: 100%, 90%, 80%, 70%, 60%
- Saves prediction matrices to volume:
  - `prediction_matrices_coffee_synthetic_acc100_v8.pkl`
  - `prediction_matrices_coffee_synthetic_acc90_v8.pkl`
  - etc.
- Validates accuracy targeting (v8 fix)

**Output files:**
- Prediction matrix pickles (one per accuracy level)
- `validation_results_v8.pkl` (validation metrics)

**Dependencies:** None (runs first)

---

### Phase 2: Grid Search Optimization (Diagnostic 16)

**File:** `diagnostic_16_optuna_with_params.ipynb`

**What it does:**
1. Loads one accuracy level (default: synthetic_acc90)
2. Loads all 10 strategies from `all_strategies_pct.py`
3. Runs 200 trials of Optuna optimization for EACH strategy
4. Finds best parameters for each strategy
5. **SAVES OUTPUT:** `diagnostic_16_best_params.pkl`

**Key code:**
```python
# At end of notebook (cell 39):
best_params = {name: params for name, (params, value) in results.items()}

# Add cost parameters to predictive strategies
for strategy in ['price_threshold_predictive', 'moving_average_predictive',
                 'expected_value', 'consensus', 'risk_adjusted']:
    if strategy in best_params:
        best_params[strategy]['storage_cost_pct_per_day'] = COMMODITY_CONFIG['storage_cost_pct_per_day']
        best_params[strategy]['transaction_cost_pct'] = COMMODITY_CONFIG['transaction_cost_pct']

# Save to pickle file
output_path = 'diagnostic_16_best_params.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(best_params, f)

print(f'\n✓ Saved best parameters to {output_path}')
print(f'  Diagnostic 17 will automatically load these parameters')
```

**Output file:**
- `diagnostic_16_best_params.pkl` (dict of strategy_name → best_params)

**Dependencies:**
- Prediction matrices from v8
- `all_strategies_pct.py`
- Price data from main notebooks

**Runtime:** ~30-60 minutes (200 trials × 10 strategies)

---

### Phase 3: Paradox Analysis (Diagnostic 17)

**File:** `diagnostic_17_paradox_analysis.ipynb`

**What it does:**
1. **LOADS INPUT:** `diagnostic_16_best_params.pkl`
2. Uses optimized parameters to run matched pair comparisons:
   - Price Threshold (baseline) vs Price Threshold Predictive
   - Moving Average (baseline) vs Moving Average Predictive
3. Trade-by-trade comparison
4. Cost breakdown (revenue, transaction costs, storage costs)
5. Hypothesis testing to identify why predictions hurt performance

**Key code:**
```python
# Cell 8: Load parameters from diagnostic 16
params_file = 'diagnostic_16_best_params.pkl'

if os.path.exists(params_file):
    with open(params_file, 'rb') as f:
        best_params = pickle.load(f)
    print(f'✓ Loaded optimized parameters from {params_file}')
else:
    raise FileNotFoundError(
        f"\n\n{'='*80}\n"
        f"ERROR: {params_file} not found!\n\n"
        f"Please run diagnostic_16_optuna_complete.ipynb first to generate\n"
        f"the optimized parameters."
    )
```

**Analysis outputs:**
- Revenue differences
- Transaction cost differences
- Storage cost differences
- Trade timing comparison
- Inventory level comparison

**Dependencies:**
- `diagnostic_16_best_params.pkl` (CRITICAL - must run diagnostic 16 first!)
- Prediction matrices from v8
- `all_strategies_pct.py`
- Price data

**Runtime:** ~5-10 minutes (uses pre-optimized parameters)

---

### Phase 4: Algorithm Validation (Diagnostic 100)

**File:** `diagnostic_100_algorithm_validation.py`

**What it does:**
1. Loads synthetic_acc100 predictions (perfect foresight)
2. Runs all strategies with 100% accurate predictions
3. Compares best prediction strategy vs best baseline
4. **CRITICAL TEST:** With perfect predictions, strategies MUST beat baselines

**Key logic:**
```python
if improvement > 0 and improvement_pct > 10:
    print("✓✓✓ ALGORITHMS VALIDATED")
    print("Conclusion: Trading algorithms are fundamentally sound.")
else:
    print("❌❌❌ ALGORITHMS BROKEN")
    print("There is a fundamental bug in the algorithm logic.")
```

**Usage:**
```bash
cd diagnostics/
python diagnostic_100_algorithm_validation.py
```

**Dependencies:**
- `prediction_matrices_coffee_synthetic_acc100_v8.pkl`
- `all_strategies_pct.py`
- Price data

**Runtime:** ~3-5 minutes

---

## 📊 Complete Testing Strategy - All Accuracy Levels

### The Accuracy Spectrum

```
┌─────────────────────────────────────────────────────────────┐
│  100% → Proves algorithms work (MUST beat baseline)        │
│   90% → Validates prediction value (should beat baseline)   │
│   80% → Tests monotonicity                                  │
│   70% → Tests monotonicity                                  │
│   60% → Tests monotonicity                                  │
└─────────────────────────────────────────────────────────────┘
```

### Testing Workflow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Run diagnostic_100_algorithm_validation.py               │
│    └─ With 100% accuracy predictions                        │
│    └─ CRITICAL: If this fails, STOP - algorithms broken     │
└──────────────────────────────────────────────────────────────┘
                              ↓
                         PASS? (Yes)
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. Run diagnostic_16_optuna_with_params.ipynb               │
│    └─ With 90% accuracy predictions                         │
│    └─ Optimizes parameters for all 10 strategies            │
│    └─ SAVES: diagnostic_16_best_params.pkl                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
                     (Saves parameters)
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. Run diagnostic_17_paradox_analysis.ipynb                 │
│    └─ LOADS: diagnostic_16_best_params.pkl                  │
│    └─ With 90% accuracy predictions                         │
│    └─ Analyzes why predictions might hurt performance       │
│    └─ Trade-by-trade breakdown                              │
└──────────────────────────────────────────────────────────────┘
                              ↓
                    (Diagnose issues)
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. Test monotonicity (Main notebooks 05 & 11)               │
│    └─ Run with 60%, 70%, 80%, 90%, 100% accuracy           │
│    └─ Verify performance improves with accuracy             │
│    └─ Expected: 60% < 70% < 80% < 90% < 100%               │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔑 Critical File Dependencies

### The Chain of Dependencies

```
01_synthetic_predictions_v8.ipynb (Main folder)
   ↓ generates
prediction_matrices_*.pkl files
   ↓ used by
diagnostic_16_optuna_with_params.ipynb
   ↓ generates
diagnostic_16_best_params.pkl  ← KEY ARTIFACT
   ↓ used by
diagnostic_17_paradox_analysis.ipynb
   ↓ analyzes
Why predictions hurt/help performance
```

### File Dependency Matrix

| File | Reads | Writes | Critical? |
|------|-------|--------|-----------|
| `diagnostic_16` | prediction_matrices, prices | `diagnostic_16_best_params.pkl` | ✅ Creates key artifact |
| `diagnostic_17` | **`diagnostic_16_best_params.pkl`**, predictions, prices | None | ⚠️ Requires diagnostic 16 output |
| `diagnostic_100` | prediction_matrices (acc100), prices | None | ✅ Independent |

---

## 🚀 Quick Start Guide

### Step 1: Wait for v8 to Complete

```bash
# Check if v8 is done
databricks fs ls dbfs:/Volumes/commodity/trading_agent/files/ | grep validation_results_v8

# Download predictions (if running locally)
databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/prediction_matrices_coffee_synthetic_acc100_v8.pkl ./diagnostics/
databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/prediction_matrices_coffee_synthetic_acc90_v8.pkl ./diagnostics/
```

### Step 2: Test Algorithm Validity (100% Accuracy)

```bash
cd diagnostics/
python diagnostic_100_algorithm_validation.py
```

**Expected:** ✓ Predictions beat baseline by >10%

**If fails:** STOP - Fix algorithms before continuing

### Step 3: Optimize Parameters (90% Accuracy)

In Databricks, run `diagnostic_16_optuna_with_params.ipynb`

**Runtime:** 30-60 minutes

**Output:** `diagnostic_16_best_params.pkl`

**Verify output exists:**
```bash
ls -lh diagnostics/diagnostic_16_best_params.pkl
```

### Step 4: Analyze Paradox (90% Accuracy)

In Databricks, run `diagnostic_17_paradox_analysis.ipynb`

**Prerequisite:** Must have `diagnostic_16_best_params.pkl` from Step 3!

**Runtime:** 5-10 minutes

**Analyzes:**
- Why predictions might hurt performance
- Cost breakdowns
- Trade timing differences

### Step 5: Test Monotonicity (All Accuracies)

In Databricks, run main notebooks:
- `05_strategy_comparison.ipynb` - Auto-discovers all accuracy levels
- `11_synthetic_accuracy_comparison.ipynb` - Compares across accuracies

**Validates:** 60% < 70% < 80% < 90% < 100%

---

## 📋 Expected Results by Accuracy Level

| Accuracy | Expected Net Earnings | vs Baseline | Purpose |
|----------|----------------------|-------------|---------|
| 100% | >$800k | +10%+ | Algorithm validation (MUST pass) |
| 90% | $755k-$775k | +4% to +7% | Performance validation |
| 80% | $740k-$760k | +2% to +5% | Monotonicity check |
| 70% | $730k-$745k | +0% to +3% | Threshold identification |
| 60% | $720k-$735k | -1% to +1% | Below threshold |
| Baseline | $727k | 0% | Reference |

---

## 🔧 Troubleshooting

### Error: "diagnostic_16_best_params.pkl not found"

**Where:** diagnostic_17_paradox_analysis.ipynb

**Cause:** Trying to run diagnostic 17 before diagnostic 16

**Solution:**
1. Run `diagnostic_16_optuna_with_params.ipynb` first
2. Wait for it to complete (30-60 min)
3. Verify file exists: `ls diagnostics/diagnostic_16_best_params.pkl`
4. Then run diagnostic 17

### Error: "prediction_matrices_coffee_synthetic_acc100 not found"

**Where:** diagnostic_100_algorithm_validation.py

**Cause:** v8 predictions not generated yet

**Solution:**
1. Wait for `01_synthetic_predictions_v8.ipynb` to complete in Databricks
2. Download the file:
   ```bash
   databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/prediction_matrices_coffee_synthetic_acc100_v8.pkl ./diagnostics/
   ```
3. Or run diagnostic_100 in Databricks (where files already exist)

### Error: "ModuleNotFoundError: No module named 'all_strategies_pct'"

**Where:** Any diagnostic notebook

**Cause:** File not in same directory or path not set

**Solution:**
1. Verify `all_strategies_pct.py` exists in diagnostics folder
2. Check the import at top of notebook:
   ```python
   import importlib.util
   spec = importlib.util.spec_from_file_location('all_strategies_pct', 'all_strategies_pct.py')
   strat = importlib.util.module_from_spec(spec)
   spec.loader.exec_module(strat)
   ```

---

## 📝 Updating This Plan

### When to Update

1. **New diagnostic created** - Add to "Current State" section
2. **Dependencies change** - Update "Critical File Dependencies"
3. **Workflow changes** - Update "The Diagnostic Workflow"
4. **New accuracy levels added** - Update "Expected Results" table

### What NOT to Update

- Don't create new .md files - update this one
- Don't document obsolete workflows
- Don't keep outdated references

---

## 🗑️ Files to Consider Removing/Consolidating

These docs reference non-existent diagnostics or may be outdated:

- `SYNTHETIC_PREDICTION_TEST_PLAN.md` - References diagnostic_01-20 (don't exist)
- `DIAGNOSTIC_EXECUTION_GUIDE.md` - References diagnostic_01-07 (don't exist)
- `DEBUGGING_PLAN.md` - May be superseded
- `CONSOLIDATED_ANALYSIS.md` - May be outdated
- `BUG_FIX_SUMMARY.md` - May be historical only
- `COMPREHENSIVE_GRID_SEARCH_PLAN.md` - Superseded by diagnostic_16?
- `DATABRICKS_OUTPUT_ACCESS_GUIDE.md` - Utility, keep?
- `DATABRICKS_QUERY_GUIDE.md` - Utility, keep?
- `HOW_TO_GET_NOTEBOOK_RESULTS.md` - Utility, keep?
- `RESULTS_ACCESS_ANALYSIS.md` - May be outdated

**Recommendation:** Review each and either:
1. Delete if obsolete
2. Consolidate into this file
3. Keep if still useful (mark as "Reference")

---

## 🎯 Success Criteria

### Must Pass (Critical)

- [ ] **100% accuracy test (diagnostic_100):** Predictions beat baseline by >10%
  - If fails: Algorithms are broken, fix before continuing
  - If passes: Algorithms are sound

### Should Pass (Validation)

- [ ] **90% accuracy (diagnostic_16+17):** Predictions beat baseline by >$30k
- [ ] **Monotonicity (notebooks 05+11):** 60% < 70% < 80% < 90% < 100%
- [ ] **Parameter optimization (diagnostic_16):** All 10 strategies optimize successfully

### Nice to Have (Analysis)

- [ ] **Cost attribution (diagnostic_17):** Understand exactly why predictions help/hurt
- [ ] **Trade timing (diagnostic_17):** Identify optimal selling patterns
- [ ] **Threshold identification:** Find minimum accuracy for value-add

---

## 📚 Related Documentation

### Use These:
- `MASTER_DIAGNOSTIC_PLAN.md` ← **THIS FILE** - Complete workflow
- `ACCURACY_LEVEL_TESTING_GUIDE.md` - Details on 100% accuracy testing
- `all_strategies_pct.py` - Strategy implementations

### Reference (Historical):
- Other .md files in diagnostics/ - Review before using

### Main Project Docs:
- `../DATABRICKS_ACCESS_NOTES.md` - How to access Databricks files
- `../00_setup_and_config.ipynb` - Configuration and paths

---

**Last Updated:** 2025-11-24
**Owner:** Claude Code (Diagnostics)
**Status:** ACTIVE - Use this as single source of truth
