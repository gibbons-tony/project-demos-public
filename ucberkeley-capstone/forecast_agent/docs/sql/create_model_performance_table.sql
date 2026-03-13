-- Model Performance Metrics Table
-- Stores evaluation metrics for all historical forecasts
-- One row per forecast window × model × horizon

CREATE TABLE IF NOT EXISTS commodity.forecast.model_performance (
    -- Forecast identifiers
    forecast_start_date DATE NOT NULL,
    data_cutoff_date DATE NOT NULL,
    commodity STRING NOT NULL,
    model_version STRING NOT NULL,
    horizon INT NOT NULL,  -- 1, 7, or 14 days ahead

    -- Point forecast metrics
    mae DOUBLE,  -- Mean Absolute Error
    rmse DOUBLE,  -- Root Mean Squared Error
    mape DOUBLE,  -- Mean Absolute Percentage Error
    directional_accuracy DOUBLE,  -- Day-to-day directional accuracy (0-1)
    directional_accuracy_from_day0 DOUBLE,  -- From forecast start (0-1)

    -- Probabilistic forecast metrics
    crps DOUBLE,  -- Continuous Ranked Probability Score
    calibration_score DOUBLE,  -- Calibration error (lower is better)
    coverage_80 DOUBLE,  -- Coverage rate at 80% prediction interval (0-1)
    coverage_95 DOUBLE,  -- Coverage rate at 95% prediction interval (0-1)
    sharpness_80 DOUBLE,  -- Average width of 80% interval
    sharpness_95 DOUBLE,  -- Average width of 95% interval

    -- Metadata
    num_paths INT,  -- Number of Monte Carlo paths used
    num_days_evaluated INT,  -- How many days had actuals available
    evaluation_timestamp TIMESTAMP,  -- When metrics were calculated

    -- Partitioning for performance
    year INT,
    month INT
)
USING DELTA
PARTITIONED BY (year, month)
COMMENT 'Historical forecast performance metrics for model comparison and dashboard';

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_model_performance_lookup
ON commodity.forecast.model_performance (commodity, model_version, forecast_start_date);

CREATE INDEX IF NOT EXISTS idx_model_performance_horizon
ON commodity.forecast.model_performance (commodity, horizon, forecast_start_date);
