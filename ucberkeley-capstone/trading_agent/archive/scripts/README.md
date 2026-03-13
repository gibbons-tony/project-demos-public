# Archive - Root-Level Scripts

This folder contains archived scripts from the trading_agent root directory that were superseded by the production framework.

---

## Why Archived

These scripts represent the **first iteration** of multi-model analysis and backtesting (Nov 10, 2025). They were replaced by the **production framework** in `commodity_prediction_analysis/production/` (Nov 24-Dec 4, 2025).

**Timeline:**
- **Nov 10**: Root scripts created (this folder)
- **Nov 24**: Production framework created (`commodity_prediction_analysis/production/`)
- **Dec 8**: Root scripts archived (cleanup for project completion)

---

## Contents

### Multi-Model Analysis Scripts

**run_multi_model_analysis.py**
- **Purpose**: Orchestrates backtesting across all commodity/model combinations
- **Replaced by**: `commodity_prediction_analysis/production/runners/multi_commodity_runner.py`
- **Used**: `analysis/model_runner.py` (also archived)
- **Output**: `./output/multi_model_analysis/`

### Forecast Backtesting

**backtest_forecasts.py**
- **Purpose**: Evaluates forecast performance across 40 historical windows
- **Replaced by**: Notebook-based workflow (notebooks 05-06)
- **Dependencies**: `forecast_client.py`
- **Output**: `backtest_results.md`

**forecast_client.py**
- **Purpose**: Simple client library for querying forecast distributions
- **Replaced by**: `data_access/forecast_loader.py` (more comprehensive)
- **Used by**: `backtest_forecasts.py`, `backfill_forecast_metadata.py`

**backfill_forecast_metadata.py**
- **Purpose**: Backfills forecast metadata table
- **Replaced by**: Direct Spark operations in notebooks
- **Dependencies**: `forecast_client.py`

### Parameter Optimization

**parameter_grid_search.py**
- **Purpose**: Grid search for optimal trading strategy parameters
- **Replaced by**: `commodity_prediction_analysis/analysis/optimization/` (Optuna-based)
- **Dependencies**: `parameter_config.py`
- **Output**: `optimal_parameters.json`, `grid_search_results.csv`
- **Referenced in**: `docs/PARAMETER_GRID_SEARCH_GUIDE.md` (outdated)

**parameter_config.py**
- **Purpose**: Configuration for parameter grid search
- **Replaced by**: `commodity_prediction_analysis/analysis/optimization/search_space.py`

**optimal_parameters_template.json**
- **Purpose**: Template for optimal parameter output
- **Replaced by**: Production config in `commodity_prediction_analysis/production/config.py`

### Integration Tests

**test_full_integration.py**
- **Purpose**: Full integration test of trading system
- **Status**: Superseded by notebook-based testing

**test_integration.py**
- **Purpose**: Integration test for data loading
- **Status**: Superseded by `data_access/test_forecast_loader.py`

**test_single_model_run.py**
- **Purpose**: Test single model backtest
- **Status**: Superseded by production framework tests

---

## What Replaced These Scripts

### Modern Workflow (Current)

**For Multi-Model Analysis:**
```python
# NEW: Use production framework
from commodity_prediction_analysis.production.runners import MultiCommodityRunner

runner = MultiCommodityRunner(spark, commodity_configs, ...)
results = runner.run_all_commodities()
```

**For Daily Recommendations:**
```bash
# NEW: Use operations module
python operations/daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1
```

**For Data Loading:**
```python
# NEW: Use data_access module
from data_access.forecast_loader import load_forecast_distributions

distributions = load_forecast_distributions(commodity, model, connection)
```

**For Parameter Optimization:**
```python
# NEW: Use Optuna-based optimization
from commodity_prediction_analysis.analysis.optimization import run_parameter_optimization

best_params = run_parameter_optimization(commodity, model)
```

---

## Key Differences: Old vs New

| Aspect | Old Scripts (Archived) | New Production Framework |
|--------|----------------------|-------------------------|
| **Architecture** | Monolithic scripts | Modular framework |
| **Execution** | Python scripts | Databricks notebooks + Python modules |
| **Data Storage** | CSV/JSON files | Delta tables + Unity Catalog |
| **Backtesting** | Custom loops | Spark-based parallel execution |
| **Optimization** | Grid search | Optuna (Bayesian optimization) |
| **Testing** | Integration scripts | pytest + production/runners/tests/ |
| **Orchestration** | Manual execution | Databricks jobs (automation-ready) |

---

## Migration Notes

**If you need to reference old logic:**
1. Check `commodity_prediction_analysis/production/` for equivalent functionality
2. Review notebooks 00-10 for updated workflow
3. See `commodity_prediction_analysis/FILE_INVENTORY.md` for current structure

**Code Reuse:**
- Core algorithm logic → Moved to `commodity_prediction_analysis/production/strategies/`
- Data loading → Refactored into `data_access/forecast_loader.py`
- Backtest engine → `commodity_prediction_analysis/production/core/backtest_engine.py`

---

## When to Delete

**Safe to delete after:**
- Project completion and final presentation (Dec 2025)
- Verification that all functionality is replicated in production framework
- 6 months post-archival (June 2026) if no active references

**Preservation reason:**
- Documents evolution from monolithic scripts → modular production framework
- Shows iteration process and design decisions
- Historical reference for "why we built it this way" questions
- Useful for understanding parameter choices and optimization history

---

**Archived:** Dec 8, 2025
**Last reviewed:** Dec 8, 2025

**See also:**
- `commodity_prediction_analysis/production/` - Current production framework
- `commodity_prediction_analysis/FILE_INVENTORY.md` - Current system inventory
- `../archive/monolithic/` - Original monolithic notebooks
