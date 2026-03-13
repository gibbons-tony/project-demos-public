# Trading Agent Refactoring Plan

**Goal:** Eliminate code duplication while preserving ALL functionality
**Approach:** Incremental, conservative, fully tested at each step
**Priority:** DO NOT LOSE anything, especially stats/charting for dashboard

---

## Current State Analysis

### Critical Components Inventory

#### ✅ EXTRACT to Modules (Reusable, No Notebook Dependencies)

**Strategies Module** (`strategies/`)
- [x] Strategy (ABC base class) - Line 1482
- [x] ImmediateSaleStrategy - Line 1539
- [x] EqualBatchStrategy - Line 1581
- [x] PriceThresholdStrategy - Line 1624
- [x] PriceThresholdPredictive - Line 1722
- [x] MovingAverageStrategy - Line 1911
- [x] MovingAveragePredictive - Line 2013
- [x] ConsensusStrategy - Line 2209
- [x] ExpectedValueStrategy - Line 2342
- [x] RiskAdjustedStrategy - Line 2474

**Backtest Module** (`backtest/`)
- [x] BacktestEngine class - Line 2720
- [x] calculate_metrics function - Line 3005

**Technical Indicators Module** (`indicators/`)
- [x] calculate_rsi - Line 1362
- [x] calculate_adx - Line 1382
- [x] calculate_std_dev_historical - Line 1423
- [x] calculate_prediction_confidence - Line 1435
- [x] calculate_rsi_predicted - Line 1452
- [x] calculate_adx_predicted - Line 1463

**Data Access Module** (already exists: `data_access/`)
- [x] generate_synthetic_predictions - Line 264
- [x] load_prediction_matrices - Line 345
- [x] Already have: load_forecast_distributions, load_actuals_from_distributions

**Config Module** (`config/`)
- [ ] Parameter management (NEW)
- [ ] Optimal parameter loading (NEW)
- [ ] Default parameter definitions (NEW)

#### ⚠️ KEEP in Notebook (Notebook-specific, Dashboard-critical)

**Statistical Analysis** (CRITICAL FOR DASHBOARD)
- bootstrap_metric - Line 5608
- Statistical test functions
- Confidence interval calculations
- P-value computations
- Significance testing

**Sensitivity Analysis** (CRITICAL FOR DASHBOARD)
- run_sensitivity_consensus - Line 4825
- run_cost_sensitivity - Line 4848
- Parameter sensitivity sweeps
- Cost sensitivity analysis

**Feature Analysis** (CRITICAL FOR DASHBOARD)
- extract_features - Line 4569
- Feature importance calculation
- Correlation analysis

**Harvest Mechanics** (Commodity-specific business logic)
- calculate_weeks_in_window - Line 173
- is_date_in_harvest_window - Line 186
- create_harvest_schedule - Line 211

**Orchestration** (Notebook flow control)
- Multi-model nested loops
- Result aggregation
- Progress tracking

**Visualization** (CRITICAL FOR DASHBOARD)
- All charting code
- Plot generation
- Display logic
- DataFrame displays

**Utility Functions** (Notebook helpers)
- get_data_paths - Line 124
- check_real_prediction_exists - Line 117
- Path manipulation

---

## Incremental Migration Plan

### Phase 1: Create Module Structure (No Breaking Changes)
**Goal:** Set up folders, keep notebook unchanged
**Risk:** None - just creating empty files

```
trading_agent/
├── strategies/
│   ├── __init__.py          (empty)
│   ├── base.py              (empty)
│   ├── baseline.py          (empty)
│   └── predictive.py        (empty)
├── backtest/
│   ├── __init__.py          (empty)
│   └── engine.py            (empty)
├── indicators/
│   ├── __init__.py          (empty)
│   └── technical.py         (empty)
└── config/
    ├── __init__.py          (empty)
    └── parameters.py        (empty)
```

**Validation:** Notebook still runs exactly as before

### Phase 2: Extract Strategies (First Module)
**Goal:** Move strategy classes to module, import in notebook
**Risk:** Low - strategies are self-contained

**Step 2a:** Copy strategies to `strategies/base.py`, `baseline.py`, `predictive.py`
- Keep original code in notebook (commented out)
- Verify strategies import correctly

**Step 2b:** Update notebook to import strategies
```python
# BEFORE (in notebook):
# class PriceThresholdStrategy(Strategy):
#     ...

# AFTER (in notebook):
from strategies import PriceThresholdStrategy
```

**Step 2c:** Run full backtest
- Verify results identical to before
- Check all 9 strategies work

**Validation:**
- Compare net_earnings for all strategies
- Must match previous run EXACTLY
- If mismatch → rollback, investigate

### Phase 3: Extract Indicators
**Goal:** Move technical indicators to module
**Risk:** Low - pure functions, no state

**Process:**
- Copy indicators to `indicators/technical.py`
- Import in notebook: `from indicators import calculate_rsi, calculate_adx, ...`
- Verify strategies still work (they use these indicators)

**Validation:**
- Run backtest, compare results
- Must match previous run EXACTLY

### Phase 4: Extract BacktestEngine
**Goal:** Move backtest engine to module
**Risk:** Medium - central to everything

**Process:**
- Copy BacktestEngine to `backtest/engine.py`
- Copy calculate_metrics to `backtest/engine.py`
- Import in notebook: `from backtest import BacktestEngine, calculate_metrics`
- Keep original in notebook (commented) as reference

**Validation:**
- Run full multi-model backtest
- Compare ALL metrics for ALL strategies
- Must match previous run EXACTLY
- Statistical tests must produce same results

### Phase 5: Create Config Module
**Goal:** Automatic parameter loading
**Risk:** Low - additive only

**Process:**
- Create `config/parameters.py` with get_strategy_parameters()
- Create `config/default_parameters.py` with hardcoded defaults
- Modify notebook to use auto-loading (optional at first)

**Validation:**
- With no optimal_parameters.json: uses defaults (same as before)
- With optimal_parameters.json: uses optimal values
- Either way, backtest runs successfully

### Phase 6: Update Grid Search
**Goal:** Use modules instead of duplicating code
**Risk:** Low - grid search is separate

**Process:**
- Modify grid search to import strategies, backtest from modules
- Remove duplicated code
- Verify grid search runs and produces optimal_parameters.json

**Validation:**
- Run grid search
- Check optimal_parameters.json is created
- Verify main notebook auto-loads it on next run

### Phase 7: Integration Testing
**Goal:** Full end-to-end validation
**Risk:** None if previous phases passed

**Process:**
1. Run grid search → produces optimal_parameters.json
2. Run main notebook → auto-loads optimal params
3. Verify ALL functionality:
   - All strategies run
   - Metrics calculated correctly
   - Statistical tests work
   - Charts display
   - Results match expectations

---

## Validation Checklist (After Each Phase)

### Functional Tests
- [ ] All 9 strategies execute without errors
- [ ] BacktestEngine runs complete simulation
- [ ] Metrics calculated: net_earnings, total_revenue, total_costs, n_trades, etc.
- [ ] Statistical tests execute: bootstrap CI, t-tests, p-values
- [ ] Sensitivity analysis runs: consensus, cost sensitivity
- [ ] Feature extraction works
- [ ] Charts display correctly

### Regression Tests (Critical!)
- [ ] **Net earnings match previous run** (for same model/commodity)
- [ ] **Transaction counts match** (verify strategy logic unchanged)
- [ ] **Statistical test results match** (verify calculations unchanged)
- [ ] **Bootstrap CIs match** (verify sampling unchanged)

### Performance Tests
- [ ] Runtime similar to before (no significant slowdown)
- [ ] Memory usage similar to before
- [ ] No new warnings or errors

---

## Rollback Plan (If Anything Goes Wrong)

Each phase has a rollback:

1. **Keep original notebook unchanged** during initial extraction
2. **Comment out old code** rather than deleting
3. **Git commit after each successful phase**
4. **If validation fails → revert to previous commit**

Example:
```python
# Phase 2 - Extract Strategies
# OLD (keep commented until validated):
# class PriceThresholdStrategy(Strategy):
#     def __init__(self, threshold_pct=0.05, ...):
#         ...

# NEW (test this first):
from strategies import PriceThresholdStrategy

# VALIDATION: If results don't match, uncomment old code, remove import, investigate
```

---

## What Gets Extracted vs. What Stays

### Module: `strategies/` (Extract)
```python
# strategies/base.py
class Strategy(ABC):
    """Base strategy class"""
    # All strategy base functionality

# strategies/baseline.py
class ImmediateSaleStrategy(Strategy): ...
class EqualBatchStrategy(Strategy): ...
class PriceThresholdStrategy(Strategy): ...
class MovingAverageStrategy(Strategy): ...

# strategies/predictive.py
class ConsensusStrategy(Strategy): ...
class ExpectedValueStrategy(Strategy): ...
class RiskAdjustedStrategy(Strategy): ...
class PriceThresholdPredictive(Strategy): ...
class MovingAveragePredictive(Strategy): ...

# strategies/__init__.py
from .baseline import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy
)
from .predictive import (
    ConsensusStrategy,
    ExpectedValueStrategy,
    RiskAdjustedStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive
)

__all__ = [
    'ImmediateSaleStrategy',
    'EqualBatchStrategy',
    # ... etc
]
```

### Module: `backtest/` (Extract)
```python
# backtest/engine.py
class BacktestEngine:
    """Backtest simulation engine"""
    # All backtest logic

def calculate_metrics(results):
    """Calculate performance metrics"""
    # All metric calculations

# backtest/__init__.py
from .engine import BacktestEngine, calculate_metrics
```

### Module: `indicators/` (Extract)
```python
# indicators/technical.py
def calculate_rsi(prices, period=14): ...
def calculate_adx(price_history, period=14): ...
def calculate_std_dev_historical(prices, period=14): ...
def calculate_prediction_confidence(predictions, horizon_day): ...
def calculate_rsi_predicted(predictions, period=14): ...
def calculate_adx_predicted(predictions): ...

# indicators/__init__.py
from .technical import (
    calculate_rsi,
    calculate_adx,
    calculate_std_dev_historical,
    calculate_prediction_confidence,
    calculate_rsi_predicted,
    calculate_adx_predicted
)
```

### Module: `config/` (Create New)
```python
# config/parameters.py
def get_strategy_parameters(commodity=None):
    """
    Load strategy parameters with auto-detection:
    1. Try commodity-specific optimal params
    2. Try generic optimal params
    3. Fallback to defaults
    """
    pass

def get_default_parameters():
    """Hardcoded default parameters"""
    pass

# config/__init__.py
from .parameters import get_strategy_parameters, get_default_parameters
```

### Notebook: Keep All Dashboard-Critical Code
```python
# KEEP IN NOTEBOOK (don't extract):

# Statistical Analysis
def bootstrap_metric(strategy_name, detailed_results, ...):
    """Bootstrap confidence intervals"""
    # Critical for dashboard statistical tests
    pass

# Sensitivity Analysis
def run_sensitivity_consensus(prices, prediction_matrices, ...):
    """Consensus parameter sensitivity"""
    # Critical for dashboard sensitivity charts
    pass

def run_cost_sensitivity(prices, prediction_matrices, ...):
    """Cost parameter sensitivity"""
    # Critical for dashboard cost analysis
    pass

# Feature Analysis
def extract_features(predictions, current_price, ...):
    """Extract features for ML"""
    # Critical for dashboard feature importance
    pass

# Harvest Mechanics
def calculate_weeks_in_window(start_month, end_month): ...
def is_date_in_harvest_window(date, harvest_windows): ...
def create_harvest_schedule(date_range, harvest_windows, ...): ...

# Visualization
# All plotting code
# All display() calls
# All chart generation

# Orchestration
# Multi-model loops
# Progress tracking
# Result aggregation
```

---

## Success Criteria

### Before Declaring Success
- [ ] All phases completed without rollback
- [ ] Regression tests pass (results match previous runs)
- [ ] Grid search works with extracted modules
- [ ] Main notebook auto-loads optimal parameters
- [ ] No code duplication between grid search and main notebook
- [ ] All statistical tests preserved and working
- [ ] All charting code preserved and working
- [ ] Documentation updated

### Final Validation Run
1. Run grid search (coffee, sarimax_auto_weather_v1)
2. Save baseline results (all metrics, all strategies)
3. Run main notebook with auto-loaded optimal params
4. Compare results to baseline from previous session
5. Verify statistical tests match
6. Verify charts display correctly

**Only if ALL tests pass → merge refactoring**

---

## Timeline Estimate

- Phase 1 (Structure): 15 minutes
- Phase 2 (Strategies): 1 hour + validation
- Phase 3 (Indicators): 30 minutes + validation
- Phase 4 (BacktestEngine): 1 hour + validation
- Phase 5 (Config): 45 minutes + validation
- Phase 6 (Grid Search): 30 minutes + validation
- Phase 7 (Integration): 1 hour testing

**Total: ~5-6 hours** (conservative, includes validation)

---

## Risk Mitigation

### High-Risk Components
1. **BacktestEngine** - Central to everything
   - Mitigation: Extract last, validate extensively
   - Keep original commented in notebook until 100% validated

2. **Strategy classes** - Complex business logic
   - Mitigation: Extract first (easier to validate)
   - Compare strategy outputs line-by-line if needed

3. **Statistical tests** - Don't break!
   - Mitigation: DON'T extract these, keep in notebook
   - Only strategies/backtest/indicators get extracted

### Low-Risk Components
1. **Indicators** - Pure functions
2. **Config module** - New code, additive only
3. **Grid search update** - Separate from main notebook

---

## Questions Before Starting

1. **Should we extract data_access functions too?**
   - generate_synthetic_predictions, load_prediction_matrices
   - Pro: Already reusable
   - Con: May touch existing data_access module

2. **Should we version the optimal_parameters.json?**
   - E.g., optimal_parameters_coffee.json, optimal_parameters_sugar.json
   - Pro: Commodity-specific optimization
   - Con: More complex loading logic

3. **Should we create a test suite?**
   - Unit tests for strategies
   - Integration tests for backtest
   - Regression tests comparing outputs
   - Pro: Catch breakage immediately
   - Con: More upfront work

---

## Decision Points

### Go/No-Go Decision After Each Phase

After each phase, evaluate:
- ✅ **GO:** Results match, tests pass → proceed to next phase
- ⛔ **NO-GO:** Results differ, tests fail → rollback, investigate, fix, retry

### Abort Criteria

Abort entire refactoring if:
- Any phase requires more than 2 rollbacks
- Results diverge and we can't identify why
- Breaking changes to dashboard-critical functionality
- Timeline exceeds 2x estimate (>10 hours)

If aborting:
- Revert all changes
- Keep current architecture
- Document lessons learned
- Consider alternative approaches

---

## Post-Refactoring Benefits

### Immediate Benefits
✅ Zero code duplication (strategies, backtest defined once)
✅ Automatic parameter loading (no manual copy-paste)
✅ Grid search runs faster (imports vs. duplication)
✅ Easier to maintain (change once, applies everywhere)
✅ Better testing (can unit test modules)

### Long-Term Benefits
✅ Reusable across future notebooks
✅ Can build CLI tools using modules
✅ Can build web API using modules
✅ Easier onboarding (modules have clear responsibilities)
✅ Foundation for dashboard (import modules, not notebooks)

### Dashboard Specifically
✅ Dashboard can import backtest, strategies directly
✅ No need to copy code or run notebooks to get functionality
✅ Statistical tests preserved in notebook (can be extracted to module later if needed)
✅ Clean separation: modules = logic, notebook = analysis/viz

---

## Next Steps

**Option A: Full Incremental Refactoring (Recommended)**
- Follow plan above
- Takes 5-6 hours
- Fully tested at each step
- Zero functionality loss guaranteed

**Option B: Proof of Concept First**
- Extract only strategies module
- Validate thoroughly
- If successful, continue with rest
- Lower initial commitment

**Option C: Defer Refactoring**
- Keep current architecture
- Accept code duplication
- Manual parameter updates
- Faster short-term, technical debt long-term

**Which option do you prefer?**
