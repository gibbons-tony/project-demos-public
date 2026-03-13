# ML Pipeline Library

**Clean, scalable PySpark ML approach for commodity price forecasting**

---

## Overview

This library replaces the legacy forecasting system with a unified PySpark ML Pipeline architecture. Inspired by the flight delay prediction pipeline, it emphasizes:
- **Simplicity**: One pipeline definition per model, clear separation of train/inference
- **Scalability**: Native PySpark parallelization, extensible transformer pattern
- **Reproducibility**: All models defined in registry, CV residuals stored for Monte Carlo

---

## Core Principles

### 1. Two-Stage Workflow

**Stage 1: Training** (`train.py`)
- Fit models with time-series cross-validation
- Save fitted pipelines to DBFS
- Track metrics (directional accuracy, MAE, RMSE) in metadata table
- Store CV residuals for Monte Carlo generation

**Stage 2: Inference** (`inference.py`)
- Load fitted pipelines from DBFS
- Generate point forecasts
- Generate 2,000 Monte Carlo paths using block bootstrap
- Write to `distributions` and `point_forecasts` tables

### 2. Pipeline Registry with Builder Functions

All models defined in `pipelines/pipeline_registry.py` using **builder functions** for dependency isolation:

```python
def build_xgboost_weather_pipeline():
    """Build XGBoost pipeline with weather features.

    Dependencies: pyspark.ml.regression.GBTRegressor
    """
    from ml_lib.transformers import WeatherFeaturesEstimator, LagFeaturesEstimator
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import GBTRegressor

    return Pipeline(stages=[
        WeatherFeaturesEstimator(),
        LagFeaturesEstimator(lags=[1, 7, 14]),
        VectorAssembler(
            inputCols=['temp_mean_c', 'humidity_mean_pct', 'lag_1', 'lag_7', 'lag_14'],
            outputCol='features'
        ),
        GBTRegressor(featuresCol='features', labelCol='close', maxIter=100)
    ])

def build_arima_pipeline():
    """Build ARIMA pipeline.

    Dependencies: statsmodels (only imported if this model is used)
    """
    from ml_lib.models import ARIMAEstimator
    from pyspark.ml import Pipeline

    return Pipeline(stages=[ARIMAEstimator(order=(1,1,1))])

PIPELINE_REGISTRY = {
    'xgboost_weather': {
        'name': 'XGBoost with Weather Features',
        'description': 'Gradient boosting with temp, humidity, precipitation',
        'builder': build_xgboost_weather_pipeline,  # Function reference
        'metadata': {
            'horizon': 14,
            'features': ['weather', 'lags'],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['pyspark.ml']
        }
    },
    'arima': {
        'name': 'ARIMA',
        'description': 'AutoRegressive Integrated Moving Average',
        'builder': build_arima_pipeline,  # Function reference
        'metadata': {
            'horizon': 14,
            'features': ['lags'],
            'target_metric': 'directional_accuracy_day0',
            'dependencies': ['statsmodels']  # Optional dependency
        }
    }
}
```

**Usage:**
```python
from ml_lib.pipelines import get_pipeline

# Only imports dependencies for xgboost_weather model
pipeline, metadata = get_pipeline('xgboost_weather')
```

**Benefits:**
- Lazy loading: Dependencies only imported when model is requested
- Isolated: Each model's imports are contained in its builder function
- Flexible: Can have models with conflicting dependencies (e.g., TensorFlow vs PyTorch)
- Clear: Easy to see what each model needs by reading its builder function

### 3. Directional Accuracy as Primary Metric

**Trading insight:** Profit depends on getting direction right, not minimizing MAE.

**Primary metric:** Directional Accuracy from Day 0
- Is day_i > day_0? (for i=1..14)
- Measures trading signal quality

**Secondary metrics:** MAE, RMSE (for model diagnostics)

### 4. Universal Monte Carlo via Block Bootstrap

**Works for ANY model type** (ARIMA, XGBoost, LSTM):
1. Collect forecast residuals during CV
2. Bootstrap blocks of residuals (preserves autocorrelation)
3. Add to point forecasts to generate 2,000 realistic paths

**Why:** Simpler than quantile regression, more general than ARIMA-specific methods.

---

## Folder Structure

```
ml_lib/
├── README.md                       # This file
├── temp/
│   └── ARCHITECTURE_ANALYSIS.md    # Detailed trade-offs and decisions
│
├── transformers/                   # Custom PySpark transformers
│   ├── weather_features.py         # Unpack weather arrays (aggregation, regions)
│   └── sentiment_features.py       # Unpack GDELT themes (weighted aggregation)
│
├── models/                         # Model implementations
│   ├── baseline.py                 # NaiveForecaster
│   └── linear.py                   # LinearRegression, Ridge, LASSO, ElasticNet
│
├── cross_validation/               # Time-series CV
│   ├── time_series_cv.py           # TimeSeriesForecastCV class
│   └── data_loader.py              # GoldDataLoader (loads gold.unified_data)
│
├── pipelines/                      # Pipeline definitions (model registry)
│   ├── pipeline_registry.py        # All model configs (builder functions)
│   └── __init__.py                 # get_pipeline(), list_models()
│
├── monte_carlo/                    # Uncertainty quantification
│   └── path_generator.py           # BlockBootstrapPathGenerator
│
├── examples/                       # Example notebooks
│   └── end_to_end_example.py       # Complete workflow demo (Databricks notebook)
│
├── train.py                        # Stage 1: Train models with CV
└── inference.py                    # Stage 2: Generate forecasts
```

---

## Quick Start

### Prerequisites

1. **Gold layer table exists:**
   ```sql
   -- Run this SQL in Databricks:
   -- research_agent/sql/create_gold_unified_data.sql
   ```

2. **Validation passed:**
   ```python
   # Run validation notebook in Databricks:
   # research_agent/infrastructure/databricks/validate_gold_unified_data.py
   ```

### Stage 1: Train Models

```bash
cd forecast_agent/ml_lib

# List available models
python train.py --list-models

# Train with 5-fold expanding window CV
python train.py \
  --commodity Coffee \
  --models naive_baseline linear_weather_min_max \
  --n-folds 5 \
  --window-type expanding

# Output:
# - Fitted pipelines: dbfs:/commodity/models/Coffee/<model>/<date>/final
# - Metadata: commodity.forecast.model_metadata
# - CV residuals: dbfs:/commodity/residuals/Coffee/<model>/<date>
```

### Stage 2: Generate Forecasts

```bash
# Load fitted pipeline and generate forecasts
python inference.py \
  --commodity Coffee \
  --models naive_baseline linear_weather_min_max \
  --n-paths 2000 \
  --block-size 3

# Output:
# - Point forecasts: commodity.forecast.point_forecasts
# - Monte Carlo paths: commodity.forecast.distributions
```

### Complete Example (Databricks Notebook)

See `examples/end_to_end_example.py` for a complete workflow demonstration including:
- Training 2 models
- Generating forecasts
- Validating results
- Visualizing uncertainty

---

## Data Flow

```
commodity.gold.unified_data (array-based daily data)
  ├─ Grain: (date, commodity)
  ├─ Weather: ARRAY<STRUCT> with ~65 regions per row
  └─ GDELT: ARRAY<STRUCT> with 7 theme groups per row
  ↓
[GoldDataLoader] → Load and filter data
  ↓
[TimeSeriesForecastCV]
  ├─ Expanding window splits (2015-2020, 2015-2021, etc.)
  ├─ Fit pipeline on each fold
  ├─ Collect residuals for uncertainty estimation
  └─ Calculate directional accuracy metrics
  ↓
[train.py] → Fitted PipelineModel saved to DBFS
  ├─ Model: dbfs:/commodity/models/Coffee/naive_baseline/2024-12-05/final
  ├─ Residuals: dbfs:/commodity/residuals/Coffee/naive_baseline/2024-12-05
  └─ Metadata: commodity.forecast.model_metadata
  ↓
[inference.py] → Load pipeline, generate forecasts
  ├─ Point forecasts (14-day predictions)
  └─ Monte Carlo paths (2,000 paths via block bootstrap)
  ↓
commodity.forecast.point_forecasts (1 row per forecast)
commodity.forecast.distributions (2,000 paths per forecast)
```

---

## Adding a New Model

### 1. Create Builder Function in Registry

Edit `pipelines/pipeline_registry.py`:
```python
def build_my_new_model_pipeline():
    """Build my new model.

    Dependencies: pyspark.ml, scikit-learn
    """
    # Import dependencies HERE (lazy loading)
    from ml_lib.transformers import WeatherFeaturesEstimator
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import RandomForestRegressor

    return Pipeline(stages=[
        WeatherFeaturesEstimator(),
        VectorAssembler(
            inputCols=['temp_mean_c', 'humidity_mean_pct'],
            outputCol='features'
        ),
        RandomForestRegressor(
            featuresCol='features',
            labelCol='close',
            numTrees=100
        )
    ])

# Add to registry
PIPELINE_REGISTRY['my_new_model'] = {
    'name': 'Random Forest with Weather',
    'description': 'RF using temperature and humidity',
    'builder': build_my_new_model_pipeline,  # Function reference
    'metadata': {
        'horizon': 14,
        'features': ['weather'],
        'target_metric': 'directional_accuracy_day0',
        'dependencies': ['pyspark.ml']
    }
}
```

**Key points:**
- Builder function name: `build_{model_name}_pipeline()`
- Import dependencies INSIDE the function (lazy loading)
- Docstring lists dependencies for documentation
- `metadata['dependencies']` tracks what's needed (for checking)

### 2. Train and Evaluate

```bash
python train.py --commodity Coffee --models my_new_model --cv-folds 5
```

### 3. Generate Forecasts

```bash
python inference.py --commodity Coffee --model my_new_model --start-date 2024-01-01
```

**That's it!** Dependencies are only loaded when you use this model.

---

## Model Persistence

**Method:** PySpark native `Pipeline.save()` + SQL metadata table

**Why:**
- Simple, no extra dependencies (no MLflow setup)
- Native PySpark API
- Easy migration to MLflow later if needed
- Metadata queryable in SQL for analysis

**Storage:**
- Fitted pipelines: `dbfs:/commodity/models/{commodity}/{model}/{date}/final`
- Fold models (optional): `dbfs:/commodity/models/{commodity}/{model}/{date}/fold_{i}`
- Metadata: `commodity.forecast.model_metadata`
- CV residuals: `dbfs:/commodity/residuals/{commodity}/{model}/{date}`

---

## Time-Series Cross-Validation

**Expanding Window (Default):**
```
Fold 1: Train [2018-2020] → Validate [2021]
Fold 2: Train [2018-2021] → Validate [2022]
Fold 3: Train [2018-2022] → Validate [2023]
...
```
- Uses all historical data
- Better for non-stationary time series
- Recommended for commodity prices

**Rolling Window (Optional):**
```
Fold 1: Train [2018-2020] → Validate [2021]
Fold 2: Train [2019-2021] → Validate [2022]
Fold 3: Train [2020-2022] → Validate [2023]
...
```
- Fixed window size slides forward
- Better for stationary data with regime changes
- Configure with `--cv-window rolling`

---

## Evaluation Metrics

### Directional Accuracy from Day 0 (Primary)

**Definition:** For each forecast horizon i ∈ {1..14}, is the direction correct?
```python
actual_direction = actual_day_i > actual_day_0
forecast_direction = forecast_day_i > forecast_day_0
correct = (actual_direction == forecast_direction)
```

**Averaged across all horizons:** `mean(correct[day_1], ..., correct[day_14])`

**Why it matters:** This is what the trading agent needs to make buy/hold/sell decisions.

### MAE and RMSE (Secondary)

Used for model diagnostics and understanding prediction quality, but NOT the primary optimization target.

---

## Monte Carlo Path Generation

**Goal:** Generate 2,000 realistic autocorrelated paths for risk analysis.

**Method:** Block Bootstrap on CV Residuals

1. During CV, collect forecast errors: `residuals = actual - predicted`
2. To generate path:
   - Start with point forecast: `[day_1, ..., day_14]`
   - Sample blocks of residuals (size 3) to preserve autocorrelation
   - Add to point forecast: `path = forecast + sampled_residuals`
   - Repeat 2,000 times

**Why this works for all models:**
- ARIMA: Residuals capture stochastic component
- XGBoost: Residuals capture prediction uncertainty
- LSTM: Residuals capture model error patterns

**Key:** Use model-specific CV residuals, not generic historical volatility.

---

## Integration with Trading Agent

**Contract:** Trading agent expects these tables:

**`commodity.forecast.distributions`**
- Columns: `commodity`, `cutoff_date`, `model_name`, `path_id`, `day_1`...`day_14`
- 2,000 rows per (commodity, cutoff_date, model) combination
- Used for risk analysis and portfolio optimization

**`commodity.forecast.point_forecasts`**
- Columns: `commodity`, `cutoff_date`, `model_name`, `day_1`...`day_14`, `actual_close`
- 1 row per (commodity, cutoff_date, model) combination
- Used for simple trading strategies

**Our output matches this contract exactly.** No changes needed to trading agent.

---

## Dependency Management Pattern

**Problem:** Different models need different dependencies (e.g., statsmodels for ARIMA, PyTorch for LSTM).

**Solution:** Builder functions with lazy imports.

### Example: Optional statsmodels dependency

```python
# pipelines/pipeline_registry.py

def build_arima_pipeline():
    """Build ARIMA pipeline.

    Dependencies: statsmodels>=0.13.0
    """
    try:
        from ml_lib.models import ARIMAEstimator
    except ImportError:
        raise ImportError(
            "ARIMA model requires statsmodels. Install with: pip install statsmodels"
        )

    from pyspark.ml import Pipeline
    return Pipeline(stages=[ARIMAEstimator(order=(1,1,1))])
```

**Benefits:**
- Only fails if you actually try to use ARIMA
- Other models work fine without statsmodels
- Clear error message if dependency missing
- Can check `metadata['dependencies']` before attempting to load

---

## Implementation Status

### Phase 1: Core Infrastructure ✅ Complete
- [x] Create folder structure
- [x] Document architecture decisions
- [x] Implement `GoldDataLoader` (array-based gold.unified_data)
- [x] Implement `TimeSeriesForecastCV` with directional accuracy
- [x] Implement `BlockBootstrapPathGenerator`
- [x] Implement custom transformers:
  - [x] `WeatherAggregator` (min/max/mean aggregations)
  - [x] `WeatherRegionSelector` (top coffee regions)
  - [x] `WeatherRegionExpander` (all ~65 regions)
  - [x] `GdeltAggregator` (weighted by article count)
  - [x] `GdeltThemeExpander` (7 theme groups)
- [x] Implement baseline models:
  - [x] `NaiveForecaster`
  - [x] Linear regression variants (Ridge, LASSO, ElasticNet)
- [x] Create pipeline registry with builder functions
- [x] Create `train.py` (Stage 1 - training workflow)
- [x] Create `inference.py` (Stage 2 - forecasting workflow)
- [x] Create end-to-end example notebook

### Phase 2: Add Advanced Models
- [ ] Add XGBoost with full feature engineering
- [ ] Add ARIMA/SARIMAX (custom Estimator wrapper)
- [ ] Add LSTM/TFT (deep learning models)
- [ ] Compare metrics across all models

### Phase 3: Production Deployment
- [ ] Run validation notebook in Databricks
- [ ] Test end-to-end workflow with Coffee 2024 data
- [ ] Wire up to Databricks scheduled jobs
- [ ] Backfill historical forecasts (2015-2024)
- [ ] Integrate with trading_agent
- [ ] Deprecate legacy code

---

## Current Models Available

1. **`naive_baseline`** - Forecast = last observed value (baseline for comparison)
2. **`linear_weather_min_max`** - Linear regression with extreme weather events (min/max)
3. **`linear_weather_all`** - Linear regression with all weather aggregations (mean + min + max)
4. **`ridge_top_regions`** - Ridge regression with top 6 coffee producing regions

**To list all models:**
```python
from ml_lib.pipelines import list_models
list_models()
```

## Next Steps

1. **Immediate:** Run validation notebook in Databricks to verify gold.unified_data
2. **Test:** Execute end-to-end example notebook with Coffee 2024 data
3. **Expand:** Add XGBoost, ARIMA, and deep learning models
4. **Production:** Backfill historical forecasts and integrate with trading_agent

---

## References

- **Architecture Analysis:** [temp/ARCHITECTURE_ANALYSIS.md](temp/ARCHITECTURE_ANALYSIS.md) - Full trade-offs and decisions
- **Current System:** [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) - Legacy train-once pattern
- **Inspiration:** Flight delay ML pipeline (DS261 project)

---

**Maintained by:** Connor Watson
**Last Updated:** 2024-12-05
**Status:** Active Development
