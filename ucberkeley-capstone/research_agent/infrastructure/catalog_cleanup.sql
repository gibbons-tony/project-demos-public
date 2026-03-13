-- ============================================================================
-- Databricks Catalog Cleanup and Reorganization
-- ============================================================================
-- This script:
-- 1. Creates forecasts schema
-- 2. Renames bronze tables (remove v_, _data, _all suffixes)
-- 3. Moves forecast tables from silver to forecasts schema
-- 4. Cleans up duplicate/old tables
--
-- Run this in Databricks SQL Editor or via databricks CLI
-- ============================================================================

-- ============================================================================
-- STEP 1: Create forecast schema if it doesn't exist
-- ============================================================================
CREATE SCHEMA IF NOT EXISTS commodity.forecast
COMMENT 'Forecast model outputs and metadata';

-- ============================================================================
-- STEP 2: Move forecast tables from silver to forecasts
-- ============================================================================

-- Create forecast tables in new schema
CREATE OR REPLACE TABLE commodity.forecast.point_forecasts AS
SELECT * FROM commodity.silver.point_forecasts;

CREATE OR REPLACE TABLE commodity.forecast.distributions AS
SELECT * FROM commodity.silver.distributions;

CREATE OR REPLACE TABLE commodity.forecast.forecast_actuals AS
SELECT * FROM commodity.silver.forecast_actuals;

CREATE OR REPLACE TABLE commodity.forecast.forecast_metadata AS
SELECT * FROM commodity.silver.forecast_metadata;

-- ============================================================================
-- STEP 3: Rename bronze tables to clean names
-- ============================================================================

-- VIX: v_vix_data_all → vix
CREATE OR REPLACE TABLE commodity.bronze.vix AS
SELECT * FROM commodity.bronze.v_vix_data_all;

-- CFTC: v_cftc_data_all → cftc
CREATE OR REPLACE TABLE commodity.bronze.cftc AS
SELECT * FROM commodity.bronze.v_cftc_data_all;

-- GDELT: v_gdelt_sentiment_all → gdelt (already exists without v_, keep it)
-- Just ensure v_gdelt_sentiment_all points to same data
CREATE OR REPLACE TABLE commodity.bronze.gdelt AS
SELECT * FROM commodity.bronze.v_gdelt_sentiment_all;

-- Macro: v_macro_data_all → macro
CREATE OR REPLACE TABLE commodity.bronze.macro AS
SELECT * FROM commodity.bronze.v_macro_data_all;

-- Market: v_market_data_all → market
CREATE OR REPLACE TABLE commodity.bronze.market AS
SELECT * FROM commodity.bronze.v_market_data_all;

-- Weather: v_weather_data_all → weather
CREATE OR REPLACE TABLE commodity.bronze.weather AS
SELECT * FROM commodity.bronze.v_weather_data_all;

-- ============================================================================
-- VALIDATION QUERIES (run these to verify)
-- ============================================================================

-- Check row counts match
SELECT 'vix' as table_name, COUNT(*) as row_count FROM commodity.bronze.vix
UNION ALL
SELECT 'cftc', COUNT(*) FROM commodity.bronze.cftc
UNION ALL
SELECT 'gdelt', COUNT(*) FROM commodity.bronze.gdelt
UNION ALL
SELECT 'macro', COUNT(*) FROM commodity.bronze.macro
UNION ALL
SELECT 'market', COUNT(*) FROM commodity.bronze.market
UNION ALL
SELECT 'weather', COUNT(*) FROM commodity.bronze.weather
UNION ALL
SELECT 'unified_data', COUNT(*) FROM commodity.silver.unified_data
UNION ALL
SELECT 'point_forecasts', COUNT(*) FROM commodity.forecast.point_forecasts
UNION ALL
SELECT 'distributions', COUNT(*) FROM commodity.forecast.distributions
UNION ALL
SELECT 'forecast_actuals', COUNT(*) FROM commodity.forecast.forecast_actuals
UNION ALL
SELECT 'forecast_metadata', COUNT(*) FROM commodity.forecast.forecast_metadata;

-- ============================================================================
-- STEP 4: Drop old tables (only run AFTER validation!)
-- ============================================================================

-- Drop old bronze tables with v_ prefix
DROP TABLE IF EXISTS commodity.bronze.v_vix_data_all;
DROP TABLE IF EXISTS commodity.bronze.v_cftc_data_all;
DROP TABLE IF EXISTS commodity.bronze.v_gdelt_sentiment_all;
DROP TABLE IF EXISTS commodity.bronze.v_macro_data_all;
DROP TABLE IF EXISTS commodity.bronze.v_market_data_all;
DROP TABLE IF EXISTS commodity.bronze.v_weather_data_all;

-- Drop old bronze tables without v_ prefix (duplicates)
DROP TABLE IF EXISTS commodity.bronze.vix_data;
DROP TABLE IF EXISTS commodity.bronze.cftc_data;
DROP TABLE IF EXISTS commodity.bronze.gdelt_sentiment;
DROP TABLE IF EXISTS commodity.bronze.macro_data;
DROP TABLE IF EXISTS commodity.bronze.market_data;
DROP TABLE IF EXISTS commodity.bronze.weather_data;

-- Drop forecast tables from silver (now in forecasts schema)
DROP TABLE IF EXISTS commodity.silver.point_forecasts;
DROP TABLE IF EXISTS commodity.silver.distributions;
DROP TABLE IF EXISTS commodity.silver.forecast_actuals;
DROP TABLE IF EXISTS commodity.silver.forecast_metadata;

-- ============================================================================
-- FINAL STATE
-- ============================================================================
-- Bronze schema: vix, cftc, gdelt, macro, market, weather
-- Silver schema: unified_data
-- Forecasts schema: point_forecasts, distributions, forecast_actuals, forecast_metadata
-- ============================================================================
