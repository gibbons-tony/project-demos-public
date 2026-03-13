CREATE OR REPLACE TABLE commodity.silver.unified_data AS

-- =============================================================================
-- STEP 1: CREATE COMPLETE DATE SPINE
-- =============================================================================
WITH date_spine AS (
  SELECT date_add('2015-07-07', x - 1) as date
  FROM (SELECT explode(sequence(1, 10000)) as x)
  WHERE date_add('2015-07-07', x - 1) <= current_date()
),

-- =============================================================================
-- STEP 2: DEDUPLICATE GLOBAL DATA
-- =============================================================================

-- Market Data: Full OHLCV data
market_clean AS (
  SELECT date, commodity, open, high, low, close, volume
  FROM commodity.bronze.market
  WHERE date >= '2015-07-07'
),

-- VIX: Simple DISTINCT (all duplicates are identical values)
vix_clean AS (
  SELECT DISTINCT date, vix
  FROM commodity.bronze.vix
  WHERE date >= '2015-07-07'
),

-- Macro: Pick row with most non-null columns
macro_ranked AS (
  SELECT
    date,
    vnd_usd, cop_usd, idr_usd, etb_usd, hnl_usd, ugx_usd, pen_usd, xaf_usd,
    gtq_usd, gnf_usd, nio_usd, crc_usd, tzs_usd, kes_usd, lak_usd, pkr_usd,
    php_usd, egp_usd, ars_usd, rub_usd, try_usd, uah_usd, irr_usd, byn_usd,
    ROW_NUMBER() OVER (
      PARTITION BY date
      ORDER BY
        (CASE WHEN vnd_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN cop_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN idr_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN etb_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN hnl_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN ugx_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN pen_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN xaf_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN gtq_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN gnf_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN nio_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN crc_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN tzs_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN kes_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN lak_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN pkr_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN php_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN egp_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN ars_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN rub_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN try_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN uah_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN irr_usd IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN byn_usd IS NOT NULL THEN 1 ELSE 0 END) DESC
    ) as rn
  FROM commodity.bronze.macro
  WHERE date >= '2015-07-07'
),

macro_clean AS (
  SELECT 
    date, vnd_usd, cop_usd, idr_usd, etb_usd, hnl_usd, ugx_usd, pen_usd, xaf_usd,
    gtq_usd, gnf_usd, nio_usd, crc_usd, tzs_usd, kes_usd, lak_usd, pkr_usd,
    php_usd, egp_usd, ars_usd, rub_usd, try_usd, uah_usd, irr_usd, byn_usd
  FROM macro_ranked
  WHERE rn = 1
),

-- =============================================================================
-- STEP 3: IDENTIFY TRADING DAYS
-- =============================================================================

trading_days AS (
  SELECT DISTINCT 
    date,
    commodity,
    1 as is_trading_day
  FROM market_clean
),

-- =============================================================================
-- STEP 4: FORWARD FILL ONTO DATE SPINE
-- =============================================================================

commodities AS (
  SELECT 'Coffee' as commodity UNION ALL SELECT 'Sugar' as commodity
),

date_commodity_spine AS (
  SELECT ds.date, c.commodity
  FROM date_spine ds
  CROSS JOIN commodities c
),

market_filled AS (
  SELECT
    dcs.date,
    dcs.commodity,
    LAST_VALUE(mc.open, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as open,
    LAST_VALUE(mc.high, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as high,
    LAST_VALUE(mc.low, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as low,
    LAST_VALUE(mc.close, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as close,
    LAST_VALUE(mc.volume, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as volume
  FROM date_commodity_spine dcs
  LEFT JOIN market_clean mc ON dcs.date = mc.date AND dcs.commodity = mc.commodity
),

vix_filled AS (
  SELECT
    ds.date,
    LAST_VALUE(vc.vix, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as vix
  FROM date_spine ds
  LEFT JOIN vix_clean vc ON ds.date = vc.date
),

macro_filled AS (
  SELECT
    ds.date,
    LAST_VALUE(mc.vnd_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as vnd_usd,
    LAST_VALUE(mc.cop_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cop_usd,
    LAST_VALUE(mc.idr_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as idr_usd,
    LAST_VALUE(mc.etb_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as etb_usd,
    LAST_VALUE(mc.hnl_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as hnl_usd,
    LAST_VALUE(mc.ugx_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as ugx_usd,
    LAST_VALUE(mc.pen_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as pen_usd,
    LAST_VALUE(mc.xaf_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as xaf_usd,
    LAST_VALUE(mc.gtq_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as gtq_usd,
    LAST_VALUE(mc.gnf_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as gnf_usd,
    LAST_VALUE(mc.nio_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as nio_usd,
    LAST_VALUE(mc.crc_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as crc_usd,
    LAST_VALUE(mc.tzs_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as tzs_usd,
    LAST_VALUE(mc.kes_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as kes_usd,
    LAST_VALUE(mc.lak_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as lak_usd,
    LAST_VALUE(mc.pkr_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as pkr_usd,
    LAST_VALUE(mc.php_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as php_usd,
    LAST_VALUE(mc.egp_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as egp_usd,
    LAST_VALUE(mc.ars_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as ars_usd,
    LAST_VALUE(mc.rub_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as rub_usd,
    LAST_VALUE(mc.try_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as try_usd,
    LAST_VALUE(mc.uah_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as uah_usd,
    LAST_VALUE(mc.irr_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as irr_usd,
    LAST_VALUE(mc.byn_usd, true) OVER (ORDER BY ds.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as byn_usd
  FROM date_spine ds
  LEFT JOIN macro_clean mc ON ds.date = mc.date
),

-- =============================================================================
-- STEP 5: WEATHER DATA (REGIONAL) - WEATHER V2 (8 FIELDS)
-- =============================================================================

weather_with_forward_fill AS (
  SELECT
    date,
    region,
    commodity,
    -- Temperature (3 fields)
    temp_max_c,
    temp_min_c,
    temp_mean_c,
    -- Precipitation (3 fields)
    precipitation_mm,
    rain_mm,
    snowfall_cm,
    -- Humidity (1 field)
    humidity_mean_pct,
    -- Wind (1 field)
    wind_speed_max_kmh,
    -- Forward fill all fields
    LAST_VALUE(temp_max_c, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as temp_max_c_filled,
    LAST_VALUE(temp_min_c, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as temp_min_c_filled,
    LAST_VALUE(temp_mean_c, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as temp_mean_c_filled,
    LAST_VALUE(precipitation_mm, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as precipitation_mm_filled,
    LAST_VALUE(rain_mm, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as rain_mm_filled,
    LAST_VALUE(snowfall_cm, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as snowfall_cm_filled,
    LAST_VALUE(humidity_mean_pct, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as humidity_mean_pct_filled,
    LAST_VALUE(wind_speed_max_kmh, true) OVER (PARTITION BY region, commodity ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as wind_speed_max_kmh_filled
  FROM commodity.bronze.weather
  WHERE date >= '2015-07-07'
),

weather_filled AS (
  SELECT DISTINCT
    date,
    region,
    commodity,
    -- Temperature (3 fields)
    temp_max_c_filled as temp_max_c,
    temp_min_c_filled as temp_min_c,
    temp_mean_c_filled as temp_mean_c,
    -- Precipitation (3 fields)
    precipitation_mm_filled as precipitation_mm,
    rain_mm_filled as rain_mm,
    snowfall_cm_filled as snowfall_cm,
    -- Humidity (1 field)
    humidity_mean_pct_filled as humidity_mean_pct,
    -- Wind (1 field)
    wind_speed_max_kmh_filled as wind_speed_max_kmh
  FROM weather_with_forward_fill
)

-- =============================================================================
-- FUTURE: GDELT SENTIMENT DATA (commodity.bronze.bronze_gkg)
-- =============================================================================
-- Uncomment to add GDELT sentiment analysis to unified_data
--
-- V2TONE is a comma-separated string with 7 dimensions:
-- 1. Tone (overall sentiment)
-- 2. Positive Score
-- 3. Negative Score
-- 4. Polarity
-- 5. Activity Reference Density
-- 6. Self/Group Reference Density
-- 7. Word Count
--
-- gdelt_raw AS (
--   SELECT
--     DATE(SQLDATE) as date,
--     CASE
--       WHEN THEMES LIKE '%COFFEE%' THEN 'Coffee'
--       WHEN THEMES LIKE '%SUGAR%' THEN 'Sugar'
--       ELSE NULL
--     END as commodity,
--     -- Parse V2TONE dimensions
--     CAST(SPLIT(V2TONE, ',')[0] AS DOUBLE) as tone,
--     CAST(SPLIT(V2TONE, ',')[1] AS DOUBLE) as positive_score,
--     CAST(SPLIT(V2TONE, ',')[2] AS DOUBLE) as negative_score,
--     CAST(SPLIT(V2TONE, ',')[3] AS DOUBLE) as polarity,
--     CAST(SPLIT(V2TONE, ',')[4] AS DOUBLE) as activity_density,
--     CAST(SPLIT(V2TONE, ',')[5] AS DOUBLE) as self_group_density,
--     CAST(SPLIT(V2TONE, ',')[6] AS DOUBLE) as word_count
--   FROM commodity.bronze.bronze_gkg
--   WHERE SQLDATE >= '20150707'  -- Match start date
--     AND (THEMES LIKE '%COFFEE%' OR THEMES LIKE '%SUGAR%')
--     AND V2TONE IS NOT NULL
-- ),
--
-- gdelt_sentiment AS (
--   SELECT
--     date,
--     commodity,
--     -- Aggregate across articles for the day
--     AVG(tone) as gdelt_tone,
--     AVG(positive_score) as gdelt_positive,
--     AVG(negative_score) as gdelt_negative,
--     AVG(polarity) as gdelt_polarity,
--     STDDEV(tone) as gdelt_tone_volatility,
--     COUNT(*) as gdelt_article_count,
--     SUM(word_count) as gdelt_total_words
--   FROM gdelt_raw
--   GROUP BY date, commodity
-- ),
--
-- gdelt_filled AS (
--   SELECT
--     ds.date,
--     c.commodity,
--     -- Forward-fill all GDELT features
--     LAST_VALUE(gs.gdelt_tone, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_tone,
--     LAST_VALUE(gs.gdelt_positive, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_positive,
--     LAST_VALUE(gs.gdelt_negative, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_negative,
--     LAST_VALUE(gs.gdelt_polarity, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_polarity,
--     LAST_VALUE(gs.gdelt_tone_volatility, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_tone_volatility,
--     LAST_VALUE(gs.gdelt_article_count, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_article_count,
--     LAST_VALUE(gs.gdelt_total_words, true) OVER (
--       PARTITION BY c.commodity ORDER BY ds.date
--       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
--     ) as gdelt_total_words
--   FROM date_spine ds
--   CROSS JOIN commodities c
--   LEFT JOIN gdelt_sentiment gs
--     ON ds.date = gs.date AND c.commodity = gs.commodity
-- ),

-- =============================================================================
-- STEP 6: FINAL JOIN WITH TRADING DAY INDICATOR
-- =============================================================================
SELECT
  wf.date,
  COALESCE(td.is_trading_day, 0) as is_trading_day,  -- 2nd column
  wf.commodity,
  -- Market Data (OHLCV)
  mf.open,
  mf.high,
  mf.low,
  mf.close,
  mf.volume,
  -- VIX
  vf.vix,
  macf.vnd_usd, macf.cop_usd, macf.idr_usd, macf.etb_usd, macf.hnl_usd, macf.ugx_usd,
  macf.pen_usd, macf.xaf_usd, macf.gtq_usd, macf.gnf_usd, macf.nio_usd, macf.crc_usd,
  macf.tzs_usd, macf.kes_usd, macf.lak_usd, macf.pkr_usd, macf.php_usd, macf.egp_usd,
  macf.ars_usd, macf.rub_usd, macf.try_usd, macf.uah_usd, macf.irr_usd, macf.byn_usd,
  wf.region,
  -- WEATHER V2 FEATURES (8 fields)
  -- Temperature (3 fields)
  wf.temp_max_c,
  wf.temp_min_c,
  wf.temp_mean_c,
  -- Precipitation (3 fields)
  wf.precipitation_mm,
  wf.rain_mm,
  wf.snowfall_cm,
  -- Humidity (1 field)
  wf.humidity_mean_pct,
  -- Wind (1 field)
  wf.wind_speed_max_kmh
  -- FUTURE: Add GDELT sentiment columns (7 features)
  -- gdf.gdelt_tone,              -- Overall sentiment
  -- gdf.gdelt_positive,          -- Positive score
  -- gdf.gdelt_negative,          -- Negative score
  -- gdf.gdelt_polarity,          -- Polarity measure
  -- gdf.gdelt_tone_volatility,   -- Sentiment disagreement
  -- gdf.gdelt_article_count,     -- News volume
  -- gdf.gdelt_total_words        -- Total coverage
FROM weather_filled wf
INNER JOIN market_filled mf ON wf.date = mf.date AND wf.commodity = mf.commodity
INNER JOIN vix_filled vf ON wf.date = vf.date
INNER JOIN macro_filled macf ON wf.date = macf.date
LEFT JOIN trading_days td ON wf.date = td.date AND wf.commodity = td.commodity
-- FUTURE: Join GDELT sentiment
-- LEFT JOIN gdelt_filled gdf ON wf.date = gdf.date AND wf.commodity = gdf.commodity
ORDER BY wf.date, wf.commodity, wf.region;
