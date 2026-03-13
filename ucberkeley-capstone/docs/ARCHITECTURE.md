# System Architecture

> **⚠️ NOTICE: This document describes legacy V1/V2 architecture (2024-2025).**
>
> **For current forecast_agent architecture**, see:
> - [forecast_agent/README.md](../forecast_agent/README.md) - Current ml_lib pipeline overview
> - [forecast_agent/docs/ARCHITECTURE.md](../forecast_agent/docs/ARCHITECTURE.md) - Train-once/inference-many pattern
> - [forecast_agent/docs/FORECASTING_EVOLUTION.md](../forecast_agent/docs/FORECASTING_EVOLUTION.md) - V1 → V2 → V3 progression
>
> **For current data architecture**, see:
> - [research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md](../research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md) - Gold layer design
> - [research_agent/docs/GOLD_MIGRATION_GUIDE.md](../research_agent/docs/GOLD_MIGRATION_GUIDE.md) - Migration from silver to gold
>
> This document is preserved for historical context only. The ground_truth pipeline described here has been moved to [forecast_agent/deprecated/](../forecast_agent/deprecated/).

---

## High-Level Data Flow (Legacy V1/V2)

```
┌─────────────────┐
│ Research Agent  │  (Francisco)
│  Data Pipeline  │
└────────┬────────┘
         │ Creates
         ↓
┌─────────────────────────────┐
│ commodity.silver.          │
│    unified_data             │  ← Single source of truth
│ (date, commodity, region)   │
└────────┬────────────────────┘
         │ Consumed by
         ↓
┌─────────────────────────────┐
│  Forecast Agent             │  (Connor - YOU)
│  ┌─────────────────────┐   │
│  │  Model Bank         │   │  ← Multiple models in parallel
│  │  - ARIMA           │   │
│  │  - SARIMAX          │   │
│  │  - LSTM             │   │
│  │  - (future models)  │   │
│  └─────────────────────┘   │
└────────┬────────────────────┘
         │ Writes
         ↓
┌────────────────────┬────────────────────┐
│ point_forecasts    │   distributions    │
│ (14-day forecasts) │ (2000 MC paths)    │
└────────┬───────────┴────────┬───────────┘
         │                     │
         └─────────┬───────────┘
                   │ Consumed by
                   ↓
         ┌─────────────────┐
         │ Risk/Trading    │  (Mark)
         │     Agent       │
         └─────────────────┘
```

## Forecast Agent Architecture (Your Domain)

### Design Philosophy

1. **Modular**: Each model is independent, swappable
2. **Scalable**: Add new models without changing infrastructure
3. **Parallel**: Train multiple models simultaneously (PySpark)
4. **Reproducible**: Configuration-driven, versioned outputs
5. **Fast iteration**: Local testing, Databricks production

### Package Structure

```
forecast_agent/
├── ground_truth/                    # Python package
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── model_registry.py       # Model definitions & hyperparameters
│   ├── core/
│   │   ├── __init__.py
│   │   ├── data_loader.py          # Load unified_data
│   │   ├── base_forecaster.py      # Abstract base class
│   │   ├── forecast_writer.py      # Write to Delta (with leakage detection)
│   │   └── evaluator.py            # Performance metrics & regression monitoring
│   ├── features/                    # Function-based feature engineering
│   │   ├── __init__.py
│   │   ├── aggregators.py          # Regional aggregation strategies
│   │   ├── transformers.py         # Time-based features (lags, diffs)
│   │   └── covariate_projection.py # Forecast horizon handling
│   └── models/
│       ├── __init__.py
│       ├── naive_forecaster.py     # Persistence baseline
│       ├── random_walk_forecaster.py # Random walk baseline
│       ├── arima_forecaster.py     # Simple ARIMA
│       ├── sarimax_forecaster.py   # Auto-fitted SARIMAX
│       └── (lstm, timesfm, xgboost...)  # Future models
├── notebooks/
│   └── experiments/                 # Model evaluation, visualization
├── proof_of_concept/
│   └── Global Forecast Agent V1.ipynb  # Original prototype
└── tests/
```

### Configuration-Driven Design

**model_registry.py** defines all models:
```python
from ground_truth.features import aggregators, covariate_projection

MODELS = {
    "naive_persistence_v1": {
        "class": "NaiveForecaster",
        "hyperparameters": {"method": "persistence"},
        "features": ["close"],
        "commodity": "Coffee",
        "feature_fn": None,
        "covariate_projection_fn": covariate_projection.none_needed
    },

    "random_walk_v1": {
        "class": "RandomWalkForecaster",
        "hyperparameters": {"with_drift": True},
        "features": ["close"],
        "commodity": "Coffee",
        "feature_fn": None,
        "covariate_projection_fn": covariate_projection.none_needed
    },

    "arima_baseline_v1": {
        "class": "ARIMAForecaster",
        "hyperparameters": {"order": (1, 1, 1)},
        "features": ["close"],
        "commodity": "Coffee",
        "feature_fn": None,
        "covariate_projection_fn": covariate_projection.none_needed
    },

    "sarimax_auto_v1": {
        "class": "SARIMAXForecaster",
        "hyperparameters": {
            "auto_order": True,  # Auto-fit (p,d,q)
            "max_p": 5,
            "max_d": 2,
            "max_q": 5
        },
        "features": ["close", "temp_c", "humidity_pct", "precipitation_mm"],
        "commodity": "Coffee",
        "feature_fn": aggregators.aggregate_regions_mean,
        "covariate_projection_fn": covariate_projection.persist_last_value
    }
}
```

### Feature Engineering - Function-Based Approach

**Design Philosophy**: Functions are composable, testable, and reusable across models.

**Aggregation Functions** (`features/aggregators.py`):
```python
def aggregate_regions_mean(df_spark, commodity, features, cutoff_date=None):
    """Average weather across all regions - simple baseline"""

def aggregate_regions_weighted(df_spark, commodity, features, cutoff_date=None):
    """Weight by production volume - more sophisticated"""

def pivot_regions_as_features(df_spark, commodity, features, cutoff_date=None):
    """Each region becomes separate feature (for LSTM/transformers)"""
```

**Covariate Projection Functions** (`features/covariate_projection.py`):
```python
def none_needed(df_spark, features, horizon=14):
    """No covariates (pure ARIMA)"""

def persist_last_value(df_spark, features, horizon=14):
    """Roll forward most recent values (prototype approach)"""

def seasonal_average(df_spark, features, horizon=14, lookback_years=3):
    """Use historical average for same calendar period"""

def weather_forecast_api(df_spark, features, horizon=14):
    """Use actual 14-day weather forecast (FUTURE - high impact)"""
```

**Transformer Functions** (`features/transformers.py`):
```python
def add_lags(df_spark, features, lags=[1, 7, 14]):
    """Add lagged features (for XGBoost, LSTM)"""

def add_rolling_stats(df_spark, features, windows=[7, 30]):
    """Add rolling mean/std (for XGBoost)"""

def add_differences(df_spark, features):
    """Add price changes (for XGBoost)"""
```

**Data Hierarchy**:
- **Global**: VIX, commodity prices, GDELT sentiment (future)
- **Country**: Forex rates (cop_usd, vnd_usd, etc.)
- **Region**: Weather (temp_c, humidity_pct, precipitation_mm)

### Execution Flow

```python
# 1. Load configuration
model_config = MODELS["sarimax_auto_v1"]

# 2. Load unified data
df = data_loader.load_unified_data(commodity="Coffee")

# 3. Apply feature engineering (if specified)
if model_config["feature_fn"]:
    df = model_config["feature_fn"](
        df_spark=df,
        commodity="Coffee",
        features=model_config["features"]
    )

# 4. Train model with dynamic cutoff (for backtesting)
forecaster = model_config["class"](
    hyperparameters=model_config["hyperparameters"],
    features=model_config["features"],
    covariate_projection_fn=model_config["covariate_projection_fn"]
)

# Dynamic cutoff_date (runtime parameter, not config)
forecaster.fit(df, cutoff_date="2024-01-15")  # For backtesting
# OR
forecaster.fit(df, cutoff_date=None)  # For production (use all data)

# 5. Generate forecasts with covariate projection
point_forecasts = forecaster.predict(horizon=14)  # Uses covariate_projection_fn
distributions = forecaster.sample(n_paths=2000, horizon=14)

# 6. Write to Delta tables with leakage detection
forecast_writer.write_point_forecasts(
    forecasts_df=point_forecasts,
    model_metadata={
        "model_version": "sarimax_auto_v1",
        "training_cutoff_date": "2024-01-15",
        "fitted_parameters": forecaster.fitted_order,
        ...
    }
)
forecast_writer.write_distributions(distributions)
forecast_writer.write_actuals(...)  # Separate table
```

### Parallelization Strategy

**Level 1: Model parallelism**
- Train different models simultaneously
- Each model version = separate Spark job

**Level 2: Commodity parallelism**
- Coffee and Sugar forecasted independently
- 2x parallelization

**Level 3: Backtesting parallelism**
- Multiple cutoff dates processed in parallel
- PySpark UDFs for walk-forward validation

**Implementation**:
```python
# Spark distributes across cutoff dates
cutoff_dates = pd.date_range('2023-01-01', '2024-10-28', freq='D')
spark_df = spark.createDataFrame([(str(d),) for d in cutoff_dates], ["cutoff_date"])

# Parallel execution
results = spark_df.rdd.map(lambda row: train_and_forecast(row.cutoff_date)).collect()
```

## Development Workflow

### Local Development (Rapid Iteration)
1. Work with `data/unified_data_snapshot_all.parquet` (468 KB)
2. Test models on sample data
3. Validate logic, schemas, outputs

### Databricks Deployment
1. Upload Python modules to Databricks Repos or DBFS
2. Run on full dataset
3. Leverage cluster parallelization

### Dual-Mode Code Pattern
```python
def load_unified_data(local_mode=False):
    if local_mode:
        return spark.read.parquet("data/unified_data_snapshot_all.parquet")
    else:
        return spark.table("commodity.silver.unified_data")
```

## Model Versioning

**Convention**: `{model_type}_{variant}_v{number}`

Examples:
- `arima_baseline_v1`: Simple ARIMA(1,1,1) on close price
- `sarimax_weather_v1`: SARIMAX with weather covariates
- `sarimax_full_v2`: All features, tuned hyperparameters
- `lstm_regional_v1`: LSTM with region pivots

**Storage**: Partitioned by `model_version` in Delta tables

**Production Flag**: Connor designates which model is "production" for trading agent

## Future Enhancements

1. **MLflow integration**: Track experiments, hyperparameters, metrics
2. **Model registry**: Centralized model storage and versioning
3. **API layer**: REST API for real-time forecasts
4. **Monitoring dashboard**: Model performance tracking
5. **Auto-retraining**: Scheduled jobs to update models daily
