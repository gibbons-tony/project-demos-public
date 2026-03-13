# Forecast Agent API Guide for Trading Agent

**Last Updated**: 2025-11-01
**Status**: ✅ Production Ready - 622K rows of historical distributions available

**Backtest Results Available**: See `backtest_results.md` for comprehensive performance evaluation across 42 forecast windows

---

## Quick Start

### Current Data Availability

**commodity.forecast.distributions**: 622,300 rows
- **42 forecast dates**: July 2018 - November 2025
- **5 models**: SARIMAX+Weather, Prophet, XGBoost+Weather, ARIMA, Random Walk
- **300 actuals rows** (path_id=0) for backtesting
- **2,000 Monte Carlo paths** per model for VaR/CVaR analysis

**commodity.forecast.point_forecasts**: 0 rows
_(Coming soon - P2 priority)_

---

## Recommended Production Model

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

---

## API: Query Distributions Table

### 1. Get Latest Forecast (Most Recent Date)

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

---

### 2. Calculate VaR and CVaR (Risk Metrics)

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

---

### 3. Get Actuals for Backtesting

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

---

### 4. Backtest Model Performance

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

---

### 5. Compare Models Side-by-Side

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

---

## Python Code Examples

### Connect to Databricks

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

### Fetch Latest Forecast Distributions

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

### Calculate VaR/CVaR in Python

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

---

## Data Quality Checks

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

---

## Model Selection Decision Tree

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

---

## Partitioning Strategy

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

## Troubleshooting

### Issue: Query returns 0 rows
**Check**:
1. Is `model_version` spelled correctly? (e.g., `sarimax_auto_weather_v1` not `sarimax_weather_v1`)
2. Are you using `Coffee` (capital C)?
3. Did you accidentally filter `is_actuals = TRUE` instead of `FALSE`?

### Issue: Too many rows (> 2,000)
**Check**:
1. Did you forget `is_actuals = FALSE`? (This excludes path_id=0)
2. Are you getting multiple forecast_start_dates? (Add `LIMIT 1` or filter by date)

### Issue: Negative prices in distributions
**Action**: Report as data quality issue. Should not happen (minimum price is capped at $10.00 in generation).

---

## Next Steps for Trading Agent

1. **Start with backtesting**:
   - Query historical distributions + actuals
   - Calculate MAE/MAPE/Coverage across all 42 forecast dates
   - Validate model performance before trading

2. **Implement VaR-based position sizing**:
   - Use 95% VaR to set stop-loss levels
   - Size positions based on acceptable risk (e.g., max 2% portfolio loss)

3. **Build ensemble strategy** (optional):
   - Query multiple models (SARIMAX, Prophet, XGBoost)
   - Weight models by recent performance
   - Use forecast_metadata table (coming soon) for dynamic weighting

4. **Monitor forecast freshness**:
   - Check `generation_timestamp` to ensure forecasts are recent
   - Set up alerts if latest forecast > 24 hours old

---

## Contact

**Forecast Agent Team**: Connor
**Data Issues**: File ticket in forecast_agent repo
**Model Questions**: See `../forecast_agent/DESIGN_DECISIONS.md`

---

**Ready to start trading? The data is live and validated!** 🚀
