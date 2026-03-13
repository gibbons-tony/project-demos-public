# Trading Agent Dashboard - Implementation Plan

**Created:** 2025-11-10
**Status:** Planning Phase

## Overview

Migrate `trading_prediction_analysis.py` to use Unity Catalog table `commodity.forecast.distributions`, add multi-model analysis loops, and create an interactive dashboard for visualizing trading backtest results across all models.

---

## Current State Analysis

### Existing Charts in trading_prediction_analysis.py
1. **Earnings Chart** - Strategy performance comparison
2. **Timeline Chart** - Trade execution timeline with price history
3. **Revenue Chart** - Gross revenue over time
4. **Cumulative Returns Chart** - Net revenue after costs
5. **Inventory/Drawdown Chart** - Inventory levels over time
6. **Cross-Commodity Comparison** - Multi-commodity performance
7. **Feature Importance Chart** - What drives strategy performance
8. **Sensitivity Analysis Charts** - Parameter sensitivity (4 subplots)
9. **Comprehensive Dashboard** - 9-panel master dashboard

### Available Models
**Coffee (10 models):**
- arima_111_v1, arima_v1
- prophet_v1
- random_walk_v1, random_walk_baseline, random_walk_v1_test
- sarimax_auto_weather_v1, sarimax_weather_v1
- xgboost_weather_v1
- naive_baseline

**Sugar (5 models):**
- arima_111_v1
- prophet_v1
- random_walk_v1
- sarimax_auto_weather_v1
- xgboost_weather_v1

### Current Data Source Issue
- **Old:** Reading CSV files from `/Volumes/commodity/silver/{commodity}_forecast_volume/distributions/*.csv`
- **New:** Should query `commodity.forecast.distributions` Delta table in Unity Catalog

---

## Implementation Phases

## Phase 1: Data Source Migration 🔧

### 1.1 Create Data Access Layer
**File:** `trading_agent/data_access/forecast_loader.py`

**Purpose:** Centralized functions to load forecast data from Unity Catalog

**Key Functions:**
```python
def get_available_models(commodity, connection):
    """Query distinct models for a commodity"""

def load_forecast_distributions(commodity, model_version, connection,
                                start_date=None, end_date=None):
    """Load distribution paths for specific model"""

def load_all_models(commodity, connection):
    """Load forecasts for all available models"""
```

### 1.2 Update Configuration
**File:** `trading_agent/commodity_prediction_analysis/config.py`

Extract configuration from notebook into standalone Python file:
- Keep COMMODITY_CONFIGS
- Keep BASELINE_PARAMS and PREDICTION_PARAMS
- Keep ANALYSIS_CONFIG
- **Remove:** File path configurations
- **Add:** Database connection parameters

### 1.3 Refactor Data Loading in Main Script
**File:** `trading_agent/commodity_prediction_analysis/trading_prediction_analysis.py`

**Changes:**
- Replace lines 3-18 (CSV file reading) with SQL queries
- Remove `get_real_prediction_path()` function (lines 113-115)
- Update prediction loading to use new data access layer
- Ensure data format matches existing processing logic

---

## Phase 2: Multi-Model Analysis Loop 🔄

### 2.1 CRITICAL: Nested Loop Structure

**Current Code Structure (PROBLEM):**
```python
# Current: Only loops through commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():  # coffee, sugar
    # Load data (uses hardcoded model or single CSV file)
    # Run analysis
    # Generate charts
```

**New Code Structure (SOLUTION):**
```python
# NEW: Nested loop through commodities AND models
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():  # coffee, sugar
    # Query available models for this commodity
    available_models = get_available_models(CURRENT_COMMODITY, connection)

    for CURRENT_MODEL in available_models:  # arima_111_v1, prophet_v1, etc.
        print(f"\n{'='*80}")
        print(f"ANALYZING: {CURRENT_COMMODITY.upper()} - {CURRENT_MODEL}")
        print(f"{'='*80}\n")

        # Load forecast distributions for THIS (commodity, model) combination
        prediction_matrices = load_forecast_distributions(
            commodity=CURRENT_COMMODITY,
            model_version=CURRENT_MODEL,
            connection=connection
        )

        # Run backtest with these predictions
        results = run_backtest_analysis(
            commodity_config=COMMODITY_CONFIGS[CURRENT_COMMODITY],
            prediction_matrices=prediction_matrices,
            prices=prices
        )

        # Store results with both commodity and model keys
        all_results[CURRENT_COMMODITY][CURRENT_MODEL] = results
```

**Total Iterations:**
- Coffee: 10 models
- Sugar: 5 models
- **Total: 15 full backtest runs**

### 2.2 Create Model Iterator
**File:** `trading_agent/analysis/model_runner.py`

**Purpose:** Run backtests across all models for all commodities

**Key Functions:**
```python
def get_available_models(commodity, connection):
    """
    Query distinct model versions for a specific commodity.

    Args:
        commodity: str - 'Coffee' or 'Sugar'
        connection: Databricks SQL connection

    Returns:
        list of model_version strings

    Example:
        >>> get_available_models('Coffee', conn)
        ['arima_111_v1', 'prophet_v1', 'sarimax_auto_weather_v1', ...]
    """
    cursor = connection.cursor()
    cursor.execute("""
        SELECT DISTINCT model_version
        FROM commodity.forecast.distributions
        WHERE commodity = ?
        ORDER BY model_version
    """, [commodity])
    return [row[0] for row in cursor.fetchall()]


def run_analysis_for_all_models(commodity, connection, config):
    """
    Run complete backtest analysis for all available models of a commodity.

    Args:
        commodity: str - 'coffee' or 'sugar'
        connection: Databricks SQL connection
        config: dict - Configuration parameters

    Returns:
        dict of {model_version: results}
    """
    results_by_model = {}

    # Get all available models
    models = get_available_models(commodity.capitalize(), connection)

    print(f"\n{commodity.upper()}: Found {len(models)} models to analyze")
    print(f"Models: {', '.join(models)}\n")

    # Run analysis for each model
    for model in models:
        print(f"\n{'='*80}")
        print(f"PROCESSING: {commodity.upper()} - {model}")
        print(f"{'='*80}\n")

        try:
            # Load predictions for this model
            predictions = load_forecast_distributions(
                commodity=commodity.capitalize(),
                model_version=model,
                connection=connection
            )

            # Run backtest
            backtest_results = run_backtest_with_predictions(
                commodity_config=config,
                prediction_matrices=predictions
            )

            results_by_model[model] = backtest_results
            print(f"✓ Completed {commodity.upper()} - {model}")

        except Exception as e:
            print(f"✗ Error processing {commodity.upper()} - {model}: {e}")
            results_by_model[model] = None

    return results_by_model


def compare_model_performance(results_dict):
    """
    Compare performance metrics across all models.

    Args:
        results_dict: nested dict {commodity: {model: results}}

    Returns:
        DataFrame with comparison metrics
    """
    comparison_rows = []

    for commodity, models in results_dict.items():
        for model, results in models.items():
            if results is None:
                continue

            comparison_rows.append({
                'commodity': commodity,
                'model': model,
                'net_earnings': results['metrics']['net_earnings'],
                'gross_revenue': results['metrics']['gross_revenue'],
                'n_trades': results['metrics']['n_trades'],
                'avg_sale_price': results['metrics']['avg_sale_price']
            })

    return pd.DataFrame(comparison_rows)
```

### 2.3 Results Storage Structure

**New Nested Structure:**
```python
all_results = {
    'coffee': {
        'arima_111_v1': {
            'strategy_results': {
                'Consensus': {...},
                'Risk-Adjusted': {...},
                'Moving Average': {...},
                # ... all 9 strategies
            },
            'charts': {
                'cumulative_returns': <plot_data>,
                'timeline': <plot_data>,
                # ... all charts
            },
            'metrics': {
                'net_earnings': 12345.67,
                'gross_revenue': 45678.90,
                'n_trades': 42,
                # ... all metrics
            },
            'statistical_results': {...},
            'feature_analysis': {...},
            'sensitivity_results': {...}
        },
        'prophet_v1': {
            # Same structure as above
        },
        # ... all 10 coffee models
    },
    'sugar': {
        'arima_111_v1': {...},
        'prophet_v1': {...},
        # ... all 5 sugar models
    }
}
```

**Access Pattern Examples:**
```python
# Get results for specific commodity and model
coffee_prophet = all_results['coffee']['prophet_v1']

# Get all models for a commodity
coffee_models = all_results['coffee'].keys()

# Compare net earnings across all coffee models
coffee_earnings = {
    model: results['metrics']['net_earnings']
    for model, results in all_results['coffee'].items()
}
```

### 2.4 Update Main Analysis Logic

**Key Changes Required:**

1. **Wrap analysis in nested loop:**
   ```python
   # OLD (single commodity loop)
   for CURRENT_COMMODITY in ['coffee', 'sugar']:
       run_analysis(CURRENT_COMMODITY)

   # NEW (nested commodity + model loop)
   for CURRENT_COMMODITY in ['coffee', 'sugar']:
       for CURRENT_MODEL in get_available_models(CURRENT_COMMODITY):
           run_analysis(CURRENT_COMMODITY, CURRENT_MODEL)
   ```

2. **Update result storage to include model key:**
   ```python
   # OLD
   results_dict[CURRENT_COMMODITY] = {...}

   # NEW
   results_dict[CURRENT_COMMODITY][CURRENT_MODEL] = {...}
   ```

3. **Add model identifier to all output files:**
   ```python
   # OLD
   output_path = f"{BASE_PATH}/cumulative_returns_{commodity}.png"

   # NEW
   output_path = f"{BASE_PATH}/cumulative_returns_{commodity}_{model}.png"
   ```

4. **Add model comparison section (new):**
   ```python
   # After all models complete, compare performance
   comparison_df = compare_models_within_commodity(
       all_results[CURRENT_COMMODITY]
   )
   ```

---

## Phase 3: Interactive Dashboard Development 📊

### 3.1 Dashboard Framework Selection

**Recommendation: Plotly Dash**

**Why?**
- ✅ Native integration with Databricks
- ✅ Rich interactive components
- ✅ Easy to deploy within Databricks Apps
- ✅ Python-based (matches existing codebase)
- ✅ Great for financial dashboards

**Alternative:** Streamlit (simpler but less customizable)

### 3.2 Dashboard Architecture

**File Structure:**
```
trading_agent/
├── dashboard/
│   ├── app.py                    # Main Dash application
│   ├── components/
│   │   ├── model_selector.py    # Dropdown for model selection
│   │   ├── chart_renderer.py    # Chart display logic
│   │   └── metrics_panel.py     # Statistics display
│   ├── layouts/
│   │   ├── main_layout.py       # Overall dashboard layout
│   │   └── style.py             # CSS styling
│   └── callbacks/
│       └── update_charts.py     # Interactive callbacks
```

### 3.3 Dashboard Layout Design (3-Tab Structure)

**NEW LAYOUT: 3 Main Tabs**

```
┌─────────────────────────────────────────────────────────────┐
│  Trading Strategy Backtest Dashboard                        │
│                                                              │
│  [Tab: ☕ COFFEE | Tab: 🍬 SUGAR | Tab: ⚖️ COFFEE vs SUGAR] │
└─────────────────────────────────────────────────────────────┘
```

---

## TAB 1: COFFEE

```
┌─────────────────────────────────────────────────────────────┐
│  ☕ COFFEE ANALYSIS                                          │
├─────────────────────────────────────────────────────────────┤
│  📊 MODEL COMPARISON LEADERBOARD (Top Section)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Model              Net Earnings  Trades  Avg Price  │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ sarimax_auto_v1    $45,678      42      $128.50 ⭐  │   │
│  │ prophet_v1         $43,210      38      $127.20     │   │
│  │ xgboost_weather_v1 $41,500      45      $126.80     │   │
│  │ ... (show all 10 models)                           │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  🔍 DETAILED MODEL ANALYSIS                                 │
│  Select Model: [sarimax_auto_weather_v1 ▼]                 │
├─────────────────────────────────────────────────────────────┤
│  Key Metrics Panel                                          │
│  ┌──────────┬──────────┬──────────┬──────────┐            │
│  │ Net      │ Trades   │ Avg Sale │ P-Value  │            │
│  │ Earnings │          │ Price    │ (vs Base)│            │
│  └──────────┴──────────┴──────────┴──────────┘            │
├─────────────────────────────────────────────────────────────┤
│  [Sub-Tab: Performance | Statistical | Sensitivity]         │
├─────────────────────────────────────────────────────────────┤
│  Chart Display Area                                         │
│  ┌───────────────────────────────────────────────┐         │
│  │  (Charts for selected model)                  │         │
│  │  - Cumulative Returns                         │         │
│  │  - Timeline                                   │         │
│  │  - Bootstrap CI                               │         │
│  │  - Feature Importance                         │         │
│  │  - Sensitivity Analysis                       │         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## TAB 2: SUGAR

```
┌─────────────────────────────────────────────────────────────┐
│  🍬 SUGAR ANALYSIS                                           │
├─────────────────────────────────────────────────────────────┤
│  📊 MODEL COMPARISON LEADERBOARD (Top Section)              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Model              Net Earnings  Trades  Avg Price  │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ prophet_v1         $38,900      35      $15.40 ⭐   │   │
│  │ sarimax_auto_v1    $37,200      40      $15.20      │   │
│  │ ... (show all 5 models)                            │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  🔍 DETAILED MODEL ANALYSIS                                 │
│  Select Model: [prophet_v1 ▼]                              │
├─────────────────────────────────────────────────────────────┤
│  (Same structure as Coffee tab)                             │
│  - Key Metrics Panel                                        │
│  - Sub-tabs for different analysis types                    │
│  - Charts for selected model                                │
└─────────────────────────────────────────────────────────────┘
```

---

## TAB 3: COFFEE vs SUGAR

```
┌─────────────────────────────────────────────────────────────┐
│  ⚖️ CROSS-COMMODITY COMPARISON                              │
├─────────────────────────────────────────────────────────────┤
│  Select Models to Compare:                                  │
│  Coffee: [sarimax_auto_weather_v1 ▼]                       │
│  Sugar:  [prophet_v1 ▼]                                     │
├─────────────────────────────────────────────────────────────┤
│  📊 SIDE-BY-SIDE COMPARISON                                 │
│  ┌──────────────────────────┬──────────────────────────┐   │
│  │  COFFEE                  │  SUGAR                   │   │
│  │  (sarimax_auto_v1)       │  (prophet_v1)            │   │
│  ├──────────────────────────┼──────────────────────────┤   │
│  │  Net: $45,678            │  Net: $38,900            │   │
│  │  Trades: 42              │  Trades: 35              │   │
│  │  Avg Price: $128.50      │  Avg Price: $15.40       │   │
│  └──────────────────────────┴──────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  COMPARISON CHARTS                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  • Earnings Comparison (Bar Chart)                  │   │
│  │  • Cumulative Returns (Dual Line Chart)             │   │
│  │  • Strategy Performance Comparison                  │   │
│  │  • Model Advantage by Commodity                     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features of Each Tab:

### Coffee & Sugar Tabs (Similar Structure):
**Top Section - Model Leaderboard:**
- Sortable table showing ALL models for that commodity
- Key metrics: Net Earnings, Trades, Avg Sale Price, P-value
- Click to select model (or use dropdown below)
- Highlight best performing model

**Middle Section - Model Selector:**
- Dropdown to select specific model for detailed view
- Updates all charts below

**Bottom Section - Detailed Analysis (Sub-Tabs):**

**Sub-Tab 1: Performance**
- Cumulative Returns Chart (interactive line)
- Trading Timeline (scatter on price history)
- Net Earnings Bar Chart
- Inventory Levels Over Time
- Gross Revenue Over Time

**Sub-Tab 2: Statistical Analysis** ⭐
- **Bootstrap Confidence Intervals** (error bars, 1000 iterations)
- **T-Test Results** (vs best baseline)
- **P-Values with Significance Stars** (*, **, ***)
- **Portfolio Value Time Series**
- Statistical comparison table

**Sub-Tab 3: Sensitivity Analysis**
- **Parameter Sensitivity Heatmap** (consensus threshold, min return)
- **Transaction Cost Sensitivity** (line chart)
- **Storage Cost Sensitivity** (line chart)
- **Prediction Advantage** (grouped bar chart)

**Sub-Tab 4: Feature Analysis**
- **Feature Importance** (Random Forest, bar chart)
- **Feature Correlation Heatmap**
- **Feature vs Return Scatter**
- **Cross-validation R² Score**

**ALL STATISTICAL ANALYSIS FROM NOTEBOOKS 04-09 PRESERVED!** ✅

### Coffee vs Sugar Tab:
**Dual Model Selectors:**
- Pick one model from Coffee (dropdown)
- Pick one model from Sugar (dropdown)

**Comparison Views:**
- Side-by-side metrics
- Overlaid charts (if applicable)
- Relative performance analysis
- Cross-commodity insights

### 3.4 Core Dashboard Features

**1. Dual Selector System (CRITICAL)**

**Commodity Selector:**
```python
# Dropdown 1: Select Commodity
commodity_dropdown = dcc.Dropdown(
    id='commodity-selector',
    options=[
        {'label': 'Coffee', 'value': 'coffee'},
        {'label': 'Sugar', 'value': 'sugar'}
    ],
    value='coffee',  # default
    clearable=False
)
```

**Model Selector (Dynamic):**
```python
# Dropdown 2: Select Model (updates based on commodity)
# Coffee selected → Shows 10 coffee models
# Sugar selected → Shows 5 sugar models
model_dropdown = dcc.Dropdown(
    id='model-selector',
    options=[],  # Populated dynamically via callback
    value=None,
    clearable=False
)

# Callback to update model options when commodity changes
@app.callback(
    Output('model-selector', 'options'),
    Output('model-selector', 'value'),
    Input('commodity-selector', 'value')
)
def update_model_options(selected_commodity):
    models = get_available_models(selected_commodity, connection)
    options = [{'label': model, 'value': model} for model in models]
    default_model = models[0] if models else None
    return options, default_model
```

**Selection Flow:**
1. User selects **Commodity** (Coffee or Sugar)
2. Model dropdown auto-updates with available models
3. User selects **Model** (e.g., sarimax_auto_weather_v1)
4. All charts and metrics update for that (commodity, model) combination

**Example Interaction:**
```
User Action: Select "Coffee"
→ Model dropdown shows: [arima_111_v1, prophet_v1, sarimax_auto_weather_v1, ...]
→ Charts show placeholder or default model

User Action: Select "sarimax_auto_weather_v1"
→ Dashboard loads: all_results['coffee']['sarimax_auto_weather_v1']
→ All charts update with this model's results
→ Metrics panel updates with this model's performance
```

**2. Metrics Panel**
- Total Return (%)
- Sharpe Ratio
- Maximum Drawdown (%)
- Win Rate (%)
- Average Trade Size
- Number of Trades
- Profit Factor

**3. Chart Tabs**
- **Performance Tab:**
  - Cumulative Returns Chart
  - Portfolio Value Over Time
  - Revenue vs Costs Breakdown

- **Strategy Comparison Tab:**
  - Strategy Earnings Comparison (Bar Chart)
  - Timeline of Trades
  - Inventory Levels Over Time

- **Sensitivity Analysis Tab:**
  - Transaction Cost Sensitivity
  - Storage Cost Sensitivity
  - Parameter Sensitivity Heatmap
  - Feature Importance

**4. Model Comparison View**
- Side-by-side comparison of selected models
- Benchmark against baseline strategies
- Statistical significance indicators

**5. Dashboard Data Loading Pattern**

**Main Callback Structure:**
```python
@app.callback(
    Output('metrics-panel', 'children'),
    Output('cumulative-returns-chart', 'figure'),
    Output('timeline-chart', 'figure'),
    Output('earnings-chart', 'figure'),
    # ... all other chart outputs
    Input('commodity-selector', 'value'),
    Input('model-selector', 'value')
)
def update_dashboard(selected_commodity, selected_model):
    """
    Main callback that updates entire dashboard when commodity or model changes.

    This is triggered whenever either dropdown changes value.
    """
    if not selected_commodity or not selected_model:
        return empty_dashboard()

    # Load results for this (commodity, model) combination
    results = all_results[selected_commodity][selected_model]

    # Update metrics panel
    metrics = create_metrics_panel(results['metrics'])

    # Update all charts
    cumulative_chart = create_cumulative_returns_chart(results)
    timeline_chart = create_timeline_chart(results)
    earnings_chart = create_earnings_chart(results)
    # ... create all other charts

    return metrics, cumulative_chart, timeline_chart, earnings_chart, ...
```

**Data Flow:**
```
User selects: Coffee + sarimax_auto_weather_v1
    ↓
Callback triggered with: ('coffee', 'sarimax_auto_weather_v1')
    ↓
Load data: all_results['coffee']['sarimax_auto_weather_v1']
    ↓
Extract:
    - Strategy results (9 strategies)
    - Charts data (cumulative returns, timeline, etc.)
    - Metrics (net earnings, trades, etc.)
    - Statistical results
    - Feature analysis
    - Sensitivity analysis
    ↓
Render all charts and metrics
    ↓
Dashboard updates in browser
```

**Key Implementation Detail:**
All 15 model results must be pre-computed and loaded into memory when dashboard starts, or loaded on-demand from cached files. Dashboard does NOT re-run backtests - it only displays pre-computed results.

### 3.5 Chart Migration Plan

**Existing Charts → Dashboard Components:**

| Current Chart | Dashboard Location | Interactive Features |
|---------------|-------------------|---------------------|
| Cumulative Returns | Performance Tab | Zoom, pan, hover tooltips |
| Timeline | Strategy Comparison | Click to see trade details |
| Earnings Comparison | Strategy Comparison | Sort by performance |
| Inventory Levels | Strategy Comparison | Toggle strategies on/off |
| Sensitivity Analysis | Sensitivity Tab | Interactive parameter sliders |
| Feature Importance | Sensitivity Tab | Sort by importance |
| Cross-Commodity | New Multi-Commodity Tab | Select commodities to compare |
| Dashboard (9-panel) | Overview Tab | High-level summary |

---

## Phase 4: Implementation Steps (Detailed)

### Step 1: Create Data Access Layer (Day 1)
1. Create `trading_agent/data_access/` directory
2. Implement `forecast_loader.py` with SQL query functions
3. Test queries against `commodity.forecast.distributions`
4. Validate data format matches existing expectations

### Step 2: Extract Configuration (Day 1)
1. Create `trading_agent/commodity_prediction_analysis/config.py`
2. Move all configuration dictionaries from notebook
3. Add database connection config
4. Update notebook to import config

### Step 3: Refactor Data Loading (Day 2)
1. Update prediction loading functions in main script
2. Replace CSV reads with SQL queries
3. Test with single model first (e.g., sarimax_auto_weather_v1)
4. Verify analysis runs end-to-end

### Step 4: Add Model Loop (Day 2-3)
1. Create `trading_agent/analysis/model_runner.py`
2. Implement model iteration logic
3. Update result storage structure
4. Run analysis for all Coffee models
5. Verify results are stored correctly

### Step 5: Set Up Dashboard Framework (Day 3-4)
1. Install Plotly Dash: `pip install dash plotly`
2. Create dashboard directory structure
3. Create basic `app.py` with simple layout
4. Test dashboard launches successfully

### Step 6: Implement Model Selector (Day 4)
1. Create `model_selector.py` component
2. Query available models from database
3. Add dropdown callbacks
4. Test model selection triggers updates

### Step 7: Migrate First Chart (Day 4-5)
1. Start with Cumulative Returns (most important)
2. Convert matplotlib → Plotly
3. Add interactive features
4. Connect to model selector

### Step 8: Build Metrics Panel (Day 5)
1. Calculate key metrics from results
2. Create metric cards layout
3. Update metrics on model change
4. Add color coding (green/red for good/bad)

### Step 9: Migrate Remaining Charts (Day 6-8)
1. Timeline Chart → Plotly
2. Earnings Comparison → Plotly
3. Sensitivity Analysis → Plotly
4. Feature Importance → Plotly
5. Add all charts to dashboard tabs

### Step 10: Add Model Comparison (Day 9)
1. Create comparison view layout
2. Allow multiple model selection
3. Show side-by-side metrics
4. Add statistical significance tests

### Step 11: Testing & Polish (Day 10)
1. Test all model selections work
2. Verify chart interactions
3. Add loading indicators
4. Improve styling/colors
5. Add help text/tooltips

### Step 12: Deploy to Databricks (Day 11)
1. Package dashboard as Databricks App
2. Configure database connections
3. Test in Databricks environment
4. Share access with team

---

## Technical Decisions

### Database Connection Strategy
**Option A:** Pass connection object through functions
**Option B:** Create singleton connection manager
**Recommendation:** Option B (cleaner, easier to manage)

### Chart Library
**Matplotlib → Plotly** conversion required
- More interactive
- Better for dashboards
- Native web rendering

### Result Caching
- Cache model results to avoid re-running expensive backtests
- Use pickle or parquet files
- Refresh cache on demand

---

## Success Criteria

✅ **Phase 1 Complete When:**
- All data loading uses `commodity.forecast.distributions` table
- No hardcoded file paths remain
- Single model analysis runs successfully

✅ **Phase 2 Complete When:**
- All 10 Coffee models run successfully
- All 5 Sugar models run successfully
- Results stored in structured format
- Model comparison metrics calculated

✅ **Phase 3 Complete When:**
- Dashboard launches successfully
- All charts migrated and interactive
- Model selector works correctly
- Metrics panel updates dynamically
- Dashboard deployed to Databricks

---

## Risk Mitigation

### Risk 1: Data Format Mismatch
**Mitigation:**
- Test with single model first
- Validate data schema matches expectations
- Add data validation checks

### Risk 2: Performance Issues
**Mitigation:**
- Implement result caching
- Use database query optimization
- Lazy load charts (only render visible ones)

### Risk 3: Dashboard Complexity
**Mitigation:**
- Start with minimal viable dashboard
- Add features incrementally
- Get user feedback early

---

## Next Steps

1. **Review this plan** with team
2. **Decide on dashboard framework** (Plotly Dash vs Streamlit)
3. **Start Phase 1:** Create data access layer
4. **Set up development environment** with required packages

---

## Questions for Discussion

1. Do we want to run analysis for all models, or select subset?
2. Should we include cross-commodity comparisons in first version?
3. What's the priority order for charts?
4. Do we need user authentication for dashboard?
5. Should results be cached, or calculated on-demand?

---

## Appendix: Required Packages

```bash
# Add to requirements.txt
dash>=2.14.0
plotly>=5.18.0
dash-bootstrap-components>=1.5.0
pandas>=2.0.0
databricks-sql-connector>=2.9.3
```

---

**Ready to proceed? Let me know which phase to start with!** 🚀
