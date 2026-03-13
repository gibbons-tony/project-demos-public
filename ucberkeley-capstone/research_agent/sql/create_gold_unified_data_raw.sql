-- =============================================================================
-- CREATE GOLD.UNIFIED_DATA_RAW - Base Table with Minimal Forward-Fill
-- =============================================================================
-- Purpose: Base table with NULLs preserved for imputation flexibility
-- Grain: (date, commodity) - ~7k rows
--
-- IMPUTATION PHILOSOPHY:
--   - ONLY forward-fill `close` price (target variable = market state on weekends)
--   - ALL other features preserved as NULL where missing (VIX, FX, OHLV, weather, GDELT)
--   - Rationale: Imputation is a MODELING decision, not a data layer decision
--   - Benefit: forecast_agent can experiment with different imputation strategies per model
--
-- MISSINGNESS INDICATORS (3 composite flags):
--   - has_market_data: 1 if VIX + any FX + OHLV present (trading day), 0 otherwise
--   - has_weather_data: 1 if weather_data array non-empty, 0 otherwise
--   - has_gdelt_data: 1 if gdelt_themes array non-empty, 0 otherwise
--
-- Benefits:
--   - 90% fewer rows than silver.unified_data (~7k vs ~75k)
--   - Models choose imputation strategy (forward-fill, mean, interpolate, etc.)
--   - Tree models can leverage missingness as signal
--   - Clean array structure for PySpark transformers
--
-- ARCHITECTURE:
--   - This is the BASE TABLE (single source of truth)
--   - commodity.gold.unified_data is DERIVED from this via forward-fill
--
-- PREREQUISITE: commodity.gold schema must exist
--   (run once: CREATE SCHEMA IF NOT EXISTS commodity.gold)
-- =============================================================================

CREATE OR REPLACE TABLE commodity.gold.unified_data_raw AS

-- =============================================================================
-- STEP 1: CREATE COMPLETE DATE SPINE
-- =============================================================================
WITH date_spine AS (
  SELECT date_add('2015-07-07', x - 1) as date
  FROM (SELECT explode(sequence(1, 10000)) as x)
  WHERE date_add('2015-07-07', x - 1) <= current_date()
),

-- =============================================================================
-- STEP 2: DEDUPLICATE GLOBAL DATA (Same as silver.unified_data)
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
-- STEP 4: JOIN SCALAR DATA ONTO DATE SPINE (MINIMAL FORWARD-FILL)
-- =============================================================================
-- DESIGN DECISION: Only forward-fill `close` price (target variable = market state)
-- All other features (VIX, FX, OHLV) kept as NULL where missing
-- This allows forecast_agent to choose imputation strategy per model
-- =============================================================================

commodities AS (
  SELECT 'Coffee' as commodity UNION ALL SELECT 'Sugar' as commodity
),

date_commodity_spine AS (
  SELECT ds.date, c.commodity
  FROM date_spine ds
  CROSS JOIN commodities c
),

-- Market data: ONLY forward-fill close price (target variable)
-- Open, high, low, volume remain NULL on non-trading days
market_filled AS (
  SELECT
    dcs.date,
    dcs.commodity,
    mc.open,   -- NULL on weekends/holidays (model decides imputation)
    mc.high,   -- NULL on weekends/holidays
    mc.low,    -- NULL on weekends/holidays
    LAST_VALUE(mc.close, true) OVER (PARTITION BY dcs.commodity ORDER BY dcs.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as close,  -- Forward-filled (target variable)
    mc.volume  -- NULL on weekends/holidays
  FROM date_commodity_spine dcs
  LEFT JOIN market_clean mc ON dcs.date = mc.date AND dcs.commodity = mc.commodity
),

-- VIX: NO forward-fill (model decides imputation strategy)
vix_raw AS (
  SELECT
    ds.date,
    vc.vix  -- NULL on weekends/holidays
  FROM date_spine ds
  LEFT JOIN vix_clean vc ON ds.date = vc.date
),

-- Macro (FX rates): NO forward-fill (model decides imputation strategy)
macro_raw AS (
  SELECT
    ds.date,
    mc.vnd_usd, mc.cop_usd, mc.idr_usd, mc.etb_usd, mc.hnl_usd,
    mc.ugx_usd, mc.pen_usd, mc.xaf_usd, mc.gtq_usd, mc.gnf_usd,
    mc.nio_usd, mc.crc_usd, mc.tzs_usd, mc.kes_usd, mc.lak_usd,
    mc.pkr_usd, mc.php_usd, mc.egp_usd, mc.ars_usd, mc.rub_usd,
    mc.try_usd, mc.uah_usd, mc.irr_usd, mc.byn_usd
  FROM date_spine ds
  LEFT JOIN macro_clean mc ON ds.date = mc.date
),

-- =============================================================================
-- STEP 5: WEATHER DATA AS ARRAY OF STRUCTS (Multi-Regional)
-- =============================================================================
-- NO FORWARD-FILL: Weather data kept raw (model decides imputation strategy)
-- =============================================================================

-- Aggregate weather data into array of structs (one per region)
-- NULL values preserved (no forward-fill)
weather_array AS (
  SELECT
    date,
    commodity,
    collect_list(
      struct(
        region,
        temp_max_c,     -- NULL if missing
        temp_min_c,     -- NULL if missing
        temp_mean_c,    -- NULL if missing
        precipitation_mm,  -- NULL if missing
        rain_mm,        -- NULL if missing
        snowfall_cm,    -- NULL if missing
        humidity_mean_pct,  -- NULL if missing
        wind_speed_max_kmh  -- NULL if missing
      )
    ) as weather_data
  FROM commodity.bronze.weather
  WHERE date >= '2015-07-07'
  GROUP BY date, commodity
),

-- =============================================================================
-- STEP 6: GDELT SENTIMENT AS ARRAY OF STRUCTS (Theme Groups)
-- =============================================================================

-- Convert wide format GDELT to array of structs
gdelt_long AS (
  SELECT
    article_date as date,
    INITCAP(commodity) as commodity,  -- Capitalize to match gold table ('coffee' -> 'Coffee')
    stack(7,
      'SUPPLY',     group_SUPPLY_count,     group_SUPPLY_tone_avg,     group_SUPPLY_tone_positive,     group_SUPPLY_tone_negative,     group_SUPPLY_tone_polarity,
      'LOGISTICS',  group_LOGISTICS_count,  group_LOGISTICS_tone_avg,  group_LOGISTICS_tone_positive,  group_LOGISTICS_tone_negative,  group_LOGISTICS_tone_polarity,
      'TRADE',      group_TRADE_count,      group_TRADE_tone_avg,      group_TRADE_tone_positive,      group_TRADE_tone_negative,      group_TRADE_tone_polarity,
      'MARKET',     group_MARKET_count,     group_MARKET_tone_avg,     group_MARKET_tone_positive,     group_MARKET_tone_negative,     group_MARKET_tone_polarity,
      'POLICY',     group_POLICY_count,     group_POLICY_tone_avg,     group_POLICY_tone_positive,     group_POLICY_tone_negative,     group_POLICY_tone_polarity,
      'CORE',       group_CORE_count,       group_CORE_tone_avg,       group_CORE_tone_positive,       group_CORE_tone_negative,       group_CORE_tone_polarity,
      'OTHER',      group_OTHER_count,      group_OTHER_tone_avg,      group_OTHER_tone_positive,      group_OTHER_tone_negative,      group_OTHER_tone_polarity
    ) AS (theme_group, article_count, tone_avg, tone_positive, tone_negative, tone_polarity)
  FROM commodity.silver.gdelt_wide
  WHERE article_date >= '2015-07-07'
),

-- Aggregate GDELT into array of structs (one per theme group)
gdelt_array AS (
  SELECT
    date,
    commodity,
    collect_list(
      struct(
        theme_group,
        article_count,
        tone_avg,
        tone_positive,
        tone_negative,
        tone_polarity
      )
    ) as gdelt_themes
  FROM gdelt_long
  GROUP BY date, commodity
),

-- NO FORWARD-FILL for GDELT (sentiment is time-sensitive, not like prices)
-- Days without articles will have NULL gdelt_themes (let the model handle it)
gdelt_filled AS (
  SELECT
    dcs.date,
    dcs.commodity,
    ga.gdelt_themes  -- NULL for days without articles (no forward-fill)
  FROM date_commodity_spine dcs
  LEFT JOIN gdelt_array ga ON dcs.date = ga.date AND dcs.commodity = ga.commodity
),

-- =============================================================================
-- STEP 7: FINAL JOIN - Combine all sources
-- =============================================================================

final_join AS (
  SELECT
    mf.date,
    mf.commodity,
    COALESCE(td.is_trading_day, 0) as is_trading_day,

    -- Market data (close is forward-filled, others have NULLs)
    mf.open,      -- NULL on weekends/holidays
    mf.high,      -- NULL on weekends/holidays
    mf.low,       -- NULL on weekends/holidays
    mf.close,     -- Forward-filled (target variable)
    mf.volume,    -- NULL on weekends/holidays

    -- VIX (NULL on weekends/holidays - model decides imputation)
    vr.vix,

    -- Exchange rates (NULL on weekends/holidays - model decides imputation)
    mr.vnd_usd, mr.cop_usd, mr.idr_usd, mr.etb_usd, mr.hnl_usd,
    mr.ugx_usd, mr.pen_usd, mr.xaf_usd, mr.gtq_usd, mr.gnf_usd,
    mr.nio_usd, mr.crc_usd, mr.tzs_usd, mr.kes_usd, mr.lak_usd,
    mr.pkr_usd, mr.php_usd, mr.egp_usd, mr.ars_usd, mr.rub_usd,
    mr.try_usd, mr.uah_usd, mr.irr_usd, mr.byn_usd,

    -- Weather data (array of structs - one per region, NULLs preserved)
    wa.weather_data,

    -- GDELT sentiment (array of structs - NULL for days without articles)
    gf.gdelt_themes,

    -- =============================================================================
    -- MISSINGNESS INDICATORS (3 composite flags for feature engineering)
    -- =============================================================================

    -- Flag 1: Market data availability (VIX + FX + OHLV all NULL together on weekends)
    CASE
      WHEN vr.vix IS NOT NULL OR mf.open IS NOT NULL THEN 1
      ELSE 0
    END as has_market_data,

    -- Flag 2: Weather data availability
    CASE
      WHEN wa.weather_data IS NOT NULL AND size(wa.weather_data) > 0 THEN 1
      ELSE 0
    END as has_weather_data,

    -- Flag 3: GDELT data availability
    CASE
      WHEN gf.gdelt_themes IS NOT NULL AND size(gf.gdelt_themes) > 0 THEN 1
      ELSE 0
    END as has_gdelt_data

  FROM market_filled mf
  INNER JOIN vix_raw vr ON mf.date = vr.date
  INNER JOIN macro_raw mr ON mf.date = mr.date
  LEFT JOIN trading_days td ON mf.date = td.date AND mf.commodity = td.commodity
  LEFT JOIN weather_array wa ON mf.date = wa.date AND mf.commodity = wa.commodity
  LEFT JOIN gdelt_filled gf ON mf.date = gf.date AND mf.commodity = gf.commodity
)

-- =============================================================================
-- FINAL SELECT
-- =============================================================================

SELECT * FROM final_join
ORDER BY commodity, date;
