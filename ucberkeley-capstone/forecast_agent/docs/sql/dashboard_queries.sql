-- ============================================================================
-- Databricks SQL Dashboard Queries for Model Performance Comparison
-- ============================================================================
-- Use these queries in Databricks SQL to create visualizations comparing
-- forecast model performance across different metrics and horizons.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Query 1: Model Comparison - MAE by Horizon
-- Chart Type: Grouped Bar Chart
-- Purpose: Compare model accuracy at different forecast horizons
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    AVG(mae_1d) as mae_1_day,
    AVG(mae_7d) as mae_7_day,
    AVG(mae_14d) as mae_14_day
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_1d IS NOT NULL
GROUP BY model_version
ORDER BY mae_14_day;

-- ----------------------------------------------------------------------------
-- Query 2: Model Performance Over Time (14-Day MAE)
-- Chart Type: Line Chart with Time Series
-- Purpose: Track how model accuracy changes over time
-- ----------------------------------------------------------------------------
SELECT
    forecast_start_date,
    model_version,
    mae_14d
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01'
ORDER BY forecast_start_date, model_version;

-- ----------------------------------------------------------------------------
-- Query 3: Probabilistic Metrics Comparison (14-Day Horizon)
-- Chart Type: Grouped Bar Chart
-- Purpose: Compare probabilistic forecast quality across models
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    AVG(crps_14d) as avg_crps,
    AVG(calibration_score_14d) as avg_calibration_error,
    AVG(coverage_80_14d) as avg_coverage_80pct,
    AVG(coverage_95_14d) as avg_coverage_95pct
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND crps_14d IS NOT NULL
GROUP BY model_version
ORDER BY avg_crps;

-- ----------------------------------------------------------------------------
-- Query 4: Model Ranking Table (All Metrics, 14-Day Horizon)
-- Chart Type: Table
-- Purpose: Comprehensive comparison of all models
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    COUNT(*) as num_forecasts,
    ROUND(AVG(mae_14d), 2) as avg_mae,
    ROUND(AVG(rmse_14d), 2) as avg_rmse,
    ROUND(AVG(mape_14d), 2) as avg_mape_pct,
    ROUND(AVG(crps_14d), 2) as avg_crps,
    ROUND(AVG(calibration_score_14d), 4) as avg_calibration,
    ROUND(AVG(coverage_80_14d), 3) as coverage_80,
    ROUND(AVG(coverage_95_14d), 3) as coverage_95,
    ROUND(AVG(sharpness_80_14d), 2) as interval_width_80
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_14d IS NOT NULL
GROUP BY model_version
ORDER BY avg_mae;

-- ----------------------------------------------------------------------------
-- Query 5: Calibration Quality Over Time
-- Chart Type: Line Chart
-- Purpose: Track calibration drift (lower is better, 0 is perfect)
-- ----------------------------------------------------------------------------
SELECT
    forecast_start_date,
    model_version,
    calibration_score_14d
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND calibration_score_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01'
ORDER BY forecast_start_date, model_version;

-- ----------------------------------------------------------------------------
-- Query 6: Coverage Rate Monitoring (80% Prediction Interval)
-- Chart Type: Line Chart
-- Purpose: Verify prediction intervals are well-calibrated (should be ~0.80)
-- ----------------------------------------------------------------------------
SELECT
    forecast_start_date,
    model_version,
    coverage_80_14d,
    0.80 as target_coverage
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND coverage_80_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01'
ORDER BY forecast_start_date, model_version;

-- ----------------------------------------------------------------------------
-- Query 7: CRPS vs MAE Scatter Plot (Model Tradeoffs)
-- Chart Type: Scatter Plot (MAE on X-axis, CRPS on Y-axis, color by model)
-- Purpose: Visualize point forecast accuracy vs distributional accuracy
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    mae_14d as point_forecast_mae,
    crps_14d as distribution_crps,
    forecast_start_date
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_14d IS NOT NULL
  AND crps_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01';

-- ----------------------------------------------------------------------------
-- Query 8: Model Performance Heatmap (Last 30 Forecasts)
-- Chart Type: Heatmap or Pivot Table
-- Purpose: Recent performance summary
-- ----------------------------------------------------------------------------
WITH recent_forecasts AS (
    SELECT
        model_version,
        forecast_start_date,
        mae_14d,
        crps_14d,
        coverage_80_14d,
        ROW_NUMBER() OVER (PARTITION BY model_version ORDER BY forecast_start_date DESC) as rn
    FROM commodity.forecast.forecast_metadata
    WHERE commodity = 'Coffee'
      AND mae_14d IS NOT NULL
)
SELECT
    model_version,
    ROUND(AVG(mae_14d), 2) as recent_mae,
    ROUND(AVG(crps_14d), 2) as recent_crps,
    ROUND(AVG(coverage_80_14d), 3) as recent_coverage,
    COUNT(*) as num_recent_forecasts
FROM recent_forecasts
WHERE rn <= 30
GROUP BY model_version
ORDER BY recent_mae;

-- ----------------------------------------------------------------------------
-- Query 9: Horizon-Specific Performance (Detailed by Day)
-- Chart Type: Grouped Bar Chart (1d, 7d, 14d side-by-side)
-- Purpose: See if models are better at short-term vs long-term forecasts
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    'MAE' as metric,
    ROUND(AVG(mae_1d), 2) as day_1,
    ROUND(AVG(mae_7d), 2) as day_7,
    ROUND(AVG(mae_14d), 2) as day_14
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee' AND mae_1d IS NOT NULL
GROUP BY model_version

UNION ALL

SELECT
    model_version,
    'CRPS' as metric,
    ROUND(AVG(crps_1d), 2) as day_1,
    ROUND(AVG(crps_7d), 2) as day_7,
    ROUND(AVG(crps_14d), 2) as day_14
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee' AND crps_1d IS NOT NULL
GROUP BY model_version

ORDER BY model_version, metric;

-- ----------------------------------------------------------------------------
-- Query 10: Model Win Rate (Best Model Count by Date)
-- Chart Type: Stacked Area Chart
-- Purpose: Show which model is "winning" on each forecast date
-- ----------------------------------------------------------------------------
WITH ranked_models AS (
    SELECT
        forecast_start_date,
        model_version,
        mae_14d,
        ROW_NUMBER() OVER (PARTITION BY forecast_start_date ORDER BY mae_14d) as rank
    FROM commodity.forecast.forecast_metadata
    WHERE commodity = 'Coffee'
      AND mae_14d IS NOT NULL
      AND forecast_start_date >= '2023-01-01'
)
SELECT
    forecast_start_date,
    model_version,
    CASE WHEN rank = 1 THEN 1 ELSE 0 END as is_best_model
FROM ranked_models
ORDER BY forecast_start_date, model_version;

-- ----------------------------------------------------------------------------
-- Query 11: Sharpness vs Coverage Tradeoff
-- Chart Type: Scatter Plot (sharpness on X, coverage on Y, color by model)
-- Purpose: Verify models aren't just making wide intervals to get good coverage
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    sharpness_80_14d as interval_width,
    coverage_80_14d as coverage_rate,
    0.80 as target_coverage
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND sharpness_80_14d IS NOT NULL
  AND coverage_80_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01';

-- ----------------------------------------------------------------------------
-- Query 12: Model Stability (Standard Deviation of MAE)
-- Chart Type: Bar Chart
-- Purpose: Identify which models have consistent vs volatile performance
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    ROUND(AVG(mae_14d), 2) as avg_mae,
    ROUND(STDDEV(mae_14d), 2) as mae_std,
    ROUND(STDDEV(mae_14d) / AVG(mae_14d), 3) as coefficient_of_variation
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_14d IS NOT NULL
GROUP BY model_version
ORDER BY coefficient_of_variation;

-- ----------------------------------------------------------------------------
-- Query 13: Monthly Performance Summary
-- Chart Type: Heatmap (months on Y-axis, models on X-axis, color by MAE)
-- Purpose: Identify seasonal patterns in model performance
-- ----------------------------------------------------------------------------
SELECT
    DATE_FORMAT(forecast_start_date, 'yyyy-MM') as forecast_month,
    model_version,
    ROUND(AVG(mae_14d), 2) as monthly_mae,
    COUNT(*) as num_forecasts
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND mae_14d IS NOT NULL
  AND forecast_start_date >= '2023-01-01'
GROUP BY DATE_FORMAT(forecast_start_date, 'yyyy-MM'), model_version
ORDER BY forecast_month, model_version;

-- ----------------------------------------------------------------------------
-- Query 14: Data Availability Check
-- Chart Type: Table
-- Purpose: Verify evaluation coverage and identify gaps
-- ----------------------------------------------------------------------------
SELECT
    model_version,
    COUNT(*) as total_forecasts,
    SUM(CASE WHEN mae_1d IS NOT NULL THEN 1 ELSE 0 END) as has_1d_metrics,
    SUM(CASE WHEN mae_7d IS NOT NULL THEN 1 ELSE 0 END) as has_7d_metrics,
    SUM(CASE WHEN mae_14d IS NOT NULL THEN 1 ELSE 0 END) as has_14d_metrics,
    SUM(CASE WHEN crps_14d IS NOT NULL THEN 1 ELSE 0 END) as has_probabilistic_metrics,
    MIN(forecast_start_date) as earliest_forecast,
    MAX(forecast_start_date) as latest_forecast
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
GROUP BY model_version
ORDER BY model_version;

-- ============================================================================
-- USAGE NOTES:
-- ============================================================================
-- 1. Create a new Databricks SQL Dashboard
-- 2. Add visualizations using the queries above
-- 3. Set up filters for:
--    - commodity (Coffee, Sugar)
--    - date_range (use forecast_start_date)
--    - horizon (1d, 7d, 14d)
--
-- 4. Recommended Dashboard Layout:
--    Row 1: Model Comparison (Query 1) + Performance Over Time (Query 2)
--    Row 2: Ranking Table (Query 4) + Probabilistic Metrics (Query 3)
--    Row 3: Calibration (Query 5) + Coverage Monitoring (Query 6)
--    Row 4: CRPS vs MAE (Query 7) + Sharpness vs Coverage (Query 11)
--
-- 5. Refresh frequency: Daily after backfill completes
-- ============================================================================
