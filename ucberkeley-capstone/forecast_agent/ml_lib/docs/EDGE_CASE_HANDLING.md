# Edge Case Handling in Transformers

**Concern:** Transformers handle array-based data (weather regions, GDELT themes). Need to ensure they handle missing data, empty arrays, and nulls gracefully at scale.

---

## Current Edge Case Coverage

### Weather Transformers

#### WeatherAggregator

**Handles:**
- ✅ Null arrays: Uses `COALESCE(aggregate(...), 0.0)` to default to 0
- ✅ Empty arrays: `aggregate([]) = NULL`, then coalesced to 0
- ✅ Nulls within struct: Field-level null handling in aggregation

**Example:**
```python
# If weather_data is NULL or empty
df.withColumn(
    "weather_temp_mean_c_min",
    expr(f"""
        COALESCE(
            aggregate({input_col}, NULL, (acc, x) ->
                CASE WHEN acc IS NULL OR x.temp_mean_c < acc
                THEN x.temp_mean_c ELSE acc END
            ),
            0.0  -- Default for null/empty arrays
        )
    """)
)
```

**Potential Issues:**
- ⚠️ Default to 0.0 might not be semantically correct for temperature
- ⚠️ Empty arrays could indicate data quality issues (should we filter?)

**Improvements Needed:**
```python
# Option 1: Use global mean instead of 0
global_temp_mean = df.select(avg("weather_temp_mean_c_min")).collect()[0][0]
df.withColumn(..., coalesce(..., lit(global_temp_mean)))

# Option 2: Forward-fill from previous day
window = Window.partitionBy("commodity").orderBy("date")
df.withColumn(...,
    coalesce(weather_col, last(weather_col, ignorenulls=True).over(window))
)

# Option 3: Mark as missing and handle in VectorAssembler
df.withColumn("has_weather_data", when(weather_col.isNull(), 0).otherwise(1))
```

#### WeatherRegionSelector

**Handles:**
- ✅ Missing regions: Returns NULL if region not found
- ✅ Nulls in fields: Per-field null handling
- ⚠️ Typos in region names: Will silently return NULL (no error)

**Improvement Needed:**
```python
# Validate regions exist in data before transforming
available_regions = df.select(
    explode("weather_data.region").alias("region")
).distinct().collect()

available_region_set = {row['region'] for row in available_regions}

for region in requested_regions:
    if region not in available_region_set:
        raise ValueError(f"Region '{region}' not found in data. Available: {available_region_set}")
```

### GDELT Transformers

#### GdeltAggregator

**Handles:**
- ✅ Null arrays: Returns 0.0 for metrics
- ✅ Empty arrays: Same as null (coalesced to 0)
- ✅ Division by zero: `NULLIF(total_articles, 0)` prevents divide-by-zero

**Example:**
```python
df.withColumn(
    "gdelt_tone_avg",
    expr(f"""
        aggregate({input_col}, 0D, (acc, x) -> acc + (x.tone_avg * x.article_count))
        / NULLIF(gdelt_total_articles, 0)  -- Safe division
    """)
)
```

**Potential Issues:**
- ⚠️ Zero articles might indicate missing data vs no news
- ⚠️ Should we differentiate "no data" from "no news"?

**Improvement:**
```python
# Add data quality flag
df.withColumn(
    "gdelt_data_available",
    when(size("gdelt_themes") > 0, 1).otherwise(0)
)

# Include in features
VectorAssembler(
    inputCols=weather_features + gdelt_features + ["gdelt_data_available"],
    ...
)
```

---

## VectorAssembler Edge Cases

**Current Configuration:**
```python
VectorAssembler(
    inputCols=all_features,
    outputCol="features",
    handleInvalid="skip"  # ✅ Skips rows with nulls/NaNs
)
```

**Handles:**
- ✅ Null values: Rows skipped entirely
- ✅ NaN values: Rows skipped
- ✅ Inf values: Rows skipped

**Trade-off:**
- 👍 Models never see invalid data
- 👎 Silently drops rows (could lose significant data)

**Improvement:**
```python
# Track how many rows are dropped
before_count = df.count()
assembled = assembler.transform(df)
after_count = assembled.count()

dropped_rows = before_count - after_count
dropped_pct = (dropped_rows / before_count) * 100

if dropped_pct > 5:
    raise ValueError(
        f"VectorAssembler dropped {dropped_pct:.1f}% of rows ({dropped_rows:,}/{before_count:,}). "
        f"Check for missing feature data."
    )
```

---

## Recommended Validation Checks

### Pre-Training Validation

Add to `TimeSeriesForecastCV` or `GoldDataLoader`:

```python
def validate_feature_quality(df: DataFrame, required_cols: List[str]) -> Dict[str, float]:
    """
    Validate feature data quality before training.

    Returns:
        Dict with null percentages, empty array counts, etc.
    """
    total_rows = df.count()

    stats = {}

    # Check null percentages
    for col in required_cols:
        null_count = df.filter(f"{col} IS NULL").count()
        stats[f"{col}_null_pct"] = (null_count / total_rows) * 100

    # Check weather array sizes
    weather_empty = df.filter("size(weather_data) = 0 OR weather_data IS NULL").count()
    stats['weather_empty_pct'] = (weather_empty / total_rows) * 100

    # Check GDELT array sizes
    gdelt_empty = df.filter("size(gdelt_themes) = 0 OR gdelt_themes IS NULL").count()
    stats['gdelt_empty_pct'] = (gdelt_empty / total_rows) * 100

    # Warn if significant missing data
    for key, value in stats.items():
        if value > 10:
            print(f"⚠️  WARNING: {key} = {value:.1f}% (threshold: 10%)")

    return stats
```

### Post-Transform Validation

Add to transformers:

```python
def validate_output_schema(self, df: DataFrame, expected_cols: List[str]):
    """Verify all expected columns were created."""
    missing = [col for col in expected_cols if col not in df.columns]

    if missing:
        raise ValueError(
            f"Transformer failed to create columns: {missing}. "
            f"Check input data quality."
        )
```

---

## Scale Performance Considerations

### Array Operations at Scale

**Current:** Using Spark SQL `aggregate()` function for array operations.

**Performance:**
- ✅ Native Spark function (optimized)
- ✅ Runs in parallel across partitions
- ✅ No Python UDFs (avoids serialization overhead)

**Potential Bottleneck:** If arrays are very large (100+ regions), consider:

```python
# Option 1: Pre-filter arrays to top N regions
df.withColumn(
    "top_weather_regions",
    expr("""
        slice(
            sort_array(weather_data, false),  -- Sort by some metric
            1, 20  -- Take top 20
        )
    """)
)

# Option 2: Sample arrays for faster aggregation
df.withColumn(
    "sampled_weather",
    expr("filter(weather_data, x -> rand() < 0.5)")  # 50% sample
)
```

### Memory Considerations

**Issue:** Wide DataFrames (100+ feature columns) can cause memory pressure.

**Solution:**
```python
# Cache after feature engineering but before model training
df_with_features = pipeline_stages[:3].fit(df).transform(df)
df_with_features.cache()  # Persist computed features
df_with_features.count()  # Materialize cache

# Train model on cached features
model = pipeline_stages[3].fit(df_with_features)
```

### Skewed Partitions

**Issue:** Some commodities have more data than others (e.g., Coffee vs Cocoa).

**Solution:**
```python
# Repartition by commodity for even distribution
df = df.repartition("commodity")

# Or use coalesce to reduce partitions after filtering
df_filtered = df.filter("commodity = 'Coffee'")
df_filtered = df_filtered.coalesce(10)  # Reduce to 10 partitions
```

---

## Testing Strategy

### Unit Tests for Edge Cases

```python
def test_weather_aggregator_null_array():
    """Test that null weather arrays don't break aggregation."""
    data = [
        ("2024-01-01", "Coffee", None),  # Null array
        ("2024-01-02", "Coffee", []),    # Empty array
        ("2024-01-03", "Coffee", [...])  # Valid array
    ]

    df = spark.createDataFrame(data, schema=...)
    transformer = WeatherAggregator()
    result = transformer.transform(df)

    # Verify no nulls in output
    assert result.filter("weather_temp_mean_c_min IS NULL").count() == 0

def test_gdelt_aggregator_zero_articles():
    """Test that zero articles doesn't cause divide-by-zero."""
    data = [
        ("2024-01-01", "Coffee", [
            {"theme_group": "SUPPLY", "article_count": 0, "tone_avg": 0.5}
        ])
    ]

    df = spark.createDataFrame(data, schema=...)
    transformer = GdeltAggregator()
    result = transformer.transform(df)

    # Verify output is valid (not NaN/Inf)
    tone_values = result.select("gdelt_tone_avg").collect()
    assert all(not math.isnan(row[0]) and not math.isinf(row[0]) for row in tone_values)
```

---

## Current Status

**Weather Transformers:**
- ✅ Null handling implemented
- ✅ Empty array handling implemented
- ⚠️ Validation warnings needed
- ⚠️ Better default values (use mean instead of 0)

**GDELT Transformers:**
- ✅ Null handling implemented
- ✅ Division by zero prevented
- ⚠️ Differentiate "no data" from "no news"

**VectorAssembler:**
- ✅ `handleInvalid="skip"` configured
- ⚠️ Need to track dropped rows
- ⚠️ Alert if >5% of data is dropped

---

## Action Items

1. **Add validation to GoldDataLoader:**
   - Check null percentages for critical columns
   - Warn if weather/GDELT arrays are empty for >10% of rows
   - Log data quality summary before training

2. **Improve default values in transformers:**
   - Use global mean instead of 0.0 for temperature
   - Forward-fill from previous day if available
   - Add `has_data` flags to indicate missing data

3. **Add unit tests for edge cases:**
   - Null arrays
   - Empty arrays
   - Division by zero
   - Skewed partitions

4. **Monitor row drops in VectorAssembler:**
   - Log before/after counts
   - Alert if >5% of rows are dropped
   - Investigate root cause of nulls

---

**Status:** Documentation complete, implementation updates needed
**Priority:** High (affects model training reliability)
**Estimated Effort:** 4 hours (2 hours implementation + 2 hours testing)
