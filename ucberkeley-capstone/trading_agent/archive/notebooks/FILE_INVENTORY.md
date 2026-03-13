# Technical Reference - Commodity Prediction Analysis

**Created:** 2025-11-24
**Purpose:** Complete technical inventory of notebooks, scripts, and outputs
**Status:** Living reference document

> **For automation patterns:** See [../../docs/AUTOMATION_GUIDE.md](../../docs/AUTOMATION_GUIDE.md)
>
> **For system priorities:** See [../MASTER_SYSTEM_PLAN.md](../MASTER_SYSTEM_PLAN.md)
>
> **For algorithm issues:** See [../../docs/ALGORITHM_ISSUES.md](../../docs/ALGORITHM_ISSUES.md)

---

## 📁 Directory Structure

```
commodity_prediction_analysis/
├── Setup & Configuration
│   └── 00_setup_and_config.ipynb
│
├── Prediction Generation
│   ├── 01_synthetic_predictions.ipynb
│   ├── 01_synthetic_predictions_calibrated.ipynb
│   ├── 01_synthetic_predictions_v6.ipynb
│   ├── 01_synthetic_predictions_v7.ipynb
│   └── 01_synthetic_predictions_v8.ipynb (CURRENT)
│   └── 02_forecast_predictions.ipynb
│
├── Core Trading System
│   ├── 03_strategy_implementations.ipynb
│   └── 04_backtesting_engine.ipynb
│
├── Analysis & Results
│   ├── 05_strategy_comparison.ipynb
│   ├── 06_statistical_validation.ipynb
│   ├── 07_feature_importance.ipynb
│   ├── 08_sensitivity_analysis.ipynb
│   ├── 09_strategy_results_summary.ipynb
│   └── 10_paired_scenario_analysis.ipynb
│
├── Utilities
│   ├── analyze_validation.py
│   └── diagnostic_forecast_coverage.ipynb
│
├── Documentation
│   ├── DATABRICKS_ACCESS_NOTES.md
│   ├── EXECUTIVE_SUMMARY.md
│   ├── RESULTS_ANALYSIS_CRITICAL_FINDINGS.md
│   └── WORKFLOW_ANALYSIS_AND_FINDINGS.md
│
├── analysis/ ⭐ NEW
│   ├── run_strategy_analysis.py (Efficiency analysis orchestrator)
│   ├── theoretical_max/ (DP-based upper bound calculation)
│   ├── efficiency/ (Efficiency ratio analysis)
│   └── optimization/ (Optuna parameter optimization)
│       ├── run_parameter_optimization.py
│       ├── optimizer.py
│       └── search_space.py
│
├── production/
│   ├── config.py (Production configuration)
│   ├── core/ (Backtest engine & tests)
│   ├── strategies/ (All 9 trading strategies)
│   ├── runners/ (Modular execution)
│   ├── scripts/ (Production workflow scripts)
│   └── test_*.py (Databricks test scripts)
│
└── diagnostics/
    └── [See diagnostics/MASTER_DIAGNOSTIC_PLAN.md]
```

---

## 📊 Notebook Inventory with Outputs

### 00_setup_and_config.ipynb

**Purpose:** Central configuration for all notebooks

**What it defines:**
- Commodity configurations (coffee, sugar)
- Harvest schedules and windows
- Cost parameters (storage: 0.025%/day, transaction: 0.25%)
- Strategy parameters (baselines and prediction-based)
- Data paths (Delta tables and Volume files)
- Analysis configuration

**Functions provided:**
- `get_data_paths(commodity, model_version)` - Generate all file/table paths
- `get_model_versions(commodity)` - List available models
- `load_forecast_data()` - Load predictions from Unity Catalog
- `load_actual_prices()` - Load actuals
- `get_harvest_schedule()` - Calculate harvest timing

**Key Constants:**
```python
FORECAST_TABLE = "commodity.forecast.distributions"
OUTPUT_SCHEMA = "commodity.trading_agent"
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"
```

**Data Saved:** None (pure configuration)

**Charts Produced:** None

---

### 01_synthetic_predictions_v8.ipynb ⭐ CURRENT

**Purpose:** Generate synthetic predictions at multiple accuracy levels with correct MAPE targeting

**Versions:**
- v8 (CURRENT): Fixed log-normal centering for accurate MAPE
- v7: Saves to volume for download
- v6: Fixed day alignment (100% = 0% MAPE)
- Earlier: calibrated, original

**What it does:**
1. Loads price data from `commodity.bronze.market`
2. Generates predictions for accuracy levels: 100%, 90%, 80%, 70%, 60%
3. For each accuracy level, creates 2000 runs × 14 horizons
4. Validates predictions against actuals
5. Calculates MAPE, MAE, CRPS, directional accuracy, coverage

**Key Function:**
```python
generate_calibrated_predictions(
    prices_df,
    model_version,  # e.g. "synthetic_acc90"
    target_accuracy=0.90,  # 90% accurate = 10% MAPE
    n_runs=2000,
    n_horizons=14
)
```

**v8 Fix Details:**
- Centers log-normal at `±target_mape` (not 0)
- Keeps run_biases for realistic correlation
- Stores actual `future_date` to avoid calendar misalignment

**Data Saved (Delta Tables):**
- `commodity.trading_agent.predictions_coffee`
- `commodity.trading_agent.predictions_sugar`

**Data Saved (Volume Files):**
- `validation_results_v8.pkl` - Validation metrics for all accuracy levels
- Prediction matrices saved by subsequent notebooks

**Charts Produced:** None (validation only)

**Runtime:** ~10-20 minutes per commodity

---

### 02_forecast_predictions.ipynb

**Purpose:** Load real forecast predictions from forecast_agent

**What it does:**
1. Queries `commodity.forecast.distributions` table
2. Filters for real predictions (is_actuals = false)
3. Processes forecasts into prediction matrices format
4. Saves matrices for use by backtesting

**Data Saved (Volume Files):**
- `prediction_matrices_{commodity}_{model_version}_real.pkl`
  - e.g. `prediction_matrices_coffee_xgboost_weather_v1_real.pkl`

**Charts Produced:** None

---

### 03_strategy_implementations.ipynb

**Purpose:** Defines all 9 trading strategies

**Strategies Implemented:**

**Baselines (4):**
1. **ImmediateSaleStrategy** - Sells weekly in batches
2. **EqualBatchStrategy** - Fixed 25% batches every 30 days
3. **PriceThresholdStrategy** - Sells when price > threshold (5%)
4. **MovingAverageStrategy** - Sells when price > 30-day MA

**Prediction-Based (5):**
5. **ConsensusStrategy** - Sells when 70%+ runs predict profit
6. **ExpectedValueStrategy** - Sells when EV improvement < $50
7. **RiskAdjustedStrategy** - Risk-based batch sizing (8%-40%)
8. **PriceThresholdPredictive** - PT baseline + predictions
9. **MovingAveragePredictive** - MA baseline + predictions

**Key Methods:**
- `decide(day, inventory, current_price, price_history, predictions)` - Make trading decision
- `reset()` - Reset strategy state
- `set_harvest_start(day)` - Set harvest window

**Data Saved:** None (pure implementation)

**Charts Produced:** None

---

### 04_backtesting_engine.ipynb

**Purpose:** Backtest engine that runs strategies

**What it does:**
1. Simulates trading over historical period
2. Tracks inventory, revenue, costs daily
3. Applies harvest schedule
4. Enforces max holding period (365 days)
5. Handles forced liquidation

**Key Class:**
```python
class BacktestEngine:
    def __init__(self, prices, prediction_matrices, commodity_config):
        # Initialize with data and configuration

    def run(self, strategy):
        # Run backtest and return results:
        # - trades: list of all trades
        # - daily_state: day-by-day inventory/costs
        # - metrics: summary statistics
```

**Metrics Calculated:**
- Net earnings (revenue - transaction costs - storage costs)
- Total revenue (without costs)
- Total costs breakdown
- Average sale price
- Number of trades
- Final inventory
- Cumulative P&L over time

**Data Saved:** None (used by downstream notebooks)

**Charts Produced:** None

---

### 05_strategy_comparison.ipynb ⭐ MAIN WORKFLOW

**Purpose:** Run all strategies on all commodities and model versions

**What it does:**
1. Auto-discovers all model versions (synthetic + real)
2. Loads prices and prediction matrices
3. Runs all 9 strategies for each commodity-model combination
4. Compares baseline vs prediction performance
5. Analyzes Risk-Adjusted strategy scenarios
6. Generates comprehensive visualizations

**Loop Structure:**
```python
for commodity in ['coffee', 'sugar']:
    for model_version in auto_discovered_models:
        for strategy in all_9_strategies:
            results = engine.run(strategy)
            # Save and visualize
```

**Data Saved (Delta Tables):**
- `commodity.trading_agent.results_{commodity}_{model}`
  - Contains metrics for all 9 strategies
  - Columns: strategy, net_earnings, total_revenue, total_costs, avg_sale_price, n_trades, type (Baseline/Prediction)

**Data Saved (Volume Files):**
- `results_detailed_{commodity}_{model}.pkl` - Full backtest results
  - Contains: trades list, daily_state DataFrame, all metrics
- `detailed_strategy_results.csv` - All strategies, all commodities, all models
- `cross_model_commodity_summary.csv` - Best strategies only

**Charts Produced (PNG files in Volume):**

1. **Net Earnings Bar Chart**
   - `net_earnings_{commodity}_{model}.png`
   - Horizontal bars for all 9 strategies
   - Baselines in blue, predictions in red
   - Shows dollar values

2. **Trading Timeline**
   - `trading_timeline_{commodity}_{model}.png`
   - Price history with trade markers
   - Marker size = trade amount
   - Color-coded by strategy
   - Shows timing differences between strategies

3. **Total Revenue (Without Costs)**
   - `total_revenue_no_costs_{commodity}_{model}.png`
   - Cumulative revenue over time (no costs deducted)
   - Shows gross selling performance
   - Prediction strategies as solid lines, baselines as dashed

4. **Cumulative Net Revenue**
   - `cumulative_returns_{commodity}_{model}.png`
   - Net earnings over time (with all costs)
   - Shows true profitability path
   - Identifies when strategies separate

5. **Inventory Drawdown**
   - `inventory_drawdown_{commodity}_{model}.png`
   - Inventory levels over time
   - Shows liquidation pace
   - Helps diagnose storage cost issues

6. **Cross-Model/Commodity Advantage**
   - `cross_model_commodity_advantage.png`
   - Bar chart comparing prediction advantage across models
   - Grouped by commodity
   - Shows which models benefit most from predictions

7. **Cross-Model/Commodity Earnings**
   - `cross_model_commodity_earnings.png`
   - Grouped bars for baseline vs prediction earnings
   - All commodities and models

**Console Output:**
- Risk-Adjusted scenario distribution (how many trades in each risk bracket)
- Forced liquidation analysis
- Best baseline, best prediction, overall best strategy
- Prediction advantage ($) and (%)

**Runtime:** ~30-60 minutes for all commodities and models

---

### 06_statistical_validation.ipynb

**Purpose:** Statistical significance testing of strategy performance

**What it does:**
1. Bootstrap resampling (1000 iterations)
2. Paired t-tests (prediction vs baseline)
3. Confidence intervals (95%)
4. Effect size calculations
5. Win/loss analysis

**Statistical Tests:**
- **Paired t-test**: Tests if prediction strategies significantly beat baselines
- **Bootstrap confidence intervals**: Quantifies uncertainty in performance difference
- **Effect size (Cohen's d)**: Measures practical significance
- **Win rate**: % of days prediction outperforms baseline

**Data Saved (Volume Files):**
- `statistical_results_{commodity}_{model}.pkl`
  - Contains: bootstrap samples, p-values, confidence intervals, effect sizes
- `statistical_comparisons_{commodity}_{model}.csv`
  - Summary table of all statistical tests
- `bootstrap_summary_{commodity}_{model}.csv`
  - Bootstrap distribution statistics

**Charts Produced:**

1. **Bootstrap Distribution**
   - Histogram of earnings differences
   - Shows 95% confidence interval
   - Indicates if zero is excluded (significance)

2. **Confidence Intervals Plot**
   - Forest plot style
   - Shows CI for each strategy pair
   - Highlights significant differences

3. **Effect Size Visualization**
   - Bar chart of Cohen's d
   - Shows practical significance
   - Categorized as small/medium/large

**Runtime:** ~5-10 minutes per commodity-model

---

### 07_feature_importance.ipynb

**Purpose:** Analyze which prediction features drive strategy decisions

**What it does:**
1. Extracts features from prediction matrices:
   - Mean predicted price
   - Standard deviation (uncertainty)
   - Upside potential (95th percentile)
   - Downside risk (5th percentile)
   - Prediction spread
2. Correlates features with strategy decisions (SELL vs WAIT)
3. Identifies which features matter most for each strategy

**Analysis Methods:**
- **Correlation analysis**: Which features correlate with sell decisions?
- **Feature distribution**: How do features differ between SELL and WAIT decisions?
- **Strategy-specific importance**: What drives each prediction strategy?

**Data Saved (Volume Files):**
- `feature_analysis_{commodity}_{model}.pkl`
  - Contains: feature matrices, correlations, importance scores

**Charts Produced:**

1. **Feature Correlation Heatmap**
   - Correlations between features and decisions
   - Separate for each strategy

2. **Feature Importance Bar Chart**
   - Ranked by correlation with decisions
   - Shows which features drive trading

3. **Feature Distribution Boxplots**
   - SELL vs WAIT distributions
   - Shows how features differ by decision

**Runtime:** ~5-10 minutes per commodity-model

---

### 08_sensitivity_analysis.ipynb

**Purpose:** Test how robust strategies are to parameter changes

**What it does:**
1. Varies key parameters:
   - Storage costs (±50%)
   - Transaction costs (±50%)
   - Strategy-specific thresholds
2. Runs backtests with each parameter variation
3. Measures impact on net earnings
4. Identifies parameter sensitivities

**Parameters Tested:**
- **Storage cost**: 0.0125% to 0.0375% per day (baseline: 0.025%)
- **Transaction cost**: 0.125% to 0.375% (baseline: 0.25%)
- **Strategy thresholds**: ±30% of baseline values

**Data Saved (Volume Files):**
- `sensitivity_results_{commodity}_{model}.pkl`
  - Contains: parameter sweep results, sensitivity metrics

**Charts Produced:**

1. **Parameter Sensitivity Plot**
   - Line chart showing earnings vs parameter value
   - Separate line for each strategy
   - Shows if strategies are robust or fragile

2. **Sensitivity Heatmap**
   - 2D heatmap: storage cost × transaction cost
   - Color = net earnings
   - Shows interaction effects

3. **Tornado Diagram**
   - Shows which parameters have biggest impact
   - Ranked by earnings variance

**Runtime:** ~15-30 minutes per commodity-model (many parameter combinations)

---

### 09_strategy_results_summary.ipynb

**Purpose:** Generate executive summary of all results

**What it does:**
1. Aggregates results across all commodities and models
2. Ranks strategies by performance
3. Identifies best strategies overall
4. Summarizes key findings
5. Generates presentation-ready tables

**Data Saved (Volume Files):**
- `summary_stats_{commodity}_{model}.csv`
  - High-level summary metrics
- `final_summary_{commodity}_{model}.csv`
  - Complete aggregated results

**Charts Produced:**

1. **Strategy Ranking Table**
   - Net earnings for all strategies
   - Sorted by performance
   - Colored by type (baseline/prediction)

2. **Performance Summary Dashboard**
   - Multi-panel figure
   - Earnings, costs, trade counts
   - Comparative view

3. **Key Findings Infographic**
   - Highlights top performers
   - Shows prediction advantage
   - Executive-friendly format

**Runtime:** ~5 minutes (reads existing results)

---

### 10_paired_scenario_analysis.ipynb

**Purpose:** Deep dive into baseline vs predictive strategy pairs

**What it does:**
1. Compares matched pairs:
   - Price Threshold vs Price Threshold Predictive
   - Moving Average vs Moving Average Predictive
2. Trade-by-trade comparison
3. Decision point analysis
4. Cost attribution

**Analysis:**
- **When do predictions help?** (market conditions, timing)
- **When do predictions hurt?** (overfitting, overtrading)
- **Why do strategies differ?** (decision logic, thresholds)

**Data Saved:** None (analysis only)

**Charts Produced:**

1. **Paired Decision Comparison**
   - Shows where baseline and predictive make different decisions
   - Highlights key divergence points

2. **Trade Timing Comparison**
   - When does each strategy trade?
   - How do timings differ?

3. **Cost Attribution Analysis**
   - Breaks down performance difference
   - Revenue vs transaction costs vs storage costs

**Runtime:** ~10-15 minutes per commodity-model

---

## 🗂️ Utility Files

### analyze_validation.py

**Purpose:** Analyze validation_results_v*.pkl files

**What it does:**
- Loads validation pickle
- Extracts MAPE, MAE, coverage metrics
- Checks if 100% accuracy shows 0% MAPE (bug verification)
- Prints summary table

**Usage:**
```bash
python analyze_validation.py
```

**Output:** Console summary only

---

### diagnostic_forecast_coverage.ipynb

**Purpose:** Check forecast data coverage and quality

**What it does:**
- Queries `commodity.forecast.distributions`
- Checks date ranges
- Identifies gaps
- Validates forecast structure

**Output:** Console diagnostics only

---

### trading_prediction_analysis_original_11_11_25.ipynb

**Purpose:** Original monolithic notebook (historical)

**What it is:**
- 4.4MB notebook from November 11, 2025
- Contains full analysis workflow in single file
- Predates the split into notebooks 00-10
- Kept for historical reference

**Status:** ARCHIVED - Use numbered notebooks (00-10) instead

**Why it exists:**
- Original implementation before workflow was modularized
- Useful for understanding evolution of approach
- May contain experimental code or earlier strategy versions

**Should you use it?** NO - Use the numbered notebooks (00-10) which are:
- Better organized
- More maintainable
- Properly documented
- Actively maintained

**Output:** Unknown (historical - not part of current workflow)

---

## 📄 Documentation Files

### DATABRICKS_ACCESS_NOTES.md ⭐

**Purpose:** How to access Databricks and avoid common mistakes

**Key Topics:**
- How notebooks run (IN Databricks, not locally)
- Volume vs local directory (ephemeral risk)
- Using databricks CLI to download files
- Pandas version compatibility

### EXECUTIVE_SUMMARY.md

**Purpose:** High-level summary of findings (historical)

**Status:** May be outdated - created early in project

### RESULTS_ANALYSIS_CRITICAL_FINDINGS.md

**Purpose:** Key findings from analysis (historical)

**Status:** May be outdated - created during initial analysis

### WORKFLOW_ANALYSIS_AND_FINDINGS.md

**Purpose:** Workflow documentation and findings (historical)

**Status:** May be outdated - created during workflow development

---

## 📊 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 00_setup_and_config                                             │
│   └─► Defines: paths, configs, parameters                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 01_synthetic_predictions_v8 or 02_forecast_predictions          │
│   └─► Generates: prediction matrices (.pkl)                    │
│   └─► Saves: validation results (.pkl)                         │
│   └─► Delta: commodity.trading_agent.predictions_{commodity}   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 03_strategy_implementations                                     │
│   └─► Defines: 9 strategy classes                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 04_backtesting_engine                                           │
│   └─► Defines: BacktestEngine class                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 05_strategy_comparison ⭐ MAIN                                  │
│   └─► Runs: All strategies on all commodities/models           │
│   └─► Saves: results_detailed_{commodity}_{model}.pkl          │
│   └─► Saves: 7 PNG charts per commodity-model                  │
│   └─► Saves: 2 cross-comparison PNGs                           │
│   └─► Delta: commodity.trading_agent.results_{commodity}_{model}│
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 06_statistical_validation                                       │
│   └─► Saves: statistical_results_{commodity}_{model}.pkl       │
│   └─► Saves: 3 statistical PNGs                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 07_feature_importance                                           │
│   └─► Saves: feature_analysis_{commodity}_{model}.pkl          │
│   └─► Saves: 3 feature analysis PNGs                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 08_sensitivity_analysis                                         │
│   └─► Saves: sensitivity_results_{commodity}_{model}.pkl       │
│   └─► Saves: 3 sensitivity PNGs                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 09_strategy_results_summary                                     │
│   └─► Saves: summary_stats_{commodity}_{model}.csv             │
│   └─► Saves: 3 summary PNGs                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 10_paired_scenario_analysis                                     │
│   └─► Saves: 3 comparison PNGs                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Complete Output Inventory

### Delta Tables (Unity Catalog)

**Location:** `commodity.trading_agent.*`

| Table Name | Created By | Contains |
|------------|------------|----------|
| `predictions_{commodity}` | 01_synthetic | All prediction runs (timestamp, run_id, day_ahead, predicted_price) |
| `results_{commodity}_{model}` | 05_comparison | Strategy metrics (strategy, net_earnings, revenue, costs, trades) |

**Grain:**
- predictions: (timestamp, run_id, day_ahead, future_date)
- results: (strategy, commodity, model_version)

---

### Volume Files (Binary/Pickle)

**Location:** `/Volumes/commodity/trading_agent/files/`

| File Pattern | Created By | Contains | Size |
|--------------|------------|----------|------|
| `validation_results_v8.pkl` | 01_synthetic | MAPE/MAE validation for all accuracy levels | ~10MB |
| `prediction_matrices_{commodity}_{model}.pkl` | 01_synthetic | Dict of {date: np.array(runs, horizons)} | ~50-200MB |
| `prediction_matrices_{commodity}_{model}_real.pkl` | 02_forecast | Same for real forecasts | ~50-200MB |
| `results_detailed_{commodity}_{model}.pkl` | 05_comparison | Full backtest results (trades, daily_state) | ~5-20MB |
| `statistical_results_{commodity}_{model}.pkl` | 06_statistical | Bootstrap samples, p-values, CIs | ~2-5MB |
| `feature_analysis_{commodity}_{model}.pkl` | 07_feature | Feature correlations, importance | ~1-5MB |
| `sensitivity_results_{commodity}_{model}.pkl` | 08_sensitivity | Parameter sweep results | ~5-10MB |

---

### Volume Files (CSV)

**Location:** `/Volumes/commodity/trading_agent/files/`

| File Pattern | Created By | Contains | Size |
|--------------|------------|----------|------|
| `detailed_strategy_results.csv` | 05_comparison | All strategies, all commodities, all models | ~100KB |
| `cross_model_commodity_summary.csv` | 05_comparison | Best strategies only (summary) | ~10KB |
| `statistical_comparisons_{commodity}_{model}.csv` | 06_statistical | Statistical test results | ~20KB |
| `bootstrap_summary_{commodity}_{model}.csv` | 06_statistical | Bootstrap statistics | ~10KB |
| `summary_stats_{commodity}_{model}.csv` | 09_summary | Aggregated metrics | ~30KB |
| `final_summary_{commodity}_{model}.csv` | 09_summary | Complete summary | ~50KB |

---

### Volume Files (PNG Charts)

**Location:** `/Volumes/commodity/trading_agent/files/`

**Per Commodity-Model (from 05_comparison):**
1. `net_earnings_{commodity}_{model}.png` - Bar chart of all strategy earnings
2. `trading_timeline_{commodity}_{model}.png` - Price + trade markers over time
3. `total_revenue_no_costs_{commodity}_{model}.png` - Cumulative gross revenue
4. `cumulative_returns_{commodity}_{model}.png` - Cumulative net earnings
5. `inventory_drawdown_{commodity}_{model}.png` - Inventory levels over time

**Cross-Comparison (from 05_comparison):**
6. `cross_model_commodity_advantage.png` - Prediction advantage by model/commodity
7. `cross_model_commodity_earnings.png` - Baseline vs prediction earnings comparison

**Per Commodity-Model (from 06_statistical):**
8. `bootstrap_distribution_{commodity}_{model}.png` - Bootstrap histogram + CI
9. `confidence_intervals_{commodity}_{model}.png` - Forest plot of CIs
10. `effect_sizes_{commodity}_{model}.png` - Cohen's d bar chart

**Per Commodity-Model (from 07_feature):**
11. `feature_correlation_heatmap_{commodity}_{model}.png` - Feature correlations
12. `feature_importance_{commodity}_{model}.png` - Ranked feature importance
13. `feature_distributions_{commodity}_{model}.png` - SELL vs WAIT boxplots

**Per Commodity-Model (from 08_sensitivity):**
14. `sensitivity_plot_{commodity}_{model}.png` - Parameter sweep lines
15. `sensitivity_heatmap_{commodity}_{model}.png` - 2D parameter interaction
16. `tornado_diagram_{commodity}_{model}.png` - Parameter impact ranking

**Per Commodity-Model (from 09_summary):**
17. `strategy_ranking_{commodity}_{model}.png` - Summary table visualization
18. `performance_dashboard_{commodity}_{model}.png` - Multi-panel summary
19. `key_findings_{commodity}_{model}.png` - Infographic

**Per Commodity-Model (from 10_paired):**
20. `paired_decisions_{commodity}_{model}.png` - Decision comparison
21. `trade_timing_comparison_{commodity}_{model}.png` - Timing analysis
22. `cost_attribution_{commodity}_{model}.png` - Performance breakdown

**Total:** ~22 PNGs per commodity-model combination

**For 2 commodities × 5 synthetic models = 10 combinations:**
- 220 PNG files minimum
- Plus cross-comparison charts
- Plus real model results (12+ additional combinations)

---

## 🔗 Integration Points for Diagnostics

### Current Issues

1. **No parameter optimization** - Uses hardcoded params from 00_setup
2. **No algorithm validation** - No 100% accuracy test
3. **Limited strategy variants** - Only 9 strategies, no alternatives
4. **No monotonicity testing** - Doesn't verify 60% < 70% < 80% < 90% < 100%

### What Diagnostics Provide

From `diagnostics/`:

**Core Strategy Implementation:**
- **all_strategies_pct.py**: 9 strategies with percentage-based framework
  - 3 baseline strategies (Equal Batches, Price Threshold, Moving Average)
  - 5 prediction strategies (Expected Value, Consensus, Risk-Adjusted, Price Threshold Pred, Moving Average Pred)
  - **UPDATED (2025-11-24)**: Redesigned matched pair strategies with 3-tier confidence system
  - HIGH confidence (CV < 5%): Override baseline completely
  - MEDIUM confidence (5-15%): Blend baseline + predictions
  - LOW confidence (CV > 15%): Follow baseline exactly

**Validation Diagnostics:**
- **diagnostic_100** (`run_diagnostic_100.py`): Algorithm validation with perfect foresight
  - Tests with 100% accurate predictions (synthetic_acc100)
  - **UPDATED (2025-11-24)**: Lowered threshold from 10% to 6% for realistic validation
  - Output: `diagnostic_100_summary.csv`, `diagnostic_100_results.pkl`

- **diagnostic_16** (`run_diagnostic_16.py`): Grid search optimized parameters
  - Optuna-based Bayesian optimization
  - Output: `diagnostic_16_best_params.pkl`, `diagnostic_16_summary.csv`

- **diagnostic_17** (`run_diagnostic_17.py`): Trade-by-trade analysis with optimized params
  - Uses: `diagnostic_16_best_params.pkl`
  - Output: Trade-level analysis

**New Accuracy Analysis Diagnostics (2025-11-24):**
- **check_prediction_models.py**: Explores available prediction models
  - Lists all model_version values in predictions table
  - Calculates CV (Coefficient of Variation) for each model
  - Helps identify confidence tiers for each accuracy level
  - Output: Console only (quick exploration)

- **run_diagnostic_accuracy_threshold.py**: **⭐ COMPREHENSIVE ACCURACY ANALYSIS**
  - **Purpose**: Determine minimum prediction accuracy for statistically significant benefit
  - Tests ALL accuracy levels: 60%, 70%, 80%, 90%, 100%
  - Compares ALL prediction strategies vs ALL baseline strategies
  - **Statistical Methods** (from 06_statistical_validation.ipynb):
    - Paired t-test on daily portfolio value changes
    - Cohen's d effect size calculation
    - Bootstrap confidence intervals (1000 iterations, 95% CI)
    - Statistical significance at p < 0.05
  - **Key Questions Answered**:
    1. What accuracy level provides statistically significant benefit?
    2. How does improvement scale with accuracy?
    3. At what accuracy does each strategy become viable?
    4. What is the confidence-based performance degradation curve?
  - **Outputs**:
    - `diagnostic_accuracy_threshold_results.pkl` - Full results with daily state tracking
    - `diagnostic_accuracy_threshold_summary.csv` - Earnings and improvements by accuracy
    - `diagnostic_accuracy_threshold_stats.csv` - Statistical test results (t-stat, p-value, Cohen's d, CIs)

- **run_diagnostic_confidence_test.py**: Tests 3-tier confidence system
  - Validates that HIGH/MEDIUM/LOW confidence tiers work as expected
  - Tests with multiple accuracy levels (100%, 90%, 80%, 70%)
  - Verifies graceful degradation as accuracy decreases
  - Output: `diagnostic_confidence_test_results.pkl`, `diagnostic_confidence_test_summary.csv`

### Integration Plan (Future Work)

**Step 1:** Port optimized parameters from diagnostics
- Load `diagnostic_16_best_params.pkl`
- Update `BASELINE_PARAMS` and `PREDICTION_PARAMS` in 00_setup

**Step 2:** Integrate diagnostic_100 test
- Add to workflow before 05_strategy_comparison
- Verify algorithms work with 100% accuracy
- Block execution if test fails

**Step 3:** Add monotonicity validation
- After 05_comparison runs all accuracies
- Verify 60% < 70% < 80% < 90% < 100%
- Add to 06_statistical or create new 06_monotonicity notebook

**Step 4:** Consolidate strategy implementations
- Replace 03_strategy_implementations.ipynb with diagnostics/all_strategies_pct.py
- Ensure consistent parameter names
- Preserve decision logging

**Step 5:** Organize outputs into final report
- Create FINAL_REPORT/ directory structure
- Aggregate all CSVs and PNGs
- Generate master summary document

---

## ## Workflow Analysis & Findings

**Source:** WORKFLOW_ANALYSIS_AND_FINDINGS.md (2025-11-22 Analysis)
**Analyst:** Claude Code
**Scope:** Comprehensive review of backtesting workflow architecture and execution patterns

### Workflow Phase Structure

The trading analysis workflow is organized into 5 distinct phases with clear dependencies:

**Phase 1: Setup & Data Preparation**
- Central configuration (00_setup_and_config)
- Synthetic predictions at 4 accuracy levels: 60%, 70%, 80%, 90% (01_synthetic_predictions)
- Real forecast integration (02_forecast_predictions)
- Cost model: Percentage-based (storage: 0.025%/day, transaction: 0.25%)

**Phase 2: Strategy Implementation**
- 9 distinct trading strategies: 4 baseline + 5 prediction-based (03_strategy_implementations)
- Technical indicators: RSI, ADX, Standard Deviation (both historical & predicted)
- Cost-benefit analysis built into strategy logic
- Dynamic batch sizing (10-45% based on confidence signals)

**Phase 3: Backtesting**
- Harvest cycle-aware backtesting engine (04_backtesting_engine)
- Multi-year support with age tracking (365-day max holding)
- Pre-harvest liquidation rules
- Percentage-based costs (realistic, scale with commodity value)

**Phase 4: Comparative Analysis**
- Master workflow notebook (05_strategy_comparison) runs all 9 strategies
- Auto-discovers model versions (synthetic + real)
- Generates 7 PNG charts per commodity-model combination
- Produces 2 cross-comparison aggregate charts

**Phase 5: Validation & Analysis**
- Statistical significance testing (06_statistical_validation) - paired t-tests, bootstrap CIs, Cohen's d
- Feature importance analysis (07_feature_importance)
- Cost sensitivity testing (08_sensitivity_analysis)
- Final reporting and dashboards (09_strategy_results_summary)
- Paired scenario deep-dive (10_paired_scenario_analysis)

### Identified Workflow Gaps

**Critical Gap: Missing Synthetic Accuracy Comparison**
- No dedicated notebook comparing performance across 4 accuracy levels (60%, 70%, 80%, 90%)
- This is essential for validation: should see monotonic improvement with accuracy
- Failure to show advantage at 90% accuracy would indicate trading logic bugs
- **Recommendation:** Create `11_synthetic_accuracy_comparison.ipynb` to fill this gap

**Known Issues:**
- Notebook 10 (paired_scenario_analysis) has path errors - references `/Volumes/commodity/silver/trading_agent_volume/` which doesn't match actual paths
- Real forecast data is sparse with many gaps >30 days - use synthetic predictions for validation
- 15 notebooks is complex to maintain and execute manually

### Phase Structure Analysis

**Key Design Insight:** Workflow uses **matched pair strategies** for clean A/B testing:
1. Price Threshold Baseline vs Price Threshold Predictive
2. Moving Average Baseline vs Moving Average Predictive
3. Consensus, Expected Value, Risk-Adjusted strategies (prediction-only variants)

This design allows:
- Isolation of prediction value-add (paired strategy earnings difference)
- Control for baseline strategy drift
- Clear measurement of when predictions help vs hurt

**Harvest Cycle Awareness:** Unlike typical backtesting, this system:
- Tracks inventory accumulation during harvest windows
- Enforces multi-year constraints (coffee: May-Sep, sugar: Oct-Dec)
- Liquidates old inventory before new harvest arrivals
- Prevents unrealistic holding across multiple harvest cycles

### Risk Assessment

**Data Quality Risks (RED - MITIGATE):**
- Real forecasts sparse with gaps >30 days - not suitable for continuous daily trading
- **Mitigation:** Use synthetic predictions for validation; real forecasts only where available

**Logic Risks (YELLOW - VALIDATE):**
- Complex strategies with multiple technical indicators - hard to debug
- Cost-benefit calculations may mask trading logic issues
- **Mitigation:** Run diagnostic_100 (100% accuracy test) before trusting results
- **Action:** Must see clear advantage at 90% accuracy; if not, indicates bugs

**Cost Assumption Risks (YELLOW - VERIFY):**
- Percentage-based costs (0.025%/day storage, 0.25% transaction) may not match real brokers
- Small basis points savings may be consumed by transaction/storage costs
- **Mitigation:** Sensitivity analysis (08_sensitivity_analysis) shows cost impact
- **Validation:** Verify results robust to ±50% cost multipliers

**Execution Risks (GREEN - DOCUMENTED):**
- Multiple `%run` dependencies between notebooks
- Interdependencies could break if notebooks moved/renamed
- **Current Mitigation:** Clear execution order documented
- **Future:** Migrate to automated script-based execution (see Automation Migration Plan)

### Strategy Validation Questions

Before trusting workflow results, these questions must be answered:

1. **Does 90% accuracy show clear advantage?**
   - Expected: Strong earnings improvement over baselines
   - If not: Indicates trading logic issues that need debugging

2. **Is performance monotonic across accuracy levels?**
   - Expected: 60% < 70% < 80% < 90% < 100% (in earnings)
   - If not: Indicates data leakage, strategy issues, or cost structure problems

3. **Are matched pairs effective?**
   - Expected: Price Threshold Predictive beats Price Threshold Baseline
   - Expected: MA Predictive beats MA Baseline
   - If not: Prediction signals may be inverted or poorly calibrated

4. **Are results statistically significant?**
   - Expected: p < 0.05 for high-accuracy scenarios (90%+)
   - Expected: Bootstrap confidence intervals exclude zero
   - If not: Sample size too small or variance too high

5. **Are results robust to cost assumptions?**
   - Expected: Performance remains positive with ±50% cost multipliers
   - Expected: Relative strategy rankings don't change dramatically
   - If not: Margin too thin, real-world execution risky

### Recommendations

**Immediate Actions:**

1. **Create accuracy comparison notebook:**
   - Run 01_synthetic_predictions for all 4 accuracy levels
   - Compare earnings/metrics across levels in single dashboard
   - Generate monotonicity validation plots
   - **Expected output:** `11_synthetic_accuracy_comparison.ipynb`

2. **Validate core algorithms:**
   - Run diagnostic_100 (100% accuracy test)
   - If 100% accuracy doesn't show clear advantage, stop and debug
   - Fix strategy logic before running full workflow

3. **Add workflow README:**
   - Document execution order (Setup → Data → Strategies → Backtest → Analysis)
   - Identify required vs optional notebooks
   - Expected runtime per phase
   - Common pitfalls and troubleshooting

4. **Fix Notebook 10 paths:**
   - Correct file paths to match actual volume structure
   - Test with real data before running at scale

**Medium-term Actions:**

1. **Automate workflow execution:**
   - Convert notebooks to executable Python scripts
   - Submit as Databricks jobs with proper dependencies
   - Enable overnight/batch execution of full workflow
   - (See Automation Migration Plan section above)

2. **Consolidate reporting:**
   - Create FINAL_REPORT/ directory
   - Aggregate all CSVs and PNGs with clear naming
   - Generate master summary document
   - Enable one-click report generation

3. **Implement monotonicity testing:**
   - Add validation that checks 60% < 70% < 80% < 90%
   - Block execution if monotonicity fails
   - Highlight any accuracy levels that violate expectations

### Execution Flow (Recommended)

```
1. 00_setup_and_config           → Configure parameters
2. 01_synthetic_predictions      → Generate test predictions (60%-90% accuracy)
3. 05_strategy_comparison        → Run all strategies on all models
4. 06_statistical_validation     → Statistical significance testing
5. 11_synthetic_accuracy_comparison → VALIDATE MONOTONICITY (NEW)
6. diagnostic_100                → Test with 100% accuracy (if step 5 looks bad)
7. 08_sensitivity_analysis       → Cost robustness testing
8. 09_strategy_results_summary   → Generate final reports
9. 10_paired_scenario_analysis   → Deep-dive paired comparison (if paths fixed)
```

### Key Findings Summary

**Strengths:**
- Sophisticated strategy design with matched pairs for clean A/B testing
- Robust harvest cycle awareness (realistic constraints)
- Comprehensive statistical validation
- Multiple visualization formats for different audiences
- Percentage-based costs (more realistic than fixed dollar amounts)

**Weaknesses:**
- Missing accuracy comparison notebook (critical validation gap)
- Real forecast data too sparse for continuous daily trading
- Complex workflow (15 notebooks) - hard to maintain
- Limited automation (manual notebook execution)
- Some path errors in notebook 10

**Critical Success Factor:**
90% accuracy synthetic predictions MUST show clear advantage over baselines. If not, trading algorithms have fundamental issues that need debugging before running real forecasts.

---

## 📋 Execution Checklist (Current Workflow)

### One-Time Setup
- [ ] Configure 00_setup_and_config
- [ ] Set commodity parameters
- [ ] Verify Unity Catalog access

### Per Run
- [ ] Generate predictions (01_synthetic_v8 or 02_forecast)
- [ ] Run 05_strategy_comparison (auto-runs 03, 04)
- [ ] Run 06_statistical_validation
- [ ] Run 07_feature_importance
- [ ] Run 08_sensitivity_analysis
- [ ] Run 09_strategy_results_summary
- [ ] Run 10_paired_scenario_analysis

### Download Results
- [ ] Download all PNGs from volume
- [ ] Download all CSVs from volume
- [ ] Download all pickles for deep analysis
- [ ] Compile into presentation/report

---

## 🎯 Key Findings (What This Workflow Reveals)

From running this workflow with v8 synthetic predictions:

**If prediction strategies beat baselines:**
- Prediction accuracy is sufficient (≥70%)
- Algorithms work correctly
- Parameters are well-tuned

**If prediction strategies lose to baselines:**
- Check diagnostic_100: Do algorithms work with 100% accuracy?
  - YES → Accuracy too low, improve forecasting
  - NO → Algorithms broken, debug decision logic
- Check diagnostic_17: Where do strategies diverge?
  - Revenue? Transaction costs? Storage costs?
- Check monotonicity: Does performance improve with accuracy?
  - YES → Just need better predictions
  - NO → Algorithm not using predictions correctly

---


## Automation

**For complete automation guide including:**
- Proven automation patterns (diagnostics 16/17/100)
- Job submission examples
- Orchestration strategies
- Monitoring and logging
- Notebook to script conversion

**See:** [../../docs/AUTOMATION_GUIDE.md](../../docs/AUTOMATION_GUIDE.md)

---

## 🐍 Python Scripts Inventory

### Root Directory Scripts

#### analyze_validation.py

**Purpose:** Analyze validation results from synthetic prediction generation

**Inputs:**
- `/Volumes/commodity/trading_agent/files/validation_results_v*.pkl` - Validation metrics from 01_synthetic_predictions

**Outputs:**
- Console output only (no files created)
- Displays MAPE, MAE, coverage, directional accuracy by accuracy level
- Verifies 100% accuracy shows 0% MAPE (bug verification)

**Usage:**
```bash
python analyze_validation.py
```

**Status:** Active - Used for quick validation checks

---

### Diagnostics Directory Scripts

#### diagnostics/run_diagnostic_16.py

**Purpose:** Optuna-based Bayesian optimization of all 9 strategy parameters

**Inputs:**
- `commodity.bronze.market` - Price data
- `commodity.trading_agent.predictions_{commodity}` - Prediction matrices
- `all_strategies_pct.py` - Strategy implementations

**Outputs:**
- `diagnostic_16_best_params.pkl` - Optimized parameters for all 9 strategies
- `diagnostic_16_summary.csv` - Summary of optimization results
- `diagnostic_16_trials.csv` - All Optuna trial results

**Usage:**
```bash
# Run on Databricks
databricks jobs submit --json @job_diagnostic_16.json
```

**Key Features:**
- 200 trials per strategy
- Bayesian optimization (smarter than grid search)
- Spark parallelization for faster execution
- Saves best parameters for use by diagnostic_17

**Status:** Active - Core optimization tool

---

#### diagnostics/run_diagnostic_17.py

**Purpose:** Trade-by-trade analysis using optimized parameters from diagnostic_16

**Inputs:**
- `diagnostic_16_best_params.pkl` - Optimized parameters (REQUIRED - run diagnostic_16 first)
- `commodity.bronze.market` - Price data
- `commodity.trading_agent.predictions_{commodity}` - Predictions

**Outputs:**
- `diagnostic_17_trade_analysis.pkl` - Detailed trade-by-trade comparison
- `diagnostic_17_summary.csv` - Performance metrics with optimized params
- `diagnostic_17_paradox_analysis.csv` - Why predictions underperform (if they do)

**Usage:**
```bash
# Must run diagnostic_16 first!
databricks jobs submit --json @job_diagnostic_17.json
```

**Key Questions Answered:**
- Where do prediction strategies diverge from baselines?
- Is underperformance from revenue, transaction costs, or storage costs?
- Which trades are different between matched pairs?

**Status:** Active - Dependent on diagnostic_16

---

#### diagnostics/run_diagnostic_100.py

**Purpose:** Algorithm validation with 100% accurate predictions (perfect foresight test)

**Inputs:**
- `commodity.bronze.market` - Price data
- `commodity.trading_agent.predictions_coffee` (filtered for `model_version = 'synthetic_acc100'`)

**Outputs:**
- `diagnostic_100_summary.csv` - Performance with perfect accuracy
- `diagnostic_100_results.pkl` - Full backtest results
- Console validation output

**Usage:**
```bash
databricks jobs submit --json @job_diagnostic_100.json
```

**Validation Logic:**
- If 100% accuracy doesn't show >6% advantage over baselines → Algorithms are broken
- Updated 2025-11-24: Lowered threshold from 10% to 6% for realistic validation
- This is a SANITY CHECK that must pass before trusting any results

**Status:** Active - Critical validation step

---

#### diagnostics/run_diagnostic_theoretical_max.py

**Purpose:** Calculate theoretical maximum performance using dynamic programming

**Inputs:**
- `commodity.bronze.market` - Price data
- Perfect 14-day foresight (simulated)

**Outputs:**
- `diagnostic_theoretical_max_results.pkl` - Best possible performance
- `diagnostic_theoretical_max_efficiency.csv` - Strategy efficiency ratios
- Console output: Actual / Theoretical Max

**Key Questions:**
1. With 100% accuracy, what's the absolute best we could do?
2. How efficient are current strategies? (Actual / Theoretical Max)
3. Where are we leaving money on the table?

**Usage:**
```bash
databricks jobs submit --json @job_diagnostic_theoretical_max.json
```

**Status:** Active - Benchmarking tool

---

#### diagnostics/run_diagnostic_accuracy_threshold.py

**Purpose:** Comprehensive accuracy analysis - determine minimum prediction accuracy for statistically significant benefit

**Inputs:**
- `commodity.bronze.market` - Price data
- `commodity.trading_agent.predictions_{commodity}` - ALL accuracy levels (60%, 70%, 80%, 90%, 100%)

**Outputs:**
- `diagnostic_accuracy_threshold_results.pkl` - Full results with daily state tracking
- `diagnostic_accuracy_threshold_summary.csv` - Earnings and improvements by accuracy
- `diagnostic_accuracy_threshold_stats.csv` - Statistical test results (t-stat, p-value, Cohen's d, 95% CIs)

**Statistical Methods:**
- Paired t-test on daily portfolio value changes
- Cohen's d effect size calculation
- Bootstrap confidence intervals (1000 iterations, 95% CI)
- Statistical significance at p < 0.05

**Key Questions Answered:**
1. What accuracy level provides statistically significant benefit?
2. How does improvement scale with accuracy?
3. At what accuracy does each strategy become viable?
4. What is the confidence-based performance degradation curve?

**Usage:**
```bash
databricks jobs submit --json @job_diagnostic_accuracy_threshold.json
```

**Status:** Active - Key statistical validation (COMPREHENSIVE)

---

#### diagnostics/run_diagnostic_confidence_test.py

**Purpose:** Test 3-tier confidence system (HIGH/MEDIUM/LOW based on CV)

**Inputs:**
- Multiple accuracy levels (100%, 90%, 80%, 70%)
- `commodity.trading_agent.predictions_{commodity}`

**Outputs:**
- `diagnostic_confidence_test_results.pkl` - Results for each confidence tier
- `diagnostic_confidence_test_summary.csv` - Performance by tier

**Confidence Tiers:**
- HIGH (CV < 5%): Override baseline completely
- MEDIUM (CV 5-15%): Blend baseline + predictions
- LOW (CV > 15%): Follow baseline exactly

**Usage:**
```bash
databricks jobs submit --json @job_diagnostic_confidence_test.json
```

**Status:** Active - Tests redesigned matched pair strategies (updated 2025-11-24)

---

#### diagnostics/all_strategies_pct.py

**Purpose:** Complete strategy suite with percentage-based framework (CORE IMPLEMENTATION)

**Inputs:** None (pure implementation - imported by other scripts)

**Outputs:** None (provides classes and functions)

**What it provides:**
- All 9 strategy classes:
  1. ImmediateSaleStrategy (baseline)
  2. EqualBatchStrategy (baseline)
  3. PriceThresholdStrategy (baseline)
  4. MovingAverageStrategy (baseline)
  5. PriceThresholdPredictive (matched pair)
  6. MovingAveragePredictive (matched pair)
  7. ExpectedValueStrategy (prediction-only)
  8. ConsensusStrategy (prediction-only)
  9. RiskAdjustedStrategy (prediction-only)

- Technical indicators:
  - RSI (Relative Strength Index)
  - ADX (Average Directional Index)
  - Standard Deviation (historical and predicted)

- Confidence calculation:
  - Coefficient of Variation (CV) from prediction ensembles
  - 3-tier system (HIGH/MEDIUM/LOW)

**Key Design Features:**
- ALL thresholds as percentages (scale-invariant)
- Matched pairs MIRROR baselines exactly (clean A/B testing)
- Full parameterization for grid search
- Batch sizes 0.0 to 0.40 (realistic batch sizing)

**Usage:**
```python
from all_strategies_pct import *

# Baselines
strategy = PriceThresholdStrategy(threshold_pct=0.05, batch_baseline=0.25)

# Matched pair (same params)
strategy_pred = PriceThresholdPredictive(threshold_pct=0.05, batch_baseline=0.25)

# Standalone
strategy_ev = ExpectedValueStrategy(
    storage_cost_pct_per_day=0.025,
    transaction_cost_pct=0.25,
    min_net_benefit_pct=0.5
)
```

**Status:** Active - Core strategy implementation (imported by all diagnostics)

**Updated:** 2025-11-24 - Redesigned matched pair strategies with 3-tier confidence system

---

#### diagnostics/check_prediction_models.py

**Purpose:** Quick exploration of available prediction models in Delta table

**Inputs:**
- `commodity.trading_agent.predictions_coffee` - Predictions table

**Outputs:**
- Console output only (no files)
- Lists all model_version values
- Calculates CV (Coefficient of Variation) for each model
- Shows date ranges and row counts

**Usage:**
```bash
# Run in Databricks notebook or as script
python check_prediction_models.py
```

**Status:** Active - Quick exploration tool

---

#### diagnostics/verify_predictions.py

**Purpose:** Quick verification that predictions exist and are structured correctly

**Inputs:**
- `commodity.trading_agent.predictions_coffee`

**Outputs:**
- Console output only
- Checks table exists
- Shows available model versions
- Displays date ranges
- Sample predictions

**Usage:**
```bash
python verify_predictions.py
```

**Status:** Active - Quick data validation

---

#### diagnostics/test_all_strategies.py

**Purpose:** Unit test that all 9 strategies can be instantiated and run

**Inputs:** None (synthetic test data)

**Outputs:**
- Console output (pass/fail for each strategy)
- Tests basic decision-making for each strategy

**Usage:**
```bash
python test_all_strategies.py
```

**Status:** Active - Unit testing

---

#### diagnostics/rebuild_notebook.py

**Purpose:** Programmatically rebuild diagnostic_16 notebook with proper Jupyter formatting

**Inputs:** None (generates from scratch)

**Outputs:**
- `diagnostic_16_optuna_with_params.ipynb` - Rebuilt notebook

**Usage:**
```bash
python rebuild_notebook.py
```

**Status:** Utility - Used when notebook gets corrupted

---

#### diagnostics/diagnostic_100_algorithm_validation.py

**Purpose:** DUPLICATE of diagnostic_100_algorithm_validation.ipynb as a Python script

**Note:** This is the notebook content extracted to .py format for reference

**Status:** Obsolete - Use `run_diagnostic_100.py` instead (proper automation script)

---

#### diagnostics/cost_config_small_farmer.py

**Purpose:** Alternative cost configuration for small farmer scenario

**Inputs:** None (config only)

**Outputs:** None (provides COMMODITY_CONFIGS dict)

**Usage:**
```python
from cost_config_small_farmer import COMMODITY_CONFIGS
```

**Status:** Experimental - Alternative cost assumptions

---

### Analysis Directory Scripts

Modern analysis infrastructure separate from old diagnostics approach.

**Purpose:** Efficiency-aware strategy analysis using theoretical maximum benchmarking
**vs Diagnostics:** Diagnostics uses paired t-tests; Analysis uses efficiency ratio (Actual/Theoretical Max)

**Documentation:** See [analysis/README.md](analysis/README.md) and [analysis/optimization/README.md](analysis/optimization/README.md)

---

#### analysis/run_strategy_analysis.py

**Purpose:** Orchestrator for comprehensive strategy analysis with theoretical maximum benchmark

**Inputs:**
- Delta table: `commodity.bronze.market` (price data)
- Pickle: prediction matrices from production
- Unity table: `commodity.trading_agent.results_{commodity}_{model}` (actual strategy results)

**Outputs:**
- CSV: `{VOLUME}/analysis/theoretical_max_decisions_{commodity}_{model}.csv`
- CSV: `{VOLUME}/analysis/efficiency_analysis_{commodity}_{model}.csv`
- Pickle: `{VOLUME}/analysis/analysis_summary_{commodity}_{model}.pkl`

**What it does:**
1. Loads price data and predictions
2. Calculates theoretical maximum earnings using DP
3. Loads actual strategy results from backtest
4. Calculates efficiency ratios (Actual / Theoretical Max)
5. Generates decision-by-decision comparisons
6. Produces summary reports and visualizations

**Usage:**
```bash
# Analyze single commodity-model combination
python analysis/run_strategy_analysis.py --commodity coffee --model arima_v1

# Compare all strategies
python analysis/run_strategy_analysis.py --commodity coffee --compare-all

# Custom results location
python analysis/run_strategy_analysis.py --commodity coffee --model arima_v1 \
    --results-table commodity.trading_agent.results_coffee_arima_v1
```

**Key Features:**
- NEW analysis approach (efficiency-based, not paired t-tests)
- Perfect foresight benchmark
- Identifies where money is left on table
- Decision quality analysis

**Status:** Production-ready - Modern analysis framework

---

#### analysis/theoretical_max/calculator.py

**Purpose:** Calculate theoretical maximum performance with perfect 14-day foresight using dynamic programming

**Algorithm:**
- Dynamic programming with discretized inventory levels
- Works backwards from last day to first day
- At each state (day, inventory), tries all possible sell amounts
- Considers storage costs, transaction costs, and future value
- Returns optimal policy and maximum achievable earnings

**Key Parameters:**
- `inventory_granularity`: float (default 2.5) - Step size for inventory discretization
- Inventory levels: 0 to 50 tons in steps

**DP Table Structure:**
```python
dp[day][inventory_idx] = max net earnings from day onwards
decisions[day][inventory_idx] = amount_to_sell
```

**Base Case:** Last day forces liquidation of all remaining inventory

**Returns:**
```python
{
    'optimal_decisions': List[Dict],  # Day-by-day optimal actions
    'total_net_earnings': float,      # Maximum achievable earnings
    'total_revenue': float,           # Gross revenue
    'total_transaction_costs': float, # Transaction costs
    'total_storage_costs': float,     # Storage costs
    'num_trades': int                 # Number of non-zero sales
}
```

**Usage:**
```python
from analysis.theoretical_max import TheoreticalMaxCalculator

calculator = TheoreticalMaxCalculator(
    prices_df=prices,
    predictions=pred_matrices,
    config={'storage_cost_pct_per_day': 0.005, 'transaction_cost_pct': 0.01}
)

result = calculator.calculate_optimal_policy(initial_inventory=50.0)
```

**Status:** Production-ready - Upper bound benchmark

---

#### analysis/efficiency/analyzer.py

**Purpose:** Compare actual strategy performance to theoretical maximum to measure efficiency

**Key Questions:**
1. How efficiently are we exploiting available predictions?
2. Where are we leaving money on the table?
3. Which strategies get closest to optimal?

**Metrics:**
- **Efficiency Ratio:** (Actual / Theoretical Max) × 100%
- **Opportunity Gap:** Theoretical Max - Actual (dollars left on table)
- **Decision Quality:** Day-by-day comparison

**Efficiency Categories:**
- EXCELLENT: ≥80% efficiency
- GOOD: 70-80% efficiency
- MODERATE: 60-70% efficiency
- POOR: <60% efficiency

**Key Methods:**
- `calculate_efficiency_ratios()` - Compute efficiency for all strategies
- `compare_decisions()` - Day-by-day comparison of actual vs optimal
- `get_summary_report()` - Summary statistics and insights
- `get_interpretation()` - Human-readable recommendations
- `identify_critical_decisions()` - Find most impactful suboptimal decisions

**Usage:**
```python
from analysis.efficiency import EfficiencyAnalyzer

analyzer = EfficiencyAnalyzer(theoretical_max_result)
efficiency_df = analyzer.calculate_efficiency_ratios(actual_results)
summary = analyzer.get_summary_report(efficiency_df)
interpretation = analyzer.get_interpretation(summary)
```

**Status:** Production-ready - Efficiency analysis framework

---

#### analysis/optimization/run_parameter_optimization.py

**Purpose:** Modern parameter optimization orchestrator using Optuna

**Migrated from:** diagnostics/run_diagnostic_16.py with enhancements:
- Efficiency-aware optimization (optimize for efficiency ratio, not just earnings)
- Integration with theoretical maximum benchmark
- Uses production config and data loaders
- Multi-objective optimization support
- Clean, modular architecture

**Inputs:**
- Delta table: `commodity.bronze.market` (prices)
- Unity table: `commodity.trading_agent.predictions_{commodity}` (predictions)
- model_version to optimize

**Outputs:**
- Pickle: `{VOLUME}/optimization/optimized_params_{commodity}_{model}_{objective}.pkl`
- Pickle: `{VOLUME}/optimization/optimization_results_{commodity}_{model}_{objective}.pkl`
- CSV: `{VOLUME}/optimization/optimization_summary_{commodity}_{model}_{objective}.csv`

**Optimization Objectives:**
1. **'earnings'**: Maximize raw net earnings (original approach)
2. **'efficiency'**: Maximize efficiency ratio (Actual / Theoretical Max)
3. **'multi'**: Multi-objective optimization (Pareto frontier of earnings + Sharpe ratio)

**Usage:**
```bash
# Optimize all strategies for efficiency
python analysis/optimization/run_parameter_optimization.py \
    --commodity coffee --objective efficiency --trials 200

# Optimize single strategy for raw earnings
python analysis/optimization/run_parameter_optimization.py \
    --commodity coffee --strategy consensus --objective earnings --trials 200

# Multi-objective optimization
python analysis/optimization/run_parameter_optimization.py \
    --commodity coffee --objective multi --trials 500
```

**Key Functions:**
- `load_data()` - Load prices and predictions from tables
- `calculate_theoretical_max()` - Calculate upper bound for efficiency objective
- `get_strategy_classes()` - Import all 9 strategy classes
- `run_optimization()` - Main workflow

**Status:** Production-ready - Optuna-based optimization with efficiency awareness

---

#### analysis/optimization/optimizer.py

**Purpose:** ParameterOptimizer class that runs Optuna trials

**Key Features:**
- Multiple optimization objectives (earnings, efficiency, multi-objective)
- Integration with theoretical maximum benchmark
- Uses production BacktestEngine for accuracy
- Full logging and result tracking

**Engine Options:**
1. **Production BacktestEngine** (default, recommended):
   - More accurate, harvest-aware
   - Required for final optimization
   - From `production.core.backtest_engine`

2. **SimpleBacktestEngine** (optional):
   - Faster for prototyping
   - Simplified logic
   - Included in optimizer.py

**Key Methods:**
- `optimize_strategy()` - Optimize single strategy
- `optimize_all_strategies()` - Optimize all provided strategies
- Returns: (best_params, best_value, study) tuple

**Usage:**
```python
from analysis.optimization.optimizer import ParameterOptimizer

optimizer = ParameterOptimizer(
    prices_df=prices,
    prediction_matrices=predictions,
    config=config,  # Full commodity config
    theoretical_max_earnings=theoretical_max,
    use_production_engine=True  # Recommended
)

best_params, best_value, study = optimizer.optimize_strategy(
    strategy_class=ConsensusStrategy,
    strategy_name='consensus',
    n_trials=200,
    objective='efficiency'
)
```

**Auto-Install:** Auto-installs Optuna if not available (for Databricks compatibility)

**Status:** Production-ready - Core optimization engine

---

#### analysis/optimization/search_space.py

**Purpose:** Parameter search space definitions for all 9 trading strategies

**Extracted from:** diagnostics/run_diagnostic_16.py with clean, modular structure

**Strategies Covered:**
1. **immediate_sale**: 2 parameters (min_batch_size, sale_frequency_days)
2. **equal_batch**: 2 parameters (batch_size, frequency_days)
3. **price_threshold**: 10 parameters (threshold_pct, batch sizes, RSI/ADX thresholds, cooldown, max_days)
4. **moving_average**: 11 parameters (ma_period, batch sizes, RSI/ADX thresholds, cooldown, max_days)
5. **price_threshold_predictive**: Inherits price_threshold + 4 prediction params
6. **moving_average_predictive**: Inherits moving_average + 4 prediction params
7. **expected_value**: 12 parameters (net_benefit, CV thresholds, batch sizes, cooldown, baseline)
8. **consensus**: 12 parameters (consensus thresholds, min_return, net_benefit, CV, batch sizes, eval_day, cooldown)
9. **risk_adjusted**: 12 parameters (min_return, net_benefit, CV thresholds, ADX, batch sizes, eval_day, cooldown)

**Total Parameters:** 70 parameters across 9 strategies

**Prediction Parameters (strategies 5-9):**
- `min_net_benefit_pct`: 0.3-1.0% (minimum benefit to act)
- `high_confidence_cv`: 0.03-0.08 (CV threshold for high confidence)
- `scenario_shift_aggressive`: 1-2 (shift for aggressive scenarios)
- `scenario_shift_conservative`: 1-2 (shift for conservative scenarios)

**Usage:**
```python
from analysis.optimization.search_space import SearchSpaceRegistry

registry = SearchSpaceRegistry()
params = registry.get_search_space(trial, 'consensus')
available = registry.get_available_strategies()
```

**Status:** Production-ready - Centralized search space registry

---

#### analysis/README.md

**Purpose:** Documentation for modern analysis framework

**Content:**
- Analysis approach overview
- Theoretical maximum methodology
- Efficiency ratio explanation
- Usage examples

**Status:** Documentation

---

#### analysis/optimization/README.md

**Purpose:** Documentation for parameter optimization system

**Content:**
- Optuna optimization workflow
- Objective function details
- Search space design
- Best practices

**Status:** Documentation

---

### Production Directory Scripts

#### production/config.py

**Purpose:** Production configuration with updated costs from diagnostic research

**Key Values:**
- Storage cost: 0.005% per day (updated from 0.025%)
- Transaction cost: 0.01% (updated from 0.25%)

**Status:** Production-ready configuration

---

#### production/core/backtest_engine.py

**Purpose:** Production backtesting engine extracted from 04_backtesting_engine.ipynb

**Inputs:**
- prices DataFrame
- prediction_matrices dict
- producer_config dict

**Outputs:** Results dict with trades, daily_state, metrics

**Key Features:**
- Harvest-based inventory (starts at 0, accumulates during harvest)
- Multi-cycle support (handles multiple harvest seasons)
- Force liquidation (365-day max holding)
- Percentage-based costs

**Status:** Production-ready - Extracted from notebook for reuse

---

#### production/core/test_backtest_engine.py

**Purpose:** Unit tests for production backtest engine

**Status:** Active - Testing framework

---

#### production/core/test_with_correct_costs.py

**Purpose:** Validation tests using updated cost assumptions

**Status:** Active - Cost validation

---

#### production/strategies/ (4 modules, 1,900 lines)

**Purpose:** All 9 trading strategies extracted from diagnostics/all_strategies_pct.py

**Modules:**
- `base.py` (76 lines) - Strategy base class
- `indicators.py` (175 lines) - RSI, ADX, CV calculations
- `baseline.py` (423 lines) - 4 baseline strategies
- `prediction.py` (1,174 lines) - 5 prediction strategies
- `__init__.py` (52 lines) - Module exports

**Strategies Implemented:**
- Baseline: Immediate Sale, Equal Batch, Price Threshold, Moving Average
- Prediction: Consensus, Expected Value, Risk-Adjusted, Price Threshold (Predictive), Moving Average (Predictive)

**Key Features:**
- Percentage-based framework (dynamic batch sizing 8-40%)
- 3-tier confidence system (high/medium/low)
- Forced liquidation logic
- Matched pairs design (baseline strategies have predictive equivalents)

**Status:** Production-ready (Completed 2025-11-24)

---

#### production/runners/ (5 modules, 1,446 lines)

**Purpose:** Modular backtest execution system that replicates notebook 05 workflow

**Modules:**
- `data_loader.py` (268 lines) - Load prices from Delta, predictions from pickle
- `strategy_runner.py` (368 lines) - Execute all 9 strategies, analyze results
- `visualization.py` (508 lines) - Generate all 5 chart types
- `result_saver.py` (302 lines) - Save metrics to Delta, detailed results to pickle
- `multi_commodity_runner.py` (393 lines) - Main orchestrator for multi-commodity execution
- `__init__.py` - Module exports
- `README.md` - Complete usage guide and API documentation

**Workflow:**
1. DataLoader: Load prices and prediction matrices
2. StrategyRunner: Execute strategies and calculate metrics
3. VisualizationGenerator: Create 5 chart types
4. ResultSaver: Persist to Delta tables and pickle files
5. MultiCommodityRunner: Orchestrate entire pipeline

**Outputs:**
- Delta tables: Metrics DataFrames in Unity Catalog
- Pickle files: Detailed results dictionaries
- PNG charts: 5 visualization types per commodity-model pair
- CSV files: Cross-commodity comparisons

**Status:** Production-ready with comprehensive test suite (Completed 2025-11-24)

**Documentation:** See `production/runners/README.md` for usage guide

---

#### production/runners/tests/ (6 test files, 2,500+ lines)

**Purpose:** Comprehensive test suite for runners module

**Test Files:**
- `conftest.py` (280 lines) - Shared fixtures and test utilities
- `test_data_loader.py` (500+ lines) - Data loading and validation tests
- `test_strategy_runner.py` (550+ lines) - Strategy execution and metrics tests
- `test_visualization.py` (500+ lines) - Chart generation tests
- `test_result_saver.py` (500+ lines) - Result persistence tests
- `test_integration.py` (450+ lines) - End-to-end workflow tests
- `__init__.py` - Test suite metadata
- `README.md` - Test execution guide

**Coverage:**
- 150+ test cases
- Expected coverage: 93%+
- Execution time: ~30-40 seconds
- Mock-based testing for Spark/Delta operations

**Test Types:**
- Unit tests (80%) - Individual functions with mocked dependencies
- Integration tests (15%) - End-to-end workflows
- Smoke tests (5%) - Databricks deployment validation

**Status:** Complete test suite (Completed 2025-11-24)

**Documentation:** See `production/runners/tests/README.md` for test execution guide

**Note:** For production system phase tracking and status, see `../../MASTER_SYSTEM_PLAN.md` (Phase 2 section)

---

### Databricks Production Testing Scripts

#### production/test_backtest.py

**Purpose:** End-to-end backtest testing on Databricks

**What it tests:**
1. Loading predictions (synthetic_acc90)
2. Running production backtest engine
3. Verifying strategy execution
4. Results persistence

**Configuration:**
- Commodity: coffee (test)
- Model: synthetic_acc90 (known good data)
- Single strategy for speed

---

#### production/test_forecast_loader.py

**Purpose:** Test real forecast loading with sparsity checking

**What it tests:**
1. Discover available model versions
2. Load forecasts from commodity.forecast.distributions
3. Sparsity checking (90%+ date coverage + 730 day minimum)
4. Matrix format transformation
5. Pickle file output

**Sparsity Requirements:**
- Minimum 730 days (2 years) of forecast date range
- Minimum 90% coverage within that range

---

#### production/test_optimizer.py

**Purpose:** Test parameter optimization on Databricks

**What it tests:**
1. Loading price data and predictions
2. Running Optuna optimization
3. Efficiency-based parameter selection
4. Results saving

**Configuration:**
- Commodity: coffee
- Model: synthetic_acc90
- Objective: efficiency (optimizes for efficiency ratio)
- Trials: 5 (minimal for testing)
- Strategy: consensus (single strategy for speed)

**Based on:** `analysis/optimization/run_parameter_optimization.py`

**Note:** Don't use sys.exit() in Databricks jobs - let scripts complete naturally or raise exceptions

---

### Legacy Directory Scripts

#### Legacy/trading_prediction_analysis.py

**Purpose:** Original monolithic script (historical)

**What it is:**
- Pre-dates the split into notebooks 00-10
- Contains full analysis workflow in single Python file
- Uses old data paths and cost assumptions

**Status:** ARCHIVED - Use numbered notebooks (00-10) instead

**Why it exists:**
- Historical reference for original implementation
- Shows evolution of approach
- May contain experimental code

**Should you use it?** NO - Use the numbered notebooks which are:
- Better organized
- More maintainable
- Properly documented
- Actively maintained

---

## 📓 Legacy & Archived Notebooks

### 01_synthetic_predictions_v6.ipynb

**Purpose:** Synthetic prediction generation (6th iteration)

**Key Fix:** Fixed day alignment (100% accuracy = 0% MAPE)

**Status:** SUPERSEDED by v8

**Why superseded:**
- v8 fixes log-normal centering for accurate MAPE targeting
- v8 stores actual future_date to avoid calendar misalignment
- v8 is more accurate and reliable

**Should you use it?** NO - Use `01_synthetic_predictions_v8.ipynb`

---

### 01_synthetic_predictions_v7.ipynb

**Purpose:** Synthetic prediction generation (7th iteration)

**Key Feature:** Saves predictions to volume for download

**Status:** SUPERSEDED by v8

**Why superseded:**
- v8 improves MAPE calibration
- v8 is the current production version

**Should you use it?** NO - Use `01_synthetic_predictions_v8.ipynb`

---

### 01_synthetic_predictions_calibrated.ipynb

**Purpose:** Early attempt at calibrated synthetic predictions

**Status:** SUPERSEDED by v8

**Why superseded:**
- Early version, less sophisticated calibration
- MAPE targeting not as accurate
- v8 incorporates all improvements

**Should you use it?** NO - Use `01_synthetic_predictions_v8.ipynb`

---

### 01_synthetic_predictions.ipynb (Original)

**Purpose:** First version of synthetic prediction generation

**Status:** SUPERSEDED by v8

**Should you use it?** NO - Use `01_synthetic_predictions_v8.ipynb`

---

### trading_prediction_analysis_original_11_11_25.ipynb

**Purpose:** Original monolithic notebook from November 11, 2025

**What it is:**
- 4.4MB notebook containing full analysis workflow in single file
- Predates the split into notebooks 00-10
- Historical snapshot of workflow before modularization

**Status:** ARCHIVED - Use numbered notebooks (00-10) instead

**Why it exists:**
- Original implementation before workflow was modularized
- Useful for understanding evolution of approach
- May contain experimental code or earlier strategy versions
- Historical reference

**Key Differences from Current Workflow:**
- Single monolithic file vs modular notebooks
- May use different cost assumptions
- May have different strategy implementations
- Older prediction generation methods

**Should you use it?** NO - Use the numbered notebooks (00-10) which are:
- Better organized
- More maintainable
- Properly documented
- Actively maintained
- Easier to debug

---

### Legacy/trading_prediction_analysis_multi_model.ipynb

**Purpose:** Multi-model version of trading analysis (historical)

**Status:** ARCHIVED

**What it is:**
- Intermediate version that added multi-model support
- Predates current workflow organization

**Should you use it?** NO - Use current numbered notebooks

---

### diagnostics/diagnostic_16_optuna_with_params.ipynb

**Purpose:** Notebook version of diagnostic_16

**Status:** Active but prefer Python script

**Note:** Use `run_diagnostic_16.py` for automated execution instead of manual notebook

---

### diagnostics/diagnostic_17_paradox_analysis.ipynb

**Purpose:** Notebook version of diagnostic_17

**Status:** Active but prefer Python script

**Note:** Use `run_diagnostic_17.py` for automated execution

---

### diagnostics/diagnostic_100_algorithm_validation.ipynb

**Purpose:** Notebook version of diagnostic_100

**Status:** Active but prefer Python script

**Note:** Use `run_diagnostic_100.py` for automated execution

**Duplicate Note:** Also exists as `diagnostic_100_algorithm_validation.py` (extracted content)

---

## 🔍 Missing Files (Identified Gaps)

### 11_synthetic_accuracy_comparison.ipynb

**Status:** NEEDED but not yet created

**Purpose:** Validate monotonicity of performance across accuracy levels

**What it should do:**
1. Run all strategies on all accuracy levels (60%, 70%, 80%, 90%, 100%)
2. Compare earnings across accuracy levels in single dashboard
3. Generate monotonicity validation plots
4. Verify: 60% < 70% < 80% < 90% < 100% (in earnings)
5. Identify any accuracy levels that violate expectations

**Why it's critical:**
- Failure to show improvement with accuracy indicates fundamental issues
- Could reveal data leakage, strategy bugs, or cost structure problems
- Essential validation step before trusting workflow results

**Expected output:**
- Monotonicity validation charts
- Accuracy-performance curves
- Statistical significance of accuracy improvements
- Console warnings if monotonicity fails

**Recommendation:** CREATE URGENTLY - This is a critical validation gap

---

### Shared Config Module

**Status:** PARTIALLY EXISTS (multiple config files, not consolidated)

**Current State:**
- `00_setup_and_config.ipynb` - Notebook-based config
- `production/config.py` - Production config (different costs)
- `diagnostics/cost_config_small_farmer.py` - Alternative config

**Problem:**
- Different configs across different components
- Hard to maintain consistency
- Cost assumptions differ (0.025% vs 0.005% storage)

**What's needed:**
- Single source of truth: `shared_config.py`
- Import by all notebooks and scripts
- Versioned configurations (baseline, production, small_farmer)

**Recommendation:** Consolidate configs into single module

---

### Automated Workflow Orchestration

**Status:** NOT YET CREATED

**What's needed:**
- `run_full_workflow.py` - Master automation script
- Runs all notebooks in sequence with proper dependencies
- Handles errors and retries
- Downloads all results
- Generates consolidated report

**Why it's needed:**
- Current workflow requires manual execution of 10+ notebooks
- Error-prone (easy to skip steps)
- Time-consuming (40+ hours of human time)
- Not reproducible

**See:** AUTOMATION MIGRATION PLAN section in this document for details

---

## 📋 Documentation Files Inventory

### DATABRICKS_ACCESS_NOTES.md

**Purpose:** How to access Databricks and avoid common mistakes

**Key Topics:**
- Notebooks run IN Databricks (not locally)
- Volume vs ephemeral directory risk
- Using databricks CLI to download files
- Pandas version compatibility issues

**Status:** Active - Essential reference

---

### EXECUTIVE_SUMMARY.md

**Purpose:** High-level summary of findings (historical)

**Status:** May be outdated - created early in project

**Recommendation:** Review and update or archive

---

### RESULTS_ANALYSIS_CRITICAL_FINDINGS.md

**Purpose:** Key findings from analysis (historical)

**Status:** May be outdated - created during initial analysis

**Recommendation:** Review and update or archive

---

### WORKFLOW_ANALYSIS_AND_FINDINGS.md

**Purpose:** Workflow documentation and findings (historical)

**Status:** May be outdated - created during workflow development

**Note:** Much of this content has been incorporated into FILE_INVENTORY.md

**Recommendation:** Archive or consolidate into FILE_INVENTORY.md

---

### CONSOLIDATED_REVIEW_PROPOSAL.md

**Purpose:** Unknown (need to inspect)

**Status:** Unknown

**Recommendation:** Review and document or remove

---

### FILE_INVENTORY.md (This File)

**Purpose:** Complete inventory of all notebooks, scripts, and outputs for integration with diagnostics

**Status:** CURRENT (updated 2025-11-24)

**Last Updated:** 2025-11-24
**Owner:** Claude Code
**Purpose:** Complete inventory for diagnostic integration planning
**Next Step:** Begin automation migration after diagnostic results analyzed
