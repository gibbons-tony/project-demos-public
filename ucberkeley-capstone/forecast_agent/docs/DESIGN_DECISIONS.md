# Design Decisions & Technical Rationale

**Project**: Commodity Price Forecasting for Algorithmic Trading
**Team**: UC Berkeley MIDS Capstone
**Last Updated**: 2025-11-01

> **Note**: This document tracks key data science and engineering decisions made throughout the project. Update as new decisions are made.

---

## 1. Infrastructure Architecture

### Decision: Databricks Unity Catalog with 3-Layer Architecture
**Chosen**: Landing → Bronze → Silver layers in Databricks Unity Catalog

**Alternatives Considered**:
- Single flat table in S3/Parquet
- Traditional data warehouse (Redshift/Snowflake)
- Lakehouse with Iceberg instead of Delta Lake

**Rationale**:
- **Landing Layer**: Raw data preservation for audit/replay
- **Bronze Layer**: Schema-on-read with data quality flags for flexible exploration
- **Silver Layer**: Curated, analytics-ready data for forecasting
- **Delta Lake**: ACID transactions, time travel, and efficient upserts
- **Unity Catalog**: Centralized governance and lineage tracking

**Trade-offs Accepted**:
- Additional complexity vs single-table approach
- Vendor lock-in to Databricks ecosystem
- Higher cost than raw S3 storage

---

## 2. Data Ingestion Strategy

### Decision: AWS Lambda + EventBridge for Daily Data Pulls
**Chosen**: Serverless Lambda functions triggered at 2AM daily

**Alternatives Considered**:
- Databricks scheduled jobs
- Apache Airflow DAGs
- Manual cron jobs

**Rationale**:
- **Serverless**: No infrastructure management, auto-scaling
- **Cost-efficient**: Pay-per-execution vs always-on compute
- **Decoupled**: Independent failure domains (market data, weather, CFTC, FX, GDELT)
- **EventBridge**: Native AWS integration with retries and DLQ

**Trade-offs Accepted**:
- 15-minute Lambda timeout constraint (required batching for weather backfill)
- Cold start latency (~1-2 seconds)
- Limited to AWS ecosystem

---

## 3. Weather Data Handling

### Decision: Forward-Fill Missing Values + Regional Aggregation
**Chosen**: Forward-fill up to 3 days, then mark as missing; aggregate 58 regions to commodity-level average

**Alternatives Considered**:
- Drop rows with missing weather data
- Interpolation (linear, spline)
- Per-region weather features (58 separate columns)
- External weather API with backfill guarantees

**Rationale**:
- **Forward-fill**: Weather changes slowly; 3-day limit prevents stale data
- **Aggregation**: Reduces dimensionality while capturing overall climate impact
- **Practical**: Historical weather data has inherent gaps; forward-fill is transparent
- **Validated**: Sugar data issue (8 days) caught by validation framework

**Trade-offs Accepted**:
- Loss of regional granularity (potential future enhancement)
- Assumption that aggregate weather correlates with prices
- Forward-fill introduces mild temporal smoothing

---

## 4. Model Selection Strategy

### Decision: Ensemble of 5 Diverse Models
**Chosen**: SARIMAX, Prophet, XGBoost, ARIMA(1,1,1), Random Walk

**Alternatives Considered**:
- Single "best" model approach
- Deep learning (LSTM, Transformer)
- Larger ensemble (10+ models)
- Only classical time series models

**Rationale**:
- **Diversity**: Different model families capture different patterns
  - SARIMAX: Seasonal patterns + weather exogenous variables
  - Prophet: Trend changes + holidays
  - XGBoost: Non-linear interactions + weather features
  - ARIMA: Classical baseline
  - Random Walk: Efficient markets hypothesis baseline
- **Ensemble Value**: Trading agent can weight models or select best per scenario
- **Interpretability**: Classical models easier to explain than deep learning
- **Data Constraints**: Only 3,763 days of data; deep learning may overfit

**Trade-offs Accepted**:
- Training time: 5 models per window vs 1 model
- Complexity: Multiple codebases to maintain
- Deep learning excluded despite potential upside (insufficient data)

---

## 5. Walk-Forward Evaluation Methodology

### Decision: Expanding Window with 14-Day Steps
**Chosen**: Initial 3 years (1,095 days) training, expand by 14 days each window, forecast 14 days ahead

**Alternatives Considered**:
- Fixed window (rolling, not expanding)
- Single train/test split
- Larger step sizes (30/60 days)
- Shorter forecast horizon (7 days)

**Rationale**:
- **Expanding Window**: Uses all available historical data (realistic for production)
- **14-Day Horizon**: Matches trading agent decision cycle
- **14-Day Steps**: Dense historical coverage for backtesting (40 windows = 560 days)
- **3-Year Initial**: Captures multiple seasonal cycles

**Trade-offs Accepted**:
- Expanding window means later models have more data (asymmetric evaluation)
- 14-day forecast horizon may be too long for volatile commodities
- Computationally expensive: 40 windows × 5 models = 200 model trainings

---

## 6. Probabilistic Forecasting Approach

### Decision: Model-Based Monte Carlo Simulation (Updated Nov 2025)
**Chosen**: 2,000 paths per model using model-specific stochastic simulation

**Alternatives Considered**:
- Simple Gaussian noise around point forecasts (original approach)
- Geometric Brownian Motion (GBM) for all models
- Analytical prediction intervals (e.g., from SARIMAX)
- Quantile regression
- Bootstrapped residuals
- Larger path counts (5,000+)

**Rationale**:
- **Model-Based Simulation**: Each model uses its own stochastic process
  - **SARIMA**: Uses `statsmodels.simulate()` to generate paths from the actual ARIMA process (respects autocorrelation, MA terms, seasonality)
  - **XGBoost**: Uses Geometric Brownian Motion (GBM) with residual-based volatility estimation
  - **Prophet**: Leverages built-in uncertainty intervals when available
  - **Random Walk**: Proper random walk simulation with step-based noise
  - **Naive**: Fallback to simple Gaussian noise
- **2,000 Paths**: Balances statistical stability with storage/compute costs
- **Centralized Module**: `utils/monte_carlo_simulation.py` provides consistent interface across all backfill scripts
- **Spark-Optimized**: Broadcast variables + RDD.map() for parallel path generation in Databricks

**Implementation Details**:
```python
# Example: SARIMA uses actual model simulation
fitted_sarimax.simulate(
    nsimulations=14,
    repetitions=1,
    initial_state=None  # Continues from training data
)
```

**Trade-offs Accepted**:
- SARIMA simulation more computationally expensive than simple noise (but more accurate)
- Fallback to Gaussian noise for unknown model types
- 2,000 paths → storage cost: 2,000 × 14 days × 5 models × 40 windows = 5.6M values per commodity

**Updated Files** (Nov 2025):
- `utils/monte_carlo_simulation.py` - New centralized simulation module
- `backfill_rolling_window.py` - Updated to use model-based simulation
- `backfill_spark.py` - Spark-parallelized with broadcast variables + RDD.map()
- `backfill_optimized.py` - In-memory optimization with model-based paths
- `backfill_daily_forecasts.py` - Graceful fallback for models without fitted objects

---

## 7. Data Schema Design

### Decision: Separate Tables for Distributions, Point Forecasts, and Metadata
**Chosen**:
- `distributions`: Wide format (day_1...day_14) with path_id
- `point_forecasts`: Long format (one row per forecast_date × model)
- `forecast_metadata`: Performance metrics and timing data

**Alternatives Considered**:
- Single unified table
- Long format for distributions (one row per path × day)
- Embedded metadata in distributions table

**Rationale**:
- **Distributions (Wide)**: Optimized for VaR/CVaR calculations (row = complete path)
- **Point Forecasts (Long)**: Optimized for time-series charting and MAE calculation
- **Separate Metadata**: Clean separation of concerns; enables dashboard without loading distributions
- **path_id=0 Convention**: Actuals stored as special "path" for consistent backtesting queries

**Trade-offs Accepted**:
- Data duplication: Actuals stored in distributions AND point_forecasts
- Wide format less flexible for ad-hoc day-level analysis
- Additional joins required for combined analysis

---

## 8. Performance Tracking Strategy

### Decision: Comprehensive Metadata with Multi-Horizon Metrics
**Chosen**: Track MAE/RMSE/MAPE at 1d, 7d, and 14d horizons + training/inference timing + hardware info

**Alternatives Considered**:
- Only 14-day aggregate metrics
- Separate evaluation scripts (not stored in database)
- Real-time metrics calculation (no pre-computation)

**Rationale**:
- **Multi-Horizon**: Short-term (1d) vs long-term (14d) performance differs; both matter for trading
- **Timing Data**: Critical for production deployment planning
- **Hardware Tracking**: Training on local vs Databricks cluster affects speed; need to normalize comparisons
- **Pre-computed**: Dashboard loads instantly vs calculating on-demand

**Trade-offs Accepted**:
- Storage overhead: 200 metadata rows (40 windows × 5 models)
- Metrics must be backfilled if calculation logic changes
- Assumes actuals are available (NULL for true future forecasts)

---

## 9. Production Forecast Strategy

### Decision: Ensemble with Recommended Production Version
**Chosen**: Generate all 5 models daily, flag recommended version based on recent performance

**Alternatives Considered**:
- Single "best" model only
- Equal-weighted ensemble averaging
- Adaptive weighting based on recent performance

**Rationale**:
- **Flexibility**: Trading agent can choose model or implement own weighting
- **Recommended Version**: Provides sensible default without forcing choice
- **All Models Available**: Allows A/B testing and fallback strategies
- **Recent Performance**: SARIMAX currently best (MAE: 7.2) but Prophet more stable

**Trade-offs Accepted**:
- 5x training cost vs single model
- Recommendation logic needs periodic review
- Trading agent must handle multiple forecast versions

---

## 10. Backtesting Infrastructure

### Decision: Historical Backfill with 40 Windows
**Chosen**: Generate 40 historical forecast windows (Jul 2018 - Oct 2024) for backtesting

**Alternatives Considered**:
- Generate forecasts on-demand for backtesting
- Fewer windows (10-20) to save compute
- Full history (100+ windows)

**Rationale**:
- **40 Windows**: 560 days of historical forecasts covers ~18 months of validation data
- **Pre-generated**: Consistent forecasts for all backtest runs (no randomness from re-training)
- **Storage-Compute Trade-off**: ~400K rows upfront vs hours of repeated computation
- **Trading Agent Unblocked**: Can immediately start strategy iteration

**Trade-offs Accepted**:
- Large storage footprint: 400K+ distribution rows
- One-time compute cost: ~30 minutes per backfill
- Fixed historical forecasts (can't tweak models without full re-run)

---

## 11. Dashboard & Visualization Strategy

### Decision: Databricks SQL Dashboard with Click-Through Windows
**Chosen**: Interactive dashboard with model performance, forecast vs actuals, and window selection

**Alternatives Considered**:
- Static Jupyter notebooks
- Streamlit/Dash web app
- Tableau/PowerBI external tool

**Rationale**:
- **Native Integration**: Direct SQL queries on Delta tables (no ETL)
- **Governance**: Same Unity Catalog permissions as data tables
- **Low Maintenance**: No separate hosting/deployment
- **Interactive**: Drill-down by model, window, commodity

**Trade-offs Accepted**:
- Limited compared to custom web app (e.g., Plotly Dash)
- Databricks-specific (not portable)
- SQL-based (less flexible than Python for complex viz)

---

## 12. Data Validation Strategy

### Decision: Continuous SQL Unit Tests + One-Time Deep Analysis
**Chosen**:
- `health_checks.py`: 10 automated SQL tests run daily
- `validate_historical_data.py`: Deep one-time analysis for backfill validation

**Alternatives Considered**:
- Manual spot-checks
- Great Expectations framework
- Real-time streaming validation

**Rationale**:
- **SQL Unit Tests**: Fast (<1 min), actionable alerts for data team
- **Exit Codes**: Integration with Databricks job alerting (0=pass, 1=fail)
- **One-Time Deep Analysis**: Catches issues like Sugar weather gap without daily overhead
- **Documented SLAs**: Clear expectations (e.g., <5% null rate, freshness <24hrs)

**Trade-offs Accepted**:
- Reactive (catches issues after ingestion, not during)
- SQL-only (can't validate complex statistical properties)
- Great Expectations more comprehensive but heavier weight

---

## 13. Model Training Strategy

### Decision: Train-Once/Inference-Many with Persistent Model Storage
**Chosen**: Separate training and inference phases with models persisted to `commodity.forecast.trained_models` table

**Alternatives Considered**:
- In-memory caching during backfill runs (non-persistent)
- Train model for every forecast date (original approach)
- File-based model storage (pickle files in S3)

**Rationale**:
- **Efficiency**: For semiannual training windows (~180 days), train 16 models instead of ~2,875 (180x fewer trainings)
- **Reproducibility**: Persist exact model state used for each forecast date
- **Versioning**: Track model versions, parameters, and training metadata
- **Scalability**: Backfill and production inference can run independently
- **Two-Phase Workflow**:
  - **Phase 1 - Training**: `train_models.py` trains N models on training windows → saves to database
  - **Phase 2 - Inference**: `backfill_rolling_window.py` loads fitted models → generates forecasts

**Model Persistence Strategy**:
- **Small models (<1MB)**: Store as JSON inline in `fitted_model_json` column (naive, random_walk)
- **Large models (≥1MB)**: Serialize with pickle, store in S3, reference path in `fitted_model_s3_path` column
- **Metadata**: Track training date, samples, parameters, AIC/BIC for model selection

**All Core Models Updated**:
1. `naive.py` - Added `naive_train()` and `naive_predict()` functions
2. `random_walk.py` - Added `random_walk_train()` and `random_walk_predict()`
3. `arima.py` - Added `arima_train()` and `arima_predict()`
4. `sarimax.py` - Added `sarimax_train()` and `sarimax_predict()`
5. `xgboost_model.py` - Added fitted_model parameter support
6. `prophet_model.py` - Added `prophet_train()` and `prophet_predict()`

**Each model now**:
- Accepts optional `fitted_model` parameter for inference-only mode
- Returns `fitted_model` in result dict for persistence
- Supports both train+predict (legacy) and inference-only (new) modes

**Trade-offs Accepted**:
- Additional database table and infrastructure complexity
- Need to manage model versioning and lifecycle
- SARIMAX/Prophet still need historical data for exogenous variable projection during inference
- Upfront training cost before backtesting can begin

**Performance Impact**:
- **Before**: ~2,875 trainings per model per commodity
- **After**: ~16 trainings per model per commodity
- **Speedup**: ~180x reduction in training operations

---

## Key Success Metrics

### Production Readiness Checklist
- [x] Data pipeline runs daily at 2AM with <5% failure rate
- [x] Forecasts generated for all 5 models within 10 minutes
- [x] Distributions table populated with 40+ historical windows
- [x] Metadata table tracks performance for model selection
- [ ] Dashboard deployed and accessible to trading agent team
- [ ] Recommended production forecast version documented

### Model Performance Targets
- **1-Day Ahead**: MAE < 10 cents/lb (SARIMAX achieving 7.2)
- **7-Day Ahead**: MAE < 15 cents/lb
- **14-Day Ahead**: MAE < 20 cents/lb
- **Stability**: <30% variance in MAE across 40 backtest windows

---

## 14. Model Evaluation Pipeline

### Decision: Post-Processing Evaluation with Comprehensive Metrics
**Chosen**: Separate `evaluate_historical_forecasts.py` script that calculates both point and probabilistic metrics

**Alternatives Considered**:
- Inline evaluation during backfill (calculate metrics while generating forecasts)
- Manual evaluation via Jupyter notebooks
- Real-time evaluation dashboard without persistent metrics

**Rationale**:
- **Separation of Concerns**: Forecast generation and evaluation are independent processes
- **Flexibility**: Can re-evaluate with new metrics without regenerating forecasts
- **Performance**: Backfill scripts focus on forecast generation; evaluation runs separately
- **Metrics Storage**: Extends existing `commodity.forecast.forecast_metadata` table with:
  - **Point Metrics** (existing): MAE, RMSE, MAPE at 1d/7d/14d horizons
  - **Probabilistic Metrics** (new): CRPS, calibration, coverage (80%/95%), sharpness at 1d/7d/14d horizons

**Implementation**:
```python
# evaluate_historical_forecasts.py usage:
python evaluate_historical_forecasts.py --commodity Coffee

# Calculates metrics for all historical forecasts in commodity.forecast.distributions
# Updates commodity.forecast.forecast_metadata with performance metrics
```

**Probabilistic Metrics Explained**:
1. **CRPS (Continuous Ranked Probability Score)**: Measures quality of full forecast distribution (lower is better)
2. **Calibration Score**: Deviation from ideal calibration (0 = perfect, measures reliability)
3. **Coverage Rate**: Fraction of actuals within prediction interval (target: 0.80 for 80% interval)
4. **Sharpness**: Average width of prediction interval (lower = more confident, but must maintain coverage)

**Schema Extension**:
```sql
-- sql/add_probabilistic_metrics_to_metadata.sql
ALTER TABLE commodity.forecast.forecast_metadata
ADD COLUMNS (
    crps_1d, crps_7d, crps_14d,
    calibration_score_1d, calibration_score_7d, calibration_score_14d,
    coverage_80_1d, coverage_80_7d, coverage_80_14d,
    coverage_95_1d, coverage_95_7d, coverage_95_14d,
    sharpness_80_1d, sharpness_80_7d, sharpness_80_14d,
    sharpness_95_1d, sharpness_95_7d, sharpness_95_14d
);
```

**Dashboard Integration**:
- **14 SQL Queries** in `sql/dashboard_queries.sql` for Databricks SQL dashboards
- Visualizations: Model comparison, performance over time, calibration monitoring, CRPS vs MAE tradeoffs
- Recommended layout: 4-row dashboard with model ranking, metrics trends, and quality checks

**Trade-offs Accepted**:
- Additional step in workflow (backfill → evaluate → dashboard)
- Metrics recalculation required if evaluation logic changes
- Extended `forecast_metadata` schema (18 new columns)

**Actuals Storage Convention**:
- Ground truth actuals stored using **hybrid approach**: `model_version='actuals'` (primary) + `is_actuals=TRUE` (legacy)
- Backfilled from `commodity.silver.unified_data` using `backfill_actuals.py`
- Handles multiple regions per date (uses `FIRST(close)` to deduplicate)
- See README.md "Actuals Storage Convention" section for detailed usage

**Updated Files** (Nov 2025):
- `backfill_actuals.py` - Backfill ground truth from unified_data with hybrid convention
- `evaluate_historical_forecasts.py` - Main evaluation script with probabilistic metrics (uses `model_version='actuals'`)
- `quick_eval.py` - Development evaluation script (gitignored, uses `model_version='actuals'`)
- `sql/add_probabilistic_metrics_to_metadata.sql` - Schema migration
- `sql/dashboard_queries.sql` - 14 dashboard queries for model comparison
- `ground_truth/core/evaluator.py` - Existing point metrics (MAE, RMSE, MAPE, directional accuracy)

---

## Future Enhancements (Not Implemented)

### Short-Term (Next 3 Months)
1. **Per-Region Weather Features**: Use all 58 regions instead of aggregate (may improve SARIMAX/XGBoost)
2. **Sugar Commodity**: Extend full pipeline to Sugar (currently Coffee-only)
3. **GDELT Sentiment Integration**: Add news sentiment as exogenous variable
4. **Adaptive Weighting**: Implement Bayesian model averaging based on recent performance

### Long-Term (6+ Months)
1. **Deep Learning**: LSTM/Transformer models once 5+ years of data available
2. **Intraday Forecasting**: Move from daily to hourly forecasts
3. **Multi-Commodity Cointegration**: Joint modeling of Coffee + Sugar + Cocoa
4. **Real-Time Updates**: Incorporate intraday news/weather for forecast revision

---

## Lessons Learned

1. **Forward-Fill Catches Real Issues**: Sugar weather gap (8 days vs 3,770 expected) would have been silent failure
2. **Wide Format Distributions**: Significantly faster for VaR calculations (10x speedup vs long format)
3. **Metadata Table Critical**: Trading agent needs performance metrics without loading 400K distribution rows
4. **Databricks SQL Fallback**: Local environment can't use Spark; SQL INSERT is slow but reliable fallback
5. **Walk-Forward is Expensive**: 40 windows × 5 models = 30 min compute; pre-generate rather than on-demand

---

**Maintenance Note**: Update this document when making decisions about:
- New data sources or features
- Model architecture changes
- Infrastructure scaling decisions
- Evaluation methodology updates
