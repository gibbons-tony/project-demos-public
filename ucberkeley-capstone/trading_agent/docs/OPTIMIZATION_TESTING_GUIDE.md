# Databricks Testing Guide - Trading Agent Optimization

**Last Updated:** 2025-11-25
**Status:** Active Development - Critical bugs being fixed

## Table of Contents
1. [Current Status](#current-status)
2. [Critical Findings](#critical-findings)
3. [Test Infrastructure](#test-infrastructure)
4. [Common Issues](#common-issues)
5. [Next Steps](#next-steps)

---

## Current Status

### Tests in Progress (2025-11-25)

1. **LP Optimizer Test** (`test_lp_only.py`)
   - **Purpose:** Validate theoretical maximum calculator using Linear Programming
   - **Status:** Fixed locally, pending push and retest
   - **Last Run:** Run 1305076827182926 - FAILED (wrong table names)

2. **Optuna Optimization Test** (`test_optimizer.py`)
   - **Purpose:** Full parameter optimization with all 10 strategies including RollingHorizonMPC
   - **Status:** Blocked by coverage validation bug
   - **Last Run:** Run 969743629182902 - FAILED (nonsensical coverage filter)

### Critical Discovery: 314.8% Efficiency Bug

**Problem:** Theoretical maximum calculator was producing impossible efficiency scores (>100%)

**Root Cause:**
- Old `PerfectForesightStrategy` used **model predictions** instead of **actual prices**
- With 90% accuracy predictions, theoretical max was artificially low
- Real strategy profits exceeded this "theoretical" maximum

**Solution Implemented:**
- Replaced with LP-based optimizer using **actual prices** (perfect foresight)
- Implements deterministic oracle/clairvoyant algorithm from academic research
- Provides true theoretical upper bound for efficiency calculation

**Files Created:**
- `production/strategies/lp_optimizer.py` - LP solver implementation
- `production/test_lp_only.py` - Standalone LP test

---

## Critical Findings

### 1. Coverage Validation Bug (FIXED 2025-11-25)

**Location:** `analysis/optimization/run_parameter_optimization.py:136-158`

**Problem (BEFORE - commit b7c9ef0):**
```python
# WRONG: Checked against ALL price dates
coverage_pct = len(common_dates) / len(all_price_dates) * 100
if coverage_pct < 50:
    raise ValueError(f"Insufficient overlap: only {coverage_pct:.1f}% coverage...")
```

**Issue:**
- Checked percentage of ALL price data (2015-2025: 2726 days)
- Predictions only go back to 2022 (951 days)
- Result: 951 perfect overlapping dates rejected as "34.9% coverage"

**Calculation Example:**
```
Price data:    2015-2025 (2726 days)
Predictions:   2022-2025 (951 days)
Overlap:       951 days (100% of prediction period!)
Coverage:      951/2726 = 34.9% ❌ WRONGLY REJECTED
```

**Solution Implemented (commit b7c9ef0):**
```python
# CORRECT: Check against PREDICTION dates
pred_coverage_pct = len(common_dates) / len(all_pred_dates) * 100

# Apply forecast loader standard: 730 day minimum
if len(common_dates) < 730:
    raise ValueError(f"Insufficient data: only {len(common_dates)} overlapping days (need 730+)")

# Apply forecast loader standard: 90%+ coverage of PREDICTION period
if pred_coverage_pct < 90:
    raise ValueError(f"Sparse predictions: only {pred_coverage_pct:.1f}% coverage of prediction period (need 90%+)")
```

**Status:** ✅ FIXED - Commit b7c9ef0 (2025-11-25, by Tony)

**Validation:** Now correctly checks coverage against prediction period (90%+ coverage + 730 day minimum)

### 2. RollingHorizonMPC Strategy Added

**Implementation:**
- 14-day limited foresight optimization from academic research
- Receding horizon control (execute only first decision, re-optimize daily)
- Shadow-priced terminal value to prevent end-of-horizon myopia
- Configurable terminal value decay and shadow price smoothing

**Files Created:**
- `production/strategies/rolling_horizon_mpc.py` - Strategy implementation

**Optuna Integration:**
- Added to `analysis/optimization/search_space.py` with hyperparameters:
  - `horizon_days`: 7-21 days
  - `terminal_value_decay`: 0.85-0.99
  - `shadow_price_smoothing`: None or 0.1-0.5 (categorical choice)
- Added to `analysis/optimization/run_parameter_optimization.py` strategy list
- Updated `analysis/optimization/optimizer.py` cost parameter handling

**Result:** Now have 10 tunable strategies (4 baseline + 5 prediction + 1 advanced optimization)

### 3. Strategy Runner Parameter Flow (FIXED 2025-11-25)

**Problem:** Production `strategy_runner.py` was NOT using Optuna-optimized parameters
- Cherry-picked only 1-2 parameters per strategy
- Hardcoded values like `batch_fraction=0.25`
- Missing parameters fell back to `__init__` defaults (unoptimized)

**Root Cause:**
```python
# BEFORE (BROKEN):
PriceThresholdStrategy(
    threshold_pct=self.baseline_params['price_threshold']['threshold_pct']  # Only 1 of 10 params!
)
PriceThresholdPredictive(
    threshold_pct=...,
    batch_fraction=0.25,  # HARDCODED! Not from Optuna!
    max_days_without_sale=60
)
```

**Solution Implemented:**
- Complete rewrite of `initialize_strategies()` method
- Uses `**params` dict unpacking to pass ALL parameters
- Helper function `add_costs()` injects commodity-level cost parameters
- All 102 Optuna-optimized strategy decision parameters now flow through

```python
# AFTER (FIXED):
PriceThresholdStrategy(**self.baseline_params.get('price_threshold', {}))  # All 10 params!
PriceThresholdPredictive(**add_costs(self.prediction_params.get('price_threshold_predictive', {})))  # All 18 params!
```

**Files Changed:**
- `production/runners/strategy_runner.py` - Fixed parameter unpacking
- `production/config.py` - Added rolling_horizon_mpc defaults
- `production/runners/__init__.py` - Updated documentation

**Status:** ✅ COMPLETED - Commit f1d0739 pushed 2025-11-25

### 4. LP and Optuna Separation

**Previous (Wrong):** Combined theoretical max calculation with Optuna optimization

**Current (Correct):**
- **Standalone LP Test** (`test_lp_only.py`): Calculate theoretical maximum only
- **Optuna Test** (`test_optimizer.py`): Optimize strategy parameters, compare to theoretical max

**Why Separate:**
- Theoretical max is constant for given commodity/config
- Optuna optimizes 10 strategies independently
- Clean separation of concerns

---

## Test Infrastructure

### Submitting Jobs

**Pattern:**
```bash
cat > /tmp/job_name.json << 'EOF'
{
  "run_name": "descriptive_name",
  "tasks": [{
    "task_key": "task_name",
    "spark_python_task": {
      "python_file": "file:///Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/path/to/script.py"
    },
    "existing_cluster_id": "1111-041828-yeu2ff2q",
    "timeout_seconds": 1800
  }]
}
EOF

databricks jobs submit --json @/tmp/job_name.json
```

**Output:**
```json
{
  "run_id": 1234567890123456
}
```

### Monitoring Jobs

**Check Status:**
```bash
databricks jobs get-run --run-id <run_id>
```

**Get Output:**
```bash
databricks jobs get-run-output --run-id <run_id>
```

**Key Fields:**
- `state.life_cycle_state`: PENDING, RUNNING, TERMINATED
- `state.result_state`: SUCCESS, FAILED, TIMED_OUT
- `state.state_message`: Error details if failed
- `tasks[0].run_page_url`: Link to Databricks UI

### Current Test Jobs

#### LP Optimizer Test
```bash
cat > /tmp/job_test_lp_v4.json << 'EOF'
{
  "run_name": "test_lp_v4_fixed",
  "tasks": [{
    "task_key": "test_lp",
    "spark_python_task": {
      "python_file": "file:///Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/test_lp_only.py"
    },
    "existing_cluster_id": "1111-041828-yeu2ff2q",
    "timeout_seconds": 900
  }]
}
EOF

databricks jobs submit --json @/tmp/job_test_lp_v4.json
```

#### Optuna Optimization Test
```bash
cat > /tmp/job_test_optuna_v5.json << 'EOF'
{
  "run_name": "test_optuna_v5_with_mpc_fixed",
  "tasks": [{
    "task_key": "test_optimizer",
    "spark_python_task": {
      "python_file": "file:///Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/test_optimizer.py"
    },
    "existing_cluster_id": "1111-041828-yeu2ff2q",
    "timeout_seconds": 1800
  }]
}
EOF

databricks jobs submit --json @/tmp/job_test_optuna_v5.json
```

---

## Common Issues

### Issue 1: Table Not Found

**Error:**
```
[TABLE_OR_VIEW_NOT_FOUND] The table or view commodity.forecast.distributions_coffee cannot be found
```

**Cause:** Wrong table name - predictions are in `commodity.trading_agent.predictions_{commodity}`

**Fix:**
```python
# Wrong
pred_table = f"commodity.forecast.distributions_{commodity}"

# Correct
pred_table = f"commodity.trading_agent.predictions_{commodity}"
```

**Fixed in:** `test_lp_only.py:47`

### Issue 2: Missing 'price' Column

**Error:**
```
KeyError: "['price'] not in index"
```

**Cause:** Market data uses 'close' column, not 'price'

**Fix:**
```python
# Load market data
market_df = spark.table("commodity.bronze.market").toPandas()
market_df['price'] = market_df['close']  # Create 'price' alias
prices = market_df[market_df['commodity'] == commodity][['date', 'price']]
```

**Fixed in:** `test_lp_only.py:41`

### Issue 3: Wrong Timestamp Column

**Error:** (Anticipated based on schema)

**Cause:** Predictions use 'timestamp' column, not 'forecast_date'

**Fix:**
```python
# Wrong
pred_dates = set(pred_df['forecast_date'])

# Correct
pred_dates = set(pd.to_datetime(pred_df['timestamp']).dt.normalize())
```

**Fixed in:** `test_lp_only.py:52`

### Issue 4: Coverage Validation Too Strict (FIXED)

**Error (BEFORE commit b7c9ef0):**
```
ValueError: Insufficient overlap: only 34.9% coverage (951/2726 days)
```

**Cause:** Was checking against ALL price history, not prediction period

**Fix:** See [Coverage Validation Bug](#1-coverage-validation-bug-fixed-2025-11-25) above

**Status:** ✅ FIXED in commit b7c9ef0 (2025-11-25)

---

## Next Steps

### Immediate (Before Next Test Run)

1. ✅ **COMPLETED (2025-11-25):** Fixed strategy_runner parameter flow
   - All 102 Optuna parameters now flow through correctly
   - See "Strategy Runner Parameter Flow" section above

2. ✅ **COMPLETED (2025-11-25):** Fixed coverage validation bug
   - Commit b7c9ef0 by Tony
   - Now correctly checks coverage against prediction period (not all price history)
   - See "Coverage Validation Bug" section above

3. **Push test_lp_only.py fixes**
   - Table name: `commodity.trading_agent.predictions_coffee`
   - Price column: `market_df['price'] = market_df['close']`
   - Timestamp column: `pd.to_datetime(pred_df['timestamp']).dt.normalize()`

4. **Commit changes with detailed message**
   ```
   Fix theoretical max calculator and add RollingHorizonMPC

   - Replace PerfectForesightStrategy with LP optimizer using actual prices
   - Add RollingHorizonMPC (14-day limited foresight) to Optuna
   - Fix coverage validation to use forecast loader standard
   - Fix test_lp_only.py table/column names
   - Separate LP and Optuna testing

   Addresses 314.8% efficiency bug (theoretical max was using predictions not prices)
   ```

4. **Rerun tests on Databricks**
   - Submit test_lp_v4 (standalone LP)
   - Submit test_optuna_v5 (with RollingHorizonMPC and fixed coverage)

### Validation (After Tests Pass)

1. **Verify theoretical max sanity**
   - Efficiency scores should be ≤ 100%
   - LP optimizer should show higher profit than any strategy
   - Total sold should equal total harvested (mass balance)

2. **Review RollingHorizonMPC results**
   - Compare to other prediction-based strategies
   - Check if shadow pricing improves over simple terminal value
   - Analyze horizon length sensitivity (7 vs 14 vs 21 days)

3. **Document optimal parameters**
   - Update MASTER_SYSTEM_PLAN.md with best parameters per strategy
   - Create performance comparison table
   - Note which strategies benefit most from optimization

### Future Work

1. **Extend to other commodities**
   - Test on cotton, wheat, sugar
   - Verify coverage standards apply across commodities
   - Compare optimal parameters across commodities

2. **Production deployment**
   - Package optimizer as reusable module
   - Add configuration for harvest schedules, costs
   - Create wrapper script for batch optimization

3. **Advanced optimization**
   - Multi-commodity portfolio optimization
   - Risk-adjusted objectives (not just profit)
   - Stochastic programming with distribution forecasts

---

## References

### Academic Research
- [research/Limited_Foresight_Inventory_Optimization.md](research/Limited_Foresight_Inventory_Optimization.md) - Shadow pricing and terminal values
- [research/Perfect_Foresight_Benchmarks.md](research/Perfect_Foresight_Benchmarks.md) - Oracle algorithms and efficiency metrics

### Related Documentation
- `MASTER_SYSTEM_PLAN.md` - Project status and task tracking
- `FILE_INVENTORY.md` - Notebook and script descriptions

### Key Files
- `production/strategies/lp_optimizer.py` - Theoretical maximum calculator
- `production/strategies/rolling_horizon_mpc.py` - Limited foresight strategy
- `production/test_lp_only.py` - Standalone LP test
- `production/test_optimizer.py` - Full Optuna optimization
- `analysis/optimization/run_parameter_optimization.py` - Main optimizer orchestrator
- `analysis/optimization/search_space.py` - Hyperparameter definitions
- `analysis/optimization/optimizer.py` - Optuna trial executor

---

**Maintainer:** Claude Code (AI Assistant)
**Project:** UC Berkeley Capstone - Trading Agent Analysis
**Last Test Run:** 2025-11-25 (test_lp_v3, test_optuna_v4)
