# Forecast Agent Architecture

## Train-Once/Inference-Many Pattern

This architecture decouples model training from forecasting, enabling massive performance improvements for historical backfills and production workflows.

### The Problem

Traditional forecasting systems retrain models for every forecast date:
- **2,875 model trainings** for a 2018-2024 Coffee backfill
- **79,560 rows loaded** per forecast (entire history)
- **24-48 hours** for full historical backfill
- Expensive compute, especially on Databricks SQL Warehouses

### The Solution

Two-phase architecture that trains models periodically and reuses them for multiple forecasts:

**Phase 1: Training (periodic, expensive)**
```bash
python train_models.py \
  --commodity Coffee \
  --models naive random_walk arima_111 sarimax_auto_weather xgboost \
  --train-frequency semiannually \
  --model-version v1.0
```

What it does:
- Trains models on fixed training windows (e.g., every 6 months)
- Persists fitted models to `commodity.forecast.trained_models` table
- Storage: JSON for small models (<1MB), S3 for large models (≥1MB)
- **Semiannual training (2018-2024): ~16 model trainings instead of ~2,875**

**Phase 2: Inference (daily, fast)**
```bash
python backfill_rolling_window.py \
  --commodity Coffee \
  --models naive xgboost \
  --train-frequency semiannually \
  --use-pretrained
```

What it does:
- Loads pretrained models from database
- Generates 2,000 Monte Carlo paths per forecast
- Writes to `commodity.forecast.distributions` table
- Auto-resumes from last completed date
- **Data loading: ~880x faster (90 rows vs 79,560 rows)**

### Performance Comparison

| Metric | Without Pretrained | With Pretrained | Speedup |
|--------|-------------------|-----------------|---------|
| Model trainings | 2,875 | 16 | **180x** |
| Data loading per forecast | 79,560 rows | 90 rows | **880x** |
| Total time (full backfill) | 24-48 hours | 1-2 hours | **24x** |

### Model Persistence Strategy

Models are stored in `commodity.forecast.trained_models` table with intelligent size-based routing:

**Small models (<1MB)**: Stored as JSON in `fitted_model_json` column
- Naive, Random Walk, ARIMA
- Fast to save/load
- No external dependencies

**Large models (≥1MB)**: Stored in S3, referenced by `fitted_model_s3_path` column
- XGBoost, SARIMAX with many parameters
- Efficient for large serialized objects
- Requires AWS credentials in environment

Example row:
```python
{
    'commodity': 'Coffee',
    'model_name': 'xgboost',
    'train_frequency': 'semiannually',
    'training_end_date': '2023-06-30',
    'fitted_model_s3_path': 's3://bucket/models/coffee_xgboost_2023-06-30.pkl',
    'model_version': 'v1.0',
    'year': 2023,
    'month': 6
}
```

### Training Frequencies

Choose based on model complexity and data volatility:

**Semiannually** (recommended for expensive models):
- XGBoost, SARIMAX with auto-tuning
- ~16 trainings for 2018-2024 Coffee backfill
- Best cost/performance tradeoff

**Monthly** (for fast models or volatile data):
- Naive, Random Walk, ARIMA(1,1,1)
- ~84 trainings for 2018-2024 Coffee backfill
- More responsive to regime changes

**Per-date** (legacy, not recommended):
- Only for model development/testing
- ~2,875 trainings for 2018-2024 Coffee backfill
- Extremely slow and expensive

### Implementation Pattern

All models implement three functions for train/predict separation:

```python
def my_model_train(df_pandas, target='close', **params) -> dict:
    """Train model and return fitted state (no forecasting)."""
    model = fit_model(df_pandas, target, **params)
    return {
        'fitted_model': model,
        'last_date': df_pandas.index[-1],
        'target': target,
        'model_type': 'my_model',
    }

def my_model_predict(fitted_model_dict, horizon=14, **params) -> pd.DataFrame:
    """Generate forecast using fitted model (no training)."""
    model = fitted_model_dict['fitted_model']
    return forecast_df  # columns: day_1 to day_14

def my_model_forecast_with_metadata(df_pandas, commodity, fitted_model=None, **params) -> dict:
    """Unified interface supporting both modes."""
    if fitted_model is None:
        fitted_model = my_model_train(df_pandas, **params)

    forecast_df = my_model_predict(fitted_model, **params)

    return {
        'forecast_df': forecast_df,
        'fitted_model': fitted_model,  # For persistence
    }
```

### Lookback Optimization

When using pretrained models, only load recent data needed for prediction:

```python
# Without pretrained: Load entire history (79,560 rows)
lookback_days = None  # Load all data since 2018

# With pretrained: Load last 90 days only (90 rows)
lookback_days = 90 if use_pretrained else None
training_df = load_training_data(connection, commodity, cutoff_date, lookback_days)
```

**Result**: 880x faster data loading (90 rows vs 79,560 rows)

### Database Reconnection Strategy

Databricks SQL Warehouses have 15-minute session timeouts. Scripts handle this automatically:

```python
# Reconnect before batch writes
if i % batch_size == 0:
    connection.close()
    connection = get_connection()

# Resume mode skips existing forecasts
if resume and forecast_exists(connection, commodity, model_name, cutoff_date):
    continue
```

Just rerun the same command to continue after timeout.

### Batch Writing

Write forecasts in batches for 10-20x speedup:

- Default: 50 forecasts per batch
- Each batch: 2,000 paths + 14 point forecasts + actuals
- Progress logged every 50 forecasts
- Automatic reconnection between batches

### Spark Parallelization

For massive backfills (1000+ dates), use Databricks Spark for parallel processing.

See: [SPARK_BACKFILL_GUIDE.md](SPARK_BACKFILL_GUIDE.md)

## Data Contracts

### Input Table

**`commodity.gold.unified_data` (Recommended)**
- Unified commodity prices with multi-regional weather (array-based), GDELT sentiment (7 theme groups), VIX, exchange rates
- Daily continuous data (including weekends) with forward-fill
- Grain: (date, commodity) - 90% fewer rows than silver (~7k vs ~75k)
- Array structures: `weather_data` (regions), `gdelt_themes` (theme groups)

**`commodity.silver.unified_data` (Legacy - Maintained for Compatibility)**
- Same features as gold, but regional grain: (date, commodity, region)
- Use gold.unified_data for new models unless you need explicit regional rows
- See `../research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md` for details

### Output Tables

All tables in `commodity.forecast` schema:

**`point_forecasts`**
- 14-day forecasts with prediction intervals
- Columns: day_1 through day_14, actual_close

**`distributions`**
- 2,000 Monte Carlo paths for risk analysis
- Columns: day_1 through day_14, path_id (0-1999)
- Actuals stored with `model_version='actuals'` and `is_actuals=TRUE`

**`forecast_metadata`**
- Model performance metrics for backtesting
- MAE, RMSE, Dir Day0 (directional accuracy from day 0)

**`trained_models`**
- Persistent model storage for train-once pattern
- Partitioned by (year, month)
- Fields: fitted_model_json OR fitted_model_s3_path

### Actuals Storage Convention

Ground truth actuals use a **hybrid convention** for backwards compatibility:

**Primary** (use in new code):
```python
WHERE model_version = 'actuals'
```

**Legacy** (maintained for compatibility):
```python
WHERE is_actuals = TRUE AND path_id = 1
```

Backfill actuals:
```bash
python backfill_actuals.py --commodity Coffee --start-date 2018-01-01 --end-date 2025-11-17
```

## Model Registry

Models are registered in `ground_truth/config/model_registry.py` with standardized interface:

```python
BASELINE_MODELS = {
    'my_new_model': {
        'name': 'My Model',
        'function': my_model.my_model_forecast_with_metadata,
        'params': {
            'target': 'close',
            'exog_features': ['temp_mean_c', 'vix'],
            'horizon': 14
        }
    }
}
```

See: [ground_truth/config/model_registry.py](../ground_truth/config/model_registry.py)

## Production Model

**SARIMAX+Weather** (`sarimax_auto_weather`)
- MAE: $3.10
- Directional Accuracy from Day 0: 69.5% ± 27.7%
- Features: temp_mean_c, humidity_mean_pct, precipitation_mm
- Horizon: 14 days
- Training: Semiannual

Evaluated using 30-window walk-forward validation (420 days, non-overlapping).

## Key Metrics

- **MAE** (Mean Absolute Error): Average prediction error in dollars
- **RMSE** (Root Mean Squared Error): Penalizes large errors
- **Dir Day0**: Directional accuracy from day 0 (primary trading metric)
- **Dir**: Day-to-day directional accuracy (less useful for trading)

## Critical Findings

### ARIMA(auto) = Naive

`auto_arima` without exogenous variables selects order (0,1,0), which is mathematically equivalent to naive forecast. **Always use exogenous features with SARIMAX models.**

### Directional Accuracy from Day 0

Traditional day-to-day directional accuracy is misleading for trading. Use **Dir Day0** metric which measures whether day i > day 0 (trading signal quality).

### Column Name Conventions

Weather and feature columns in unified_data:
- `temp_mean_c` (NOT temp_c)
- `humidity_mean_pct` (NOT humidity_pct)
- `vix` (NOT vix_close)
