-- =============================================================================
-- CREATE GOLD.UNIFIED_DATA - Production Table with Forward-Fill
-- =============================================================================
-- Purpose: Production-ready table with all features forward-filled
-- Grain: (date, commodity) - ~7k rows
--
-- ARCHITECTURE (DRY Principle):
--   - Built FROM commodity.gold.unified_data_raw (base table)
--   - Applies forward-fill to ALL features with NULLs
--   - Single source of truth: unified_data_raw
--   - This table is a DERIVED transformation, not a duplicate build
--
-- Benefits:
--   - DRY: No duplicate logic (date spine, deduplication, array aggregation)
--   - Maintainability: Fix bugs in one place (unified_data_raw)
--   - Clear lineage: Bronze → Raw (NULLs) → Production (forward-filled)
--   - Simple: ~122 lines vs 300+ lines of duplicated SQL
--
-- PREREQUISITE:
--   - commodity.gold schema must exist
--   - commodity.gold.unified_data_raw must exist
--   - Run create_gold_unified_data_raw.sql FIRST
-- =============================================================================

CREATE OR REPLACE TABLE commodity.gold.unified_data AS
SELECT
  date,
  commodity,
  is_trading_day,

  -- =========================================================================
  -- MARKET DATA: Forward-fill OHLV (close already forward-filled in base)
  -- =========================================================================
  LAST_VALUE(open, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as open,

  LAST_VALUE(high, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as high,

  LAST_VALUE(low, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as low,

  close,  -- Already forward-filled in base table

  LAST_VALUE(volume, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as volume,

  -- =========================================================================
  -- VIX: Forward-fill (global, not per-commodity)
  -- =========================================================================
  LAST_VALUE(vix, true) OVER (
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as vix,

  -- =========================================================================
  -- EXCHANGE RATES (24 columns): Forward-fill (global, not per-commodity)
  -- =========================================================================
  LAST_VALUE(vnd_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as vnd_usd,
  LAST_VALUE(cop_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as cop_usd,
  LAST_VALUE(idr_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as idr_usd,
  LAST_VALUE(etb_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as etb_usd,
  LAST_VALUE(hnl_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as hnl_usd,
  LAST_VALUE(ugx_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as ugx_usd,
  LAST_VALUE(pen_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as pen_usd,
  LAST_VALUE(xaf_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as xaf_usd,
  LAST_VALUE(gtq_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as gtq_usd,
  LAST_VALUE(gnf_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as gnf_usd,
  LAST_VALUE(nio_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as nio_usd,
  LAST_VALUE(crc_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as crc_usd,
  LAST_VALUE(tzs_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as tzs_usd,
  LAST_VALUE(kes_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as kes_usd,
  LAST_VALUE(lak_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as lak_usd,
  LAST_VALUE(pkr_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as pkr_usd,
  LAST_VALUE(php_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as php_usd,
  LAST_VALUE(egp_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as egp_usd,
  LAST_VALUE(ars_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as ars_usd,
  LAST_VALUE(rub_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as rub_usd,
  LAST_VALUE(try_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as try_usd,
  LAST_VALUE(uah_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as uah_usd,
  LAST_VALUE(irr_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as irr_usd,
  LAST_VALUE(byn_usd, true) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) as byn_usd,

  -- =========================================================================
  -- WEATHER DATA (array): Forward-fill entire array
  -- =========================================================================
  LAST_VALUE(weather_data, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as weather_data,

  -- =========================================================================
  -- GDELT THEMES (array): Forward-fill entire array
  -- =========================================================================
  LAST_VALUE(gdelt_themes, true) OVER (
    PARTITION BY commodity
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) as gdelt_themes

  -- NOTE: Missingness flags (has_market_data, has_weather_data, has_gdelt_data)
  -- are NOT included in production table - they're only useful for experimental models

FROM commodity.gold.unified_data_raw
ORDER BY commodity, date;
