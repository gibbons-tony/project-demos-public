# Trading Agent TODO

Last Updated: 2025-01-14 (Session 4 - Refactored Notebooks + Execution Issues)

## 📊 Progress Summary

**Overall Status: Phase 2 - 7/11 Notebooks Working, 3 Need Fixes**

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Data Source Migration | ✅ Complete | 100% |
| Phase 2: Multi-Model Framework | ⚠️ Partial (7/11 notebooks working) | 64% |
| Phase 3: Operations & Integration | ✅ Complete | 100% |
| Phase 3.5: Parameter Optimization | ✅ Complete | 100% |
| Phase 4: Interactive Dashboard | ⏸️ Pending | 0% |

**Major Accomplishments (Session 4):**
- ✅ Refactored monolithic notebook into 11 modular notebooks (00-10)
- ✅ Complete backtest pipeline working (225 strategy×model runs)
- ✅ Statistical validation working (bootstrap CIs, t-tests, p-values)
- ✅ Identified and documented execution issues (notebooks 07, 09, 10)
- ✅ Critical finding: Sparse forecasts mean predictions fall back to baselines
- ✅ Notebooks with outputs now synced to git via Databricks CLI

**What's Working:**
- ✅ Unity Catalog connection and data loading (25 model×commodity combinations)
- ✅ Modular notebook architecture (notebooks 00-06 working perfectly)
- ✅ Backtest engine (225 strategy×model runs complete)
- ✅ Statistical validation (bootstrap CIs, t-tests, p-values)
- ✅ Synthetic prediction generation for accuracy threshold analysis
- ✅ Daily operational recommendations with JSON export
- ✅ Multi-currency pricing in 15+ currencies
- ✅ Complete WhatsApp integration workflow documented
- ✅ Grid search framework for parameter optimization

**What's Broken:**
- ❌ Notebook 07: Feature importance (date range mismatch - 0/25 models successful)
- ❌ Notebook 08: Sensitivity analysis (output truncated - unknown if completed)
- ❌ Notebook 09: Results summary (missing input files from notebook 07)
- ❌ Notebook 10: Paired scenario analysis (wrong file paths)

**What's Missing:**
- ❌ Interactive dashboard
- ❌ Grid search execution (framework complete, runs after execution fixes)

**Next Actions (In Order):**
1. Fix execution issues in notebooks 07, 09, 10 (~2 hours)
2. Run grid search in separate file (optimize baseline params)
3. Wait for continuous forecast data from forecast team
4. Dashboard development

---

## ✅ Completed

### Phase 1: Data Source Migration ✅
- [x] Created data access layer (`trading_agent/data_access/`)
  - [x] `forecast_loader.py` with 8 functions for Unity Catalog queries
  - [x] `get_available_models(commodity, connection)` - returns list of model versions
  - [x] `load_forecast_distributions(commodity, model_version, connection)` - loads data
  - [x] `transform_to_prediction_matrices()` - converts to backtest format
  - [x] Verified 100% format compatibility with existing backtest engine
  - [x] Testing: 244,120 rows loaded in 4.2 seconds

- [x] Modified `trading_prediction_analysis.py` to use Unity Catalog
  - [x] Updated `load_prediction_matrices()` function (lines 264-355)
  - [x] Added `model_version` and `connection` parameters
  - [x] Maintains backward compatibility with local files
  - [x] Returns source string: `'UNITY_CATALOG:<model>'`

### Phase 2: Multi-Model Analysis Loop ✅
- [x] Created model runner framework (`trading_agent/analysis/`)
  - [x] `model_runner.py` with nested loop orchestration
  - [x] `run_analysis_for_model()` - single commodity/model combination
  - [x] `run_analysis_for_all_models()` - all models for one commodity
  - [x] `run_analysis_for_all_commodities()` - complete nested loop
  - [x] `compare_model_performance()` - cross-model comparison

- [x] Implemented NESTED loop structure (commodity → model)
  - [x] Queries available models from Unity Catalog
  - [x] Coffee: 10 models, Sugar: 5 models = **15 total runs**
  - [x] Result storage: `results[commodity][model_version]`

- [x] Created orchestration script
  - [x] `run_multi_model_analysis.py` - end-to-end workflow
  - [x] Configurable commodity parameters
  - [x] Model comparison summaries
  - [x] JSON output per model

- [x] End-to-end testing verified
  - [x] Unity Catalog connection working
  - [x] 15 models discovered and queryable
  - [x] Data format 100% compatible
  - [x] Single model test: 4.2s execution, 41 dates, 12K paths

### Phase 2 Status Tracking
- [x] Created `PHASE_2_STATUS.md` with detailed progress
- [x] Updated `.gitignore` for test scripts
- [x] Git commit pushed (7c26665)

### Phase 3: Operational Tools & Integration ✅ (Session 3)

**Daily Recommendations Tool:**
- [x] Created `trading_agent/operations/daily_recommendations.py`
  - [x] Queries latest predictions from Unity Catalog
  - [x] Runs all 9 trading strategies (4 baseline + 5 prediction-based)
  - [x] Generates actionable recommendations (SELL/HOLD with quantities)
  - [x] Command-line interface: `--commodity`, `--model`, `--all-models`
  - [x] Performance: Real-time recommendations from live forecasts

**WhatsApp/Messaging Integration:**
- [x] Added `--output-json` option for structured data export
- [x] Implemented `analyze_forecast()` function
  - [x] Extracts 14-day price range (10th-90th percentile)
  - [x] Identifies best 3-day sale window (highest median prices)
  - [x] Daily forecast breakdown (median, p25, p75)
- [x] Implemented `calculate_financial_impact()` function
  - [x] Compares sell-now vs wait scenarios
  - [x] Calculates potential gain/loss in USD and local currencies
- [x] Returns tuple: `(recommendations_df, structured_data)`
- [x] JSON output includes all data for WhatsApp message template

**Multi-Currency Support:**
- [x] Added `get_exchange_rates()` function
  - [x] Queries `commodity.bronze.fx_rates` table
  - [x] Fetches ALL available currency pairs automatically
  - [x] Supports 15+ currencies (COP, VND, BRL, INR, THB, IDR, ETB, HNL, UGX, MXN, EUR, GBP, JPY, etc.)
- [x] Automatic local currency price calculation
  - [x] Current price in all available currencies
  - [x] Financial impact in all currencies
  - [x] Exchange rates included in output
- [x] Updated `get_current_state()` to include exchange rates

**Comprehensive Documentation:**
- [x] Created `trading_agent/operations/README.md` (437 lines)
  - [x] Quick start guide
  - [x] Command-line options
  - [x] JSON output format specification
  - [x] Complete WhatsApp integration guide (7-step workflow)
  - [x] Code examples for messaging service implementation
  - [x] Data mapping reference table
  - [x] Currency support documentation
  - [x] Troubleshooting guide

**Data Loading Simplification:**
- [x] Added `load_actuals_from_distributions()` function
  - [x] Loads actuals from `commodity.forecast.distributions` (is_actuals=TRUE)
  - [x] Reshapes 14-day format into date/price rows
  - [x] Removes duplicates, sorts by date
  - [x] Returns standard DataFrame format
- [x] Updated multi-model notebook to use distributions table
  - [x] Removed CSV loading for prices
  - [x] Single source of truth: Unity Catalog
  - [x] Fallback to `commodity.bronze.market_data` if needed
- [x] Exported `load_actuals_from_distributions` in data_access module

**Data Source Verification:**
- [x] Verified ALL data sources in Databricks
  - [x] Actuals: `commodity.forecast.distributions` (is_actuals=TRUE)
  - [x] Predictions: `commodity.forecast.distributions` (is_actuals=FALSE)
  - [x] Exchange rates: `commodity.bronze.fx_rates`
  - [x] Price fallback: `commodity.bronze.market_data`
- [x] Zero CSV file dependencies
- [x] Complete Unity Catalog integration

**Git Commits (Session 3):**
- [x] c954e5b - WhatsApp/messaging integration
- [x] bd81eaf - Exchange rate and local currency support
- [x] dff4bcd - Fetch all currency pairs automatically
- [x] 7ffa7e3 - Comprehensive WhatsApp integration guide
- [x] 0051176 - Load actuals from distributions table

### Phase 3.5: Parameter Optimization (Grid Search) ✅ (Session 3 - End)

**Grid Search Framework:**
- [x] Created `parameter_grid_search.py` - Standalone Python script
- [x] Created `commodity_prediction_analysis/parameter_grid_search_notebook.py` - Databricks notebook
- [x] Created `parameter_config.py` - Utilities for loading and applying optimal parameters
- [x] Created `optimal_parameters_template.json` - Template showing expected structure
- [x] Created `optional_load_optimal_parameters_cell.py` - Integration code for main notebook

**Parameter Grid Definitions:**
- [x] Defined parameter ranges for all 9 strategies:
  - [x] ImmediateSale: min_batch_size, sale_frequency_days (16 combos)
  - [x] EqualBatch: batch_size, frequency_days (25 combos)
  - [x] PriceThreshold: threshold_pct, batch_fraction, max_days_without_sale (80 combos)
  - [x] MovingAverage: ma_period, batch_fraction, max_days_without_sale (80 combos)
  - [x] Consensus: consensus_threshold, min_return, evaluation_day (60 combos)
  - [x] ExpectedValue: min_ev_improvement, baseline_batch, baseline_frequency (100 combos)
  - [x] RiskAdjusted: min_return, max_uncertainty, consensus_threshold, evaluation_day (192 combos)
- [x] Total: 553 parameter combinations to test (coarse grid)
- [x] Fine-grained grids defined for 2-stage optimization

**Grid Search Features:**
- [x] Maximizes net revenue as objective function
- [x] Ensures matched pairs share baseline parameters:
  - [x] PriceThresholdStrategy ↔ PriceThresholdPredictive
  - [x] MovingAverageStrategy ↔ MovingAveragePredictive
- [x] Two-stage optimization (coarse → fine-grained)
- [x] Optional sampling for large grids
- [x] Comprehensive results output (JSON + CSV)
- [x] Visualization of parameter impact on net revenue

**Documentation:**
- [x] Created `docs/PARAMETER_GRID_SEARCH_GUIDE.md` (comprehensive 450+ line guide)
  - [x] Quick start guide
  - [x] Parameter grid definitions and ranges
  - [x] Matched pair constraint explanation
  - [x] Two-stage optimization workflow
  - [x] Results interpretation guide
  - [x] Validation workflow
  - [x] Advanced usage examples
  - [x] Troubleshooting section
  - [x] Best practices
- [x] Updated `docs/README.md` to include grid search guide

**Output Format:**
- [x] `optimal_parameters.json` - Best parameters for each strategy
- [x] `grid_search_results_all.csv` - All tested combinations
- [x] Parameter update instructions printed to console
- [x] Visualization charts for parameter sensitivity

**Integration:**
- [x] Optional loading of optimal parameters in main notebook
- [x] Automatic verification of commodity match
- [x] Fallback to default parameters if file not found

**Status:** ✅ **Framework Complete**
- Grid search framework fully implemented and documented
- Ready to run optimization to find actual optimal parameter values
- All utilities and documentation in place

**Next Steps:**
1. Run `parameter_grid_search_notebook.py` in Databricks
2. Review optimal parameters
3. Validate performance vs baseline
4. Update main notebook with optimal values
5. Re-run multi-model analysis
6. Deploy to production

## 🔄 In Progress

None - All Phase 3.5 components complete!

## 📋 Pending (Lower Priority)

### Phase 4: Interactive Dashboard Development (3-Tab Structure)

**Dashboard Structure:**
- Tab 1: Coffee (model leaderboard + detailed analysis)
- Tab 2: Sugar (model leaderboard + detailed analysis)
- Tab 3: Coffee vs Sugar (cross-commodity comparison)

**Coffee/Sugar Tab Components:**
- [ ] Top: Model comparison leaderboard (all models ranked)
- [ ] Middle: Model selector dropdown
- [ ] Bottom: Detailed analysis with 4 sub-tabs:
  - [ ] Sub-Tab 1: Performance (cumulative returns, timeline, earnings)
  - [ ] Sub-Tab 2: Statistical Analysis (bootstrap CI, t-tests, p-values) ⭐
  - [ ] Sub-Tab 3: Sensitivity Analysis (parameter/cost sensitivity)
  - [ ] Sub-Tab 4: Feature Analysis (importance, correlations)

**Coffee vs Sugar Tab:**
- [ ] Dual model selectors (one per commodity)
- [ ] Side-by-side metrics comparison
- [ ] Cross-commodity charts

**Statistical Analysis Components (ALL PRESERVED):**
- [ ] Bootstrap confidence intervals (1000 iterations)
- [ ] T-tests and p-values
- [ ] Significance stars (*, **, ***)
- [ ] Feature importance (Random Forest)
- [ ] Feature correlation heatmap
- [ ] Parameter sensitivity heatmaps
- [ ] Cost sensitivity analysis

---

#### Dashboard Implementation Plan (Mapped to Notebook)

**Current State:** Notebook generates all required charts across 13 cells. Charts are in Cells 7, 9, 10, 11, 12.

**📄 Detailed Analysis:** See [`../trading_agent/DASHBOARD_DATA_ANALYSIS.md`](../trading_agent/DASHBOARD_DATA_ANALYSIS.md)
- Complete chart inventory (20+ visualizations)
- Current data storage structure in notebook
- Comprehensive data structure design
- Data extraction strategy

**Chart → Dashboard Mapping:**

**Sub-Tab 1: Performance**
- Source: Cell 7 (Charts 1, 2, 3, 4, 5) + Cell 11 (Plot 1)
- Charts: Net Earnings bar chart, Cumulative Net Revenue (main), Trading Timeline, Total Revenue, Inventory Drawdown, Portfolio Value
- Data needed: `results_df`, `daily_state`, `trades`, `portfolio_values`

**Sub-Tab 2: Statistical Analysis**
- Source: Cell 8 (data) + Cell 11 (Plots 2, 4)
- Charts: Net Earnings with significance stars, Bootstrap CIs
- Data needed: `pairwise_comparisons`, `bootstrap_confidence_intervals`, `p_values`, `cohens_d`

**Sub-Tab 3: Sensitivity Analysis**
- Source: Cell 10 (full figure) + Cell 11 (Plots 5, 6, 7, 8)
- Charts: Consensus parameter heatmap, Transaction/Storage cost sensitivity, Prediction advantage, Parameter grid
- Data needed: `transaction_costs`, `storage_costs`, `parameter_sensitivity`, `consensus_grid`

**Sub-Tab 4: Feature Analysis**
- Source: Cell 9 (full figure) + Cell 11 (Plot 3)
- Charts: Feature importance, Feature correlation heatmap
- Data needed: `feature_importance`, `feature_correlations`

**Tab 3: Cross-Commodity**
- Source: Cell 7 (Chart 6) + Cell 12 (2 figures)
- Charts: Best strategy by commodity, Prediction advantage by commodity, Scenario analysis
- Data needed: `all_commodity_results`, cross-commodity comparison data

**Implementation Steps:**

**Step 1: Data Export (Notebook Cell 13)** ⭐ PRIORITY
- [ ] Create export function in notebook
- [ ] Extract all data that powers the 11 charts
- [ ] Structure: `{commodity}/{model_version}/data.json`
- [ ] Include: metrics, time_series, trades, statistical_tests, sensitivity, features
- [ ] Size: ~300KB per model × 15 models = ~4.5MB total
- [ ] Location: `/dbfs/FileStore/trading_agent/dashboard_data/`

**Step 2: Dashboard Framework Selection**
- [ ] Choose: Streamlit (simpler) vs Dash (more customizable)
- [ ] Recommendation: Streamlit for faster MVP
- [ ] Deploy: Databricks hosted app

**Step 3: Dashboard Development**
- [ ] Build 3-tab layout (Coffee, Sugar, Cross-Commodity)
- [ ] Add model selector dropdown per tab
- [ ] Create 4 sub-tabs per commodity tab
- [ ] Implement lazy loading (load data only when tab selected)
- [ ] Recreate all charts using Plotly (interactive) or Matplotlib

**Step 4: Testing & Validation**
- [ ] Verify all 20+ charts render correctly
- [ ] Validate data accuracy vs notebook outputs
- [ ] Test model switching (should update all charts)
- [ ] Test cross-commodity comparisons

**Step 5: Deployment**
- [ ] Deploy to Databricks as shared app
- [ ] Document access instructions
- [ ] Add refresh mechanism (re-run notebook → dashboard auto-updates)

**Data Structure Template:**
```json
{
  "metadata": {"commodity": "coffee", "model_version": "sarimax_auto_weather_v1"},
  "strategies": {
    "Consensus": {
      "metrics": {"net_earnings": float, "total_revenue": float, ...},
      "time_series": {"dates": [...], "cumulative_net_revenue": [...], ...},
      "trades": [{"date": str, "price": float, "amount": float}, ...]
    }
  },
  "statistical_tests": {"pairwise_comparisons": [...], "bootstrap_cis": [...]},
  "sensitivity_analysis": {"transaction_costs": {...}, "storage_costs": {...}},
  "feature_analysis": {"importances": [...], "correlations": [...]}
}
```

**Next Action:** Implement Step 1 (Data Export) in notebook

## 🚫 Blocked

### Forecast Data Coverage Issue (2025-01-11)

**Discovery:** `commodity.forecast.distributions` contains 44 scattered forecast dates, not continuous coverage.

**Current dates:** 2018-07-06 through 2025-11-01, but NOT consecutive
- Expected: 14-day step size → continuous coverage of ~588 days
- Actual: Random/sampled dates with large gaps between them
- Example: 2018-07-06, 2018-08-03, 2018-08-17, 2018-09-14, etc.

**Impact on Trading Backtest:**
- Each forecast covers 14 days → up to 616 dates with predictions
- But variable horizon coverage per date (some have 14 days ahead, others only 1-6 days)
- Current BacktestEngine expects key = forecast_start_date, only works on 44 days
- Need to adapt to variable forecast horizons per date

**Question for Forecast Team:**
- Was this intentional (model evaluation sampling)?
- Or should there be continuous 14-day-step forecasts?
- Can we generate continuous forecasts for a specific period (e.g., 2019-2020)?

**Potential Adaptations (if sparse data is final):**
1. **Option A:** Reshape data to be keyed by actual date (not forecast_start_date)
2. **Option B:** Modify strategies to handle variable forecast horizons (3-14 days)
3. **Option C:** Use synthetic predictions to fill gaps (Cell 2 in notebook)

**Status:** BLOCKED - Awaiting response from forecast team (Connor Watson)

**Related Files:**
- Analysis: `trading_agent/DASHBOARD_DATA_ANALYSIS.md` (Section 4.2)
- Notebook: Cell 7 queries commodity.forecast.distributions

## 🔧 Execution Issues (Notebooks 06-10)

**Discovered:** 2025-01-14 (after refactored notebook execution in Databricks)
**Status:** Multiple notebooks have execution failures blocking downstream analysis

### Issue Summary

| Notebook | Status | Issue | Priority |
|----------|--------|-------|----------|
| 06_statistical_validation | ✅ Working | None | - |
| 07_feature_importance | ❌ Failing | Date range mismatch - 0/25 models | HIGH |
| 08_sensitivity_analysis | ⚠️ Unknown | Output truncated | LOW |
| 09_strategy_results_summary | ❌ Failing | Missing input files | HIGH |
| 10_paired_scenario_analysis | ❌ Failing | Wrong file paths | MEDIUM |

### ❌ Issue 1: Notebook 07 - Feature Importance (CRITICAL)

**Problem:** All 42 prediction dates fall outside price data range → 0 features extracted

**Root Cause:**
```
Price data:       2022-01-03 to 2025-10-31 (965 days)
Prediction data:  2018-07-06 to 2025-11-01 (42 dates)
Overlap:          ZERO dates
```

**Why:** Feature extraction requires both current price and future price (14 days ahead). No predictions have matching price data.

**Fix:** Extend price data loading back to 2018 (not just 2022)
- Update notebook 01 or 02 to load from `commodity.bronze.market` starting 2018-01-01
- This gives full coverage of all 42 prediction dates

**Impact:** Blocking notebook 09 (missing `feature_analysis.pkl` files)

### ❌ Issue 2: Notebook 09 - Results Summary

**Problem:** Cannot load required input files from notebooks 06-08

**Missing Files:**
- ❌ `feature_analysis.pkl` (from notebook 07 - FAILED)
- ⚠️ `sensitivity_results.pkl` (from notebook 08 - unknown if exists)
- ✅ `statistical_results.pkl` (from notebook 06 - exists)

**Fix:**
1. Fix notebook 07 (see Issue 1)
2. Add graceful error handling for missing files:
```python
try:
    with open(MODEL_DATA_PATHS['feature_analysis'], 'rb') as f:
        feature_results = pickle.load(f)
except FileNotFoundError:
    feature_results = {'feature_importance': pd.DataFrame()}  # Empty placeholder
```

### ❌ Issue 3: Notebook 10 - Paired Scenario Analysis

**Problem:** Using wrong file path (old location)

**Current (WRONG):**
```python
BASE_PATH = '/Volumes/commodity/silver/trading_agent_volume'
```

**Correct:**
```python
BASE_PATH = '/Volumes/commodity/trading_agent/files'
```

**Additional Issue:** File naming mismatch
- Expects: `results_coffee.csv`
- Actual: Results stored in Delta tables `commodity.trading_agent.results_coffee_<model>`

**Fix:** Update paths and use Delta tables instead of CSV files

### ⚠️ Issue 4: Notebook 08 - Sensitivity Analysis

**Problem:** Output truncated due to size limit

**Status:** Unknown if notebook actually completed successfully
- Files may have been saved even though output was truncated
- Need to verify `sensitivity_results.pkl` files exist in `/Volumes/commodity/trading_agent/files/`

**Fix:** Reduce print verbosity or verify files exist

### Priority Fix Order

1. **HIGH:** Fix notebook 07 date range (extend price data to 2018) - 30 min
2. **HIGH:** Make notebook 09 handle missing files gracefully - 30 min
3. **MEDIUM:** Fix notebook 10 file paths - 45 min
4. **LOW:** Verify notebook 08 output files exist - 15 min

**Total Estimated Effort:** ~2 hours

### Next Steps After Execution Fixes

5. **Run Grid Search (Separate File)** - Create new standalone notebook/file for parameter optimization
   - Will run infrequently (not part of regular analysis pipeline)
   - Optimizes baseline strategy parameters (now that we know baselines win)
   - Will be valuable when continuous forecasts become available
   - Framework already complete from Phase 3.5
   - Estimated: 1-2 hours runtime for full grid search

## Notes

### Data Architecture
- **Forecast data:** `commodity.forecast.distributions` (actuals + predictions)
- **Price data:** `commodity.bronze.market_data`
- **Exchange rates:** `commodity.bronze.fx_rates`
- **Zero CSV dependencies** - All data in Unity Catalog

### Operational Tools
- **Daily recommendations:** `trading_agent/operations/daily_recommendations.py`
  - Command: `python operations/daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1 --output-json recs.json`
  - Generates real-time trading recommendations for all 9 strategies
  - JSON output ready for WhatsApp/messaging integration

### Multi-Currency Support
- Supports 15+ currencies automatically from Databricks
- Includes: COP, VND, BRL, INR, THB, IDR, ETB, HNL, UGX, MXN, EUR, GBP, JPY, CNY, AUD, CHF, KRW, ZAR
- All financial metrics available in USD + local currencies

### Documentation
- Forecast API Guide: `trading_agent/FORECAST_API_GUIDE.md`
- Operations Guide: `trading_agent/operations/README.md` (437 lines)
- WhatsApp Integration: Complete 7-step workflow with code examples

### Model Coverage
- **Coffee:** 10 real models + 6 synthetic = 16 total
- **Sugar:** 5 real models + 6 synthetic = 11 total
- **Synthetic models:** Test accuracy thresholds (50%, 60%, 70%, 80%, 90%, 100%)

### Ready for Production
✅ Real-time daily recommendations
✅ Multi-model backtesting framework
✅ Synthetic accuracy analysis
✅ Multi-currency support
✅ WhatsApp/messaging integration ready
✅ Complete Databricks integration

**Next Step:** Dashboard development or production deployment
