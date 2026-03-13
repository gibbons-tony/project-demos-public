# Unified Data Architecture

**Purpose**: Document the design philosophy and technical approach for unified commodity data

**Owner**: Research Agent (Stuart & Francisco)

---

## Overview: Silver vs Gold Layers

This document covers TWO unified data tables:

| Table | Grain | Rows | Use Case |
|-------|-------|------|----------|
| **commodity.silver.unified_data** | (date, commodity, region) | ~75k | Regional analysis, data exploration |
| **commodity.gold.unified_data** | (date, commodity) | ~7k | **ML training** (array-based, flexible aggregation) |

**Recommendation**: Use **gold.unified_data** for ML models - it's faster (90% fewer rows) and more flexible.

---

## Gold Layer (Recommended for ML)

### Data Hierarchy

**Grain**: One row per `(date, commodity)`

```
Date (daily, continuous)
  ├── Commodity (Coffee, Sugar)
      ├── weather_data: ARRAY<STRUCT<region, temp, precip, ...>>
      ├── gdelt_themes: ARRAY<STRUCT<theme_group, count, tone, ...>>
```

**Why this grain?**
- **90% fewer rows**: ~7k vs ~75k (faster training, lower memory)
- **Flexible aggregation**: Models decide how to use regional data
  - Mean temperature across all regions
  - Weighted by production volume
  - Separate features per region
  - Learn regional importance via attention mechanisms
- **Clean ML integration**: Array operations work natively with PySpark ML transformers
- **Includes GDELT**: News sentiment as array of theme groups

**Schema Details**: See [docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md)

---

## Silver Layer (Legacy, Maintained for Compatibility)

### Data Hierarchy

**Grain**: One row per `(date, commodity, region)`

```
Date (daily, continuous)
  ├── Commodity (Coffee, Sugar)
      ├── Region (Bugisu_Uganda, Chiapas_Mexico, ...)
```

**Why this grain?**
- **Date**: Full calendar coverage (trading + non-trading days)
- **Commodity**: Separate time series for Coffee and Sugar
- **Region**: Preserves geographic granularity for weather data
- **Flexibility**: Forecast models can aggregate/pivot regions as needed (but requires manual pivoting)

---

## Data Sources & Frequencies

Data arrives at different frequencies. We normalize to **daily grain** using forward-fill.

| Source | Frequency | Grain | Records | Challenges |
|--------|-----------|-------|---------|------------|
| **Market Data** | Trading days only | (date, commodity) | ~2.7k | Weekends/holidays missing |
| **VIX** | Trading days only | (date) | ~3.6k | Weekends/holidays missing |
| **Weather** | Daily | (date, commodity, region) | ~75k | Most complete |
| **Exchange Rates** | Weekdays | (date, currency) | ~3.6k | Weekends missing |
| **GDELT** (future) | Irregular | (date, commodity) | Variable | Not every day has articles |

**Challenge**: How to join data with different availabilities?

---

## Joining Strategy: Date Spine + Forward Fill

### 1. Create Date Spine (Complete Calendar)

```sql
date_spine AS (
  SELECT date_add('2015-07-07', x - 1) as date
  FROM (SELECT explode(sequence(1, 10000)) as x)
  WHERE date_add('2015-07-07', x - 1) <= current_date()
)
```

**Result**: Every single day from 2015-07-07 to today (~3,500 days)

**Why?**
- Ensures no date gaps
- Allows forward-filling for non-trading days
- Models train on continuous time series

### 2. Forward Fill Each Source

**Principle**: Use last known value until new data arrives (step function)

```sql
market_filled AS (
  SELECT
    dcs.date,
    dcs.commodity,
    LAST_VALUE(mc.close, true) OVER (
      PARTITION BY dcs.commodity
      ORDER BY dcs.date
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) as close,
    ...
  FROM date_commodity_spine dcs
  LEFT JOIN market_clean mc ON dcs.date = mc.date AND dcs.commodity = mc.commodity
)
```

**What this does**:
- **Trading day** (e.g., Monday): Use actual close price
- **Non-trading day** (e.g., Saturday): Use Friday's close price
- **Next trading day** (e.g., next Monday): Update to new close price

**Behavior**: Step function (flat until update)

### 3. Join All Sources

```sql
FROM weather_filled wf
INNER JOIN market_filled mf ON wf.date = mf.date AND wf.commodity = mf.commodity
INNER JOIN vix_filled vf ON wf.date = vf.date
INNER JOIN macro_filled macf ON wf.date = macf.date
LEFT JOIN trading_days td ON wf.date = td.date AND wf.commodity = td.commodity
```

**Result**: Every row has values for all features (no NULLs after forward-fill)

---

## Why Forward Fill? (Preventing Data Leakage)

### Alternative Approaches (We Don't Use)

**❌ Backward Fill**:
```sql
LAST_VALUE(...) OVER (ORDER BY date DESC)  -- WRONG!
```
**Problem**: Uses future data! Saturday's value would use Monday's close. **Data leakage!**

**❌ Interpolation**:
```sql
AVG(...) OVER (ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING)  -- WRONG!
```
**Problem**: Uses future data to estimate current values. **Data leakage!**

**✅ Forward Fill (What We Use)**:
```sql
LAST_VALUE(...) OVER (ORDER BY date ASC)  -- CORRECT
```
**Correct**: Only uses past data. No future information leak.

### Real-World Interpretation

**Saturday, Jan 14, 2024**:
- Market is closed → No new price data
- Our system uses: Friday Jan 13's close price
- **Realistic**: If a trader checked prices on Saturday, they'd see Friday's closing value

**This matches reality**: Information doesn't travel backward in time.

---

## Trading Day Indicator

We add `is_trading_day` flag to distinguish real vs forward-filled data:

```sql
COALESCE(td.is_trading_day, 0) as is_trading_day
```

**Values**:
- `1` = Trading day (actual data)
- `0` = Non-trading day (forward-filled)

**Usage in forecasting**:
```python
# Train only on trading days
df_train = df.filter("is_trading_day = 1")
```

**Why important?**
- Models train on actual market movements
- Avoids bias from duplicated weekend values
- Proper time series frequency (skip non-trading days)

---

## Data Flow Diagram

```
Bronze Layer (Raw)
  ├── market_data
  ├── vix_data
  ├── weather_data
  ├── macro_data
  └── bronze_gkg (GDELT)
         ↓
    Deduplication
         ↓
    Date Spine Creation
         ↓
    Forward Fill (per source)
         ↓
    Join All Sources
         ↓
Silver Layer (Unified)
  └── unified_data
       (date, commodity, region) grain
       All features forward-filled
       No NULLs after initial data
```

---

## Handling Missing Data

### Initial Data Gaps

**Problem**: No data before 2015-07-07

**Solution**: Data only exists from start date forward. Models can't forecast before this.

### Source-Specific Gaps

**Problem**: Weather data might be missing for specific region on specific day

**Solution**: Forward-fill handles this automatically:
```sql
LAST_VALUE(temp_c, true) OVER (...)
```
If today's temperature is NULL, use yesterday's.

### New Source Integration (GDELT)

**Problem**: GDELT data is irregular (not every day has articles)

**Solution**: Same forward-fill pattern:
```sql
LAST_VALUE(gdelt_tone, true) OVER (
  PARTITION BY commodity
  ORDER BY date
  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
)
```

**Behavior**:
- **Article published**: Update sentiment score
- **No articles**: Keep last known sentiment
- **First article ever**: No sentiment until first article

---

## Performance & Scale

**Current Size**:
- Rows: ~75k (10 years × 2 commodities × ~65 regions × 365 days / region coverage)
- Columns: 37
- Size: ~50 MB (estimated)

**After GDELT** (7 new columns):
- Size: ~54 MB
- Minimal impact

**Query Performance**:
- Forward-fill CTEs: ~30 seconds
- Full table creation: ~1-2 minutes
- Queries on unified_data: <1 second (indexed on date, commodity)

---

## Design Decisions & Rationale

### 1. Why Regional Grain?

**Decision**: Keep region-level weather (not aggregate)

**Rationale**:
- Forecast models can choose aggregation strategy
- ARIMA: Simple mean across regions
- LSTM: Each region as separate feature
- XGBoost: Weighted by production
- **Flexibility** > Pre-aggregation

### 2. Why Forward Fill vs NULL?

**Decision**: Forward-fill all sources

**Rationale**:
- No NULL handling in forecast models
- Matches reality (last known value persists)
- Prevents data leakage (only backward looking)
- Simpler downstream processing

### 3. Why Include Non-Trading Days?

**Decision**: Full calendar, not just trading days

**Rationale**:
- Weather changes every day (even weekends)
- Complete time series for ARIMA/LSTM
- `is_trading_day` flag lets models filter if needed
- Real-world scenario: Forecast on Saturday for Monday

### 4. Why Deduplication Before Join?

**Decision**: Dedupe each source independently first

**Rationale**:
- VIX has duplicate rows (same values) → DISTINCT
- Macro has duplicate rows (different sources) → Keep most complete row
- Clean data before expensive joins
- Easier debugging

---

## Example: Market Data on Weekend

**Scenario**: Coffee price on Saturday, Jan 14, 2024

**Data Flow**:

1. **Bronze**: `market_data` has no row for Jan 14 (market closed)

2. **Market Clean**:
   ```
   2024-01-12 (Fri): close = 167.50
   2024-01-15 (Mon): close = 168.20
   # Jan 14 (Sat) missing
   ```

3. **Date Spine**:
   ```
   2024-01-12
   2024-01-13
   2024-01-14  ← We need this
   2024-01-15
   ```

4. **Forward Fill**:
   ```sql
   LAST_VALUE(close, true) OVER (ORDER BY date)
   ```
   Result:
   ```
   2024-01-12: 167.50 (actual)
   2024-01-13: 167.50 (forward-filled from Fri)
   2024-01-14: 167.50 (forward-filled from Fri)
   2024-01-15: 168.20 (actual, new data)
   ```

5. **Trading Day Flag**:
   ```
   2024-01-12: is_trading_day = 1
   2024-01-13: is_trading_day = 0
   2024-01-14: is_trading_day = 0
   2024-01-15: is_trading_day = 1
   ```

**Result**: Model trains on actual prices (Fri + Mon), weekend shows last known value

---

## Future Enhancements

### Considered But Not Implemented

1. **Hour-level granularity**: Futures trade 24hrs → Could capture intraday
   - **Why not**: Complexity, most models need daily frequency

2. **Multiple imputation**: Statistical fill instead of forward-fill
   - **Why not**: Introduces uncertainty, forward-fill matches reality

3. **Separate tables per frequency**: Daily table, weekly table, etc.
   - **Why not**: Harder to join, forward-fill handles this

4. **Interpolation for weather**: Smooth between data points
   - **Why not**: Risk of data leakage if not careful

---

## Validation Queries

**Check for NULLs** (should be zero after forward-fill):
```sql
SELECT
  'close' as col, SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_count
FROM commodity.silver.unified_data
UNION ALL
SELECT 'vix', SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END)
FROM commodity.silver.unified_data;
```

**Check grain uniqueness**:
```sql
SELECT COUNT(*) as total_rows,
       COUNT(DISTINCT date, commodity, region) as unique_combinations
FROM commodity.silver.unified_data;
-- Should match!
```

**Check forward-fill worked**:
```sql
SELECT date, commodity, close, is_trading_day
FROM commodity.silver.unified_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 10;
-- Weekend rows should show 0 for is_trading_day
-- Weekend close should match Friday's
```

---

**Document Version**: 1.0
**Last Updated**: 2024-10-28
**See Also**: `GDELT_PROCESSING.md`, `sql/create_unified_data.sql`
