# Trading Agent Technical Documentation

This folder contains technical documentation for implementation details and analyses.

---

## Contents

### Multi-Model Analysis

**[MULTI_MODEL_ANALYSIS.md](MULTI_MODEL_ANALYSIS.md)**

Comprehensive guide to the multi-model backtesting framework:
- **Implementation details**: Unity Catalog connection, model discovery, data loading
- **Synthetic predictions**: How accuracy-controlled forecasts are generated
- **Accuracy threshold analysis**: Finding that 70% accuracy is minimum for profitability
- **Real model benchmarking**: Comparison to synthetic accuracy levels
- **Usage examples**: Running analysis, comparing models, interpreting results
- **Statistical insights**: Performance vs accuracy, diminishing returns, ceiling analysis

**Key Finding:** Best real model (`sarimax_auto_weather_v1`) performs at ~75% effective accuracy, providing $2,390 advantage over baseline strategies.

### Parameter Optimization

**[PARAMETER_GRID_SEARCH_GUIDE.md](PARAMETER_GRID_SEARCH_GUIDE.md)**

Complete guide to optimizing trading strategy parameters via grid search:
- **Grid search framework**: Test 100s-1000s of parameter combinations automatically
- **Parameter grids**: Defined ranges for all 10 trading strategies
- **Matched pair enforcement**: Ensures baseline/predictive pairs share same parameters
- **Two-stage optimization**: Coarse search → fine-grained refinement
- **Results analysis**: Interpreting optimal values, sensitivity analysis, validation
- **Integration workflow**: Update notebook parameters, deploy to production
- **Best practices**: Validation, statistical testing, periodic re-optimization

**Key Finding:** Grid search can improve net revenue by 10-20% through systematic parameter optimization.

---

## For Users

If you're looking for user-facing documentation:
- **Quick Start & Overview**: [`../README.md`](../README.md)
- **Daily Recommendations**: [`../operations/README.md`](../operations/README.md)
- **Unity Catalog Queries & Data Access**: [DATABRICKS_GUIDE.md](DATABRICKS_GUIDE.md)

---

## Archived Documentation

Previous versions of technical documentation have been consolidated:
- ~~MULTI_MODEL_MODIFICATIONS.md~~ → Merged into MULTI_MODEL_ANALYSIS.md
- ~~ACCURACY_THRESHOLD_ANALYSIS.md~~ → Merged into MULTI_MODEL_ANALYSIS.md
- ~~DATA_FORMAT_VERIFICATION.md~~ → Removed (historical verification, no longer needed)
- ~~backtest_results.md~~ → Removed (outdated Nov 1 results, superseded by multi-model analysis)

---

Last Updated: 2025-11-10 (Session 3 - Added Parameter Grid Search Guide)
