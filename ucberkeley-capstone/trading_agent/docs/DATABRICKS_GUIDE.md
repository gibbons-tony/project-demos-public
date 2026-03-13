# Databricks Guide

**Purpose:** Comprehensive guide for accessing Databricks, querying data, managing outputs, and working with notebooks in the trading_agent project.

**Last Updated:** 2025-11-24

---

## Quick Start

### Connection & Authentication

### Workspace Access

**URL:** https://dbc-5e4780f4-fcec.cloud.databricks.com

**Primary User:** `ground.truth.datascience@gmail.com`

**Notebooks Location:** `/Workspace/Users/ground.truth.datascience@gmail.com/`

### CLI Configuration

**Set credentials before running databricks CLI commands:**

```bash
export DATABRICKS_HOST=https://dbc-5e4780f4-fcec.cloud.databricks.com
export DATABRICKS_TOKEN=***REMOVED***
```

**Or add to `~/.databrickscfg`:**
```ini
[DEFAULT]
host = https://dbc-5e4780f4-fcec.cloud.databricks.com
token = ***REMOVED***
```

### Python REST API

```python
import requests

def query_databricks(sql, warehouse_id="d88ad009595327fd"):
    response = requests.post(
        "https://dbc-5e4780f4-fcec.cloud.databricks.com/api/2.0/sql/statements/",
        headers={
            "Authorization": "Bearer YOUR_TOKEN",
            "Content-Type": "application/json"
        },
        json={
            "warehouse_id": warehouse_id,
            "statement": sql,
            "wait_timeout": "50s"
        }
    )
    result = response.json()
    return result.get('result', {}).get('data_array', [])
```

---

## Data Access Patterns

### Overview

This section covers how to query forecast distributions, load actuals, compare models, and select the best model for production use.

### Current Data Availability

**commodity.forecast.distributions**: 622,300 rows
- **42 forecast dates**: July 2018 - November 2025
- **5 models**: SARIMAX+Weather, Prophet, XGBoost+Weather, ARIMA, Random Walk
- **300 actuals rows** (path_id=0) for backtesting
- **2,000 Monte Carlo paths** per model for VaR/CVaR analysis

**commodity.forecast.point_forecasts**: 0 rows
_(Coming soon - P2 priority)_

### Recommended Production Model

**Primary Recommendation**: `arima_111_v1` (Best Accuracy)
**Backtest Performance** (42 forecast windows):
- 7-day MAE: $3.49 (3.23% MAPE)
- RMSE: $4.56
- 95% Coverage: 85.0%
- Bias: -$0.28 (slight underforecasting)

**Alternative**: `sarimax_auto_weather_v1` (Weather-Enhanced)
**Backtest Performance**:
- 7-day MAE: $3.55 (3.27% MAPE) - only $0.06 worse than ARIMA
- RMSE: $4.58
- 95% Coverage: 81.7%
- Bias: -$0.63
- **Advantage**: Incorporates weather variables (temp, humidity, precipitation)

**Recommendation**: Use `arima_111_v1` for maximum accuracy, or `sarimax_auto_weather_v1` if you want weather-conditional forecasts.

**Other Models Available**:
- `xgboost_weather_v1` - MAE $3.77, captures non-linear interactions
- `random_walk_v1` - MAE $4.38, best calibrated intervals (88.3% coverage)
- `prophet_v1` - MAE $7.36, not recommended (poor accuracy and calibration)

### Querying Forecast Distributions

#### Get Latest Forecast (Most Recent Date)

```sql
-- Get 2,000 Monte Carlo paths for latest forecast
SELECT
  forecast_start_date,
  data_cutoff_date,
  generation_timestamp,
  path_id,
  day_1, day_2, day_3, day_4, day_5, day_6, day_7,
  day_8, day_9, day_10, day_11, day_12, day_13, day_14
FROM commodity.forecast.distributions
WHERE model_version = 'sarimax_auto_weather_v1'
  AND commodity = 'Coffee'
  AND is_actuals = FALSE  -- Exclude path_id=0 (actuals row)
  AND has_data_leakage = FALSE  -- Data quality check
  AND forecast_start_date = (
    SELECT MAX(forecast_start_date)
    FROM commodity.forecast.distributions
    WHERE model_version = 'sarimax_auto_weather_v1'
  )
ORDER BY path_id
```

**Expected Result**: 2,000 rows (one per Monte Carlo path)

#### Calculate VaR and CVaR (Risk Metrics)

```sql
-- Calculate Value at Risk for 7-day ahead forecast
SELECT
  forecast_start_date,
  data_cutoff_date,

  -- Summary Statistics
  AVG(day_7) as mean_price,
  STDDEV(day_7) as price_volatility,

  -- Value at Risk (VaR)
  PERCENTILE(day_7, 0.05) as var_95_lower,  -- 95% VaR (downside)
  PERCENTILE(day_7, 0.95) as var_95_upper,  -- 95% VaR (upside)

  -- Conditional Value at Risk (CVaR / Expected Shortfall)
  PERCENTILE(day_7, 0.01) as cvar_99_lower,  -- 99% CVaR (worst 1%)
  PERCENTILE(day_7, 0.99) as cvar_99_upper,  -- 99% CVaR (best 1%)

  -- Min/Max scenarios
  MIN(day_7) as worst_case,
  MAX(day_7) as best_case

FROM commodity.forecast.distributions
WHERE model_version = 'sarimax_auto_weather_v1'
  AND commodity = 'Coffee'
  AND is_actuals = FALSE  -- Exclude actuals
  AND has_data_leakage = FALSE
GROUP BY forecast_start_date, data_cutoff_date
ORDER BY forecast_start_date DESC
LIMIT 1
```

**Use Cases**:
- **VaR 95%**: "There's a 5% chance the price will be below $X"
- **CVaR 99%**: "If we're in the worst 1% of scenarios, expected price is $Y"
- **Position Sizing**: Use VaR to determine maximum risk exposure

### Loading Actuals for Backtesting

```sql
-- Get realized prices (path_id=0) for forecast evaluation
SELECT
  forecast_start_date,
  data_cutoff_date,
  day_1, day_2, day_3, day_4, day_5, day_6, day_7,
  day_8, day_9, day_10, day_11, day_12, day_13, day_14
FROM commodity.forecast.distributions
WHERE path_id = 0  -- Actuals row
  AND is_actuals = TRUE
  AND commodity = 'Coffee'
ORDER BY forecast_start_date DESC
```

**Expected Result**: 60 rows (42 forecast dates × 5 models, but some models failed to converge for some windows)

### Multi-Model Queries

#### Backtest Model Performance

```sql
-- Compare forecast vs actuals across all historical windows
WITH forecasts AS (
  SELECT
    forecast_start_date,
    AVG(day_7) as forecast_mean_day7,
    PERCENTILE(day_7, 0.05) as forecast_lower_95,
    PERCENTILE(day_7, 0.95) as forecast_upper_95
  FROM commodity.forecast.distributions
  WHERE model_version = 'sarimax_auto_weather_v1'
    AND commodity = 'Coffee'
    AND is_actuals = FALSE
    AND has_data_leakage = FALSE
  GROUP BY forecast_start_date
),
actuals AS (
  SELECT
    forecast_start_date,
    day_7 as actual_day7
  FROM commodity.forecast.distributions
  WHERE path_id = 0
    AND is_actuals = TRUE
    AND commodity = 'Coffee'
)
SELECT
  f.forecast_start_date,
  f.forecast_mean_day7,
  f.forecast_lower_95,
  f.forecast_upper_95,
  a.actual_day7,

  -- Error Metrics
  f.forecast_mean_day7 - a.actual_day7 as error,
  ABS(f.forecast_mean_day7 - a.actual_day7) as abs_error,
  ABS(f.forecast_mean_day7 - a.actual_day7) / a.actual_day7 * 100 as mape,

  -- Coverage (Did actual fall within 95% interval?)
  CASE
    WHEN a.actual_day7 BETWEEN f.forecast_lower_95 AND f.forecast_upper_95 THEN 1
    ELSE 0
  END as within_95_interval

FROM forecasts f
JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
ORDER BY f.forecast_start_date DESC
```

**Metrics**:
- **MAE**: Mean Absolute Error
- **MAPE**: Mean Absolute Percentage Error
- **Coverage**: % of actuals that fell within 95% prediction interval (should be ~95%)

#### Compare Models Side-by-Side

```sql
-- Compare all 5 models on the same forecast date
WITH model_stats AS (
  SELECT
    model_version,
    forecast_start_date,
    AVG(day_14) as mean_forecast_14d,
    STDDEV(day_14) as volatility_14d,
    PERCENTILE(day_14, 0.05) as var_95_14d
  FROM commodity.forecast.distributions
  WHERE commodity = 'Coffee'
    AND is_actuals = FALSE
    AND has_data_leakage = FALSE
    AND forecast_start_date = '2024-10-01'  -- Example date
  GROUP BY model_version, forecast_start_date
),
actual_value AS (
  SELECT day_14 as actual_14d
  FROM commodity.forecast.distributions
  WHERE path_id = 0
    AND forecast_start_date = '2024-10-01'
  LIMIT 1
)
SELECT
  ms.model_version,
  ms.mean_forecast_14d,
  ms.volatility_14d,
  ms.var_95_14d,
  av.actual_14d,
  ABS(ms.mean_forecast_14d - av.actual_14d) as abs_error
FROM model_stats ms
CROSS JOIN actual_value av
ORDER BY abs_error ASC
```

### Best Model Selection

#### Model Selection Decision Tree

```
START
  ├─ Need best forecast accuracy? (Backtest MAE: $3.49)
  │  └─> Use: arima_111_v1 (RECOMMENDED)
  │
  ├─ Need weather-conditional forecasts? (MAE: $3.55, only $0.06 worse)
  │  └─> Use: sarimax_auto_weather_v1
  │
  ├─ Need best-calibrated prediction intervals? (88% coverage)
  │  └─> Use: random_walk_v1
  │
  ├─ Need to capture non-linear weather effects? (MAE: $3.77)
  │  └─> Use: xgboost_weather_v1
  │
  └─ Need ensemble for robustness?
     └─> Average: arima_111_v1 + sarimax_auto_weather_v1 + xgboost_weather_v1
```

### Python Code Examples

#### Connect to Databricks

```python
from databricks import sql
import os

# Initialize connection
conn = sql.connect(
    server_hostname=os.environ['DATABRICKS_HOST'],
    http_path=os.environ['DATABRICKS_HTTP_PATH'],
    access_token=os.environ['DATABRICKS_TOKEN']
)

cursor = conn.cursor()
```

#### Fetch Latest Forecast Distributions

```python
query = """
    SELECT path_id, day_1, day_2, day_3, day_4, day_5, day_6, day_7,
           day_8, day_9, day_10, day_11, day_12, day_13, day_14
    FROM commodity.forecast.distributions
    WHERE model_version = 'sarimax_auto_weather_v1'
      AND commodity = 'Coffee'
      AND is_actuals = FALSE
      AND forecast_start_date = (
        SELECT MAX(forecast_start_date)
        FROM commodity.forecast.distributions
        WHERE model_version = 'sarimax_auto_weather_v1'
      )
    ORDER BY path_id
"""

cursor.execute(query)
rows = cursor.fetchall()

# Convert to numpy array for analysis
import numpy as np
distributions = np.array([[row[i] for i in range(1, 15)] for row in rows])
# Shape: (2000 paths, 14 days)

print(f"Loaded {len(distributions)} Monte Carlo paths")
print(f"7-day forecast: Mean=${distributions[:, 6].mean():.2f}, "
      f"Std=${distributions[:, 6].std():.2f}")
```

#### Calculate VaR/CVaR in Python

```python
import numpy as np

# Fetch distributions (from query above)
day_7_prices = distributions[:, 6]  # Day 7 column

# Value at Risk (VaR)
var_95 = np.percentile(day_7_prices, 5)  # 5th percentile (downside risk)
var_99 = np.percentile(day_7_prices, 1)  # 1st percentile (extreme downside)

# Conditional Value at Risk (CVaR / Expected Shortfall)
cvar_99 = day_7_prices[day_7_prices <= var_99].mean()

print(f"VaR 95% (downside): ${var_95:.2f}")
print(f"VaR 99% (extreme): ${var_99:.2f}")
print(f"CVaR 99% (expected loss if extreme): ${cvar_99:.2f}")

# Use for position sizing
max_portfolio_value = 100000  # $100k portfolio
var_loss = max_portfolio_value * (1 - var_95 / day_7_prices.mean())
print(f"Potential 95% VaR loss: ${var_loss:.2f}")
```

### Data Quality Checks

**Always filter on these flags**:

```sql
WHERE has_data_leakage = FALSE  -- Ensures data_cutoff_date < forecast_start_date
  AND is_actuals = FALSE        -- Excludes path_id=0 unless you want actuals
  AND commodity = 'Coffee'      -- Currently only Coffee available
```

**Data Quality Issues to Watch**:
- Rows with `has_data_leakage = TRUE` (should be 0, but filter defensively)
- `path_id` should range from 0 to 2,000 (0 = actuals, 1-2000 = forecast paths)
- All `day_*` columns should be > 0 (no negative prices)

### Partitioning Strategy

**Current Partitioning**:
```
Partitioned by: (model_version, commodity)
```

**Query Optimization**:
```sql
-- ✅ GOOD: Uses partition columns
WHERE model_version = 'sarimax_auto_weather_v1'
  AND commodity = 'Coffee'

-- ❌ BAD: Full table scan (no partition filter)
WHERE forecast_start_date > '2024-01-01'
```

**Recommendation**: Always include `model_version` and `commodity` in WHERE clause.

---

## Data Catalog

### Quick Reference Tables

#### Key Stats at a Glance

| Metric | Value |
|--------|-------|
| **Total Data Volume** | ~23.8 million rows |
| **Commodities** | Coffee, Sugar |
| **Forecast Models** | 27 (17 real + 10 synthetic) |
| **Date Range** | 2018-01-01 to 2025-11-22 |
| **Currencies Supported** | 15+ |

#### Essential Tables for Daily Recommendations

```python
# 1. Current Market Price
commodity.bronze.market_data
→ Latest close price, OHLCV data (~5,000 rows)

# 2. Forecast Predictions
commodity.forecast.distributions
→ 2000 Monte Carlo paths × 14 days (~622,300 rows)
→ Use: Calculate VaR, percentiles, expected values

# 3. Model Performance
commodity.forecast.forecast_metadata
→ MAE, RMSE, CRPS metrics (~500 rows)
→ Best model: arima_111_v1 ($3.49 MAE)

# 4. Exchange Rates
commodity.bronze.fx_rates
→ 15+ currencies (~150,000 rows)
→ Use: Multi-currency pricing
```

#### Critical Filters (ALWAYS Use)

```sql
WHERE is_actuals = FALSE         -- Exclude actuals unless needed
  AND has_data_leakage = FALSE   -- Data quality check
  AND model_success = TRUE       -- Only converged models
  AND commodity IN ('Coffee', 'Sugar')
  AND model_version = '...'      -- Required for partition pruning
```

### Table Organization

#### Data Organization Overview

```
commodity/                          # Unity Catalog
├── bronze/                         # Raw ingestion layer
│   ├── market_data                # Historical OHLCV prices (~5K rows)
│   ├── fx_rates                   # Exchange rates (15+ currencies, ~150K rows)
│   └── gdelt_bronze               # Raw GDELT data (~23M rows)
├── silver/                         # Cleaned/transformed layer
│   ├── unified_data               # Integrated market + weather + FX (~75K rows)
│   └── gdelt_wide                 # GDELT sentiment aggregated (~3.5K rows)
└── forecast/                       # Forecast agent outputs
    ├── distributions              # Monte Carlo paths (~622K rows)
    ├── forecast_metadata          # Model performance metrics (~500 rows)
    └── point_forecasts            # [Deprecated - 0 rows]
```

#### Key Tables Cheat Sheet

| Table | Purpose | Rows | Use For | Update Freq |
|-------|---------|------|---------|------------|
| `commodity.bronze.market_data` | Historical prices | ~5K | Current price, trends | Daily |
| `commodity.forecast.distributions` | Predictions | ~622K | VaR, percentiles, forecasts | Daily |
| `commodity.forecast.forecast_metadata` | Model accuracy | ~500 | Best model selection | Daily |
| `commodity.bronze.fx_rates` | Exchange rates | ~150K | Multi-currency pricing | Daily |
| `commodity.silver.unified_data` | Integrated data | ~75K | Model features | Daily |
| `commodity.silver.gdelt_wide` | Sentiment | ~3.5K | News sentiment (INCOMPLETE) | Daily |
| `commodity.bronze.gdelt_bronze` | Raw sentiment | ~23M | Raw article data | Daily |

#### Commodity Coverage

| Commodity | Market Data | Forecasts | GDELT | Models |
|-----------|-------------|-----------|-------|--------|
| Coffee | ✅ | ✅ | ✅ | 16 |
| Sugar | ✅ | ✅ | ✅ | 11 |

#### Date Ranges

| Data Source | Earliest | Latest | Coverage | Update Freq |
|-------------|----------|--------|----------|------------|
| Market Data | 2018-01-01 | 2025-11-22 | ~2,500 days | Daily |
| Forecasts | 2018-07-01 | 2025-11-22 | 42 windows | Daily |
| GDELT Bronze | 2021-01-01 | 2025-11-22 | 1,767 days | Daily |
| GDELT Silver | 2021-01-01 | 2021-01-02 | 2 days (0.1%) | Daily (processing) |
| FX Rates | 2020-01-01 | 2025-11-22 | ~2,000 days | Daily |

### Complete Table Schemas

#### commodity.bronze.market_data

**Purpose:** Historical commodity futures prices (OHLCV format)
**Grain:** One row per (date, commodity)
**Estimated Rows:** ~5,000+

| Column | Type | Description | Nulls |
|--------|------|-------------|-------|
| `date` | DATE | Trading date | No |
| `commodity` | STRING | 'Coffee' or 'Sugar' | No |
| `open` | FLOAT | Opening price ($/kg or $/lb) | No |
| `high` | FLOAT | Daily high | No |
| `low` | FLOAT | Daily low | No |
| `close` | FLOAT | Closing price (PRIMARY TARGET VARIABLE) | No |
| `volume` | FLOAT | Trading volume | Some |

**Data Source:** Yahoo Finance / CME futures contracts
**Update Frequency:** Daily after market close

**Sample Query:**
```sql
SELECT commodity, COUNT(*) as days, MIN(date) as start, MAX(date) as end, AVG(close) as avg_price
FROM commodity.bronze.market_data
GROUP BY commodity;
-- Expected: Coffee ~2,500 days, Sugar ~2,500 days
```

#### commodity.bronze.fx_rates

**Purpose:** Exchange rates for multi-currency support
**Grain:** One row per (date, currency_pair)
**Estimated Rows:** ~150,000

| Column | Type | Description |
|--------|------|-------------|
| `date` | DATE | Rate date |
| `currency_pair` | STRING | Format: 'COP/USD', 'VND/USD' |
| `rate` | FLOAT | Exchange rate (foreign per USD) |

**Supported Currencies (15+):**
- Major Producers: COP, VND, BRL, INR, THB, IDR, ETB, HNL, UGX, MXN, PEN
- Major Economies: EUR, GBP, JPY, CNY, AUD, CHF, KRW, ZAR

**Sample Query:**
```sql
-- Get latest rates for all currencies
WITH ranked AS (
  SELECT currency_pair, rate, date,
         ROW_NUMBER() OVER (PARTITION BY currency_pair ORDER BY date DESC) as rn
  FROM commodity.bronze.fx_rates
)
SELECT currency_pair, rate, date
FROM ranked
WHERE rn = 1
ORDER BY currency_pair;
```

#### commodity.silver.unified_data

**Purpose:** Master dataset integrating market + weather + FX
**Owner:** Research Agent
**Grain:** One row per (date, commodity, region)
**Estimated Rows:** ~75,000

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

**Key Features:**
- Forward-filled for non-trading days
- No duplicates on (date, commodity, region)
- ~65 regions covered
- Critical for model training

#### commodity.forecast.distributions

**Purpose:** Monte Carlo forecast paths for risk analysis (VaR, CVaR)
**Owner:** Forecast Agent
**Grain:** One row per (forecast_start_date, model_version, path_id)
**Partitioning:** (model_version, commodity)
**Estimated Rows:** ~622,300

| Column | Type | Description | Required |
|--------|------|-------------|----------|
| `path_id` | INT | Sample path ID (0-2000, where 0=actuals) | Yes |
| `forecast_start_date` | DATE | First day of forecast | Yes |
| `data_cutoff_date` | DATE | Last training date | Yes |
| `generation_timestamp` | TIMESTAMP | When generated | Yes |
| `model_version` | STRING | Model identifier | Yes |
| `commodity` | STRING | 'Coffee' or 'Sugar' | Yes |
| `day_1` to `day_14` | FLOAT | Forecasted prices (14 columns) | Yes |
| `is_actuals` | BOOLEAN | TRUE for path_id=0, FALSE otherwise | Yes |
| `has_data_leakage` | BOOLEAN | TRUE if forecast_start_date <= data_cutoff_date | Yes |

**Data Structure:**
- **path_id=0:** Actuals row (when available) with `is_actuals=TRUE`
- **path_id=1-2000:** Forecast paths with `is_actuals=FALSE`
- **Total:** 2,001 rows per forecast date

**Sample Query:**
```sql
-- Calculate 95% VaR for day 7
SELECT
  forecast_start_date,
  PERCENTILE(day_7, 0.05) as var_95_lower,
  PERCENTILE(day_7, 0.95) as var_95_upper,
  AVG(day_7) as mean_price,
  STDDEV(day_7) as volatility
FROM commodity.forecast.distributions
WHERE model_version = 'sarimax_auto_weather_v1'
  AND commodity = 'Coffee'
  AND is_actuals = FALSE
  AND has_data_leakage = FALSE
GROUP BY forecast_start_date
ORDER BY forecast_start_date DESC;
```

#### commodity.forecast.forecast_metadata

**Purpose:** Model performance metrics and forecast accuracy tracking
**Owner:** Forecast Agent
**Grain:** One row per (forecast_start_date, commodity, model_version)
**Partitioning:** commodity
**Estimated Rows:** ~500+

| Column | Type | Description |
|--------|------|-------------|
| `forecast_start_date` | DATE | Forecast date |
| `data_cutoff_date` | DATE | Training data cutoff |
| `commodity` | STRING | 'Coffee' or 'Sugar' |
| `model_version` | STRING | Model identifier |
| `model_success` | BOOLEAN | Did model converge? |
| `generation_timestamp` | TIMESTAMP | When generated |
| `mae_1d` | FLOAT | Mean Absolute Error (1-day ahead) |
| `mae_7d` | FLOAT | MAE (7-day ahead) |
| `mae_14d` | FLOAT | MAE (14-day ahead) |
| `rmse_1d` | FLOAT | Root Mean Squared Error (1-day) |
| `rmse_7d` | FLOAT | RMSE (7-day) |
| `rmse_14d` | FLOAT | RMSE (14-day) |
| `crps_1d` | FLOAT | Continuous Ranked Probability Score (1-day) |
| `crps_7d` | FLOAT | CRPS (7-day) |
| `crps_14d` | FLOAT | CRPS (14-day) |

**Sample Query:**
```sql
-- Get best model for Coffee by 14-day MAE
SELECT
  model_version,
  COUNT(*) as forecast_count,
  AVG(mae_14d) as avg_mae_14d,
  AVG(rmse_14d) as avg_rmse_14d,
  MIN(forecast_start_date) as earliest,
  MAX(forecast_start_date) as latest
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND model_success = TRUE
  AND mae_14d IS NOT NULL
GROUP BY model_version
ORDER BY avg_mae_14d ASC;
```

#### commodity.silver.gdelt_wide

**Purpose:** GDELT sentiment aggregated by commodity and date
**Grain:** One row per (article_date, commodity)
**Estimated Rows:** ~3,500+ (completion in progress)

**Schema (252 columns total):**
- `article_date` (DATE) - Article publication date
- `commodity` (STRING) - 'Coffee' or 'Sugar'
- **43 theme metrics** with 5 sub-columns each (215 columns total)
  - {theme}_article_count (INT) - Articles mentioning theme
  - {theme}_avg_tone (FLOAT) - Average sentiment (-100 to +100)
  - {theme}_total_mentions (INT) - Total mentions
  - {theme}_avg_v2counts (FLOAT) - Average V2 counts
  - {theme}_avg_v1counts (FLOAT) - Average V1 counts
- **7 group aggregates** (35 columns): ECON, ENV, LEADER, PROTEST, SOC, TAX, TERROR

**Key Themes (43 total):**
- Economic: ECON_STOCKMARKET, ECON_PRICERISE, ECON_PRICEFALL, ECON_INFLATIONRISE
- Environmental: ENV_WEATHER, ENV_RAIN, ENV_FLOOD, ENV_DROUGHT, ENV_COLD
- Agriculture: AGRI_*, ARMEDCONFLICT_*, DISEASE_*, LEADER_*, PROTEST_*, TAX_*

**Status:** 2/1,767 dates complete (0.1%) - Backfill in progress
**ETA:** 2-3 hours for full completion

**Sample Query:**
```sql
-- Get recent sentiment for Coffee
SELECT
  article_date,
  commodity,
  ECON_article_count,
  ECON_avg_tone,
  ENV_WEATHER_article_count,
  ENV_WEATHER_avg_tone,
  AGRI_article_count,
  AGRI_avg_tone
FROM commodity.silver.gdelt_wide
WHERE commodity = 'Coffee'
  AND article_date >= CURRENT_DATE - INTERVAL 30 DAYS
ORDER BY article_date DESC;
```

### Sample Queries

#### Get Latest Forecast (Aggregated)

```sql
SELECT
  forecast_start_date,
  model_version,
  PERCENTILE(day_7, 0.10) as p10,    -- Downside risk
  PERCENTILE(day_7, 0.50) as median, -- Expected price
  PERCENTILE(day_7, 0.90) as p90,    -- Upside potential
  AVG(day_7) as mean,
  STDDEV(day_7) as volatility
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee'
  AND is_actuals = FALSE
  AND has_data_leakage = FALSE
  AND model_version = 'arima_111_v1'  -- Best model
  AND forecast_start_date = (SELECT MAX(forecast_start_date) FROM commodity.forecast.distributions)
GROUP BY forecast_start_date, model_version;
```

#### Get Current Market State

```sql
-- Latest price
SELECT close, date
FROM commodity.bronze.market_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 1;

-- Latest FX rates
SELECT currency_pair, rate
FROM commodity.bronze.fx_rates
WHERE date = (SELECT MAX(date) FROM commodity.bronze.fx_rates);
```

#### Generate Daily Recommendation (Multi-Step)

```sql
-- Step 1: Get latest forecast distributions
WITH latest_forecast AS (
  SELECT forecast_start_date, model_version
  FROM commodity.forecast.distributions
  WHERE commodity = 'Coffee'
    AND is_actuals = FALSE
  ORDER BY forecast_start_date DESC
  LIMIT 1
),
forecast_stats AS (
  SELECT
    d.forecast_start_date,
    d.model_version,
    PERCENTILE(d.day_1, 0.50) as day1_median,
    PERCENTILE(d.day_7, 0.50) as day7_median,
    PERCENTILE(d.day_14, 0.50) as day14_median,
    PERCENTILE(d.day_14, 0.10) as day14_p10,
    PERCENTILE(d.day_14, 0.90) as day14_p90
  FROM commodity.forecast.distributions d
  INNER JOIN latest_forecast lf
    ON d.forecast_start_date = lf.forecast_start_date
    AND d.model_version = lf.model_version
  WHERE d.is_actuals = FALSE
    AND d.has_data_leakage = FALSE
  GROUP BY d.forecast_start_date, d.model_version
)
SELECT * FROM forecast_stats;

-- Step 2: Get current market price
SELECT close, date
FROM commodity.bronze.market_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 1;

-- Step 3: Get model performance
SELECT mae_14d, rmse_14d, model_success
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND model_version = (SELECT model_version FROM forecast_stats LIMIT 1)
ORDER BY forecast_start_date DESC
LIMIT 1;
```

#### Monitor Model Accuracy Over Time

```sql
-- Track rolling MAE for each model
SELECT
  model_version,
  DATE_TRUNC('month', forecast_start_date) as month,
  AVG(mae_14d) as avg_mae,
  COUNT(*) as forecast_count,
  SUM(CASE WHEN model_success THEN 1 ELSE 0 END) as successful_forecasts
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
  AND forecast_start_date >= '2024-01-01'
GROUP BY model_version, DATE_TRUNC('month', forecast_start_date)
ORDER BY month DESC, avg_mae ASC;
```

#### Get Multi-Currency Prices

```sql
-- Calculate current price in all available currencies
WITH current_price AS (
  SELECT close as price_usd
  FROM commodity.bronze.market_data
  WHERE commodity = 'Coffee'
  ORDER BY date DESC
  LIMIT 1
),
latest_rates AS (
  SELECT currency_pair, rate
  FROM commodity.bronze.fx_rates
  WHERE date = (SELECT MAX(date) FROM commodity.bronze.fx_rates)
)
SELECT
  lr.currency_pair,
  cp.price_usd,
  cp.price_usd * lr.rate as price_local,
  lr.rate
FROM current_price cp
CROSS JOIN latest_rates lr
ORDER BY lr.currency_pair;
```

#### Backtest Strategy Performance

```sql
-- Compare forecasts vs actuals for all historical windows
WITH forecasts AS (
  SELECT
    forecast_start_date,
    model_version,
    AVG(day_14) as forecast_mean,
    PERCENTILE(day_14, 0.50) as forecast_median
  FROM commodity.forecast.distributions
  WHERE commodity = 'Coffee'
    AND is_actuals = FALSE
    AND has_data_leakage = FALSE
  GROUP BY forecast_start_date, model_version
),
actuals AS (
  SELECT
    forecast_start_date,
    day_14 as actual_price
  FROM commodity.forecast.distributions
  WHERE commodity = 'Coffee'
    AND path_id = 0
    AND is_actuals = TRUE
)
SELECT
  f.forecast_start_date,
  f.model_version,
  f.forecast_median,
  a.actual_price,
  ABS(f.forecast_median - a.actual_price) as abs_error,
  ABS(f.forecast_median - a.actual_price) / a.actual_price * 100 as mape
FROM forecasts f
INNER JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
ORDER BY f.forecast_start_date DESC;
```

### Data Quality Notes

#### Critical Invariants

```sql
-- 1. Forecast dates must be after cutoff dates
CHECK (forecast_start_date > data_cutoff_date)

-- 2. Path IDs in valid range
CHECK (path_id BETWEEN 0 AND 2000)

-- 3. Actuals flag matches path_id
CHECK ((path_id = 0 AND is_actuals = TRUE) OR
       (path_id > 0 AND is_actuals = FALSE))

-- 4. Prices are positive
CHECK (day_1 > 0 AND day_14 > 0)

-- 5. No duplicate forecasts
UNIQUE (forecast_start_date, model_version, commodity, path_id)
```

#### Known Data Quality Issues

**1. GDELT Silver Incomplete**
- **Issue:** Only 2/1,767 dates processed (0.1%)
- **Impact:** Cannot use sentiment signals yet
- **ETA:** 2-3 hours for completion
- **Workaround:** Use placeholder values or skip sentiment

**2. Identical Model Results**
- **Issue:** All 12 Coffee models produce identical backtest results
- **Impact:** Can't differentiate model performance
- **Status:** Under investigation
- **Hypothesis:** Models may share underlying features

**3. Missing FX Rates for Some Days**
- **Issue:** Weekend/holiday gaps in fx_rates table
- **Impact:** Multi-currency pricing incomplete
- **Workaround:** Forward-fill last known rate

**4. Prophet Model Underperformance**
- **Issue:** Prophet MAE = $7.36 (2× worse than ARIMA)
- **Impact:** Should not be used for production
- **Action:** Filter out prophet_v1 from model selection

#### Data Completeness by Table

| Table | Coverage | Status |
|-------|----------|--------|
| commodity.bronze.market_data | 100% (2018-present) | Complete |
| commodity.forecast.distributions | 100% (42 forecast windows) | Complete |
| commodity.forecast.forecast_metadata | 100% (corresponding forecasts) | Complete |
| commodity.bronze.fx_rates | 95% (weekend/holiday gaps) | Forward-fill workaround |
| commodity.silver.unified_data | 100% (continuous daily) | Complete |
| commodity.silver.gdelt_wide | 0.1% (2/1,767 dates) | **IN PROGRESS** |

---

## How Notebooks Run in Databricks

**Important:** These notebooks run IN Databricks, not locally.

### Key Concepts

- **Notebooks use `%run ./00_setup_and_config`** to load configuration
- **The `spark` object is pre-configured** in Databricks environment
- **NO local SparkSession setup needed** - it's already there
- **`__file__` is undefined in Jobs execution** - use try/except fallback

---

## File Storage Locations

### Unity Catalog Volume (Persistent Storage) ⭐ RECOMMENDED

```python
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"
```

**Use this for:**
- Pickle files: `prediction_matrices_*.pkl`, `results_detailed_*.pkl`, etc.
- Images: `*.png` files
- CSV exports: `*.csv` files
- Any results that need to persist after cluster stops

**Access via Databricks CLI:**

```bash
# List files
databricks fs ls dbfs:/Volumes/commodity/trading_agent/files/

# Download a file
databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/myfile.pkl ./myfile.pkl

# Upload a file
databricks fs cp ./myfile.pkl dbfs:/Volumes/commodity/trading_agent/files/myfile.pkl

# Check file size
databricks fs ls dbfs:/Volumes/commodity/trading_agent/files/ | grep validation
```

### Delta Tables (Structured Data)

```python
OUTPUT_SCHEMA = "commodity.trading_agent"
```

**Tables created:**
- `commodity.trading_agent.predictions_{commodity}`
- `commodity.trading_agent.predictions_prepared_{commodity}_{model}`
- `commodity.trading_agent.results_{commodity}_{model}`
- `commodity.trading_agent.diagnostic_results`

**Access via Spark (in notebook):**

```python
df = spark.table("commodity.trading_agent.predictions_coffee")
```

**Access via CLI:**

```bash
databricks sql query "SELECT * FROM commodity.trading_agent.predictions_coffee LIMIT 10"
```

### Notebook Local Directory (EPHEMERAL - DO NOT USE)

When you save with `open('file.pkl', 'wb')` without a full path, it goes to:
- `/databricks/driver/` on the cluster
- **This is TEMPORARY** - lost when cluster terminates
- **Always save to VOLUME_PATH instead!**

---

## Correct Pattern for Saving Files

### ❌ WRONG (ephemeral):
```python
with open('validation_results.pkl', 'wb') as f:
    pickle.dump(data, f)
```

### ✅ CORRECT (persistent):
```python
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"
output_path = f"{VOLUME_PATH}/validation_results.pkl"

with open(output_path, 'wb') as f:
    pickle.dump(data, f)
```

---

## Accessing Notebook Outputs

### The Problem

Databricks notebooks have two states:
1. **Source** - The code/markdown cells (persisted in git/workspace)
2. **Execution outputs** - Results from running cells (ephemeral, session-based)

When you export via Workspace API:
- ✅ Gets source code
- ❌ Does NOT get execution outputs (even with HTML/IPYNB format)

### Solution 1: Auto-Save Results to Files ⭐ RECOMMENDED

**Implementation pattern:**

```python
# Last cell of any diagnostic notebook
import pickle
import json
from datetime import datetime

# Collect all important results
results = {
    'timestamp': datetime.now().isoformat(),
    'summary': {
        'best_strategy': best_strategy_name,
        'net_earnings': float(best_earnings),
        # ... other key metrics
    },
    'detailed_results': all_results_dict
}

# Save pickle for programmatic access
pkl_path = f'/Volumes/commodity/trading_agent/files/{notebook_name}_results.pkl'
with open(pkl_path, 'wb') as f:
    pickle.dump(results, f)

# Save JSON for human readability
json_path = pkl_path.replace('.pkl', '.json')
with open(json_path, 'w') as f:
    json.dump(results['summary'], f, indent=2)

print(f"✅ Results saved to:")
print(f"   PKL: {pkl_path}")
print(f"   JSON: {json_path}")
print(f"\n📥 Download with:")
print(f"   databricks fs cp dbfs:{pkl_path.replace('/Volumes', '/Volumes')} /tmp/")
```

**Advantages:**
- ✅ Fully automated
- ✅ Works for any notebook type
- ✅ Programmatically accessible
- ✅ Persists indefinitely
- ✅ Can version/timestamp results

**Reusable template function:**

```python
def save_diagnostic_results(notebook_name, results_dict, summary_dict=None):
    """
    Standard function for saving diagnostic results.

    Args:
        notebook_name: Name of the diagnostic (e.g., 'diagnostic_12')
        results_dict: Full results dictionary (saved as pickle)
        summary_dict: Optional human-readable summary (saved as JSON)
    """
    import pickle
    import json
    from datetime import datetime

    # Base path
    base_path = f'/Volumes/commodity/trading_agent/files/{notebook_name}_results'

    # Add timestamp and metadata
    results_with_meta = {
        'timestamp': datetime.now().isoformat(),
        'notebook': notebook_name,
        'results': results_dict
    }

    # Save pickle
    pkl_path = f'{base_path}.pkl'
    with open(pkl_path, 'wb') as f:
        pickle.dump(results_with_meta, f)
    print(f"✅ Saved pickle: {pkl_path}")

    # Save JSON summary if provided
    if summary_dict:
        json_path = f'{base_path}.json'
        with open(json_path, 'w') as f:
            json.dump({
                'timestamp': results_with_meta['timestamp'],
                'notebook': notebook_name,
                'summary': summary_dict
            }, f, indent=2)
        print(f"✅ Saved JSON: {json_path}")

    # Print download instructions
    print(f"\n{'='*80}")
    print(f"RESULTS READY FOR DOWNLOAD")
    print(f"{'='*80}")
    print(f"\nDownload command:")
    print(f"  databricks fs cp dbfs:{pkl_path.replace('/Volumes', '/Volumes')} /tmp/")
    if summary_dict:
        print(f"  databricks fs cp dbfs:{json_path.replace('/Volumes', '/Volumes')} /tmp/")

    return pkl_path
```

### Solution 2: Download Existing Data Files

**What worked (Tested 2025-11-22):**

```bash
# 1. Download the pickle file
databricks fs cp \
  dbfs:/Volumes/commodity/trading_agent/files/results_detailed_coffee_synthetic_acc90.pkl \
  /tmp/results_detailed.pkl

# 2. Analyze it with Python
python3 << 'EOF'
import pickle

with open('/tmp/results_detailed.pkl', 'rb') as f:
    all_results = pickle.load(f)

# Now analyze all_results dictionary
for strategy_name, result in all_results.items():
    trades = result['trades']
    # Count reasons, etc.
EOF
```

**Why this works:**
- Diagnostic notebooks load data from pickle files
- These pickle files ARE accessible via `databricks fs cp`
- You can download and analyze them directly without needing notebook outputs

**Key paths:**
```
/Volumes/commodity/trading_agent/files/results_detailed_coffee_synthetic_acc90.pkl
/Volumes/commodity/trading_agent/files/prediction_matrices_coffee_synthetic_acc90.pkl
/Volumes/commodity/trading_agent/files/cross_model_commodity_summary.csv
```

### Solution 3: Run as Databricks Job

Jobs preserve execution outputs that can be exported:

```bash
# Create job
databricks jobs create --json '{
  "name": "diagnostic_12_runner",
  "tasks": [{
    "task_key": "run_diagnostic",
    "notebook_task": {
      "notebook_path": "/Workspace/Repos/.../diagnostic_12_fixed_strategy_validation"
    },
    "new_cluster": { ... }
  }]
}'

# Run job and export results
databricks jobs run-now --job-id JOB_ID
databricks runs export --run-id RUN_ID --file /tmp/diagnostic_12_with_outputs.html
```

### Solution 4: Save to Spark Tables

Write results to Delta tables and query remotely:

```python
# In notebook
results_df = pd.DataFrame([{
    'notebook': 'diagnostic_12',
    'timestamp': datetime.now(),
    'strategy': 'Expected Value Fixed',
    'net_earnings': 755000.0,
    'vs_baseline_pct': 3.8
}])

spark.createDataFrame(results_df).write.mode('append').saveAsTable(
    'commodity.trading_agent.diagnostic_results'
)
```

**Query remotely:**
```bash
databricks sql query "SELECT * FROM commodity.trading_agent.diagnostic_results WHERE notebook = 'diagnostic_12' ORDER BY timestamp DESC LIMIT 1"
```

---

## Automated Remote Execution Pattern ⭐ NEW

For long-running diagnostics or production workflows, convert notebooks to executable Python scripts that run remotely via the Databricks Jobs API.

### When to Use

- ✅ Long-running diagnostics (> 30 minutes)
- ✅ Computationally intensive tasks (Optuna optimization, etc.)
- ✅ Sequential workflows
- ✅ When you want to "set it and forget it"
- ✅ Production-grade automation

### Implementation Workflow

**Step 1: Convert Notebook to Executable Python Script**

```python
"""
Diagnostic N: Description
Databricks execution script with result saving
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path
import sys
import os

# Get script directory (works everywhere)
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Fallback to hardcoded path for Databricks jobs
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/diagnostics'

# Use importlib for module loading (not direct imports)
import importlib.util

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/diagnostics/all_strategies_pct.py',
    'all_strategies_pct.py'
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        print(f"Found module at: {path}")
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find module. Tried: {possible_paths}")

# Load module using importlib
spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)


def load_data_from_delta():
    """Load data from Delta tables (not pickle files)"""
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    # Load prices
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = 'coffee'"
    ).toPandas()

    # Normalize dates IMMEDIATELY
    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)

    # Load predictions
    pred_df = spark.table(f"commodity.trading_agent.predictions_coffee").filter(
        "model_version = 'synthetic_acc100'"
    ).toPandas()

    return prices_df, pred_df


def main():
    print("="*80)
    print("DIAGNOSTIC N: Title")
    print("="*80)
    print(f"Execution time: {datetime.now()}")

    # Load data
    prices, predictions = load_data_from_delta()

    # Run analysis
    results = run_analysis(prices, predictions)

    # Save results to volume
    volume_path = "/Volumes/commodity/trading_agent/files"
    output_file = f"{volume_path}/diagnostic_N_results.pkl"

    with open(output_file, 'wb') as f:
        pickle.dump(results, f)

    print(f"✓ Saved results to: {output_file}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

**Step 2: Commit and Push to Git**

```bash
git add diagnostics/run_diagnostic_N.py
git commit -m "Add executable diagnostic_N script"
git push
```

**Step 3: Update Databricks Repo (CRITICAL - DO NOT SKIP)**

```bash
# This step is MANDATORY after every git push
databricks repos update 1904868124027877 --branch main
```

**Why this matters:**
- ❌ If you skip this: Databricks runs OLD code from stale repo
- ✅ Solution: ALWAYS run `databricks repos update` after `git push`

**Step 4: Submit Job via Databricks CLI**

```bash
# Create job config
cat > /tmp/diagnostic_N_job.json << 'EOF'
{
  "run_name": "diagnostic_N_description",
  "tasks": [{
    "task_key": "diagnostic_N",
    "spark_python_task": {
      "python_file": "file:///Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/diagnostics/run_diagnostic_N.py"
    },
    "existing_cluster_id": "1111-041828-yeu2ff2q",
    "timeout_seconds": 3600
  }]
}
EOF

# Submit job
databricks jobs submit --json @/tmp/diagnostic_N_job.json
```

**Step 5: Monitor Execution**

```bash
# Check status
databricks jobs get-run <RUN_ID> --output json | jq '.state'

# Get run URL
databricks jobs get-run <RUN_ID> --output json | jq -r '.run_page_url'
```

**Automated monitoring script:**

```python
import subprocess
import json
import time

def monitor_job(run_id):
    while True:
        result = subprocess.run(
            ["databricks", "jobs", "get-run", run_id, "--output", "json"],
            capture_output=True, text=True
        )
        status = json.loads(result.stdout)
        state = status.get('state', {})

        if state.get('life_cycle_state') == 'TERMINATED':
            return state.get('result_state') == 'SUCCESS'

        time.sleep(60)  # Check every minute
```

**Step 6: Download Results**

```bash
# After job completes
databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/diagnostic_N_results.pkl /tmp/
```

---

## Common Patterns & Best Practices

### Reading Files from Volume

```python
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"
input_path = f"{VOLUME_PATH}/validation_results.pkl"

with open(input_path, 'rb') as f:
    data = pickle.load(f)
```

### Date Normalization (CRITICAL for Dictionary Lookups)

**The Problem:**
```python
# Timestamps with different times don't match
current_date = Timestamp('2022-01-03 00:00:00')
dict_key = Timestamp('2022-01-03 05:30:00.123456')
# They are NOT equal, so dictionary lookups return None!
```

**The Solution:**
```python
# Normalize ALL dates to midnight (strip time component)

# When loading price data
market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()

# When building prediction dictionary
date_key = pd.Timestamp(timestamp).normalize()
prediction_matrices[date_key] = matrix

# Now lookup succeeds
predictions = prediction_matrices.get(current_date, None)  # ✓ Found!
```

### Module Loading in Databricks Jobs

**Problem:** Direct imports fail with `NotebookImportException`

```python
# ❌ This FAILS in Databricks Repos
import all_strategies_pct
```

**Solution:** Use importlib to load modules explicitly

```python
import importlib.util
import os

# Try multiple paths to find the module
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # __file__ not defined in Databricks jobs - use hardcoded path
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/diagnostics/all_strategies_pct.py',
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find module")

# Load module using importlib
spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)
```

### Downloading Files to Local Machine

```bash
# Set credentials
export DATABRICKS_HOST=https://dbc-5e4780f4-fcec.cloud.databricks.com
export DATABRICKS_TOKEN=***REMOVED***

# Download from volume
databricks fs cp dbfs:/Volumes/commodity/trading_agent/files/validation_results_full.pkl ./validation_results_full.pkl

# Check file size
databricks fs ls dbfs:/Volumes/commodity/trading_agent/files/ | grep validation
```

---

## Troubleshooting

### Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| **"Table not found"** | Wrong table name | Use full name: `commodity.silver.gdelt_wide` |
| **Slow query** | No partition filters | Add `WHERE commodity = 'coffee' AND article_date >= '2024-01-01'` |
| **No results** | Bad filters | Check filters, verify with `SELECT COUNT(*)` |
| **`NotebookImportException`** | Direct import of .py file | Use `importlib` instead |
| **`NameError: __file__` undefined** | Jobs don't define `__file__` | Wrap in try/except with fallback path |
| **Dictionary lookup returns None** | Date/time mismatch | Use `.dt.normalize()` on all dates |
| **Job runs old code** | Forgot repo update | Run `databricks repos update 1904868124027877 --branch main` |

### Pandas Version Issues

If you get pandas version errors when loading pickles locally:

```bash
# Downgrade to pandas 1.5.3 which is compatible
pip install 'pandas==1.5.3'
```

Then load normally:
```python
import pickle
with open('validation_results_full.pkl', 'rb') as f:
    data = pickle.load(f)
```

### Databricks Repo Sync

**Critical issue:** Jobs run old code if you forget to update the repo after pushing

```bash
# Correct workflow:
git push                                                    # Push changes to GitHub
databricks repos update 1904868124027877 --branch main    # Pull in Databricks
databricks jobs submit --json @job.json                   # NOW submit job
```

**Find repo ID if needed:**
```bash
databricks repos list --output json | grep -A 5 ucberkeley-capstone
```

---

## Common Commodities & Configurations

```python
COMMODITY_CONFIGS = {
    'coffee': {
        'table': 'commodity.trading_agent.predictions_coffee',
        'silver_table': 'commodity.silver.unified_data'
    },
    'sugar': {
        'table': 'commodity.trading_agent.predictions_sugar',
        'silver_table': 'commodity.silver.unified_data'
    }
}
```

---

## Key Takeaways

### Data Access
1. **Best model for Coffee**: `arima_111_v1` (MAE: $3.49) or `sarimax_auto_weather_v1` for weather-conditional forecasts
2. **Always filter**: `has_data_leakage = FALSE`, `is_actuals = FALSE`, `model_success = TRUE`
3. **Use partition columns**: Include `model_version` and `commodity` in WHERE clauses for performance
4. **Check data catalog**: Complete schemas and sample queries in Data Catalog section

### Notebook Operations
5. **Notebooks run IN Databricks** - not locally
6. **Always save to `/Volumes/commodity/trading_agent/files`** - not local directory
7. **Use `databricks CLI` to download files** to local machine
8. **Delta tables** for structured data, **Volumes** for binary/images
9. **`spark` object** is pre-configured - don't create it

### Best Practices
10. **Normalize dates with `.dt.normalize()`** for reliable dictionary lookups
11. **Use importlib for module loading** in Databricks jobs
12. **ALWAYS run `databricks repos update` after `git push`** before submitting jobs
13. **Save results to files** for reliable access after execution
14. **Query structured data** from Delta tables, not pickle files

**Production Testing Best Practices (from Phase 2 validation):**
15. **Use absolute imports in production modules** - Change `from strategies import` to `from production.strategies import` for Databricks Jobs compatibility
16. **Query unified_data correctly** - Use `.filter(f"commodity = '{commodity.title()}'")` and select `'close'` column, rename to `'price'` for consistency
17. **Match original notebook patterns** - Review notebook implementations before creating production versions to ensure data access patterns match
18. **Use strategy class defaults** - Don't pass config parameters to strategies unless needed; strategies have sensible defaults (e.g., `ImmediateSaleStrategy()` with no args)
19. **Verify BacktestEngine result keys** - Production engine returns `net_earnings`, `trades`, `daily_state` NOT `total_earnings`, `transaction_history`, `final_inventory`

---

**Last Updated:** 2025-11-24
**Source:** Merged from DATABRICKS_GUIDE.md, FORECAST_API_GUIDE.md, and DATA_REFERENCE.md
