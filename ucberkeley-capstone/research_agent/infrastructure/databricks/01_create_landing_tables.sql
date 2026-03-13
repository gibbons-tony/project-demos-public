-- ============================================
-- DATABRICKS LANDING LAYER - Table Creation
-- ============================================
-- Creates incremental landing tables from S3
-- Run this once, then refresh daily with new data

USE CATALOG commodity;

-- Market Data (Coffee & Sugar prices) - Full OHLCV data
CREATE OR REPLACE TABLE commodity.landing.market_data_inc
USING DELTA
AS
SELECT
  CAST(date AS DATE) as date,
  commodity,
  CAST(`open` AS DOUBLE) as open,
  CAST(`high` AS DOUBLE) as high,
  CAST(`low` AS DOUBLE) as low,
  CAST(`close` AS DOUBLE) as close,
  CAST(`volume` AS BIGINT) as volume,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/market_data/*.csv',
  format => 'csv',
  header => true
)
UNION ALL
SELECT
  CAST(date AS DATE) as date,
  commodity,
  CAST(`open` AS DOUBLE) as open,
  CAST(`high` AS DOUBLE) as high,
  CAST(`low` AS DOUBLE) as low,
  CAST(`close` AS DOUBLE) as close,
  CAST(`volume` AS BIGINT) as volume,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/market_data/history/*.csv',
  format => 'csv',
  header => true
);

-- Macro Data (FX rates via FRED)
CREATE OR REPLACE TABLE commodity.landing.macro_data_inc
USING DELTA
AS SELECT *,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/macro_data/*.csv',
  format => 'csv',
  header => true
);

-- VIX Data (volatility index)
CREATE OR REPLACE TABLE commodity.landing.vix_data_inc
USING DELTA
AS
SELECT *,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/vix_data/*.csv',
  format => 'csv',
  header => true
)
UNION ALL
SELECT *,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/vix_data/history/*.csv',
  format => 'csv',
  header => true
);

-- Weather Data (growing regions)
CREATE OR REPLACE TABLE commodity.landing.weather_data_inc
USING DELTA
AS SELECT *,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/weather_data/*.csv',
  format => 'csv',
  header => true
)
WHERE date IS NOT NULL;

-- CFTC Data (trader positioning)
CREATE OR REPLACE TABLE commodity.landing.cftc_data_inc
USING DELTA
AS SELECT
  `Market and Exchange Names` as market_name,
  `As of Date in Form YYYY-MM-DD` as date,
  `Open Interest (All)` as open_interest,
  `Noncommercial Positions-Long (All)` as noncomm_long,
  `Noncommercial Positions-Short (All)` as noncomm_short,
  `Commercial Positions-Long (All)` as comm_long,
  `Commercial Positions-Short (All)` as comm_short,
  `% of OI-Noncommercial-Long (All)` as pct_oi_noncomm_long,
  `% of OI-Noncommercial-Short (All)` as pct_oi_noncomm_short,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/cftc_data/*.csv',
  format => 'csv',
  header => true
);

-- GDELT News Data (commodity-filtered news sentiment)
-- Note: Raw GDELT files at s3://groundtruth-capstone/landing/gdelt/raw/*.zip
-- Filtered JSONL at s3://groundtruth-capstone/landing/gdelt/filtered/*.jsonl
CREATE OR REPLACE TABLE commodity.landing.gdelt_sentiment_inc
USING DELTA
AS SELECT
  date,
  TO_TIMESTAMP(date, 'yyyyMMddHHmmss') as event_timestamp,
  source_url,
  themes,
  locations,
  persons,
  organizations,
  tone,
  all_names,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/gdelt/filtered/*.jsonl',
  format => 'json'
);

-- Verify tables created
SHOW TABLES IN commodity.landing;

-- Check row counts
SELECT 'market_data_inc' as `table`, COUNT(*) as rows FROM commodity.landing.market_data_inc
UNION ALL
SELECT 'macro_data_inc', COUNT(*) FROM commodity.landing.macro_data_inc
UNION ALL
SELECT 'vix_data_inc', COUNT(*) FROM commodity.landing.vix_data_inc
UNION ALL
SELECT 'weather_data_inc', COUNT(*) FROM commodity.landing.weather_data_inc
UNION ALL
SELECT 'cftc_data_inc', COUNT(*) FROM commodity.landing.cftc_data_inc
UNION ALL
SELECT 'gdelt_sentiment_inc', COUNT(*) FROM commodity.landing.gdelt_sentiment_inc;
