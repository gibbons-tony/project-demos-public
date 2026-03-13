# Trading Agent Dashboard - Complete Data Analysis

**Date:** 2025-01-11
**Purpose:** Document all notebook outputs, current data storage, and design comprehensive data structure for dashboard

---

## 1. Current Notebook Data Storage (Cell 7)

### 1.1 Main Results Storage Structure

**Variable: `all_commodity_results`**

Currently stored as (lines in Cell 7):
```python
all_commodity_results[CURRENT_COMMODITY][CURRENT_MODEL] = {
    'commodity': CURRENT_COMMODITY,
    'model_version': CURRENT_MODEL,
    'results_df': results_df,           # DataFrame with summary metrics
    'results_dict': results_dict,        # Dict with detailed backtest results
    'best_baseline': best_baseline,      # Series from results_df
    'best_prediction': best_prediction,  # Series from results_df
    'best_overall': best_overall,        # Series from results_df
    'earnings_diff': earnings_diff,      # float
    'pct_diff': pct_diff,               # float
    'prices': prices,                    # DataFrame with date, price
    'config': commodity_config           # Dict with costs, harvest windows
}
```

### 1.2 Strategy Results Detail

**Variable: `results_dict`** (per strategy)

```python
results_dict[strategy_name] = {
    # From BacktestEngine.run()
    'daily_state': DataFrame,  # Columns: day, date, inventory, daily_storage_cost
    'trades': List[Dict],      # Each trade: {date, day, price, amount, revenue, transaction_cost, reason}
    'total_revenue': float,
    'total_transaction_costs': float,
    'total_storage_costs': float,
    'net_earnings': float,
    'final_inventory': float
}
```

### 1.3 Summary Metrics

**Variable: `results_df`** (DataFrame with one row per strategy)

Columns from `calculate_metrics()`:
- `strategy`: str
- `net_earnings`: float
- `total_revenue`: float
- `total_costs`: float
- `total_transaction_costs`: float
- `total_storage_costs`: float
- `avg_sale_price`: float
- `n_trades`: int
- `inventory_sold_pct`: float
- `avg_days_held`: float
- `type`: str ('Baseline' or 'Prediction')
- `commodity`: str

---

## 2. Chart-by-Chart Data Requirements

### Cell 7 Charts (6 charts per commodity×model)

#### Chart 7.1: Net Earnings by Strategy
**File:** `net_earnings_{commodity}.png`
**Data Source:** `results_df`
**Required Fields:**
- `results_df['strategy']` - strategy names
- `results_df['net_earnings']` - y-axis values
- `results_df['type']` - for coloring (blue=baseline, orange=prediction)

#### Chart 7.2: Trading Timeline
**File:** `trading_timeline_{commodity}.png`
**Data Source:** `prices` + `results_dict[strategy]['trades']` for all strategies
**Required Fields:**
- `prices['date']` - x-axis (background line)
- `prices['price']` - y-axis (background line)
- For each strategy:
  - `trades[i]['date']` - scatter x-position
  - `trades[i]['price']` - scatter y-position
  - `trades[i]['amount']` - marker size

#### Chart 7.3: Cumulative Total Revenue (Without Costs)
**File:** `total_revenue_no_costs_{commodity}.png`
**Data Source:** `results_dict[strategy]['daily_state']` + `trades`
**Required Fields:**
- For each strategy:
  - `daily_state['date']` - x-axis
  - Computed: cumulative sum of `trades['revenue']` by day - y-axis

**Computation Logic:**
```python
cumulative_revenue = []
running_revenue = 0
for row in daily_state:
    if row['day'] in trades_by_day:
        running_revenue += trades_by_day[row['day']]['revenue']
    cumulative_revenue.append(running_revenue)
```

#### Chart 7.4: Cumulative Net Revenue ⭐ MAIN CHART
**File:** `cumulative_returns_{commodity}.png`
**Data Source:** `results_dict[strategy]['daily_state']` + `trades`
**Required Fields:**
- For each strategy:
  - `daily_state['date']` - x-axis
  - Computed: cumulative (revenue - transaction_costs - storage_costs) - y-axis

**Computation Logic:**
```python
cumulative_net = []
running_revenue = 0
running_transaction = 0
running_storage = 0
for row in daily_state:
    if row['day'] in trades_by_day:
        running_revenue += trades_by_day[row['day']]['revenue']
        running_transaction += trades_by_day[row['day']]['transaction_cost']
    running_storage += row['daily_storage_cost']
    net = running_revenue - running_transaction - running_storage
    cumulative_net.append(net)
```

#### Chart 7.5: Inventory Drawdown
**File:** `inventory_drawdown_{commodity}.png`
**Data Source:** `results_dict[strategy]['daily_state']`
**Required Fields:**
- For each strategy:
  - `daily_state['date']` - x-axis
  - `daily_state['inventory']` - y-axis

#### Chart 7.6: Cross-Commodity Comparison
**File:** `cross_commodity_comparison.png`
**Data Source:** `all_commodity_results` (after all commodities/models processed)
**Required Fields:**
- `commodity_names` - x-axis labels
- For each commodity:
  - `best_baseline['net_earnings']` - bar height
  - `best_prediction['net_earnings']` - bar height
  - `earnings_diff` - advantage value

---

### Cell 8 Data Outputs (No charts, but powers Cell 11)

#### Statistical Tests
**Storage:** Saved to pickle/CSV files
**Data Computed:**

**Pairwise Comparisons:**
```python
{
    'strategy_a': str,  # e.g., "Consensus"
    'strategy_b': str,  # e.g., "Price Threshold"
    'earnings_diff': float,
    'p_value': float,
    'significant': bool,  # p < 0.05
    'cohens_d': float,
    'significance_stars': str  # "", "*", "**", "***"
}
```

**Bootstrap Confidence Intervals:**
```python
{
    'strategy': str,
    'mean': float,
    'ci_lower': float,  # 2.5th percentile
    'ci_upper': float,  # 97.5th percentile
    'std': float,
    'n_bootstrap': 1000
}
```

**Data Source for Bootstrap:**
- `results_dict[strategy]['daily_state']` - used to resample portfolio values
- Resamples with replacement 1000 times

---

### Cell 9 Chart: Feature Importance

#### Chart 9.1: Feature Analysis (2 subplots)
**File:** `feature_importance_{commodity}.png`
**Data Source:** Computed from `prediction_matrices` + `prices`

**Subplot 1: Feature Importance**
**Required Fields:**
```python
{
    'features': [
        'median_predicted_return',
        'prediction_agreement',
        'prediction_std',
        'rsi_predicted',
        'adx_predicted',
        'prediction_confidence',
        'current_momentum'
    ],
    'importances': [0.28, 0.22, 0.18, 0.12, 0.10, 0.07, 0.03],
    'model_score': 0.73  # R^2 from Random Forest
}
```

**Subplot 2: Correlation Heatmap**
**Required Fields:**
```python
{
    'feature_names': [...],  # Same as above
    'correlation_matrix': [
        [1.00, 0.65, -0.45, 0.32, ...],
        [0.65, 1.00, -0.38, 0.28, ...],
        ...
    ]  # 7×7 matrix
}
```

**Data Extraction:**
- Requires running `extract_features()` for each prediction date
- Builds feature DataFrame
- Trains RandomForestRegressor on features → actual returns
- Extracts feature_importances_ and correlation matrix

---

### Cell 10 Chart: Sensitivity Analysis

#### Chart 10.1: Sensitivity Analysis (4 subplots)
**File:** `sensitivity_analysis_{commodity}.png`

**Subplot 1: Consensus Parameter Heatmap**
**Data Source:** `run_sensitivity_consensus()` output
**Required Fields:**
```python
{
    'consensus_thresholds': [0.5, 0.6, 0.7, 0.8],
    'min_returns': [0.03, 0.05, 0.08, 0.10],
    'net_earnings_matrix': [
        [120000, 122000, 125430, 123000],  # min_return=0.03
        [118000, 125000, 128000, 124000],  # min_return=0.05
        [115000, 122000, 126000, 121000],  # min_return=0.08
        [110000, 118000, 120000, 115000]   # min_return=0.10
    ]
}
```

**Subplot 2 & 3: Cost Sensitivity**
**Data Source:** `run_cost_sensitivity()` output
**Required Fields:**
```python
# Transaction costs
{
    'cost_multipliers': [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    'best_prediction_earnings': [130000, 128000, 125430, 122000, 118000, 110000],
    'best_baseline_earnings': [115000, 112000, 110000, 107000, 103000, 95000]
}

# Storage costs (same structure)
{
    'cost_multipliers': [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    'best_prediction_earnings': [145000, 135000, 125430, 115000, 105000, 85000],
    'best_baseline_earnings': [125000, 117000, 110000, 102000, 95000, 80000]
}
```

**Subplot 4: Prediction Advantage**
**Computed from above:**
```python
{
    'cost_multipliers': [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    'transaction_advantage': [15000, 16000, 15430, 15000, 15000, 15000],  # pred - base
    'storage_advantage': [20000, 18000, 15430, 13000, 10000, 5000]
}
```

---

### Cell 11 Chart: Main Dashboard (9 subplots in 3×3 grid)

#### Chart 11: Dashboard Figure
**File:** `dashboard_{commodity}.png`
**Data Source:** Aggregates from Cells 7, 8, 9, 10

**Plot 1: Portfolio Value Over Time**
**Data Source:** Computed from `results_dict[strategy]['daily_state']`
**Required Fields:**
```python
# For each strategy
{
    'dates': [...],
    'portfolio_value': [...]  # Cumulative net earnings (same as Chart 7.4)
}
```

**Plot 2: Net Earnings with Significance Stars**
**Data Source:** `results_df` + Cell 8 statistical tests
**Required Fields:**
```python
# For each strategy
{
    'strategy': str,
    'net_earnings': float,
    'type': str,  # for coloring
    'significance_stars': str  # from statistical tests vs best baseline
}
```

**Plot 3: Feature Importance**
**Data Source:** Cell 9 feature analysis
**Required Fields:** Same as Chart 9.1 Subplot 1

**Plot 4: Bootstrap Confidence Intervals**
**Data Source:** Cell 8 bootstrap results
**Required Fields:**
```python
# For each strategy
{
    'strategy': str,
    'mean': float,
    'ci_lower': float,
    'ci_upper': float,
    'type': str  # for coloring
}
```

**Plot 5 & 6: Cost Sensitivity**
**Data Source:** Cell 10 sensitivity analysis
**Required Fields:** Same as Chart 10.1 Subplots 2 & 3

**Plot 7: Prediction Advantage**
**Data Source:** Cell 10 sensitivity analysis
**Required Fields:** Same as Chart 10.1 Subplot 4

**Plot 8: Parameter Sensitivity Heatmap**
**Data Source:** Cell 10 sensitivity analysis
**Required Fields:** Same as Chart 10.1 Subplot 1

**Plot 9: Summary Table**
**Data Source:** `results_df`
**Required Fields:**
```python
# Top 5 strategies by net_earnings
[
    {
        'strategy': str,
        'net_earnings': float,
        'avg_sale_price': float,
        'n_trades': int
    },
    ...  # 5 rows
]
```

---

### Cell 12 Charts: Three-Scenario Analysis

#### Chart 12.1: Scenario Analysis (8 subplots)
**File:** `scenario_analysis_{scenario}_{commodity}.png`
**Data Source:** Runs backtest for 3 specific scenarios (e.g., different initial inventory levels)

**Required Fields:**
- Same structure as main results, but for each scenario
- Allows comparison across scenarios

#### Chart 12.2: Cross-Commodity Scenario
**File:** `cross_commodity_scenario_{scenario}.png`
**Required Fields:**
- Similar to Chart 7.6 but for specific scenario comparison

---

## 3. Comprehensive Data Structure Design

### 3.1 Top-Level Structure

```json
{
  "metadata": {
    "export_timestamp": "2025-01-11T15:30:00Z",
    "notebook_version": "v2.0",
    "total_commodities": 2,
    "total_models": 15
  },

  "commodities": {
    "coffee": {
      "models": {
        "sarimax_auto_weather_v1": { /* ModelData */ },
        "prophet_baseline_v1": { /* ModelData */ },
        ...
      },
      "config": { /* CommodityConfig */ }
    },
    "sugar": { ... }
  }
}
```

### 3.2 ModelData Structure (per commodity×model)

```json
{
  "metadata": {
    "commodity": "coffee",
    "model_version": "sarimax_auto_weather_v1",
    "run_date": "2025-01-11",
    "n_prediction_dates": 42,
    "n_paths": 2000,
    "forecast_horizon": 14,
    "price_stats": {
      "min": 150.25,
      "max": 350.75,
      "mean": 225.30,
      "date_range_start": "2023-01-01",
      "date_range_end": "2024-12-31"
    }
  },

  "strategies": {
    "Consensus": { /* StrategyData */ },
    "Expected Value": { /* StrategyData */ },
    "Risk-Adjusted": { /* StrategyData */ },
    "Price Threshold": { /* StrategyData */ },
    "Moving Average": { /* StrategyData */ },
    "Immediate Sale": { /* StrategyData */ },
    "Equal Batch": { /* StrategyData */ },
    "Price Threshold Predictive": { /* StrategyData */ },
    "Moving Average Predictive": { /* StrategyData */ }
  },

  "statistical_analysis": { /* StatisticalData */ },
  "sensitivity_analysis": { /* SensitivityData */ },
  "feature_analysis": { /* FeatureData */ },

  "best_performers": {
    "best_overall": {
      "strategy": "Expected Value",
      "net_earnings": 125430.50
    },
    "best_baseline": {
      "strategy": "Price Threshold",
      "net_earnings": 110000.00
    },
    "best_prediction": {
      "strategy": "Expected Value",
      "net_earnings": 125430.50
    },
    "prediction_advantage_usd": 15430.50,
    "prediction_advantage_pct": 14.0
  }
}
```

### 3.3 StrategyData Structure

```json
{
  "summary_metrics": {
    "net_earnings": 125430.50,
    "total_revenue": 450200.00,
    "total_costs": 324769.50,
    "total_transaction_costs": 12500.00,
    "total_storage_costs": 312269.50,
    "avg_sale_price": 245.75,
    "n_trades": 42,
    "inventory_sold_pct": 98.5,
    "avg_days_held": 65.3,
    "final_inventory": 15.0,
    "strategy_type": "prediction"
  },

  "time_series": {
    "dates": ["2023-01-15", "2023-01-16", ...],
    "cumulative_net_revenue": [0, -500, 1200, 5430, ...],
    "cumulative_total_revenue": [0, 15000, 45000, ...],
    "inventory": [1000, 975, 950, ...],
    "daily_storage_cost": [100, 97.5, 95, ...],
    "portfolio_value": [0, -500, 1200, 5430, ...]
  },

  "trades": [
    {
      "date": "2023-01-20",
      "day": 5,
      "price": 245.30,
      "amount": 25.5,
      "revenue": 6255.15,
      "transaction_cost": 125.10,
      "reason": "Price above MA(14) by 5.2%",
      "batch_pct": 2.55
    },
    ...
  ],

  "trade_statistics": {
    "total_trades": 42,
    "avg_trade_size": 23.8,
    "largest_trade": 150.0,
    "smallest_trade": 5.0,
    "median_trade_size": 20.0,
    "trades_per_month": 3.5
  }
}
```

### 3.4 StatisticalData Structure

```json
{
  "pairwise_comparisons": [
    {
      "strategy_a": "Consensus",
      "strategy_b": "Price Threshold",
      "earnings_diff": 15430.50,
      "pct_diff": 14.0,
      "p_value": 0.023,
      "significant": true,
      "significance_stars": "**",
      "cohens_d": 0.65,
      "effect_size": "medium"
    },
    ...
  ],

  "bootstrap_confidence_intervals": [
    {
      "strategy": "Consensus",
      "mean": 125430.50,
      "ci_lower": 118200.30,
      "ci_upper": 132450.80,
      "std": 4250.15,
      "n_bootstrap": 1000,
      "strategy_type": "prediction"
    },
    ...
  ],

  "best_vs_baseline": {
    "best_prediction_strategy": "Expected Value",
    "best_baseline_strategy": "Price Threshold",
    "p_value": 0.012,
    "significant": true,
    "earnings_advantage": 15430.50,
    "pct_advantage": 14.0
  }
}
```

### 3.5 SensitivityData Structure

```json
{
  "transaction_costs": {
    "cost_multipliers": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    "best_prediction_earnings": [130000, 128000, 125430, 122000, 118000, 110000],
    "best_baseline_earnings": [115000, 112000, 110000, 107000, 103000, 95000],
    "advantage": [15000, 16000, 15430, 15000, 15000, 15000],
    "best_prediction_strategy": "Expected Value",
    "best_baseline_strategy": "Price Threshold"
  },

  "storage_costs": {
    "cost_multipliers": [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    "best_prediction_earnings": [145000, 135000, 125430, 115000, 105000, 85000],
    "best_baseline_earnings": [125000, 117000, 110000, 102000, 95000, 80000],
    "advantage": [20000, 18000, 15430, 13000, 10000, 5000],
    "best_prediction_strategy": "Expected Value",
    "best_baseline_strategy": "Price Threshold"
  },

  "parameter_sensitivity": {
    "strategy": "Consensus",
    "parameter_grid": {
      "consensus_thresholds": [0.5, 0.6, 0.7, 0.8],
      "min_returns": [0.03, 0.05, 0.08, 0.10],
      "net_earnings_matrix": [
        [120000, 122000, 125430, 123000],
        [118000, 125000, 128000, 124000],
        [115000, 122000, 126000, 121000],
        [110000, 118000, 120000, 115000]
      ]
    },
    "optimal_params": {
      "consensus_threshold": 0.7,
      "min_return": 0.05,
      "net_earnings": 128000
    }
  }
}
```

### 3.6 FeatureData Structure

```json
{
  "feature_importance": {
    "features": [
      "median_predicted_return",
      "prediction_agreement",
      "prediction_std",
      "rsi_predicted",
      "adx_predicted",
      "prediction_confidence",
      "current_momentum"
    ],
    "importances": [0.28, 0.22, 0.18, 0.12, 0.10, 0.07, 0.03],
    "model_type": "RandomForestRegressor",
    "n_samples": 42,
    "r2_score": 0.73,
    "training_params": {
      "n_estimators": 100,
      "max_depth": 10
    }
  },

  "feature_correlations": {
    "feature_names": [
      "median_predicted_return",
      "prediction_agreement",
      "prediction_std",
      "rsi_predicted",
      "adx_predicted",
      "prediction_confidence",
      "current_momentum"
    ],
    "correlation_matrix": [
      [1.00, 0.65, -0.45, 0.32, 0.15, -0.22, 0.58],
      [0.65, 1.00, -0.38, 0.28, 0.12, -0.18, 0.45],
      [-0.45, -0.38, 1.00, -0.15, -0.08, 0.35, -0.30],
      [0.32, 0.28, -0.15, 1.00, 0.42, -0.10, 0.25],
      [0.15, 0.12, -0.08, 0.42, 1.00, -0.05, 0.18],
      [-0.22, -0.18, 0.35, -0.10, -0.05, 1.00, -0.15],
      [0.58, 0.45, -0.30, 0.25, 0.18, -0.15, 1.00]
    ]
  },

  "feature_statistics": {
    "median_predicted_return": {"mean": 0.045, "std": 0.032, "min": -0.02, "max": 0.15},
    "prediction_agreement": {"mean": 0.72, "std": 0.18, "min": 0.35, "max": 0.95},
    "prediction_std": {"mean": 0.08, "std": 0.04, "min": 0.01, "max": 0.20},
    "rsi_predicted": {"mean": 52.3, "std": 15.2, "min": 15.0, "max": 85.0},
    "adx_predicted": {"mean": 25.8, "std": 12.5, "min": 5.0, "max": 65.0},
    "prediction_confidence": {"mean": 0.68, "std": 0.15, "min": 0.30, "max": 0.95},
    "current_momentum": {"mean": 0.02, "std": 0.05, "min": -0.15, "max": 0.20}
  }
}
```

### 3.7 CommodityConfig Structure

```json
{
  "commodity": "coffee",
  "initial_inventory": 1000,
  "storage_cost_pct_per_day": 0.0002,
  "transaction_cost_pct": 0.02,
  "forecast_horizon": 14,
  "harvest_windows": [
    {"start_month": 10, "end_month": 3, "description": "Main harvest"},
    {"start_month": 4, "end_month": 5, "description": "Mitaca harvest"}
  ],
  "currency": "USD",
  "unit": "ton"
}
```

---

## 4. Data Extraction Strategy

### 4.1 Where Data Currently Lives

**In Memory (Cell 7 execution):**
- `all_commodity_results` - main results container
- `results_df` - summary metrics DataFrame
- `results_dict` - detailed backtest results dict
- `prices` - price history DataFrame

**Saved to Files:**
- `results.csv` or Delta table - summary metrics
- `results_detailed.pkl` - pickled results_dict
- Chart PNG files (11 files)

**Computed in Cell 8:**
- Statistical test results - saved to pickle
- Bootstrap CIs - saved to CSV

**Computed in Cell 9:**
- Feature importance - computed but not saved as structured data
- Correlation matrix - computed but not saved

**Computed in Cell 10:**
- Sensitivity analysis - computed but not saved as structured data

### 4.2 What Needs to be Extracted

**From Cell 7:**
- ✅ `results_df` - already saved
- ✅ `results_dict` - already saved (pickle)
- ❌ Time series data (cumulative revenue, portfolio value) - COMPUTED ON FLY, NOT SAVED
- ❌ Best performers summary - COMPUTED, NOT SAVED
- ❌ Cross-commodity comparison - COMPUTED, NOT SAVED

**From Cell 8:**
- ✅ Statistical tests - saved
- ✅ Bootstrap CIs - saved
- ❌ Organized pairwise comparisons with significance stars - COMPUTED, NOT SAVED CLEANLY

**From Cell 9:**
- ❌ Feature importance - COMPUTED, NOT SAVED
- ❌ Correlation matrix - COMPUTED, NOT SAVED

**From Cell 10:**
- ❌ Sensitivity analysis results - COMPUTED, NOT SAVED
- ❌ Parameter grids - COMPUTED, NOT SAVED

### 4.3 Extraction Implementation

Need to add export function at end of Cell 7 (or new Cell 13):

```python
def export_dashboard_data(commodity, model, results_df, results_dict,
                          stat_results, sensitivity_results, feature_results,
                          best_performers, prices, config):
    """
    Export all data needed for dashboard in structured JSON format
    """

    # Build complete data structure
    data = {
        "metadata": { ... },
        "strategies": { ... },
        "statistical_analysis": { ... },
        "sensitivity_analysis": { ... },
        "feature_analysis": { ... },
        "best_performers": { ... }
    }

    # Save as JSON
    output_path = f'/dbfs/FileStore/trading_agent/dashboard_data/{commodity}/{model}/data.json'
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)  # default=str for dates

    return output_path
```

---

## 5. Size Estimates

**Per commodity×model:**
- Metadata: ~0.5KB
- 9 strategies × (metrics 1KB + time_series 15KB + trades 5KB): ~190KB
- Statistical analysis: ~30KB
- Sensitivity analysis: ~40KB
- Feature analysis: ~10KB
- Best performers: ~1KB

**Total per model:** ~270KB
**Total for 15 models:** ~4MB

**Acceptable for:**
- JSON file storage
- Git repository (if needed)
- Dashboard lazy loading
- Browser caching

---

## 6. Dashboard Loading Strategy

### Phase 1: Initial Load (Fast)
- Load metadata for all models
- Display model leaderboard
- User selects commodity + model

### Phase 2: Model Data Load (Lazy)
- Load single JSON file for selected model (~270KB)
- Parse into data structures
- Ready to render any sub-tab

### Phase 3: Chart Rendering (On-Demand)
- When user clicks sub-tab, render only those charts
- Reuse data already loaded in Phase 2

### Phase 4: Model Switching
- Load new model's JSON file
- Update all visible charts
- Cache loaded models in memory

---

## 7. Next Steps

1. **Implement export function** in notebook Cell 13
2. **Run notebook** for all models to generate JSON files
3. **Validate data completeness** - ensure all 20+ charts can be recreated
4. **Build dashboard** using exported JSON files
5. **Test end-to-end** - notebook run → data export → dashboard display

---

Last Updated: 2025-01-11
