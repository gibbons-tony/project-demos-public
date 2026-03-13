# Production Runners Module

**Purpose**: Modular backtest execution system that replicates notebook 05 workflow in automation-ready format

**Created**: 2025-11-24
**Version**: 1.0.0

---

## Architecture

```
production/runners/
├── data_loader.py              # Load prices & prediction matrices
├── strategy_runner.py          # Execute all 9 strategies
├── visualization.py            # Generate all 5 chart types
├── result_saver.py             # Save to Delta/pickle
├── multi_commodity_runner.py   # Main orchestrator
├── __init__.py                 # Module exports
└── README.md                   # This file
```

### Module Dependencies

```
multi_commodity_runner.py
  ├── data_loader.py           (268 lines)
  ├── strategy_runner.py       (368 lines)
  ├── visualization.py         (508 lines)
  └── result_saver.py          (302 lines)

Total: 1,446 lines of production code
```

---

## Quick Start

### Basic Usage

```python
from production.runners import MultiCommodityRunner
from production.config import COMMODITY_CONFIGS

# Strategy parameters (from notebook 00)
BASELINE_PARAMS = {
    'equal_batch': {'batch_size': 0.25, 'frequency_days': 30},
    'price_threshold': {'threshold_pct': 0.05},
    'moving_average': {'ma_period': 30}
}

PREDICTION_PARAMS = {
    'consensus': {'consensus_threshold': 0.70, 'min_return': 0.03, 'evaluation_day': 14},
    'expected_value': {'min_ev_improvement': 50, 'baseline_batch': 0.15, 'baseline_frequency': 10},
    'risk_adjusted': {'min_return': 0.03, 'max_uncertainty': 0.35, 'consensus_threshold': 0.60, 'evaluation_day': 14}
}

# Initialize runner
runner = MultiCommodityRunner(
    spark=spark,
    commodity_configs=COMMODITY_CONFIGS,
    baseline_params=BASELINE_PARAMS,
    prediction_params=PREDICTION_PARAMS
)

# Run all commodities and models
results = runner.run_all_commodities()

# Get summary
summary = runner.get_summary()
print(f"Processed {summary['total_combinations']} commodity-model combinations")
```

### Advanced Usage: Run Single Commodity

```python
# Run only coffee
results = runner.run_all_commodities(commodities=['coffee'])

# Access results for specific model
coffee_results = results['coffee']['synthetic_90pct']
print(f"Best strategy: {coffee_results['best_overall']['strategy']}")
print(f"Net earnings: ${coffee_results['best_overall']['net_earnings']:,.2f}")
```

---

## Module Details

### 1. DataLoader (`data_loader.py`)

**Purpose**: Load prices and prediction matrices for commodity-model pairs

**Key Methods**:
- `load_commodity_data(commodity, model_version, data_paths)` → Returns (prices_df, prediction_matrices_dict)
- `discover_model_versions(commodity)` → Returns (synthetic_versions, real_versions)
- `get_data_summary(prices, prediction_matrices)` → Returns summary statistics

**Features**:
- Automatic source type detection (synthetic vs real)
- Date alignment validation
- Data quality checks

### 2. StrategyRunner (`strategy_runner.py`)

**Purpose**: Initialize and execute all 9 strategies

**Key Methods**:
- `initialize_strategies()` → Returns (baselines, prediction_strategies)
- `run_all_strategies(commodity, model_version)` → Returns (results_dict, metrics_df)
- `analyze_best_performers(metrics_df)` → Returns best baseline/prediction/overall
- `analyze_risk_adjusted_scenarios(results_dict)` → Returns scenario distribution
- `analyze_forced_liquidations(results_dict)` → Returns liquidation analysis

**Features**:
- 4 baseline strategies (Immediate Sale, Equal Batch, Price Threshold, Moving Average)
- 5 prediction strategies (Consensus, Expected Value, Risk-Adjusted, 2 A/B test pairs)
- Comprehensive metrics calculation
- Scenario analysis for Risk-Adjusted strategy

### 3. VisualizationGenerator (`visualization.py`)

**Purpose**: Generate all backtest visualization charts

**Key Methods**:
- `generate_all_charts(...)` → Returns dict mapping chart_type to file_path
- `generate_cross_commodity_comparison(comparison_df)` → Returns comparison chart paths

**Charts Generated** (5 per commodity-model pair):
1. **Net Earnings Bar Chart** - Compare strategy performance
2. **Trading Timeline** - Scatter plot of all trades over time
3. **Total Revenue (Without Costs)** - Cumulative revenue tracking
4. **Cumulative Net Revenue (With Costs)** - True earnings after costs
5. **Inventory Drawdown** - Inventory levels over time

**Phase 3 Support**:
- Set `output_organized=True` to use categorized subdirectories:
  - `performance/` - Earnings and revenue charts
  - `timelines/` - Timeline and inventory charts

### 4. ResultSaver (`result_saver.py`)

**Purpose**: Persist results to Delta tables and pickle files

**Key Methods**:
- `save_results(...)` → Returns dict mapping result_type to save_path
- `save_cross_commodity_results(...)` → Returns saved file paths
- `load_results(commodity, model_version)` → Returns loaded results
- `validate_results(metrics_df, results_dict)` → Returns validation status

**Outputs**:
- **Delta Tables**: Metrics DataFrames in Unity Catalog
- **Pickle Files**: Detailed results dictionaries
- **CSV Files**: Cross-commodity comparisons

### 5. MultiCommodityRunner (`multi_commodity_runner.py`)

**Purpose**: Main orchestrator tying all modules together

**Key Methods**:
- `run_all_commodities(commodities=None)` → Returns all_commodity_results dict
- `get_summary()` → Returns execution summary

**Workflow**:
1. Loop through all commodities
2. Discover model versions for each commodity
3. For each commodity-model pair:
   - Load data via DataLoader
   - Run strategies via StrategyRunner
   - Generate charts via VisualizationGenerator
   - Save results via ResultSaver
4. Generate cross-commodity comparison

---

## Output Structure

### Per Commodity-Model Pair

**Delta Tables** (Unity Catalog):
- `commodity.trading_agent.results_{commodity}_{model}` - Metrics DataFrame

**Pickle Files** (Volume):
- `prediction_matrices_{commodity}_{model}.pkl` - Input prediction matrices
- `results_detailed_{commodity}_{model}.pkl` - Full results dictionary

**Charts** (PNG, Volume):
- `net_earnings_{commodity}_{model}.png`
- `trading_timeline_{commodity}_{model}.png`
- `total_revenue_no_costs_{commodity}_{model}.png`
- `cumulative_returns_{commodity}_{model}.png`
- `inventory_drawdown_{commodity}_{model}.png`

### Cross-Commodity Comparison

**CSV Files** (Volume):
- `cross_model_commodity_summary.csv` - Best strategies per commodity-model
- `detailed_strategy_results.csv` - All strategies, all combinations

**Charts** (PNG, Volume):
- `cross_model_commodity_advantage.png` - Prediction advantage comparison
- `cross_model_commodity_earnings.png` - Best earnings comparison

---

## Integration with Existing System

### Replicates Notebook 05

This module provides **identical functionality** to notebook 05 but in modular form:

| Notebook 05 Section | Production Module |
|---------------------|-------------------|
| Data loading | `DataLoader` |
| Strategy initialization | `StrategyRunner.initialize_strategies()` |
| Backtest execution | `StrategyRunner.run_all_strategies()` |
| Visualization generation | `VisualizationGenerator.generate_all_charts()` |
| Results saving | `ResultSaver.save_results()` |
| Cross-commodity comparison | `MultiCommodityRunner._generate_cross_commodity_comparison()` |

### Uses Production Infrastructure

**Strategies** (from `production/strategies/`):
- ✓ All 9 strategies (4 baseline + 5 prediction)
- ✓ Percentage-based framework
- ✓ 3-tier confidence system
- ✓ Forced liquidation logic

**Backtest Engine** (from `production/core/`):
- ✓ Harvest-based inventory
- ✓ Correct cost calculations (0.005%, 0.01%)
- ✓ Multi-cycle support

**Configuration** (from `production/config.py`):
- ✓ Updated commodity configs
- ✓ Correct percentage-based costs

---

## Next Steps

### Phase 2c: Orchestration Layer
- [ ] Create job submission wrapper for Databricks Jobs API
- [ ] Implement progress monitoring
- [ ] Add error recovery and retry logic
- [ ] Enable overnight batch execution

### Phase 3: Consolidation
- [ ] Organize outputs into categorized directories
- [ ] Generate 4-tier markdown reports (executive, detailed, technical, validation)
- [ ] Prepare LLM data files (parquet, JSON)
- [ ] Create archival system (keep last 10 runs)

### Phase 4: WhatsApp LLM
- [ ] Populate `commodity.whatsapp_llm.*` tables
- [ ] Integrate with WhatsApp bot

---

## Testing

### Unit Testing

```python
# Test data loader
from production.runners import DataLoader
loader = DataLoader(spark=spark)
prices, matrices = loader.load_commodity_data('coffee', 'synthetic_90pct', data_paths)
assert len(prices) > 0
assert len(matrices) > 0

# Test strategy runner
from production.runners import StrategyRunner
runner = StrategyRunner(prices, matrices, commodity_config, baseline_params, prediction_params)
results_dict, metrics_df = runner.run_all_strategies('coffee', 'synthetic_90pct')
assert len(results_dict) == 9  # 9 strategies
assert len(metrics_df) == 9
```

### Integration Testing

```python
# Run full pipeline for one commodity-model pair
runner = MultiCommodityRunner(spark, COMMODITY_CONFIGS, BASELINE_PARAMS, PREDICTION_PARAMS)
results = runner.run_all_commodities(commodities=['coffee'])
assert 'coffee' in results
assert len(results['coffee']) > 0  # At least one model version
```

---

## Performance Considerations

**Memory**:
- Prediction matrices can be large (500 runs × 14 horizons × N dates)
- Each commodity-model pair processes independently
- Results are saved immediately after completion

**Execution Time** (approximate):
- Single commodity-model pair: 2-5 minutes
- All commodities (2) × All models (15): 30-60 minutes
- Dominated by backtest execution (strategy.decide() calls)

**Optimization Opportunities**:
- Parallelize across commodity-model pairs using Spark
- Cache prediction matrices in memory for multiple strategy runs
- Use smaller synthetic datasets for testing

---

## Data Sources

### Table Overview

The production runners need two types of data:
1. **Actual prices** - Historical price data for backtesting
2. **Predictions** - Forecast distributions for prediction-based strategies

### commodity.silver.unified_data (Recommended for Prices)

**Usage:** Load actual historical prices

**Structure:**
- `date` - Every day since 2015-07-07 (continuous, no gaps)
- `commodity` - Lowercase (e.g., "coffee")
- `region` - Multiple regions, but prices are identical
- `close` - Closing price (forward-filled for non-trading days)

**Advantages:**
- ✓ Continuous daily coverage (no weekends/holidays gaps)
- ✓ Forward-filled (no NULL values)
- ✓ Consistent with optimization code (`analysis/optimization/run_parameter_optimization.py`)
- ✓ Simple to use (just aggregate across regions)

**Example:**
```python
prices = spark.table("commodity.silver.unified_data").filter(
    "lower(commodity) = 'coffee'"
).groupBy("date").agg(
    F.first("close").alias("price")  # Same across all regions
).toPandas()
```

### commodity.forecast.distributions (Sparse, Mixed Structure)

**Usage:** Contains both actuals and forecasts (distinguished by `is_actuals` flag)

**Structure:**
- `forecast_date` - Date of forecast/actual
- `commodity` - **Title case** (e.g., "Coffee")
- `model_version` - Model identifier
- `is_actuals` - TRUE for actual prices, FALSE for forecasts
- `close` - Closing price
- [Monte Carlo distribution columns...]

**Challenges:**
- ✗ Sparse coverage for forecasts (model-dependent)
- ✗ Trading days only for actuals (weekends/holidays missing)
- ✗ Mixed data (actuals + forecasts in same table)
- ✗ Title case commodity names (inconsistent with unified_data)

**When to use:**
- Loading Monte Carlo forecast distributions
- Validating forecast coverage
- NOT recommended for loading actual prices (use unified_data instead)

### Prediction Matrices (Pickle Files)

**Usage:** Fast access to prediction distributions for backtesting

**Location:** `/Volumes/commodity/trading_agent/files/prediction_matrices_{commodity}_{model}.pkl`

**Structure:**
```python
{
    pd.Timestamp('2022-01-03'): np.array([[...]]),  # shape: (n_runs, n_horizons)
    pd.Timestamp('2022-01-04'): np.array([[...]]),
    ...
}
```

**Generated by:**
- Notebook 01: Synthetic predictions (accuracy-controlled)
- Notebook 02: Real model predictions (from forecast.distributions)

### Data Alignment (CRITICAL)

**Problem:**
Different data sources have different date coverage, causing 0% match rates when misaligned.

**Example Mismatch:**
```
unified_data dates:          ~3,700 dates (continuous daily, 2015-2025)
forecast.distributions:      ~2,500 dates (trading days only)
Prediction matrix keys:      ~951 dates (model-dependent)
```

**Solution:**
Always use `commodity.silver.unified_data` for prices to ensure maximum date overlap with prediction matrices.

**Validation:**
```python
# Check overlap
common_dates = set(prices.date) & set(prediction_matrices.keys())
pred_coverage = len(common_dates) / len(prediction_matrices) * 100

# Should be 90%+ for good alignment
if pred_coverage < 90:
    raise ValueError(f"Poor alignment: {pred_coverage:.1f}% coverage")
```

---

## Troubleshooting

### Common Issues

1. **"Spark session required"**
   - Ensure `spark` is available in environment
   - In Databricks notebook: `spark` is automatically available
   - In script: Create spark session first

2. **"Prediction matrices not found"**
   - Run data preparation first (notebook 01 or 02)
   - Check that pickle files exist in volume path
   - Verify model_version matches available data

3. **"No model versions found"**
   - Check that predictions table has data for commodity
   - Verify Unity Catalog permissions
   - Review data_loader logs for discovery process

4. **"Strategy mismatch" validation error**
   - Should not occur in production (indicates bug)
   - Check that all 9 strategies executed successfully
   - Review strategy_runner logs

---

## Contact

**Module Owner**: Trading Agent Team
**Created**: 2025-11-24
**Last Updated**: 2025-11-24

For questions or issues, refer to:
- `MASTER_SYSTEM_PLAN.md` - Overall system architecture
- `NOTEBOOK_REVIEW_SUMMARY.md` - Notebook analysis and design decisions
- `FILE_INVENTORY.md` - Complete file structure
