-- Create forecast_testing schema for ml_lib validation
-- Purpose: Isolate experimental forecasts from production commodity.forecast schema

CREATE SCHEMA IF NOT EXISTS commodity.forecast_testing
COMMENT 'Testing schema for ml_lib pipeline validation - experimental forecasts only';

-- ============================================================================
-- Test Forecast Distributions (matching production schema)
-- ============================================================================

CREATE OR REPLACE TABLE commodity.forecast_testing.distributions (
  forecast_date DATE NOT NULL COMMENT 'Date forecast was generated',
  commodity STRING NOT NULL COMMENT 'Coffee or Sugar',
  model_name STRING NOT NULL COMMENT 'Model identifier (e.g., naive, xgboost, sarimax)',
  forecast_day INT NOT NULL COMMENT 'Days ahead (1-14)',
  path_id INT NOT NULL COMMENT 'Monte Carlo path number (1-2000)',
  forecasted_price DOUBLE COMMENT 'Predicted price for this path',

  -- Metadata
  table_source STRING COMMENT 'gold.unified_data or gold.unified_data_raw',
  imputation_strategy STRING COMMENT 'forward_fill, mean_7d, zero, etc.',
  pipeline_version STRING COMMENT 'ml_lib version for tracking',

  CONSTRAINT pk_test_distributions PRIMARY KEY (forecast_date, commodity, model_name, forecast_day, path_id)
) USING DELTA
PARTITIONED BY (commodity, forecast_date)
COMMENT 'Test forecast distributions for ml_lib validation';

-- ============================================================================
-- Test Point Forecasts (matching production schema)
-- ============================================================================

CREATE OR REPLACE TABLE commodity.forecast_testing.point_forecasts (
  forecast_date DATE NOT NULL COMMENT 'Date forecast was generated',
  commodity STRING NOT NULL COMMENT 'Coffee or Sugar',
  model_name STRING NOT NULL COMMENT 'Model identifier',
  forecast_day INT NOT NULL COMMENT 'Days ahead (1-14)',

  -- Point estimates
  forecasted_price DOUBLE COMMENT 'Median predicted price',
  lower_bound DOUBLE COMMENT '5th percentile',
  upper_bound DOUBLE COMMENT '95th percentile',

  -- Metadata
  table_source STRING COMMENT 'gold.unified_data or gold.unified_data_raw',
  imputation_strategy STRING COMMENT 'Imputation approach used',
  pipeline_version STRING COMMENT 'ml_lib version',

  CONSTRAINT pk_test_point_forecasts PRIMARY KEY (forecast_date, commodity, model_name, forecast_day)
) USING DELTA
PARTITIONED BY (commodity, forecast_date)
COMMENT 'Test point forecasts for ml_lib validation';

-- ============================================================================
-- Test Model Metadata (enhanced for ml_lib testing)
-- ============================================================================

CREATE OR REPLACE TABLE commodity.forecast_testing.model_metadata (
  commodity STRING NOT NULL COMMENT 'Coffee or Sugar',
  model_name STRING NOT NULL COMMENT 'Model identifier',
  training_date DATE NOT NULL COMMENT 'Date model was trained',

  -- Cross-validation metrics
  cv_mean_directional_accuracy DOUBLE COMMENT 'Mean DA across all folds',
  cv_std_directional_accuracy DOUBLE COMMENT 'Std dev of DA across folds',
  cv_mean_mae DOUBLE COMMENT 'Mean MAE across all folds',
  cv_mean_rmse DOUBLE COMMENT 'Mean RMSE across all folds',

  -- Per-horizon metrics
  da_day_1 DOUBLE COMMENT 'Directional accuracy for day 1',
  da_day_3 DOUBLE COMMENT 'Directional accuracy for day 3',
  da_day_7 DOUBLE COMMENT 'Directional accuracy for day 7',
  da_day_14 DOUBLE COMMENT 'Directional accuracy for day 14',

  mae_day_1 DOUBLE COMMENT 'MAE for day 1',
  mae_day_7 DOUBLE COMMENT 'MAE for day 7',
  mae_day_14 DOUBLE COMMENT 'MAE for day 14',

  -- Configuration
  hyperparameters STRING COMMENT 'JSON string of model hyperparameters',
  table_source STRING COMMENT 'gold.unified_data or gold.unified_data_raw',
  imputation_strategy STRING COMMENT 'Imputation configuration used',
  pipeline_version STRING COMMENT 'ml_lib version',

  -- Performance
  training_duration_seconds DOUBLE COMMENT 'Total training time',
  imputation_duration_seconds DOUBLE COMMENT 'Imputation overhead',
  cluster_name STRING COMMENT 'Databricks cluster used',

  -- Lifecycle
  is_promoted_to_production BOOLEAN DEFAULT FALSE COMMENT 'Has this been promoted to production?',
  promoted_at TIMESTAMP COMMENT 'When was it promoted',
  notes STRING COMMENT 'Testing notes or observations',

  CONSTRAINT pk_test_model_metadata PRIMARY KEY (commodity, model_name, training_date)
) USING DELTA
PARTITIONED BY (commodity, training_date)
COMMENT 'Test model metadata for ml_lib pipeline validation';

-- ============================================================================
-- Test Validation Results (new table for tracking test outcomes)
-- ============================================================================

CREATE OR REPLACE TABLE commodity.forecast_testing.validation_results (
  test_date DATE NOT NULL COMMENT 'Date test was run',
  test_name STRING NOT NULL COMMENT 'Test identifier (e.g., imputation_performance, cv_naive_baseline)',
  commodity STRING NOT NULL COMMENT 'Coffee or Sugar',

  -- Test configuration
  table_source STRING COMMENT 'gold.unified_data or gold.unified_data_raw',
  imputation_strategy STRING COMMENT 'Imputation config tested',
  model_name STRING COMMENT 'Model tested (if applicable)',

  -- Test results
  test_status STRING COMMENT 'SUCCESS, FAILED, WARNING',
  test_duration_seconds DOUBLE COMMENT 'How long the test took',

  -- Metrics
  imputation_time_seconds DOUBLE COMMENT 'Imputation overhead',
  row_count INT COMMENT 'Rows processed',
  null_rate_before DOUBLE COMMENT 'NULL rate before imputation (%)',
  null_rate_after DOUBLE COMMENT 'NULL rate after imputation (%)',

  -- Performance comparison
  baseline_metric DOUBLE COMMENT 'Metric from baseline (e.g., production table)',
  test_metric DOUBLE COMMENT 'Metric from test run',
  metric_name STRING COMMENT 'What metric was compared (DA, MAE, RMSE)',

  -- Notes
  observations STRING COMMENT 'Key findings or issues',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),

  CONSTRAINT pk_test_validation_results PRIMARY KEY (test_date, test_name, commodity)
) USING DELTA
PARTITIONED BY (test_date)
COMMENT 'Validation test results for ml_lib pipeline';

-- ============================================================================
-- Indexes and Optimization
-- ============================================================================

-- Optimize for common query patterns
OPTIMIZE commodity.forecast_testing.distributions;
OPTIMIZE commodity.forecast_testing.point_forecasts;
OPTIMIZE commodity.forecast_testing.model_metadata;
OPTIMIZE commodity.forecast_testing.validation_results;

-- ============================================================================
-- Permissions (optional - adjust based on your setup)
-- ============================================================================

-- GRANT SELECT, INSERT, UPDATE ON SCHEMA commodity.forecast_testing TO forecast_agent_users;

-- ============================================================================
-- Documentation
-- ============================================================================

SELECT
  'forecast_testing schema created successfully!' as status,
  'Use this schema for ml_lib pipeline validation before promoting to production' as purpose,
  'Tables: distributions, point_forecasts, model_metadata, validation_results' as tables_created;
