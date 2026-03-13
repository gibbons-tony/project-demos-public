# Model Selection Strategy: Fit Many, Publish Few

**Core Principle**: Test hundreds of model configurations, publish only the best ~15 to production

**Why**: Trading agent tests ALL published forecasts → must curate a diverse, high-quality set

---

## Problem Statement

**Without Selection**:
- Fit 200 model configs → publish all 200 → trading agent tests 200 forecasts
- ❌ Trading agent explodes (too many forecasts to test)
- ❌ Wasted compute backfilling low-quality models
- ❌ Noise in forecast selection
- ❌ Production tables cluttered with experiments

**With Selection**:
- Fit 200 model configs → evaluate metrics → select top 15 → publish only 15
- ✅ Trading agent tests curated set (manageable)
- ✅ Only backfill high-quality models
- ✅ Clear signal in forecast selection
- ✅ Production tables clean

---

## Workflow: Fit → Evaluate → Select → Publish

### Phase 1: Experimentation (forecast_testing)

**Goal**: Test many configurations to find best performers

```python
# Fit hundreds of configurations in forecast_testing
configs = [
    # Naive variations
    {'model': 'naive', 'lag': 1},
    {'model': 'naive', 'lag': 7},

    # SARIMAX variations
    {'model': 'sarimax', 'order': (1,1,1), 'seasonal': (1,1,1,7), 'weather': True},
    {'model': 'sarimax', 'order': (2,1,2), 'seasonal': (1,1,1,7), 'weather': True},
    {'model': 'sarimax', 'order': (1,1,1), 'seasonal': (0,1,1,7), 'weather': False},
    # ... 50 more SARIMAX configs

    # XGBoost variations
    {'model': 'xgboost', 'max_depth': 3, 'n_estimators': 100, 'learning_rate': 0.1},
    {'model': 'xgboost', 'max_depth': 5, 'n_estimators': 200, 'learning_rate': 0.05},
    # ... 50 more XGBoost configs

    # Prophet variations
    {'model': 'prophet', 'changepoint_prior_scale': 0.05, 'seasonality_mode': 'multiplicative'},
    # ... 30 more Prophet configs

    # Random Forest, etc.
    # ... 50 more configs
]

for config in configs:
    # Fit in forecast_testing
    model = train_model(config)

    # Save metadata to forecast_testing.model_metadata
    save_metadata(
        schema='commodity.forecast_testing',
        model_name=f"{config['model']}_{config_hash(config)}",
        metrics=evaluate(model),
        hyperparameters=json.dumps(config)
    )
```

**Result**: ~200 models in `forecast_testing.model_metadata`

---

### Phase 2: Evaluation & Selection

**Goal**: Select top ~15 models based on multiple criteria

#### Selection Criteria

**Primary Metrics** (required):
- Directional Accuracy (DA) > 0.60 (60% correct direction)
- MAE < 5.0 (acceptable error)
- Confidence Interval Width reasonable (not too wide/narrow)

**Secondary Metrics** (nice-to-have):
- Stable across folds (CV std dev < 0.05)
- Fast training (< 10 min)
- Robust to outliers

**Diversity Criteria** (critical):
- Must include variety of model types:
  * Baseline: Naive (1-2 models)
  * Statistical: ARIMA/SARIMAX (3-4 models)
  * Machine Learning: XGBoost, RF (3-4 models)
  * Neural/Advanced: Prophet, TFT (2-3 models)
  * Ensemble: Combinations (1-2 models)
- Mix of feature sets:
  * Price-only models
  * Price + weather
  * Price + GDELT
  * Price + weather + GDELT
- Mix of horizons:
  * Short-term optimized (day 1-3)
  * Medium-term optimized (day 7)
  * Long-term optimized (day 14)

#### Selection Query

```sql
-- Top models by directional accuracy (raw performance)
CREATE OR REPLACE TEMP VIEW top_by_da AS
SELECT
  model_name,
  cv_mean_directional_accuracy as da,
  cv_mean_mae as mae,
  cv_std_directional_accuracy as da_std,
  hyperparameters,
  training_duration_seconds,
  ROW_NUMBER() OVER (ORDER BY cv_mean_directional_accuracy DESC) as rank_da
FROM commodity.forecast_testing.model_metadata
WHERE commodity = 'Coffee'
  AND cv_mean_directional_accuracy > 0.60  -- Minimum threshold
  AND cv_mean_mae < 5.0                     -- Acceptable error
ORDER BY cv_mean_directional_accuracy DESC;

-- Best models per model type (diversity)
CREATE OR REPLACE TEMP VIEW best_per_type AS
SELECT
  SUBSTRING(model_name, 1, POSITION('_' IN model_name) - 1) as model_type,
  model_name,
  cv_mean_directional_accuracy as da,
  cv_mean_mae as mae,
  ROW_NUMBER() OVER (
    PARTITION BY SUBSTRING(model_name, 1, POSITION('_' IN model_name) - 1)
    ORDER BY cv_mean_directional_accuracy DESC
  ) as rank_within_type
FROM commodity.forecast_testing.model_metadata
WHERE commodity = 'Coffee'
  AND cv_mean_directional_accuracy > 0.60;

-- Final selection: Top 15 diverse models
CREATE OR REPLACE TABLE commodity.forecast_testing.selected_for_publication AS
SELECT
  model_name,
  da,
  mae,
  'High DA, top performer' as selection_reason
FROM top_by_da
WHERE rank_da <= 5  -- Top 5 overall

UNION ALL

-- Add best from each model type (ensures diversity)
SELECT
  model_name,
  da,
  mae,
  CONCAT('Best ', model_type, ' model') as selection_reason
FROM best_per_type
WHERE rank_within_type = 1  -- Best per type
  AND model_name NOT IN (SELECT model_name FROM top_by_da WHERE rank_da <= 5)  -- Avoid duplicates

LIMIT 15;  -- Cap at 15 total
```

**Result**: ~15 selected models ready for backfill

---

### Phase 3: Backfill (Selected Models Only)

**Goal**: Generate historical forecasts for selected models only

```python
# Only backfill selected models
selected_models = spark.table('commodity.forecast_testing.selected_for_publication').collect()

for row in selected_models:
    model_name = row['model_name']

    print(f"Backfilling {model_name} (reason: {row['selection_reason']})...")

    # Backfill 2018-2024 (or whatever date range)
    backfill_forecast(
        model_name=model_name,
        start_date='2018-01-01',
        end_date='2024-12-31',
        output_schema='commodity.forecast_testing'  # Still in testing
    )

print(f"Backfilled {len(selected_models)} selected models")
```

**Time Savings**:
- Before: 200 models × 24 hours = 4,800 hours (200 days!)
- After: 15 models × 24 hours = 360 hours (15 days)
- **Reduction**: 93% fewer compute hours!

---

### Phase 4: Validation (Testing Schema)

**Goal**: Validate backfilled forecasts before promotion

```sql
-- Check backfill completeness for selected models
SELECT
  model_name,
  COUNT(DISTINCT forecast_date) as dates_backfilled,
  MIN(forecast_date) as first_date,
  MAX(forecast_date) as last_date,
  COUNT(*) as total_forecasts
FROM commodity.forecast_testing.distributions
WHERE model_name IN (SELECT model_name FROM commodity.forecast_testing.selected_for_publication)
GROUP BY model_name;

-- Expected: ~2,500 dates × 14 days × 2000 paths = 70M rows per model
```

**Validation Checks**:
- ✅ Complete date coverage (no gaps)
- ✅ All horizons present (1-14 days)
- ✅ 2,000 paths per forecast
- ✅ Reasonable price ranges (no NaNs, no extreme outliers)

---

### Phase 5: Promotion to Production

**Goal**: Move validated forecasts to production schema

```sql
-- Promote selected models to production
INSERT INTO commodity.forecast.distributions
SELECT
  forecast_date,
  commodity,
  model_name,
  forecast_day,
  path_id,
  forecasted_price
FROM commodity.forecast_testing.distributions
WHERE model_name IN (SELECT model_name FROM commodity.forecast_testing.selected_for_publication);

INSERT INTO commodity.forecast.point_forecasts
SELECT
  forecast_date,
  commodity,
  model_name,
  forecast_day,
  forecasted_price,
  lower_bound,
  upper_bound
FROM commodity.forecast_testing.point_forecasts
WHERE model_name IN (SELECT model_name FROM commodity.forecast_testing.selected_for_publication);

INSERT INTO commodity.forecast.model_metadata
SELECT *
FROM commodity.forecast_testing.model_metadata
WHERE model_name IN (SELECT model_name FROM commodity.forecast_testing.selected_for_publication);

-- Mark as promoted
UPDATE commodity.forecast_testing.model_metadata
SET
  is_promoted_to_production = TRUE,
  promoted_at = CURRENT_TIMESTAMP()
WHERE model_name IN (SELECT model_name FROM commodity.forecast_testing.selected_for_publication);
```

**Result**: 15 curated models in production for trading agent to test

---

## Selection Strategy Details

### Diversity Matrix (Target: 15 Models)

| Model Type | Count | Example Configs |
|------------|-------|-----------------|
| **Naive** | 1-2 | Simple baseline, 7-day seasonal |
| **ARIMA/SARIMAX** | 3-4 | With/without weather, different orders |
| **XGBoost** | 3-4 | Different depths, feature sets |
| **Prophet** | 2-3 | Different seasonalities, changepoint priors |
| **Random Forest** | 1-2 | Different tree counts |
| **Ensemble** | 1-2 | Combinations of above |

### Feature Set Diversity

| Feature Set | Count | Purpose |
|-------------|-------|---------|
| Price only | 2-3 | Baseline, pure price signal |
| Price + Weather | 4-5 | Agricultural impact |
| Price + GDELT | 2-3 | News/sentiment impact |
| Price + Weather + GDELT | 4-5 | Full feature set |

### Horizon Optimization

| Horizon | Count | Optimization |
|---------|-------|--------------|
| Short (day 1-3) | 3-4 | Low latency, high accuracy |
| Medium (day 7) | 5-6 | Balanced performance |
| Long (day 14) | 3-4 | Longer-term trends |

---

## Example Selection Results

```sql
-- Example selected models (15 total)
SELECT * FROM commodity.forecast_testing.selected_for_publication;

+------------------------+-------+-------+--------------------------------+
| model_name             | da    | mae   | selection_reason               |
+------------------------+-------+-------+--------------------------------+
| sarimax_weather_v12    | 0.715 | 2.85  | High DA, top performer         |
| xgboost_deep_v8        | 0.698 | 3.12  | High DA, top performer         |
| prophet_multi_v5       | 0.692 | 3.05  | High DA, top performer         |
| ensemble_avg_v3        | 0.688 | 2.95  | High DA, top performer         |
| sarimax_no_weather_v3  | 0.682 | 3.22  | High DA, top performer         |
| naive_seasonal_v1      | 0.605 | 4.15  | Best naive model               |
| arima_auto_v2          | 0.658 | 3.45  | Best arima model               |
| xgboost_shallow_v4     | 0.672 | 3.28  | Best xgboost model (shallow)   |
| prophet_simple_v1      | 0.665 | 3.38  | Best prophet model (simple)    |
| rf_balanced_v6         | 0.670 | 3.31  | Best rf model                  |
| sarimax_gdelt_v7       | 0.680 | 3.18  | Best with GDELT                |
| xgboost_gdelt_v9       | 0.675 | 3.25  | Best ML with GDELT             |
| tft_v2                 | 0.668 | 3.35  | Best neural model              |
| sarimax_short_v4       | 0.685 | 2.98  | Best for day 1-3               |
| xgboost_long_v11       | 0.665 | 3.42  | Best for day 14                |
+------------------------+-------+-------+--------------------------------+
```

**Diversity Check**:
- ✅ 5 model types (naive, SARIMAX, XGBoost, Prophet, RF, TFT, ensemble)
- ✅ Mix of feature sets (price-only, +weather, +GDELT, +both)
- ✅ Mix of performance profiles (high DA, low MAE, balanced)
- ✅ 15 total (manageable for trading agent)

---

## Benefits

### Compute Efficiency
- **Before**: Backfill 200 models → 4,800 compute-hours
- **After**: Backfill 15 models → 360 compute-hours
- **Savings**: 93% reduction

### Trading Agent Manageability
- **Before**: Test 200 forecasts → combinatorial explosion
- **After**: Test 15 forecasts → focused evaluation
- **Improvement**: 93% fewer tests, better signal

### Production Clarity
- **Before**: 200 models cluttering production
- **After**: 15 curated, diverse models
- **Result**: Clear, interpretable forecast ensemble

### Experimentation Freedom
- **Before**: Hesitant to test many configs (cost/clutter)
- **After**: Test hundreds without production impact
- **Result**: Better model discovery

---

## Implementation Checklist

### Phase 1: Experimentation
- [ ] Define config grid (200+ variations)
- [ ] Fit all configs in forecast_testing schema
- [ ] Save metadata (DA, MAE, hyperparameters)
- [ ] Track training duration

### Phase 2: Selection
- [ ] Run selection query (top 15 diverse models)
- [ ] Review selected models for diversity
- [ ] Adjust thresholds if needed (DA > 0.60, MAE < 5.0)
- [ ] Save selection to `selected_for_publication` table

### Phase 3: Backfill
- [ ] Backfill only selected 15 models
- [ ] Monitor backfill progress
- [ ] Validate completeness (no gaps)

### Phase 4: Validation
- [ ] Check date coverage
- [ ] Validate price ranges
- [ ] Compare vs existing production models

### Phase 5: Promotion
- [ ] Copy to commodity.forecast (production)
- [ ] Mark as promoted in forecast_testing
- [ ] Document selection rationale
- [ ] Notify trading agent team

---

## Monitoring

### Selection Metrics Dashboard

```sql
-- How many configs tested?
SELECT COUNT(*) as configs_tested
FROM commodity.forecast_testing.model_metadata;

-- How many passed threshold?
SELECT COUNT(*) as passed_threshold
FROM commodity.forecast_testing.model_metadata
WHERE cv_mean_directional_accuracy > 0.60
  AND cv_mean_mae < 5.0;

-- How many selected?
SELECT COUNT(*) as selected_for_publication
FROM commodity.forecast_testing.selected_for_publication;

-- Diversity check
SELECT
  SUBSTRING(model_name, 1, POSITION('_' IN model_name) - 1) as model_type,
  COUNT(*) as count
FROM commodity.forecast_testing.selected_for_publication
GROUP BY model_type;
```

---

## Future Enhancements

1. **Automated Selection**: Use ML to select diverse ensemble
2. **Pareto Frontier**: Select models on DA-MAE pareto frontier
3. **Trading Signal**: Select models that maximize trading profit (not just DA)
4. **Ensemble Weighting**: Weight models in final ensemble by selection score
5. **Continuous Updates**: Re-run selection monthly, retire underperformers

---

**TL;DR**: Test hundreds, publish ~15. Use forecast_testing as experimental sandbox, curate best diverse set for production.
