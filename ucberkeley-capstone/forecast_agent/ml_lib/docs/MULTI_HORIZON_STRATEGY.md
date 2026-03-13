# Multi-Horizon Forecasting Strategy

**Issue:** Linear regression models in `pipeline_registry.py` currently output only `forecast_day_1`, but we need 14-day forecasts.

**Solution:** Use the **Direct Multi-Horizon** strategy where we train 14 separate models.

---

## Problem Statement

PySpark's `LinearRegression` (and similar models) are single-output by default:

```python
LinearRegression(
    featuresCol="features",
    labelCol="close",
    predictionCol="forecast_day_1"  # Only outputs day 1!
)
```

For 14-day forecasts, we need `forecast_day_1` through `forecast_day_14`.

---

## Solution Options

### Option 1: Direct Multi-Horizon (CHOSEN ✅)

**Strategy:** Train 14 separate models, one for each forecast horizon.

```python
models = []
for day in range(1, 15):
    models.append(
        LinearRegression(
            featuresCol="features",
            labelCol=f"target_day_{day}",  # Shifted target
            predictionCol=f"forecast_day_{day}"
        )
    )

pipeline = Pipeline(stages=[
    WeatherAggregator(...),
    GdeltAggregator(...),
    VectorAssembler(...),
    *models  # 14 models in sequence
])
```

**Pros:**
- Simple, robust
- Each horizon gets its own model (can learn different patterns)
- Works with any PySpark estimator
- Easy to parallelize (train models in parallel)

**Cons:**
- 14x training time (mitigated by autoscaling cluster)
- 14x model storage (small models, not an issue)

**Implementation:**
- Modify `pipeline_registry.py` to generate 14 models per pipeline
- Update `TimeSeriesForecastCV` to handle multi-model pipelines
- Validation: Check that all `forecast_day_1...forecast_day_14` columns exist

### Option 2: Recursive Strategy

**Strategy:** Use forecast from day i as input for day i+1.

```
day_1 = model.predict(features)
day_2 = model.predict(features + lag_feature(day_1))
day_3 = model.predict(features + lag_feature(day_2))
...
```

**Pros:**
- Only one model to train
- Captures auto-correlation

**Cons:**
- Error compounds (day_14 has accumulated errors from days 1-13)
- Complex feature engineering (need to create lag features dynamically)
- Harder to validate

**Status:** Not recommended for now (use Direct instead)

### Option 3: Multi-Output Wrapper

**Strategy:** Wrap model in custom multi-output estimator.

```python
class MultiOutputRegressor(Estimator):
    def _fit(self, df):
        models = []
        for day in range(1, 15):
            model = LinearRegression(labelCol=f"target_day_{day}")
            models.append(model.fit(df))
        return MultiOutputModel(models)
```

**Pros:**
- Clean abstraction
- Encapsulates multi-horizon logic

**Cons:**
- Need to implement custom PySpark Estimator
- More complex debugging
- Harder to integrate with existing CV code

**Status:** Future enhancement (after Direct strategy is validated)

---

## Chosen Solution: Direct Multi-Horizon

### Implementation Steps

1. **Create shifted target columns**

In `TimeSeriesForecastCV`, before training:

```python
# Add shifted targets for each horizon
for day in range(1, 15):
    df = df.withColumn(
        f"target_day_{day}",
        lead("close", day).over(Window.orderBy("date"))
    )
```

2. **Update pipeline_registry.py**

```python
def build_linear_weather_min_max_pipeline() -> Pipeline:
    """Build 14 linear regression models (one per horizon)."""
    from ml_lib.transformers.weather_features import WeatherAggregator
    from ml_lib.transformers.sentiment_features import GdeltAggregator
    from pyspark.ml.feature import VectorAssembler
    from pyspark.ml.regression import LinearRegression

    # Feature engineering stages
    weather = WeatherAggregator(inputCol="weather_data", aggregation="min_max")
    gdelt = GdeltAggregator(inputCol="gdelt_themes")
    assembler = VectorAssembler(
        inputCols=[...],
        outputCol="features",
        handleInvalid="skip"
    )

    # 14 models (one per horizon)
    models = []
    for day in range(1, 15):
        models.append(
            LinearRegression(
                featuresCol="features",
                labelCol=f"target_day_{day}",
                predictionCol=f"forecast_day_{day}",
                regParam=0.0,
                maxIter=100
            )
        )

    return Pipeline(stages=[weather, gdelt, assembler, *models])
```

3. **Validation**

After pipeline.fit(df):

```python
predictions = pipeline.transform(df)

# Verify all columns exist
for day in range(1, 15):
    assert f"forecast_day_{day}" in predictions.columns
```

---

## Current Status

**Baseline Model (NaiveForecaster):**
✅ Already generates all 14 days correctly

**Linear Regression Models:**
⚠️ Need update to use Direct Multi-Horizon strategy

**Action Items:**
1. Update `pipeline_registry.py` for all linear models
2. Add target shifting to `TimeSeriesForecastCV`
3. Test end-to-end with updated pipelines
4. Validate that CV metrics are calculated across all horizons

---

## Edge Cases to Handle

### 1. Insufficient Data for Long Horizons

If data ends on 2024-12-05, we can't create `target_day_14` for dates after 2024-11-21.

**Solution:** Filter out rows where any target is null before training.

```python
# Drop rows with null targets
for day in range(1, 15):
    df = df.filter(col(f"target_day_{day}").isNotNull())
```

### 2. Null Features

Some dates may have null weather or GDELT data.

**Solution:** Use `handleInvalid="skip"` in `VectorAssembler` (already configured).

### 3. Model Persistence

With 14 models per pipeline, saved pipelines will be larger.

**Solution:** No change needed. `Pipeline.save()` handles multiple stages automatically.

---

## Testing Plan

1. **Unit test:** Create sample data with 30 rows, verify 14 models train successfully
2. **Integration test:** Run end-to-end on Coffee 2024, verify forecast shape is (n_dates, 14)
3. **CV test:** Ensure directional accuracy is calculated for all horizons
4. **Persistence test:** Save/load pipeline, verify all 14 models are restored

---

## Performance Considerations

**Training Time:**
- Single model: ~1 minute
- 14 models (sequential): ~14 minutes
- 14 models (parallel): ~1-2 minutes (with Spark parallelization)

**Recommendation:** Use training cluster (i3.2xlarge, 2-8 workers) for full training.

**Optimization:** Models can be trained in parallel since they're independent. Spark automatically parallelizes Pipeline stages that don't depend on each other.

---

## Alternatives Considered

### Direct + Separate Pipelines (NOT CHOSEN)

Train 14 completely separate pipelines instead of one pipeline with 14 models.

**Rejected because:**
- Duplicates feature engineering 14 times (inefficient)
- Harder to maintain (14 pipeline definitions)
- Direct multi-horizon keeps feature engineering shared (better)

---

## References

- Taieb, S. B., et al. (2012). "A review and comparison of strategies for multi-step ahead time series forecasting"
- PySpark ML Pipeline docs: https://spark.apache.org/docs/latest/ml-pipeline.html

---

**Status:** Implementation in progress
**Last Updated:** 2024-12-05
**Next Steps:** Update pipeline_registry.py and test
