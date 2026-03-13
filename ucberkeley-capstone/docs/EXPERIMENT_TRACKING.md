# Experiment Tracking Database Design

> **⚠️ NOTICE: This document describes a proposed design for the legacy ground_truth pipeline (V1/V2).**
>
> **Status**: Design phase (never implemented). The forecast_agent has since migrated to ml_lib (V3) with a different approach:
> - **Current approach**: "Fit many, publish few" pattern - see [forecast_agent/ml_lib/MODEL_SELECTION_STRATEGY.md](../forecast_agent/ml_lib/MODEL_SELECTION_STRATEGY.md)
> - **Current testing**: `commodity.forecast_testing` schema for experimentation - see [forecast_agent/ml_lib/VALIDATION_WORKFLOW.md](../forecast_agent/ml_lib/VALIDATION_WORKFLOW.md)
> - **Legacy context**: ground_truth pipeline moved to [forecast_agent/deprecated/](../forecast_agent/deprecated/)
>
> This document is preserved for historical reference. Path references below (forecast_agent/ground_truth/) are outdated.

---

**Original Purpose**: Track all model experiments to demonstrate platform's experimentation capabilities while enabling systematic pruning of poor-performing models.

---

## Business Justification

### Current Challenge
- 25+ models in `model_registry.py`
- No systematic way to compare experiments over time
- Can't prune poor performers without losing experiment history
- Presentation needs to show experimentation scale

### Solution
- Dedicated `commodity.experiments.model_runs` table
- Track every experiment with full reproducibility
- Enable pruning config while preserving history
- Showcase ML engineering rigor for capstone presentation

---

## Schema Design

### Table: `commodity.experiments.model_runs`

```sql
CREATE TABLE IF NOT EXISTS commodity.experiments.model_runs (
  -- Identifiers
  experiment_id STRING NOT NULL,           -- UUID for this run
  model_name STRING NOT NULL,              -- e.g., "sarimax_auto_weather_v1"
  model_version STRING NOT NULL,           -- e.g., "v1", "v2"
  run_timestamp TIMESTAMP NOT NULL,        -- When experiment ran

  -- Configuration
  model_type STRING NOT NULL,              -- "SARIMAX", "XGBoost", "Prophet", etc.
  hyperparameters MAP<STRING, STRING>,     -- JSON of all hyperparameters
  feature_config MAP<STRING, BOOLEAN>,     -- Which features were used
  data_version STRING,                     -- unified_data snapshot version

  -- Training Context
  training_start_date DATE NOT NULL,       -- First date in training set
  training_end_date DATE NOT NULL,         -- Last date in training set
  forecast_horizon_days INT NOT NULL,      -- Usually 14
  commodity STRING NOT NULL,               -- "Coffee" or "Sugar"

  -- Performance Metrics
  mae_1day DOUBLE,                         -- 1-day ahead MAE
  mae_7day DOUBLE,                         -- 7-day ahead MAE
  mae_14day DOUBLE,                        -- 14-day ahead MAE
  rmse_14day DOUBLE,                       -- 14-day ahead RMSE
  mape_14day DOUBLE,                       -- 14-day ahead MAPE
  directional_accuracy DOUBLE,             -- % correct direction from day 0

  -- Statistical Tests
  dm_test_vs_naive DOUBLE,                 -- Diebold-Mariano statistic
  dm_pvalue DOUBLE,                        -- Statistical significance
  beats_baseline BOOLEAN,                  -- TRUE if statistically better than naive

  -- Infrastructure
  execution_time_seconds DOUBLE,           -- Training + inference time
  hardware_config STRING,                  -- "local" or cluster details
  databricks_cluster_id STRING,            -- If run on Databricks
  cost_estimate_usd DOUBLE,                -- Estimated compute cost

  -- Artifacts
  model_path STRING,                       -- S3 path to serialized model
  dashboard_url STRING,                    -- Link to evaluation dashboard

  -- Metadata
  run_by STRING,                           -- "Connor", "Francisco", "Tony", "automated"
  notes STRING,                            -- Free-form notes
  is_production BOOLEAN DEFAULT FALSE,     -- Promoted to production?

  -- Constraints
  PRIMARY KEY (experiment_id)
)
USING DELTA
PARTITIONED BY (commodity, run_timestamp)
COMMENT 'Experiment tracking for all model runs - enables pruning while preserving history';
```

---

## Usage Patterns

### 1. Recording an Experiment

```python
from datetime import datetime
import uuid

experiment = {
    "experiment_id": str(uuid.uuid4()),
    "model_name": "sarimax_auto_weather_v1",
    "model_version": "v1",
    "run_timestamp": datetime.now(),
    "model_type": "SARIMAX",
    "hyperparameters": {
        "order": "(1,1,1)",
        "seasonal_order": "(1,1,1,7)",
        "exog_vars": "temp_c,humidity_pct,precipitation_mm"
    },
    "feature_config": {
        "weather": True,
        "vix": False,
        "cop_usd": False
    },
    "training_start_date": "2022-01-01",
    "training_end_date": "2024-12-31",
    "forecast_horizon_days": 14,
    "commodity": "Coffee",
    "mae_14day": 3.10,
    "directional_accuracy": 0.695,
    "beats_baseline": True,
    "execution_time_seconds": 45.2,
    "hardware_config": "local",
    "run_by": "Connor"
}

# Write to Databricks
spark.createDataFrame([experiment]).write.mode("append").saveAsTable(
    "commodity.experiments.model_runs"
)
```

### 2. Finding Best Models

```sql
-- Top 5 models by MAE for Coffee
SELECT
  model_name,
  model_version,
  mae_14day,
  directional_accuracy,
  execution_time_seconds,
  run_timestamp
FROM commodity.experiments.model_runs
WHERE commodity = 'Coffee'
  AND beats_baseline = TRUE
ORDER BY mae_14day ASC
LIMIT 5;
```

### 3. Experiment History for Presentation

```sql
-- Show experimentation scale
SELECT
  model_type,
  COUNT(*) as total_experiments,
  COUNT(DISTINCT model_name) as unique_models,
  AVG(mae_14day) as avg_mae,
  MIN(mae_14day) as best_mae,
  SUM(execution_time_seconds) / 3600 as total_hours
FROM commodity.experiments.model_runs
WHERE commodity = 'Coffee'
GROUP BY model_type
ORDER BY total_experiments DESC;
```

### 4. Pruning Decision Support

```sql
-- Models that should be removed from registry
SELECT
  model_name,
  COUNT(*) as num_runs,
  AVG(mae_14day) as avg_mae,
  AVG(execution_time_seconds) as avg_time,
  MAX(run_timestamp) as last_run
FROM commodity.experiments.model_runs
WHERE beats_baseline = FALSE
GROUP BY model_name
HAVING COUNT(*) >= 3  -- Consistently poor
ORDER BY avg_mae DESC;
```

---

## Integration with Existing Code

### forecast_agent/ground_truth/core/backtester.py

Add experiment logging after each evaluation window:

```python
def log_experiment(model_name, results, config):
    """Log experiment to tracking database"""
    experiment = {
        "experiment_id": str(uuid.uuid4()),
        "model_name": model_name,
        "run_timestamp": datetime.now(),
        "mae_14day": results["mae"],
        "rmse_14day": results["rmse"],
        "directional_accuracy": results["directional_accuracy"],
        # ... other fields
    }

    writer = DatabricksWriter(schema="experiments")
    writer.write_experiment(experiment)
```

### forecast_agent/ground_truth/config/model_registry.py

Add metadata to support experiment tracking:

```python
BASELINE_MODELS = {
    "sarimax_auto_weather_v1": {
        "type": "SARIMAX",
        "function": fit_sarimax_auto,
        "params": {...},
        "experiment_tags": {
            "feature_set": "weather",
            "complexity": "medium",
            "production_candidate": True
        }
    }
}
```

---

## Benefits

### For Capstone Presentation
1. **Demonstrate scale**: "We ran 100+ experiments across 25 model variants"
2. **Show rigor**: Statistical tests, proper evaluation methodology
3. **Prove reproducibility**: Full config + hardware tracking
4. **Cost awareness**: Track and optimize compute costs

### For Development
1. **Enable pruning**: Remove poor models from registry with confidence
2. **Track improvements**: See how models evolve over time
3. **Debug regressions**: "Why did performance drop?"
4. **Share learnings**: Team can see what was tried

### For Production
1. **Model governance**: Know exactly what's running in production
2. **Audit trail**: Full history of model changes
3. **Cost optimization**: Identify expensive models
4. **A/B testing**: Compare model variants systematically

---

## Implementation Plan

1. **P2 Priority**: Create table schema in Databricks
2. **P2 Priority**: Add logging to backtester.py
3. **P3 Priority**: Backfill historical experiments (40 windows × 25 models)
4. **P3 Priority**: Build experiment dashboard in Databricks SQL
5. **Future**: Integrate with MLflow or custom experiment tracking UI

---

## Example Presentation Slide

**"Rigorous Experimentation Process"**

```
25 Model Variants Tested
├─ 8 SARIMAX configurations
├─ 11 XGBoost variants
├─ 2 Prophet models
├─ 3 Baselines (Naive, Random Walk, ARIMA)
└─ 1 Advanced (NeuralProphet)

100+ Experiment Runs
├─ 40 historical windows (walk-forward validation)
├─ 2 commodities (Coffee, Sugar)
├─ Statistical significance testing (Diebold-Mariano)
└─ Full reproducibility tracking

Production Model: sarimax_auto_weather_v1
├─ MAE: $3.10 (14-day horizon)
├─ Directional Accuracy: 69.5%
└─ Statistically beats naive baseline (p < 0.05)
```

---

**Last Updated**: 2025-01-11
**Status**: Design complete, pending implementation
