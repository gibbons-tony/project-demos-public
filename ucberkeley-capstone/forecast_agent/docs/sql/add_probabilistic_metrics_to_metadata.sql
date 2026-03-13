-- Extend forecast_metadata table with probabilistic forecast metrics
-- This adds CRPS, calibration, coverage, and sharpness columns

ALTER TABLE commodity.forecast.forecast_metadata
ADD COLUMNS (
    -- Probabilistic Metrics (1-day, 7-day, 14-day horizons)
    crps_1d DECIMAL(10,4) COMMENT 'Continuous Ranked Probability Score (1-day)',
    crps_7d DECIMAL(10,4) COMMENT 'Continuous Ranked Probability Score (7-day)',
    crps_14d DECIMAL(10,4) COMMENT 'Continuous Ranked Probability Score (14-day)',

    calibration_score_1d DECIMAL(10,4) COMMENT 'Calibration error (1-day, 0=perfect)',
    calibration_score_7d DECIMAL(10,4) COMMENT 'Calibration error (7-day, 0=perfect)',
    calibration_score_14d DECIMAL(10,4) COMMENT 'Calibration error (14-day, 0=perfect)',

    coverage_80_1d DECIMAL(10,4) COMMENT '80% prediction interval coverage rate (1-day)',
    coverage_80_7d DECIMAL(10,4) COMMENT '80% prediction interval coverage rate (7-day)',
    coverage_80_14d DECIMAL(10,4) COMMENT '80% prediction interval coverage rate (14-day)',

    coverage_95_1d DECIMAL(10,4) COMMENT '95% prediction interval coverage rate (1-day)',
    coverage_95_7d DECIMAL(10,4) COMMENT '95% prediction interval coverage rate (7-day)',
    coverage_95_14d DECIMAL(10,4) COMMENT '95% prediction interval coverage rate (14-day)',

    sharpness_80_1d DECIMAL(10,4) COMMENT 'Average 80% interval width (1-day)',
    sharpness_80_7d DECIMAL(10,4) COMMENT 'Average 80% interval width (7-day)',
    sharpness_80_14d DECIMAL(10,4) COMMENT 'Average 80% interval width (14-day)',

    sharpness_95_1d DECIMAL(10,4) COMMENT 'Average 95% interval width (1-day)',
    sharpness_95_7d DECIMAL(10,4) COMMENT 'Average 95% interval width (7-day)',
    sharpness_95_14d DECIMAL(10,4) COMMENT 'Average 95% interval width (14-day)'
);

-- Add comment explaining the addition
COMMENT ON TABLE commodity.forecast.forecast_metadata IS
'Forecast performance metrics including point forecasts (MAE, RMSE, MAPE) and probabilistic metrics (CRPS, calibration, coverage, sharpness)';
