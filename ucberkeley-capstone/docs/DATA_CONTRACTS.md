# Data Contracts

**Critical**: These schemas define interfaces between agents. Changes require team alignment.

---

## Input Tables

### commodity.gold.unified_data (PRODUCTION - Forward-Filled)

**Owner**: Research Agent
**Grain**: One row per (date, commodity)
**Rows**: ~7k (2 commodities × ~3,500 days)
**Created**: Dec 2024
**Status**: ✅ Production - Stable, all features forward-filled

**Purpose**: Production table with all features forward-filled for stable, proven ML pipelines.

**Use when**:
- ✅ Running existing production models
- ✅ Want proven, stable data
- ✅ Don't need imputation flexibility
- ✅ Minimizing risk

---

### commodity.gold.unified_data_raw (EXPERIMENTAL - NULLs Preserved)

**Owner**: Research Agent
**Grain**: One row per (date, commodity)
**Rows**: ~7k (2 commodities × ~3,500 days)
**Created**: Dec 2024
**Status**: ⚠️ Experimental - Requires `ImputationTransformer`

**Purpose**: Experimental table with NULLs preserved for imputation flexibility and experimentation.

**Use when**:
- ✅ Building new models
- ✅ Want control over imputation strategy
- ✅ Model handles NULLs natively (e.g., XGBoost)
- ✅ Experimenting with different imputation approaches

#### Schema

| Column | Type | Description | Nulls |
|--------|------|-------------|-------|
| **Primary Keys** ||||
| `date` | DATE | Calendar date (continuous, no gaps) | Never |
| `commodity` | STRING | 'Coffee' or 'Sugar' | Never |
| **Flags** ||||
| `is_trading_day` | INT | 1 = trading day, 0 = weekend/holiday | Never |
| **Market Data** ||||
| `open` | DOUBLE | Futures open price (USD) | Yes (~30%) |
| `high` | DOUBLE | Daily high | Yes (~30%) |
| `low` | DOUBLE | Daily low | Yes (~30%) |
| `close` | DOUBLE | Futures close price (USD, **target variable**, forward-filled) | Never |
| `volume` | DOUBLE | Trading volume | Yes (~30%) |
| **Market Volatility** ||||
| `vix` | DOUBLE | Volatility index | Yes (~30%) |
| **Exchange Rates** (24 columns) ||||
| `vnd_usd` | DOUBLE | Vietnamese Dong / USD | Yes (~30%) |
| `cop_usd` | DOUBLE | Colombian Peso / USD (critical for trader use case) | Yes (~30%) |
| `idr_usd` | DOUBLE | Indonesian Rupiah / USD | Yes (~30%) |
| ... | DOUBLE | 21 more exchange rates | Yes (~30%) |
| **Weather Data** (Array of Structs) ||||
| `weather_data` | ARRAY&lt;STRUCT&gt; | Multi-regional weather data (struct fields may be NULL) | Rare |
| **GDELT Sentiment** (Array of Structs) ||||
| `gdelt_themes` | ARRAY&lt;STRUCT&gt; | News sentiment by theme group | Yes (~73%) |

#### Array Structures

**weather_data**: Array of structs, one per region
```sql
ARRAY<STRUCT<
  region STRING,              -- e.g., 'Sul_de_Minas', 'Bugisu_Uganda'
  temp_max_c DOUBLE,
  temp_min_c DOUBLE,
  temp_mean_c DOUBLE,
  precipitation_mm DOUBLE,
  rain_mm DOUBLE,
  snowfall_cm DOUBLE,
  humidity_mean_pct DOUBLE,
  wind_speed_max_kmh DOUBLE
>>
```

**gdelt_themes**: Array of structs, one per theme group (7 groups)
```sql
ARRAY<STRUCT<
  theme_group STRING,         -- SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER
  article_count INT,
  tone_avg DOUBLE,
  tone_positive DOUBLE,
  tone_negative DOUBLE,
  tone_polarity DOUBLE
>>
```

#### Comparison: Production vs. Experimental Tables

| Aspect | `unified_data` (Production) | `unified_data_raw` (Experimental) |
|--------|----------------------------|-------------------------------------------|
| **Imputation** | All features forward-filled | Only `close` forward-filled |
| **NULLs in VIX** | Never (forward-filled) | ~30% (weekends/holidays) |
| **NULLs in FX (24 cols)** | Never (forward-filled) | ~30% (weekends/holidays) |
| **NULLs in OHLV** | Never (forward-filled) | ~30% (weekends/holidays) |
| **NULLs in weather** | Never (forward-filled) | Rare (API gaps) |
| **NULLs in GDELT** | Never (forward-filled) | ~73% (days without articles) |
| **Missingness flags** | ❌ No | ✅ Yes (3 composite flags) |
| **Use case** | Production, stable pipelines | Experimentation, new models |
| **Requires ImputationTransformer** | ❌ No | ✅ Yes |

**Additional columns in `unified_data_raw`**:
- `has_market_data INT`: 1 if VIX + any FX + OHLV present (trading day), 0 otherwise
- `has_weather_data INT`: 1 if weather_data array non-empty, 0 otherwise
- `has_gdelt_data INT`: 1 if gdelt_themes array non-empty, 0 otherwise

---

#### Data Quality & Imputation Philosophy (unified_data_raw ONLY)

**Core Principle**: Imputation is a **modeling decision**, not a data layer decision.

- ✅ **Continuous dates**: No gaps from 2015-07-07 to present
- ✅ **Unique grain**: (date, commodity) is unique
- ✅ **90% row reduction**: vs silver.unified_data (~7k vs ~75k rows)
- ✅ **Validated**: See `research_agent/tests/validation/validate_gold_tables.py`

**Imputation Strategy (Minimal Assumptions)**:
- ✅ **`close` price**: Forward-filled (target variable = market state on weekends)
- ⚠️  **All other features**: NULL preserved where missing (VIX, FX, OHLV, weather, GDELT)
  - Rationale: Different models need different imputation strategies
  - Tree models (XGBoost): Can handle NULLs natively
  - Linear models (SARIMAX): May want forward-fill, mean, or interpolation
  - Forecast agent chooses imputation per model using `ImputationTransformer`

**NULL Expectations by Feature Type**:
- `open`, `high`, `low`, `volume`: NULL on weekends/holidays (~30% of rows)
- `vix`: NULL on weekends/holidays (~30% of rows)
- `vnd_usd`, `cop_usd`, ... (24 FX rates): NULL on weekends/holidays (~30% of rows)
- `weather_data`: May have NULL values in struct fields if weather API had gaps
- `gdelt_themes`: NULL for days without articles (~73% of rows)
  - GDELT coverage: 2021-01-01 onwards (~2,051 dates with articles)
  - Pre-2021 dates always have `gdelt_themes = NULL`

#### Usage Pattern

```python
# Load gold.unified_data for ML training
df = spark.table("commodity.gold.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1")

# Explode weather array to access regional data
from pyspark.sql.functions import explode

weather_df = df.select(
    "date",
    "commodity",
    "close",
    explode("weather_data").alias("weather")
).select(
    "date",
    "commodity",
    "close",
    "weather.region",
    "weather.temp_mean_c",
    "weather.precipitation_mm"
)

# Or aggregate weather features (mean temperature across all regions)
from pyspark.sql.functions import expr

agg_df = df.select(
    "date",
    "commodity",
    "close",
    expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.temp_mean_c, acc -> acc / size(weather_data))").alias("avg_temp")
)
```

#### Handling NULLs (Imputation)

Since gold.unified_data preserves NULLs for all features except `close`, forecast_agent must handle imputation:

```python
# Option 1: Tree models (XGBoost) - use NULLs natively
df = spark.table("commodity.gold.unified_data")
# XGBoost handles NULLs automatically, no imputation needed

# Option 2: Use ImputationTransformer (forecast_agent pattern)
from forecast_agent.ml_lib.transformers import ImputationTransformer

df = spark.table("commodity.gold.unified_data_raw")  # Use raw table with NULLs
imputer = ImputationTransformer(strategy='forward_fill')  # or 'mean', 'median', 'interpolate'
df_imputed = imputer.transform(df)

# Option 3: Custom per-feature imputation
imputer = ImputationTransformer(strategies={
    'vix': 'forward_fill',      # VIX changes slowly
    'cop_usd': 'mean',           # FX: use mean
    'temp_mean_c': 'interpolate' # Weather: interpolate
})
df_imputed = imputer.transform(df)
```

**When to use gold.unified_data**:
- ✅ Training ML models with flexible regional aggregation
- ✅ Models that need to choose how to aggregate regions (mean, weighted, separate features)
- ✅ When you want fewer rows for faster processing (~90% reduction)
- ✅ When you need GDELT sentiment data
- ✅ When you want control over imputation strategy per model

---

### commodity.silver.unified_data (Legacy)

**Owner**: Research Agent (Francisco)
**Grain**: One row per (date, commodity, region)
**Rows**: ~75k (as of Oct 2024)
**Status**: ⚠️ Maintained for compatibility, prefer gold.unified_data for new models

### Schema

| Column | Type | Description | Nulls |
|--------|------|-------------|-------|
| `date` | DATE | Calendar date | No |
| `is_trading_day` | INT | 1 = trading day, 0 = weekend/holiday | No |
| `commodity` | STRING | 'Coffee' or 'Sugar' | No |
| `close` | FLOAT | Futures close price (USD) | No |
| `high` | FLOAT | Daily high | No |
| `low` | FLOAT | Daily low | No |
| `open` | FLOAT | Daily open | No |
| `volume` | FLOAT | Trading volume | Some |
| `vix` | FLOAT | Volatility index | Some |
| `region` | STRING | Producing region (e.g., 'Bugisu_Uganda') | No |
| `temp_c` | FLOAT | Temperature (Celsius) | Some |
| `humidity_pct` | FLOAT | Humidity percentage | Some |
| `precipitation_mm` | FLOAT | Precipitation (mm) | Some |
| `*_usd` | FLOAT | Exchange rates (vnd_usd, cop_usd, etc.) | Some |

**Key Columns for Forecasting**:
- `close`: Primary target variable
- `is_trading_day`: Filter for model training (only use trading days)
- `region`: Enables hierarchical/regional models
- Weather columns: Important covariates
- `cop_usd`: Critical for Colombian trader use case

**Data Quality**:
- Forward-filled to handle non-trading days
- No duplicates on (date, commodity, region)
- ~65 regions covered

**Usage Pattern**:
```python
# Load only trading days for Coffee
df = spark.table("commodity.silver.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1")
```

## Output 1: commodity.forecast.point_forecasts

**Owner**: Forecast Agent (Connor - YOU)
**Grain**: One row per (forecast_date, model_version, day_ahead)

### Schema

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `forecast_date` | DATE | Target date being forecasted | Yes |
| `data_cutoff_date` | DATE | Last training date (< forecast_date) | Yes |
| `generation_timestamp` | TIMESTAMP | When forecast was generated | Yes |
| `day_ahead` | INT | Horizon (1-14 days) | Yes |
| `forecast_mean` | FLOAT | Point forecast (cents/lb) | Yes |
| `forecast_std` | FLOAT | Standard error | Yes |
| `lower_95` | FLOAT | 95% CI lower bound | Yes |
| `upper_95` | FLOAT | 95% CI upper bound | Yes |
| `model_version` | STRING | Model identifier (e.g., 'sarimax_v0') | Yes |
| `commodity` | STRING | 'Coffee' or 'Sugar' | Yes |
| `model_success` | BOOLEAN | Did model converge? | Yes |
| `actual_close` | FLOAT | Realized close price (NULL for future dates) | No |
| `has_data_leakage` | BOOLEAN | TRUE if forecast_date <= data_cutoff_date | Yes |

**Partitioning**: `commodity`, `forecast_date`

**Critical Invariants**:
- `data_cutoff_date < forecast_date` (prevents data leakage)
- `has_data_leakage = TRUE if forecast_date <= data_cutoff_date` (data quality flag)
- `has_data_leakage` should always be FALSE in production (filter out bad data)
- `actual_close` is NULL for future dates, populated during backfill
- Daily forecasts create overlapping predictions
- Each target date has up to 14 forecasts (from different cutoff dates)

**Usage by Trading Agent**:
```sql
-- Get 7-day ahead forecasts for backtesting (with actuals)
SELECT forecast_date, forecast_mean, lower_95, upper_95, actual_close
FROM commodity.forecast.point_forecasts
WHERE day_ahead = 7
  AND has_data_leakage = FALSE  -- Filter out any bad data
  AND model_version = 'production_v1'
  AND forecast_date BETWEEN '2023-01-01' AND '2023-12-31'
```

## Output 2: commodity.forecast.distributions

**Owner**: Forecast Agent (Connor - YOU)
**Grain**: One row per (forecast_start_date, model_version, path_id)

### Schema

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `path_id` | INT | Sample path ID (0-2000, where 0=actuals) | Yes |
| `forecast_start_date` | DATE | First day of forecast | Yes |
| `data_cutoff_date` | DATE | Last training date | Yes |
| `generation_timestamp` | TIMESTAMP | When generated | Yes |
| `model_version` | STRING | Model identifier | Yes |
| `commodity` | STRING | 'Coffee' or 'Sugar' | Yes |
| `day_1` to `day_14` | FLOAT | Forecasted prices | Yes |
| `is_actuals` | BOOLEAN | TRUE for path_id=0 (actuals), FALSE otherwise | Yes |
| `has_data_leakage` | BOOLEAN | TRUE if forecast_start_date <= data_cutoff_date | Yes |

**Partitioning**: `model_version`, `commodity`

**Purpose**: Monte Carlo paths for risk analysis (VaR, CVaR)

**Key Features**:
- **path_id=0**: Actuals row (when available) with is_actuals=TRUE
- **path_id=1-2000**: Forecast paths with is_actuals=FALSE
- **has_data_leakage = TRUE if forecast_start_date <= data_cutoff_date** (data quality flag)
- **has_data_leakage** should always be FALSE in production (filter out bad data)
- Total: 2,001 rows per forecast (2,000 paths + 1 actuals)

**Typical Usage**:
```sql
-- Calculate 95% VaR for day 7 (exclude actuals path)
SELECT forecast_start_date,
       PERCENTILE(day_7, 0.05) as var_95,
       AVG(day_7) as mean_price
FROM commodity.forecast.distributions
WHERE forecast_start_date = '2024-01-15'
  AND is_actuals = FALSE  -- Exclude path_id=0
  AND has_data_leakage = FALSE
  AND model_version = 'production_v1'
GROUP BY forecast_start_date
```

```sql
-- Get actuals from distributions (path_id=0)
SELECT forecast_start_date,
       day_1, day_2, day_3, day_4, day_5, day_6, day_7
FROM commodity.forecast.distributions
WHERE path_id = 0  -- Actuals row
  AND is_actuals = TRUE
ORDER BY forecast_start_date DESC
```

## Output 3: commodity.forecast.forecast_metadata

**Owner**: Forecast Agent (Connor - YOU)
**Grain**: One row per (forecast_date, commodity)

### Schema

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `forecast_date` | DATE | Target date | Yes |
| `commodity` | STRING | 'Coffee' or 'Sugar' | Yes |
| `actual_close` | FLOAT | Realized close price | Yes |

**Partitioning**: `commodity`

**Purpose**: Store realized prices for backtesting and evaluation

**What is "actual"?**
- Currently: **Close price** from futures market (industry standard for commodity traders)
- Future consideration: VWAP or estimated VWAP for better execution price representation

**Why separate table?**
- Prevents accidental inclusion in forecast statistics (no path_id confusion)
- Simple, clean joins
- Easy to understand and maintain

**Typical Usage - Compare Forecast vs Actual**:
```sql
-- Calculate forecast errors
SELECT
  pf.forecast_date,
  pf.forecast_mean,
  a.actual_close,
  pf.forecast_mean - a.actual_close as error,
  ABS(pf.forecast_mean - a.actual_close) as abs_error
FROM commodity.forecast.point_forecasts pf
JOIN commodity.forecast.forecast_metadata a
  ON pf.forecast_date = a.forecast_date
  AND pf.commodity = a.commodity
WHERE pf.day_ahead = 7
  AND pf.data_cutoff_date < pf.forecast_date
```

**For Colombian Trader Use Case - Include COP/USD**:
```sql
-- Forecast value in Colombian Pesos
SELECT
  pf.forecast_date,
  pf.forecast_mean * u.cop_usd as forecast_value_cop,
  a.actual_close * u.cop_usd as actual_value_cop,
  (pf.forecast_mean - a.actual_close) * u.cop_usd as error_cop
FROM commodity.forecast.point_forecasts pf
JOIN commodity.forecast.forecast_metadata a
  ON pf.forecast_date = a.forecast_date AND pf.commodity = a.commodity
JOIN commodity.silver.unified_data u
  ON a.forecast_date = u.date AND a.commodity = u.commodity
WHERE u.is_trading_day = 1
  AND pf.commodity = 'Coffee'
  AND pf.day_ahead = 7
LIMIT 1  -- One row per date (multiple regions in unified_data)
```

**Implementation Notes**:
- Connor populates this table during backtesting
- Lookup actual close prices from `unified_data` WHERE `is_trading_day = 1`
- Only write actuals for dates where forecasts were generated
