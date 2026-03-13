# Gold Unified Data - Complete Dependency Graph

**Purpose**: Complete data lineage from AWS Lambda → S3 → Databricks Bronze → Silver → Gold
**Last Updated**: 2025-12-05
**Target Table**: `commodity.gold.unified_data`

---

## 📊 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│ SCHEDULED DATA INGESTION (2 AM UTC Daily)                          │
│ AWS Lambda + EventBridge + Step Functions                          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ S3 LANDING ZONE                                                     │
│ s3://groundtruth-capstone/landing/*                                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ DATABRICKS BRONZE LAYER (Deduplication)                            │
│ commodity.bronze.* tables                                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ DATABRICKS SILVER LAYER (Transformations)                          │
│ commodity.silver.* tables                                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ DATABRICKS GOLD LAYER (ML-Ready)                                   │
│ commodity.gold.unified_data                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Source #1: Market Data (Coffee & Sugar Prices)

### Lambda Function
**Name**: `market-data-fetcher`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `groundtruth-market-data-daily`)
**Source**: Yahoo Finance API (yfinance)
**Code**: `research_agent/infrastructure/lambda/functions/market-data-fetcher/app.py`

### Data Flow
```
Lambda: market-data-fetcher (daily 2 AM UTC)
  ↓
S3: s3://groundtruth-capstone/landing/market_data/*.csv
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.market_data_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.market (DEDUP on date, commodity)
  ↓
Databricks SQL: create_gold_unified_data.sql
  commodity.gold.unified_data
    (columns: date, commodity, open, high, low, close, volume)
```

### Key Details
- **Grain**: (date, commodity) - trading days only
- **Deduplication**: Latest `ingest_ts` wins
- **Forward-fill**: Applied in gold layer (LAST_VALUE)
- **Commodities**: Coffee (KC=F), Sugar (SB=F)

---

## 🔄 Data Source #2: VIX (Volatility Index)

### Lambda Function
**Name**: `vix-data-fetcher`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `groundtruth-vix-data-daily`)
**Source**: Yahoo Finance API (yfinance)
**Code**: `research_agent/infrastructure/lambda/functions/vix-data-fetcher/app.py`

### Data Flow
```
Lambda: vix-data-fetcher (daily 2 AM UTC)
  ↓
S3: s3://groundtruth-capstone/landing/vix_data/*.csv
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.vix_data_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.vix (DEDUP on date)
  ↓
Databricks SQL: create_gold_unified_data.sql
  commodity.gold.unified_data (column: vix)
```

### Key Details
- **Grain**: (date) - trading days only
- **Deduplication**: Latest `ingest_ts` wins
- **Forward-fill**: Applied in gold layer (LAST_VALUE)

---

## 🔄 Data Source #3: FX Rates (Macro/Currency Data)

### Lambda Function
**Name**: `fx-calculator-fetcher`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `groundtruth-fx-data-daily`)
**Source**: Federal Reserve Economic Data (FRED)
**Code**: `research_agent/infrastructure/lambda/functions/fx-calculator-fetcher/app.py`

### Data Flow
```
Lambda: fx-calculator-fetcher (daily 2 AM UTC)
  ↓
S3: s3://groundtruth-capstone/landing/macro_data/*.csv
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.macro_data_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.macro (DEDUP on date)
  ↓
Databricks SQL: create_gold_unified_data.sql
  commodity.gold.unified_data
    (24 FX columns: vnd_usd, cop_usd, idr_usd, etb_usd, hnl_usd, ugx_usd,
     pen_usd, xaf_usd, gtq_usd, gnf_usd, nio_usd, crc_usd, tzs_usd, kes_usd,
     lak_usd, pkr_usd, php_usd, egp_usd, ars_usd, rub_usd, try_usd, uah_usd,
     irr_usd, byn_usd)
```

### Key Details
- **Grain**: (date) - weekdays only
- **Deduplication**: Row with most non-NULL columns wins
- **Forward-fill**: Applied in gold layer (LAST_VALUE)
- **Currencies**: 24 coffee/sugar-producing country currencies

---

## 🔄 Data Source #4: Weather Data (Growing Regions)

### Lambda Function
**Name**: `weather-data-fetcher`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `groundtruth-weather-data-daily`)
**Source**: Open-Meteo Archive API (no API key required)
**Code**: `research_agent/infrastructure/lambda/functions/weather-data-fetcher/app.py`

### Configuration
**Region Coordinates**: `s3://groundtruth-capstone/config/region_coordinates.json`
- Lambda loads coordinates from S3 (v2 - correct growing region coordinates)
- 67 regions across coffee/sugar producing areas
- **Updated Nov 2025**: Coordinates now use precise growing region centers (not state capitals)

### Data Flow
```
Lambda: weather-data-fetcher (daily 2 AM UTC)
  ↓ loads coordinates from
S3 Config: s3://groundtruth-capstone/config/region_coordinates.json
  ↓ writes weather data to
S3: s3://groundtruth-capstone/landing/weather_v2/*.csv
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.weather_data_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.weather (DEDUP on date, region, commodity)
  ↓
Databricks SQL: create_gold_unified_data.sql
  commodity.gold.unified_data
    (weather field: ARRAY<STRUCT<region, temp_max_c, temp_min_c, temp_mean_c,
                                   precipitation_mm, rain_mm, snowfall_cm,
                                   humidity_mean_pct, wind_speed_max_kmh>>)
```

### Key Details
- **Grain**: (date, region, commodity) - every day
- **Regions**: 67 coffee/sugar growing regions worldwide
- **Deduplication**: Latest `ingest_ts` wins
- **Forward-fill**: Applied per-region in gold layer (LAST_VALUE)
- **Gold Structure**: Array of structs (one per region), allowing models to aggregate flexibly

---

## 🔄 Data Source #5: CFTC (Trader Positioning Data)

### Lambda Function
**Name**: `cftc-data-fetcher`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `groundtruth-cftc-data-daily`)
**Source**: CFTC Disaggregated Futures Only Reports
**Code**: `research_agent/infrastructure/lambda/functions/cftc-data-fetcher/app.py`

### Data Flow
```
Lambda: cftc-data-fetcher (daily 2 AM UTC)
  ↓
S3: s3://groundtruth-capstone/landing/cftc_data/*.csv
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.cftc_data_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.cftc (DEDUP on date, market_name)
  ↓
[NOT CURRENTLY USED IN GOLD.UNIFIED_DATA]
```

### Key Details
- **Grain**: (date, market_name) - weekly (Tuesdays)
- **Status**: ⚠️ **Not currently used in gold.unified_data**
- **Deduplication**: Latest `ingest_ts` wins
- **Columns**: open_interest, noncomm_long, noncomm_short, comm_long, comm_short, pct_oi_noncomm_long, pct_oi_noncomm_short

---

## 🔄 Data Source #6: GDELT (News Sentiment)

### Pipeline Components
**Step Function**: `gdelt-daily-incremental-pipeline`
**Schedule**: `cron(0 2 * * ? *)` ✅ **ENABLED** (EventBridge: `gdelt-daily-discovery-schedule`)

**Related Step Functions** (orchestrate GDELT processing):
- `gdelt-bronze-silver-pipeline`
- `gdelt-daily-master-pipeline`
- `groundtruth-gdelt-backfill`
- `groundtruth-gdelt-bronze-processing`

### Data Flow
```
Step Function: gdelt-daily-incremental-pipeline (daily 2 AM UTC)
  ↓ (downloads GDELT master CSV, filters for coffee/sugar themes)
S3 Raw: s3://groundtruth-capstone/landing/gdelt/raw/*.zip
  ↓ (filtering Lambda/processing)
S3 Filtered: s3://groundtruth-capstone/landing/gdelt/filtered/*.jsonl
  ↓
Databricks SQL: 01_create_landing_tables.sql
  commodity.landing.gdelt_sentiment_inc
  ↓
Databricks SQL: 02_create_bronze_views.sql
  commodity.bronze.gdelt
  ↓ (theme grouping + aggregation - EXTERNAL PROCESSING)
S3 Processed: s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/
  ↓
Databricks SQL: gdelt_silver_simple.sql
  commodity.silver.gdelt_wide (partitioned by commodity)
  ↓ (optional: forward-fill)
Databricks SQL: create_gdelt_fillforward.sql
  commodity.silver.gdelt_wide_fillforward
  ↓
Databricks SQL: create_gold_unified_data.sql
  commodity.gold.unified_data
    (gdelt_themes field: ARRAY<STRUCT<theme_group, article_count,
                                       tone_avg, tone_positive, tone_negative,
                                       tone_polarity>>)
```

### Key Details
- **Grain**: (article_date, commodity)
- **Theme Groups**: SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER
- **Processing**: Multi-stage pipeline (raw → filtered → bronze → silver wide → gold)
- **Forward-fill**: Applied in gold layer (LAST_VALUE on gdelt_themes array)
- **Gold Structure**: Array of structs (one per theme group)

---

## 📊 Final Gold Table Structure

### Table: `commodity.gold.unified_data`

**Created by**: `research_agent/sql/create_gold_unified_data.sql`
**Grain**: (date, commodity) - every day from 2015-07-07 to present
**Row Count**: ~7,000 rows (~3,500 days × 2 commodities)

### Schema
```sql
CREATE TABLE commodity.gold.unified_data AS
SELECT
  date,                    -- DATE (2015-07-07 to present, complete daily)
  commodity,               -- STRING ('Coffee' or 'Sugar')
  is_trading_day,          -- INT (1 = trading day, 0 = weekend/holiday)

  -- Market Data (forward-filled from trading days)
  open,                    -- DOUBLE
  high,                    -- DOUBLE
  low,                     -- DOUBLE
  close,                   -- DOUBLE
  volume,                  -- BIGINT

  -- VIX (forward-filled)
  vix,                     -- DOUBLE

  -- FX Rates (forward-filled) - 24 columns
  vnd_usd, cop_usd, idr_usd, etb_usd, hnl_usd, ugx_usd, pen_usd, xaf_usd,
  gtq_usd, gnf_usd, nio_usd, crc_usd, tzs_usd, kes_usd, lak_usd, pkr_usd,
  php_usd, egp_usd, ars_usd, rub_usd, try_usd, uah_usd, irr_usd, byn_usd,

  -- Weather Data (ARRAY OF STRUCTS, forward-filled per region)
  weather_data ARRAY<STRUCT<
    region STRING,
    temp_max_c DOUBLE,
    temp_min_c DOUBLE,
    temp_mean_c DOUBLE,
    precipitation_mm DOUBLE,
    rain_mm DOUBLE,
    snowfall_cm DOUBLE,
    humidity_mean_pct DOUBLE,
    wind_speed_max_kmh DOUBLE
  >>,

  -- GDELT Sentiment (ARRAY OF STRUCTS, forward-filled)
  gdelt_themes ARRAY<STRUCT<
    theme_group STRING,        -- SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER
    article_count BIGINT,
    tone_avg DOUBLE,
    tone_positive DOUBLE,
    tone_negative DOUBLE,
    tone_polarity DOUBLE
  >>
```

---

## 🔧 Databricks Scripts Execution Order

### 1. Landing Layer (reads S3 → creates landing.* tables)
**Script**: `research_agent/infrastructure/databricks/01_create_landing_tables.sql`
**Schedule**: ⏸️ **Manual** (run after S3 data arrives)

Creates:
- `commodity.landing.market_data_inc`
- `commodity.landing.macro_data_inc`
- `commodity.landing.vix_data_inc`
- `commodity.landing.weather_data_inc`
- `commodity.landing.cftc_data_inc`
- `commodity.landing.gdelt_sentiment_inc`

---

### 2. Bronze Layer (deduplicates landing → bronze)
**Script**: `research_agent/infrastructure/databricks/02_create_bronze_views.sql`
**Schedule**: ⏸️ **Manual** (run after landing layer)

Creates:
- `commodity.bronze.market` (DEDUP on date, commodity)
- `commodity.bronze.macro` (DEDUP on date, picks row with most non-NULL FX)
- `commodity.bronze.vix` (DEDUP on date)
- `commodity.bronze.weather` (DEDUP on date, region, commodity)
- `commodity.bronze.cftc` (DEDUP on date, market_name)
- `commodity.bronze.gdelt` (no dedup, keeps all articles)

---

### 3. Silver Layer - GDELT Wide (theme aggregation)
**Script**: `research_agent/infrastructure/databricks/gdelt_silver_simple.sql`
**Schedule**: ⏸️ **Manual**
**Input**: S3 directly (`s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/`)
**Output**: `commodity.silver.gdelt_wide`

**Note**: This is an external table pointing to S3 parquet files generated by Step Functions

---

### 4. Silver Layer - GDELT Forward Fill (optional)
**Script**: `research_agent/infrastructure/databricks/create_gdelt_fillforward.sql`
**Schedule**: ⏸️ **Manual**
**Input**: `commodity.silver.gdelt_wide`
**Output**: `commodity.silver.gdelt_wide_fillforward`

**Purpose**: Creates continuous daily records (count columns = 0 for missing dates, tone columns forward-filled)

---

### 5. Gold Layer - Unified Data (ML-ready)
**Script**: `research_agent/sql/create_gold_unified_data.sql`
**Schedule**: ⏸️ **Manual** (user runs when needed)
**Runtime**: ~10 minutes
**Output**: `commodity.gold.unified_data`

**Dependencies**:
- `commodity.bronze.market`
- `commodity.bronze.vix`
- `commodity.bronze.macro`
- `commodity.bronze.weather` ⬅️ **Weather v2 coordinates**
- `commodity.silver.gdelt_wide` ⬅️ **NOT gdelt_wide_fillforward** (forward-fill happens in gold SQL)

---

## ⚠️ Unused/Obsolete Components

### Scripts
1. **`databricks/weather_forecast_setup.sql`**
   - Purpose: Historical weather forecast table setup
   - Status: ⚠️ **Appears obsolete** - not referenced in gold.unified_data
   - Action: Review for removal

2. **`create_gdelt_fillforward.sql`**
   - Purpose: Forward-fill GDELT data
   - Status: ⚠️ **Superseded** - gold SQL does forward-fill directly
   - Action: Candidate for archival (if not used elsewhere)

3. **CFTC Bronze Table**
   - Created but not used in gold.unified_data
   - Status: ⚠️ **Created but unused**
   - Action: Either integrate into gold or document as "available but not used"

### EventBridge Rules (DISABLED)
1. `gdelt-daily-pipeline-schedule` - ❌ **DISABLED**
2. `gdelt-daily-silver-transform` - ❌ **DISABLED**
3. `groundtruth-gdelt-daily-update` - ❌ **DISABLED**

**Action**: Clarify if these are truly obsolete or used by active Step Functions

---

## 📅 Scheduling Summary

### ✅ ACTIVE (Daily 2 AM UTC)
| EventBridge Rule | Lambda/Step Function | S3 Output |
|------------------|---------------------|-----------|
| `groundtruth-market-data-daily` | `market-data-fetcher` | `landing/market_data/` |
| `groundtruth-vix-data-daily` | `vix-data-fetcher` | `landing/vix_data/` |
| `groundtruth-fx-data-daily` | `fx-calculator-fetcher` | `landing/macro_data/` |
| `groundtruth-weather-data-daily` | `weather-data-fetcher` | `landing/weather_v2/` |
| `groundtruth-cftc-data-daily` | `cftc-data-fetcher` | `landing/cftc_data/` |
| `gdelt-daily-discovery-schedule` | `gdelt-daily-incremental-pipeline` | `landing/gdelt/filtered/` |

### ⏸️ MANUAL (No schedule)
- Databricks landing → bronze → silver → gold SQL scripts
- Must be run manually or via Databricks Jobs (not currently configured)

### ❌ DISABLED (Superseded or obsolete)
- `gdelt-daily-pipeline-schedule`
- `gdelt-daily-silver-transform`
- `groundtruth-gdelt-daily-update`

---

## 🎯 Recommendations

### 1. Databricks Job Orchestration
**Issue**: SQL scripts run manually, no automated landing → bronze → gold pipeline
**Recommendation**: Create Databricks Workflow to run scripts in sequence:
1. `01_create_landing_tables.sql` (after 2:30 AM, giving Lambdas time)
2. `02_create_bronze_views.sql`
3. `gdelt_silver_simple.sql` (REFRESH external table)
4. `create_gold_unified_data.sql`

### 2. CFTC Integration or Removal
**Issue**: CFTC data fetched but not used
**Recommendation**: Either:
- Add CFTC features to gold.unified_data, OR
- Document as "available for future use", OR
- Disable Lambda to save costs

### 3. Archive Obsolete Scripts
**Issue**: Old scripts create confusion
**Recommendation**: Move to `archive/`:
- `weather_forecast_setup.sql` (if confirmed obsolete)
- GDELT forward-fill script (if not used elsewhere)
- Disabled EventBridge rules (delete or document why disabled)

### 4. Documentation Updates
**Issue**: Weather v2 migration complete but docs may reference old names
**Recommendation**: Update `DATA_SOURCES.md` and `UNIFIED_DATA_ARCHITECTURE.md` to reflect:
- Weather table is now `bronze.weather` (not `weather_v2`)
- S3 path is `landing/weather_v2/` (but table name dropped v2)
- Coordinates are v2 (growing regions, not state capitals)

---

## 📝 Related Documentation

- [UNIFIED_DATA_ARCHITECTURE.md](../UNIFIED_DATA_ARCHITECTURE.md) - Detailed schema and design
- [DATA_SOURCES.md](../DATA_SOURCES.md) - Data source reference
- [WEATHER_V2_MIGRATION_PLAN.md](./WEATHER_V2_MIGRATION_PLAN.md) - Weather coordinate migration
- [RUN_WEATHER_MIGRATION.md](./RUN_WEATHER_MIGRATION.md) - Weather migration execution

---

**Document Owner**: Research Agent
**Last Updated**: 2025-12-05
**Status**: Complete dependency analysis
