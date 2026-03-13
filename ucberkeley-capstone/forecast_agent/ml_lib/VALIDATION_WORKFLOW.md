# ml_lib Validation Workflow

**Purpose**: Validate new ml_lib pipeline before promoting to production

**Testing Schema**: `commodity.forecast_testing` (isolated from production)

---

## Overview

The `forecast_testing` schema provides a safe environment to validate ml_lib pipeline changes:

```
Development → Test in forecast_testing → Validate → Promote to forecast (production)
```

---

## Setup (One-Time)

### 1. Create Testing Schema

```bash
cd forecast_agent
python setup_testing_schema.py
```

This creates:
- ✅ `commodity.forecast_testing.distributions`
- ✅ `commodity.forecast_testing.point_forecasts`
- ✅ `commodity.forecast_testing.model_metadata`
- ✅ `commodity.forecast_testing.validation_results`

### 2. Verify Schema

```sql
SHOW TABLES IN commodity.forecast_testing;

-- Should show:
-- distributions
-- point_forecasts
-- model_metadata
-- validation_results
```

---

## Validation Workflow

### Phase 1: Imputation Testing (Day 1)

**Goal**: Validate `ImputationTransformer` performance and correctness

**Test Script**: `notebooks/test_imputation_pipeline.py`

**Success Criteria**:
- ✅ Imputation time < 60 seconds (for 7k rows)
- ✅ All NULLs removed (except keep_null strategy)
- ✅ Row count unchanged
- ✅ Imputed values match production table (for forward_fill strategy)

**Record Results**:
```sql
INSERT INTO commodity.forecast_testing.validation_results
VALUES (
  CURRENT_DATE(),                     -- test_date
  'imputation_performance',            -- test_name
  'Coffee',                            -- commodity
  'gold.unified_data_raw',             -- table_source
  'production_config',                 -- imputation_strategy
  NULL,                                -- model_name
  'SUCCESS',                           -- test_status
  45.2,                                -- test_duration_seconds
  30.1,                                -- imputation_time_seconds
  7612,                                -- row_count
  31.1,                                -- null_rate_before (%)
  0.0,                                 -- null_rate_after (%)
  NULL, NULL, NULL,                    -- baseline/test metrics (not applicable)
  'Imputation completed in 30.1s, all NULLs removed successfully',
  CURRENT_TIMESTAMP()
);
```

---

### Phase 2: Naive Baseline (Day 1)

**Goal**: Validate cross-validation framework with simplest model

**Model**: Naive (tomorrow = today)

**Configuration**:
```python
from forecast_agent.ml_lib.cross_validation import TimeSeriesForecastCV
from forecast_agent.ml_lib.cross_validation.data_loader import GoldDataLoader

# Load data
loader = GoldDataLoader(table_name='commodity.gold.unified_data')
df = loader.load(commodity='Coffee')

# Run CV
cv = TimeSeriesForecastCV(
    n_folds=5,
    horizon=14,
    model_type='naive'
)
results = cv.fit(df)
```

**Success Criteria**:
- ✅ CV completes without errors
- ✅ Produces 5 fold results
- ✅ Metrics calculated (DA, MAE, RMSE)
- ✅ Results saved to `forecast_testing.model_metadata`

---

### Phase 3: Production vs Raw Comparison (Day 1-2)

**Goal**: Compare same model on production (forward-filled) vs raw (imputed) table

**Test**: SARIMAX model on both tables

**Configuration 1: Production Table**:
```python
loader = GoldDataLoader(table_name='commodity.gold.unified_data')
df_prod = loader.load(commodity='Coffee')

cv_prod = TimeSeriesForecastCV(n_folds=5, model_type='sarimax')
results_prod = cv_prod.fit(df_prod)
```

**Configuration 2: Raw Table + Imputation**:
```python
from forecast_agent.ml_lib.transformers import create_production_imputer

loader = GoldDataLoader(table_name='commodity.gold.unified_data_raw')
df_raw = loader.load(commodity='Coffee')

imputer = create_production_imputer()
df_imputed = imputer.transform(df_raw).cache()
df_imputed.count()

cv_raw = TimeSeriesForecastCV(n_folds=5, model_type='sarimax')
results_raw = cv_raw.fit(df_imputed)
```

**Comparison**:
```sql
-- Compare metrics
SELECT
  'production' as source,
  cv_mean_directional_accuracy,
  cv_mean_mae,
  cv_mean_rmse
FROM commodity.forecast_testing.model_metadata
WHERE model_name = 'sarimax' AND table_source = 'gold.unified_data'

UNION ALL

SELECT
  'raw + imputation' as source,
  cv_mean_directional_accuracy,
  cv_mean_mae,
  cv_mean_rmse
FROM commodity.forecast_testing.model_metadata
WHERE model_name = 'sarimax' AND table_source = 'gold.unified_data_raw';
```

**Success Criteria**:
- ✅ Directional accuracy difference < 0.01 (1%)
- ✅ MAE within ±5% of baseline
- ✅ Training time < 1.2x baseline (with caching)

---

### Phase 4: XGBoost with Native NULL Handling (Day 2-3)

**Goal**: Test tree model with keep_null strategy (leverages missingness as signal)

**Configuration**:
```python
from forecast_agent.ml_lib.transformers import ImputationTransformer

loader = GoldDataLoader(table_name='commodity.gold.unified_data_raw')
df_raw = loader.load(commodity='Coffee')

# Minimal imputation - XGBoost handles NULLs natively
imputer = ImputationTransformer(
    default_strategy='keep_null',
    feature_strategies={
        'close': 'forward_fill'  # Target must be non-null
    }
)

df_imputed = imputer.transform(df_raw).cache()
df_imputed.count()

cv = TimeSeriesForecastCV(n_folds=5, model_type='xgboost')
results = cv.fit(df_imputed)
```

**Success Criteria**:
- ✅ XGBoost trains successfully with NULLs
- ✅ Directional accuracy >= baseline (may improve with missingness signal)
- ✅ No errors during training

---

### Phase 5: Full Model Suite (Day 3-4)

**Goal**: Validate all models on gold tables

**Models to Test**:
1. Naive (baseline) ✅
2. ARIMA ✅
3. SARIMAX (with weather) ✅
4. XGBoost ✅
5. Prophet ✅
6. Random Forest ✅

**For Each Model**:
1. Run on `gold.unified_data` (production)
2. Run on `gold.unified_data_raw` (with imputation)
3. Record metadata to `forecast_testing.model_metadata`
4. Compare metrics
5. Document observations

---

## Promotion Criteria

**Model is ready for production if**:

1. **Performance Validated** ✅
   - Directional accuracy difference < 0.01 vs baseline
   - MAE within ±5% of baseline
   - No degradation in key metrics

2. **Stability Validated** ✅
   - All CV folds complete successfully
   - No errors during training
   - Consistent performance across folds (std dev < 0.05)

3. **Performance Acceptable** ✅
   - Imputation overhead < 60s
   - Total training time < 1.2x baseline
   - Memory usage acceptable

4. **Documentation Complete** ✅
   - Hyperparameters recorded
   - Imputation strategy documented
   - Observations noted

**Promotion Process**:
```sql
-- Mark model as promoted
UPDATE commodity.forecast_testing.model_metadata
SET
  is_promoted_to_production = TRUE,
  promoted_at = CURRENT_TIMESTAMP(),
  notes = 'Validated on gold.unified_data_raw with production_imputer. DA: 0.695, MAE: 3.10. Ready for production.'
WHERE commodity = 'Coffee'
  AND model_name = 'sarimax_auto_weather'
  AND training_date = '2024-12-05';

-- Copy to production schema
INSERT INTO commodity.forecast.model_metadata
SELECT
  commodity,
  model_name,
  training_date,
  cv_mean_directional_accuracy,
  cv_mean_mae,
  cv_mean_rmse,
  -- ... other columns
FROM commodity.forecast_testing.model_metadata
WHERE is_promoted_to_production = TRUE;
```

---

## Monitoring & Reporting

### Daily Validation Report

```sql
SELECT
  test_date,
  test_name,
  commodity,
  test_status,
  COUNT(*) as test_count,
  AVG(test_duration_seconds) as avg_duration,
  SUM(CASE WHEN test_status = 'SUCCESS' THEN 1 ELSE 0 END) as success_count
FROM commodity.forecast_testing.validation_results
WHERE test_date >= CURRENT_DATE() - INTERVAL 7 DAYS
GROUP BY test_date, test_name, commodity, test_status
ORDER BY test_date DESC;
```

### Model Performance Summary

```sql
SELECT
  model_name,
  table_source,
  imputation_strategy,
  AVG(cv_mean_directional_accuracy) as avg_da,
  AVG(cv_mean_mae) as avg_mae,
  COUNT(*) as training_runs,
  SUM(CASE WHEN is_promoted_to_production THEN 1 ELSE 0 END) as promoted_count
FROM commodity.forecast_testing.model_metadata
GROUP BY model_name, table_source, imputation_strategy
ORDER BY avg_da DESC;
```

---

## Troubleshooting

### Issue: Test Failed with Error

1. Check `validation_results` table for error details
2. Review notebook output in Databricks
3. Validate input data quality
4. Check cluster configuration

### Issue: Performance Degradation

1. Compare with baseline metrics
2. Check imputation strategy (may need tuning)
3. Validate hyperparameters
4. Consider different table source

### Issue: Slow Imputation (> 60s)

1. Verify caching is enabled (`df.cache()` + `df.count()`)
2. Check cluster size (use ml-testing-cluster minimum)
3. Reduce date range for testing
4. Simplify imputation strategy

---

## Next Steps After Validation

1. **Week 1**: Complete Phase 1-2 (imputation + naive baseline)
2. **Week 2**: Complete Phase 3-4 (comparison + XGBoost)
3. **Week 3**: Complete Phase 5 (full model suite)
4. **Week 4**: Promote successful models to production
5. **Month 2**: Deprecate silver table, gold becomes primary

---

**Questions?** See `ml_lib/QUICKSTART.md` for quick reference or `research_agent/GOLD_MIGRATION_GUIDE.md` for detailed migration guidance.
