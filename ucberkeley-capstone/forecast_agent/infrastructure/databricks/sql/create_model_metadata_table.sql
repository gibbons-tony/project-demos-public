-- Create enhanced model metadata table for ML pipeline tracking
--
-- This table stores comprehensive metadata about trained models including:
-- - Cross-validation metrics (directional accuracy, MAE, RMSE)
-- - Model configuration and hyperparameters
-- - Training metadata (data range, feature importance, etc.)
-- - Storage locations (model path, residuals path)
-- - Performance metrics by horizon (day 1, day 7, day 14)
--
-- Usage:
--   Run this SQL in Databricks SQL Editor or notebook
--   Table will be created in commodity.forecast schema

CREATE TABLE IF NOT EXISTS commodity.forecast.model_metadata (
  -- Primary identifiers
  commodity STRING NOT NULL COMMENT 'Commodity being forecasted (e.g., Coffee, Wheat)',
  model_name STRING NOT NULL COMMENT 'Model identifier from pipeline registry',
  training_date DATE NOT NULL COMMENT 'Date when model was trained',

  -- Cross-validation configuration
  n_folds INT NOT NULL COMMENT 'Number of CV folds used',
  window_type STRING NOT NULL COMMENT 'CV window type: expanding or rolling',
  horizon INT NOT NULL COMMENT 'Forecast horizon in days (typically 14)',
  validation_months INT COMMENT 'Months per validation fold',
  min_train_months INT COMMENT 'Minimum training months required',

  -- Primary CV metrics (averaged across all folds)
  cv_mean_directional_accuracy DOUBLE COMMENT 'Mean directional accuracy from day 0 (primary metric)',
  cv_mean_mae DOUBLE COMMENT 'Mean absolute error across all horizons',
  cv_mean_rmse DOUBLE COMMENT 'Root mean squared error across all horizons',
  cv_std_directional_accuracy DOUBLE COMMENT 'Std dev of directional accuracy across folds',
  cv_std_mae DOUBLE COMMENT 'Std dev of MAE across folds',
  cv_std_rmse DOUBLE COMMENT 'Std dev of RMSE across folds',

  -- Directional accuracy by horizon (key trading metrics)
  da_day_1 DOUBLE COMMENT 'Directional accuracy for day 1 forecast',
  da_day_3 DOUBLE COMMENT 'Directional accuracy for day 3 forecast',
  da_day_7 DOUBLE COMMENT 'Directional accuracy for day 7 forecast',
  da_day_14 DOUBLE COMMENT 'Directional accuracy for day 14 forecast',

  -- MAE by horizon
  mae_day_1 DOUBLE COMMENT 'MAE for day 1 forecast',
  mae_day_7 DOUBLE COMMENT 'MAE for day 7 forecast',
  mae_day_14 DOUBLE COMMENT 'MAE for day 14 forecast',

  -- Training data statistics
  training_start_date DATE COMMENT 'First date in training data',
  training_end_date DATE COMMENT 'Last date in training data',
  training_row_count BIGINT COMMENT 'Number of rows in training data',
  training_date_count BIGINT COMMENT 'Number of unique dates in training data',

  -- Model storage locations
  model_path STRING NOT NULL COMMENT 'DBFS path to fitted final model',
  residual_path STRING NOT NULL COMMENT 'DBFS path to CV residuals (for Monte Carlo)',
  fold_models_saved BOOLEAN COMMENT 'Whether individual fold models were saved',

  -- Feature metadata
  features ARRAY<STRING> COMMENT 'List of feature groups used (e.g., weather, gdelt, vix)',
  feature_count INT COMMENT 'Total number of features in model',
  weather_aggregation STRING COMMENT 'Weather aggregation type: mean, min_max, all, regions',
  gdelt_aggregation STRING COMMENT 'GDELT aggregation type: weighted, themes',

  -- Model-specific hyperparameters (stored as JSON for flexibility)
  hyperparameters STRING COMMENT 'JSON string of model hyperparameters',

  -- CV fold details (full JSON)
  cv_metrics_json STRING COMMENT 'Full CV metrics JSON with per-fold details',

  -- Performance summary
  target_metric STRING COMMENT 'Primary metric optimized (directional_accuracy_day0)',
  best_horizon INT COMMENT 'Forecast day with best performance',
  worst_horizon INT COMMENT 'Forecast day with worst performance',

  -- Model comparison
  baseline_comparison DOUBLE COMMENT 'Improvement over naive baseline (percentage)',
  rank_vs_other_models INT COMMENT 'Rank compared to other models for this commodity',

  -- Training metadata
  training_duration_seconds DOUBLE COMMENT 'Time taken to train model (seconds)',
  cluster_name STRING COMMENT 'Databricks cluster used for training',
  spark_version STRING COMMENT 'Spark version used',

  -- Audit fields
  created_at TIMESTAMP NOT NULL COMMENT 'Timestamp when model was trained',
  created_by STRING COMMENT 'User who trained the model',

  -- Model lifecycle
  is_production BOOLEAN DEFAULT FALSE COMMENT 'Whether this model is used in production',
  deprecated_at TIMESTAMP COMMENT 'When model was deprecated',
  deprecated_reason STRING COMMENT 'Why model was deprecated',

  -- Notes
  notes STRING COMMENT 'Free-form notes about training run'
)
USING DELTA
PARTITIONED BY (commodity, training_date)
COMMENT 'Model metadata and metrics for ML forecasting pipeline'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
);

-- Create unique constraint on (commodity, model_name, training_date)
-- Note: Delta doesn't support unique constraints, so we enforce via merge logic

-- Create useful indexes for queries
CREATE INDEX IF NOT EXISTS idx_model_metadata_commodity
  ON commodity.forecast.model_metadata (commodity);

CREATE INDEX IF NOT EXISTS idx_model_metadata_model_name
  ON commodity.forecast.model_metadata (model_name);

CREATE INDEX IF NOT EXISTS idx_model_metadata_training_date
  ON commodity.forecast.model_metadata (training_date);

-- Sample query patterns

-- Get latest model for each commodity
-- SELECT commodity, model_name, training_date, cv_mean_directional_accuracy
-- FROM commodity.forecast.model_metadata
-- WHERE training_date = (
--   SELECT MAX(training_date)
--   FROM commodity.forecast.model_metadata m2
--   WHERE m2.commodity = model_metadata.commodity
--     AND m2.model_name = model_metadata.model_name
-- )
-- ORDER BY commodity, cv_mean_directional_accuracy DESC;

-- Compare all models for Coffee
-- SELECT
--   model_name,
--   training_date,
--   ROUND(cv_mean_directional_accuracy, 4) as directional_accuracy,
--   ROUND(cv_mean_mae, 2) as mae,
--   features
-- FROM commodity.forecast.model_metadata
-- WHERE commodity = 'Coffee'
-- ORDER BY training_date DESC, cv_mean_directional_accuracy DESC;

-- Performance by horizon
-- SELECT
--   model_name,
--   ROUND(da_day_1, 4) as day_1,
--   ROUND(da_day_7, 4) as day_7,
--   ROUND(da_day_14, 4) as day_14
-- FROM commodity.forecast.model_metadata
-- WHERE commodity = 'Coffee'
--   AND training_date = (SELECT MAX(training_date) FROM commodity.forecast.model_metadata WHERE commodity = 'Coffee')
-- ORDER BY da_day_14 DESC;
