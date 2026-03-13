-- ============================================
-- DATABRICKS BRONZE LAYER - Deduplication Tables
-- ============================================
-- Creates tables with automatic deduplication
-- Uses QUALIFY to keep only latest version of each record
-- Tables use clean names: market, vix, macro, weather, cftc, gdelt

USE CATALOG commodity;

-- Market Data (Coffee & Sugar) - Full OHLCV data
CREATE OR REPLACE TABLE commodity.bronze.market AS
SELECT date, commodity, open, high, low, close, volume
FROM commodity.landing.market_data_inc
QUALIFY ROW_NUMBER() OVER (PARTITION BY date, commodity ORDER BY ingest_ts DESC) = 1;

-- Macro Data (FX rates)
CREATE OR REPLACE TABLE commodity.bronze.macro AS
SELECT *
FROM commodity.landing.macro_data_inc
QUALIFY ROW_NUMBER() OVER (PARTITION BY date ORDER BY ingest_ts DESC) = 1;

-- VIX Data (volatility)
CREATE OR REPLACE TABLE commodity.bronze.vix AS
SELECT date, vix
FROM commodity.landing.vix_data_inc
QUALIFY ROW_NUMBER() OVER (PARTITION BY date ORDER BY ingest_ts DESC) = 1;

-- Weather Data
CREATE OR REPLACE TABLE commodity.bronze.weather AS
SELECT *
FROM commodity.landing.weather_data_inc
QUALIFY ROW_NUMBER() OVER (PARTITION BY date, region, commodity ORDER BY ingest_ts DESC) = 1;

-- CFTC Data (trader positioning)
CREATE OR REPLACE TABLE commodity.bronze.cftc AS
SELECT *
FROM commodity.landing.cftc_data_inc
QUALIFY ROW_NUMBER() OVER (PARTITION BY date, market_name ORDER BY ingest_ts DESC) = 1;

-- GDELT News Sentiment (all records, no deduplication)
CREATE OR REPLACE TABLE commodity.bronze.gdelt AS
SELECT
  date,
  TO_TIMESTAMP(date, 'yyyyMMddHHmmss') as event_timestamp,
  source_url,
  themes,
  locations,
  persons,
  organizations,
  tone,
  all_names
FROM commodity.landing.gdelt_sentiment_inc;

-- Verify tables created
USE CATALOG commodity;
SHOW TABLES IN commodity.bronze;

-- Sample query: Coffee prices over time
SELECT * FROM commodity.bronze.market
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 10;
