# Migration Guide: Silver → Gold Unified Data

**Purpose**: Guide for transitioning forecast models from `commodity.silver.unified_data` to `commodity.gold.*`

**Audience**: Forecast Agent developers

**Status**: Two gold tables available (Dec 2024)

---

## ⚠️ IMPORTANT: Two Gold Tables Available

**Choose the right table for your use case:**

| Table | Imputation | Use Case | Status |
|-------|-----------|----------|--------|
| **`commodity.gold.unified_data`** | All features forward-filled | Production, existing models | ✅ Stable |
| **`commodity.gold.unified_data_raw`** | Only `close` forward-filled | Experimentation, new models | ⚠️ Experimental |

**Quick Decision Tree:**
- Building a **new model**? → Use `unified_data_raw`
- Running **existing production** models? → Use `unified_data`
- Want **imputation flexibility**? → Use `unified_data_raw`
- Want **zero risk, proven data**? → Use `unified_data`

---

## 🏗️ Architecture: DRY Principle

**Key Design Decision**: Production table is DERIVED from experimental table (not a duplicate build)

```
Bronze Sources (market, vix, macro, weather, GDELT)
  ↓
  ↓ [Complex logic: date spine, deduplication, array aggregation]
  ↓
commodity.gold.unified_data_raw  ← SINGLE SOURCE OF TRUTH
  ↓
  ↓ [Simple transformation: forward-fill NULLs]
  ↓
commodity.gold.unified_data  ← DERIVED TABLE
```

**Benefits**:
- ✅ **DRY**: All complex logic lives in ONE place (`unified_data_raw`)
- ✅ **Maintainability**: Fix bugs/add features in base table, production inherits automatically
- ✅ **Performance**: Production table rebuilds in ~10 seconds (vs ~1-2 min for base)
- ✅ **Clear Lineage**: Base table → Derived table (not parallel independent builds)

**Build Order**:
1. **First**: Build `unified_data_raw` (base table, ~1-2 min)
2. **Second**: Build `unified_data` FROM base table (derived, ~10 sec)

---

## Which Table Should I Use?

### Use `commodity.gold.unified_data` (Production) if:

✅ **You have existing models in production**
- Models already tuned to forward-filled data
- Don't want to revalidate performance
- Stability is more important than flexibility

✅ **You want proven, stable data**
- All features forward-filled (no NULLs to handle)
- Consistent behavior across all features
- No imputation logic required in pipeline

✅ **You don't need imputation flexibility**
- Forward-fill is acceptable for all features
- Not experimenting with different strategies
- Want simple, predictable data

✅ **You're minimizing risk**
- Production forecasts must be reliable
- Can't afford pipeline failures
- Validated, proven data source

---

### Use `commodity.gold.unified_data_raw` (Experimental) if:

✅ **You're building a new model**
- Starting fresh, can design pipeline for NULLs
- Want to choose best imputation strategy per feature
- Can experiment without production risk

✅ **You want control over imputation strategy**
- Different features need different strategies (forward-fill, mean, interpolate)
- Want to experiment with imputation approaches
- Need per-model imputation flexibility

✅ **Your model handles NULLs natively**
- Tree models (XGBoost, Random Forest) can split on missingness
- Want to leverage "missing data" as a feature signal
- Missingness may be informative (e.g., weekends)

✅ **You want to leverage missingness indicators**
- Table includes `has_market_data`, `has_weather_data`, `has_gdelt_data` flags
- Can use flags as features (e.g., "is_weekend = !has_market_data")
- Explicit about what's missing vs. imputed

**Requirements if using `unified_data_raw`:**
- Must implement `ImputationTransformer` in your pipeline
- Must handle NULLs explicitly (or use model that handles them)
- Must validate performance vs. forward-filled baseline

---

## Why Migrate?

| Benefit | Silver | Gold | Improvement |
|---------|--------|------|-------------|
| **Row count** | ~75k rows | ~7k rows | 90% reduction |
| **Memory usage** | High | Low | 90% reduction |
| **Training speed** | Baseline | Faster | Data loading 90% faster |
| **Regional flexibility** | Fixed (exploded rows) | Flexible (arrays) | Models choose aggregation |
| **GDELT sentiment** | ❌ Not available | ✅ 7 theme groups | New feature source |
| **Query performance** | Slower (large scans) | Faster (smaller table) | 90% fewer rows to scan |
| **Imputation** | All forward-filled | Only `close` forward-filled | Models choose strategy |

---

## Schema Comparison

### Silver (Legacy)
```
Grain: (date, commodity, region)
Rows: ~75,000

Columns:
  date, commodity, region,           # Keys
  close, open, high, low, volume,    # Market data
  vix,                                # Volatility
  vnd_usd, cop_usd, ... (24 FX),     # Exchange rates
  temp_mean_c,                        # Weather (scalar, one region)
  precipitation_mm,
  humidity_mean_pct
```

### Gold (Recommended)
```
Grain: (date, commodity)
Rows: ~7,000

Columns:
  date, commodity,                    # Keys
  close, open, high, low, volume,     # Market data
  vix,                                # Volatility
  vnd_usd, cop_usd, ... (24 FX),     # Exchange rates
  weather_data,                       # ARRAY<STRUCT> - all regions
  gdelt_themes                        # ARRAY<STRUCT> - 7 theme groups
```

---

## Imputation Philosophy (CRITICAL CHANGE)

**Gold table only forward-fills `close` price. All other features preserve NULLs.**

### Why This Matters

**Silver (Legacy)**:
- All features forward-filled (VIX, FX, weather, etc.)
- Imputation strategy hard-coded in data layer
- Models cannot experiment with different imputation approaches

**Gold (New)**:
- Only `close` forward-filled (target variable = market state)
- All other features: NULL on weekends/holidays (~30% of rows)
- **Models choose imputation strategy** using `ImputationTransformer`

### Migration Requirement

**You must add imputation to your training pipeline:**

```python
# Option 1: Tree models (XGBoost) - no imputation needed
df = spark.table("commodity.gold.unified_data")
# XGBoost handles NULLs natively

# Option 2: Time series models (SARIMAX) - use ImputationTransformer
from forecast_agent.transformers import ImputationTransformer

df = spark.table("commodity.gold.unified_data")
imputer = ImputationTransformer(strategy='forward_fill')
df_imputed = imputer.transform(df)

# Option 3: Custom per-feature imputation (recommended)
imputer = ImputationTransformer(strategies={
    'vix': 'forward_fill',           # VIX changes slowly
    'cop_usd': 'mean',                # FX: use mean over window
    'temp_mean_c': 'interpolate',     # Weather: interpolate
    'open': 'forward_fill',           # OHLV: forward-fill from last trading day
    'high': 'forward_fill',
    'low': 'forward_fill',
    'volume': 'forward_fill'
})
df_imputed = imputer.transform(df)
```

### NULL Expectations

| Feature Type | NULL % | When NULL |
|--------------|--------|-----------|
| `close` | 0% | Never (forward-filled) |
| `open`, `high`, `low`, `volume` | ~30% | Weekends/holidays |
| `vix` | ~30% | Weekends/holidays |
| All FX rates (24 columns) | ~30% | Weekends/holidays |
| `weather_data` struct fields | Rare | Weather API gaps |
| `gdelt_themes` | ~73% | Days without articles |

---

## Migration Path

### Option 1: Simple Aggregation (Recommended for Tree-Based Models)

**Use case**: Models that don't need regional granularity (XGBoost, LightGBM, SARIMAX)

**Before (Silver)**:
```python
from pyspark.sql.functions import mean

# Manually aggregate regions (slow, memory intensive)
df = spark.table("commodity.silver.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1") \
    .groupBy("date", "commodity") \
    .agg(
        mean("close").alias("close"),
        mean("temp_mean_c").alias("avg_temp"),
        mean("precipitation_mm").alias("avg_precip")
    )
```

**After (Gold)**:
```python
from pyspark.sql.functions import expr

# Use pre-aggregated data (fast, low memory)
df = spark.table("commodity.gold.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1") \
    .select(
        "date",
        "commodity",
        "close",
        expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.temp_mean_c) / size(weather_data)").alias("avg_temp"),
        expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.precipitation_mm) / size(weather_data)").alias("avg_precip")
    )
```

### Option 2: Exploded Regional Features (For Regional Models)

**Use case**: Models that need per-region features (hierarchical models, attention mechanisms)

**Before (Silver)**:
```python
# Regions already exploded (75k rows)
df = spark.table("commodity.silver.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1")
# Each (date, commodity) has ~35 rows (one per region)
```

**After (Gold)**:
```python
from pyspark.sql.functions import explode

# Explode arrays on-demand (more flexible)
df = spark.table("commodity.gold.unified_data") \
    .filter("commodity = 'Coffee' AND is_trading_day = 1") \
    .select(
        "date",
        "commodity",
        "close",
        explode("weather_data").alias("weather")
    ) \
    .select(
        "date",
        "commodity",
        "close",
        "weather.region",
        "weather.temp_mean_c",
        "weather.precipitation_mm"
    )
```

### Option 3: Weighted Aggregation (Advanced)

**Use case**: Weight regions by production volume

**Gold only** (requires array operations):
```python
from pyspark.sql.functions import expr

# Define production weights per region (example)
production_weights = {
    "Sul_de_Minas": 0.35,
    "Cerrado": 0.25,
    "Mogiana": 0.20,
    # ... more regions
}

# Weighted average temperature
df = spark.table("commodity.gold.unified_data") \
    .filter("commodity = 'Coffee'") \
    .select(
        "date",
        "commodity",
        "close",
        expr(f"""
            aggregate(
                weather_data,
                0.0,
                (acc, w) -> acc + CASE
                    WHEN w.region = 'Sul_de_Minas' THEN w.temp_mean_c * {production_weights['Sul_de_Minas']}
                    WHEN w.region = 'Cerrado' THEN w.temp_mean_c * {production_weights['Cerrado']}
                    ELSE 0.0
                END
            )
        """).alias("weighted_temp")
    )
```

---

## GDELT Sentiment Features (New in Gold)

**Array structure**:
```sql
gdelt_themes: ARRAY<STRUCT<
  theme_group STRING,      -- SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER
  article_count INT,
  tone_avg DOUBLE,
  tone_positive DOUBLE,
  tone_negative DOUBLE,
  tone_polarity DOUBLE
>>
```

**⚠️ IMPORTANT - GDELT is NOT Forward-Filled**:
- Unlike prices/weather, **GDELT sentiment is NOT forward-filled** (it's time-sensitive)
- Days without news articles have `gdelt_themes = NULL`
- GDELT coverage: **2021-01-01 onwards** (~2,051 dates with articles out of ~7k total rows)
- Pre-2021 dates: Always `gdelt_themes = NULL`
- Your model must handle NULL sentiment (options: use 0s, interpolate, or ignore)
- Weather data IS forward-filled (covers full range 2015-07-07 to present)

**Usage**:
```python
from pyspark.sql.functions import expr, explode_outer

# Explode GDELT themes
df = spark.table("commodity.gold.unified_data") \
    .select(
        "date",
        "commodity",
        "close",
        explode_outer("gdelt_themes").alias("theme")
    ) \
    .select(
        "date",
        "commodity",
        "close",
        "theme.theme_group",
        "theme.article_count",
        "theme.tone_avg"
    )

# Or aggregate (e.g., mean tone across all themes)
# Use COALESCE to handle NULL arrays (days without articles)
agg_df = spark.table("commodity.gold.unified_data") \
    .select(
        "date",
        "commodity",
        "close",
        expr("""
            CASE
                WHEN gdelt_themes IS NULL THEN 0.0
                WHEN size(gdelt_themes) = 0 THEN 0.0
                ELSE aggregate(gdelt_themes, 0.0, (acc, t) -> acc + t.tone_avg) / size(gdelt_themes)
            END
        """).alias("avg_tone")
    )

# Or filter to only dates with GDELT data
gdelt_only_df = spark.table("commodity.gold.unified_data") \
    .filter("gdelt_themes IS NOT NULL AND size(gdelt_themes) > 0")
```

---

## Backward Compatibility

**Silver table will remain available** for:
- ✅ Existing models in production
- ✅ Regional analysis requiring explicit rows
- ✅ Legacy workflows that haven't migrated

**No breaking changes** - both tables are maintained.

---

## Migration Checklist

### For Existing Models

- [ ] Read DATA_CONTRACTS.md to understand gold schema
- [ ] Decide aggregation strategy (simple mean, weighted, regional)
- [ ] Update data loading code to use `commodity.gold.unified_data`
- [ ] Update feature engineering to use array operations
- [ ] Test with small date range to verify correctness
- [ ] Benchmark training speed (should be faster)
- [ ] Run backfill to compare forecast quality
- [ ] Update documentation/comments to reference gold table

### For New Models

- [ ] Start with `commodity.gold.unified_data` (don't use silver)
- [ ] Use array operations for weather/GDELT features
- [ ] Consider GDELT sentiment as additional signal
- [ ] Document which aggregation approach you chose

---

## Performance Tips

### ✅ DO
- Use `commodity.gold.unified_data` for new models
- Filter on `is_trading_day = 1` early to reduce rows further
- Use `aggregate()` SQL function for array operations (faster than UDFs)
- Explode arrays only when needed (not for simple aggregations)

### ❌ DON'T
- Join silver + gold (choose one)
- Explode arrays and then immediately re-aggregate (use aggregate() instead)
- Load entire table into pandas (use Spark for large date ranges)

---

## Example: Migrating SARIMAX Model

**Before (Silver)**:
```python
# ground_truth/models/sarimax_auto_weather.py

def get_training_data(spark, commodity, cutoff_date):
    # Group regions to get single time series
    df = spark.table("commodity.silver.unified_data") \
        .filter(f"commodity = '{commodity}' AND is_trading_day = 1") \
        .filter(f"date <= '{cutoff_date}'") \
        .groupBy("date") \
        .agg(
            first("close").alias("close"),
            mean("temp_mean_c").alias("temp"),
            mean("humidity_mean_pct").alias("humidity"),
            mean("precipitation_mm").alias("precip")
        ) \
        .orderBy("date")
    return df.toPandas()
```

**After (Gold)**:
```python
# ground_truth/models/sarimax_auto_weather.py

def get_training_data(spark, commodity, cutoff_date):
    from pyspark.sql.functions import expr

    # Use gold table with pre-aggregated data
    df = spark.table("commodity.gold.unified_data") \
        .filter(f"commodity = '{commodity}' AND is_trading_day = 1") \
        .filter(f"date <= '{cutoff_date}'") \
        .select(
            "date",
            "close",
            expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.temp_mean_c) / size(weather_data)").alias("temp"),
            expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.humidity_mean_pct) / size(weather_data)").alias("humidity"),
            expr("aggregate(weather_data, 0.0, (acc, w) -> acc + w.precipitation_mm) / size(weather_data)").alias("precip")
        ) \
        .orderBy("date")
    return df.toPandas()
```

**Performance gain**: 90% faster data loading (fewer rows to scan and group)

---

## Validation

After migrating, validate that forecasts are equivalent:

```bash
# Run validation script
python research_agent/infrastructure/tests/validate_gold_unified_data.py

# Compare silver vs gold query results
python research_agent/infrastructure/tests/compare_silver_gold_outputs.py
```

---

## Questions?

- **Schema details**: See [docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md)
- **Architecture**: See [UNIFIED_DATA_ARCHITECTURE.md](UNIFIED_DATA_ARCHITECTURE.md)
- **SQL source**: See [sql/create_gold_unified_data.sql](sql/create_gold_unified_data.sql)
- **Validation**: See [infrastructure/tests/validate_gold_unified_data.py](infrastructure/tests/validate_gold_unified_data.py)

---

**Last Updated**: 2025-12-06
**Owner**: Research Agent Team
