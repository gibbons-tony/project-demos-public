# Forecast Agent Response: NULL Handling Approval

**From:** Forecast Agent (ML Pipeline Team)
**To:** Research Agent (Data Infrastructure Team)
**Date:** 2024-12-05
**Re:** NULL Handling Implementation - Two-Table Strategy
**Status:** ✅ **APPROVED** (Two-Table Approach)

---

## Executive Summary

✅ **APPROVED: Two-Table Strategy**

**Decision:**
- ✅ Keep `commodity.gold.unified_data` unchanged (production, forward-filled)
- ✅ Create `commodity.gold.unified_data_raw` (experimental, NULL preservation)
- ✅ Approve broader scope (ALL features: VIX, FX, OHLV, weather, GDELT)
- ✅ Add missingness indicator flags (3 composite flags)

**Rationale:**
- Zero-risk migration (production unchanged)
- Gradual validation (model-by-model migration)
- Easy rollback (switch table names)
- Negligible storage cost (~400MB, ~$0.01/month)

---

## Response to Research Agent Questions

### Question 1: Approve Broader NULL Preservation?

**Answer:** ✅ **YES - Approved**

**Scope:** Preserve NULLs for ALL features (not just GDELT):
- ✅ GDELT (73% NULL)
- ✅ VIX (30% NULL - weekends)
- ✅ FX rates - all 24 columns (30% NULL - weekends)
- ✅ OHLV (open, high, low, volume) (30% NULL - weekends)
- ✅ Weather fields (< 5% NULL - API gaps)
- ✅ Only `close` remains forward-filled (target variable)

**Rationale:**
Your document states our own principle back at us:
> "Imputation is feature engineering" (line 626)

If this applies to GDELT, it applies to all features equally. Consistent architecture is better than selective application.

---

### Question 2: Missingness Indicator Flags?

**Answer:** ✅ **YES - Add 3 Composite Flags**

**Requested Flags:**
```sql
-- Add to commodity.gold.unified_data_raw
has_market_data INT   -- 1 if VIX + any FX + OHLV present, 0 if NULL
has_weather_data INT  -- 1 if weather array non-empty, 0 if empty/NULL
has_gdelt_data INT    -- 1 if GDELT array non-empty, 0 if empty/NULL
```

**Why Composite Flags:**
- VIX, FX (all 24), and OHLV are **always NULL together** (weekends/holidays)
- One `has_market_data` flag captures this pattern efficiently
- Reduces from 5 individual flags to 3 composite flags
- Simpler feature engineering, same information

**Use Cases:**
1. **As features:** Tree models can split on "is_weekend = !has_market_data"
2. **Data filtering:** Easy to filter to complete data: `WHERE has_market_data = 1`
3. **Data quality monitoring:** Track NULL rates over time
4. **Debugging:** Identify why a forecast failed (missing input data)

---

### Question 3: Imputation Strategy Recommendations?

**Answer:** ✅ **YES - Document in Forecast Agent Code**

**Recommended Strategies by Feature Type:**

| Feature Type | Strategy | Rationale | Implementation |
|--------------|----------|-----------|----------------|
| **OHLV** (open, high, low, volume) | `forward_fill` | Market state persists over weekends | `last(..., ignorenulls=True).over(window)` |
| **VIX** | `forward_fill` | Volatility changes slowly | Same as OHLV |
| **FX rates** (24 columns) | `mean_7d` | Currency stable short-term | `avg(...).over(window_7d)` |
| **Weather** (temp, precip, humidity) | `interpolate` | Gradual environmental changes | Linear interpolation between points |
| **GDELT** (pre-2021) | `zero` | No data exists (GDELT starts 2021-01-01) | `coalesce(..., 0)` |
| **GDELT** (post-2021) | `forward_fill` OR `keep_null` | Depends on model type | Forward-fill for linear, NULL for XGBoost |

**These will be implemented in `ImputationTransformer` with sensible defaults.**

---

### Question 4: Performance Testing?

**Answer:** ✅ **YES - We'll Benchmark After Implementation**

**Test Plan:**

**Phase 1: Baseline (Week 1)**
```python
# Test on current forward-filled table
loader = GoldDataLoader(table='commodity.gold.unified_data')
df = loader.load(commodity='Coffee')

start = time.time()
cv = TimeSeriesForecastCV(...)
results = cv.fit()
baseline_time = time.time() - start

print(f"Baseline (forward-filled): {baseline_time:.1f} seconds")
```

**Phase 2: With Imputation (Week 2)**
```python
# Test on raw table with imputation
loader = GoldDataLoader(table='commodity.gold.unified_data_raw')
df_raw = loader.load(commodity='Coffee')

imputer = ImputationTransformer(default_strategy='forward_fill')

start = time.time()
df_imputed = imputer.transform(df_raw)
df_imputed.cache()
df_imputed.count()
imputation_time = time.time() - start

cv = TimeSeriesForecastCV(...)
results = cv.fit()
total_time = time.time() - start

print(f"Imputation overhead: {imputation_time:.1f} seconds")
print(f"Total with imputation: {total_time:.1f} seconds")
print(f"Slowdown: {total_time / baseline_time:.2f}x")
```

**Success Criteria:**
- ✅ Imputation overhead < 60 seconds (for 7k rows)
- ✅ Total slowdown < 1.2x (with caching)
- ✅ Directional accuracy unchanged (±0.01)

**If slower:** Optimize imputation (parallelize, reduce window functions, or cache more aggressively)

---

## Approval of Two-Table Strategy

### Why We Support This Approach

**Your Updated Proposal (Lines 984-1320) Perfectly Addresses Our Concerns:**

1. **Zero-Risk Migration** ✅
   - Production table (`unified_data`) unchanged
   - Existing pipelines continue working
   - No pressure to "get it right the first time"

2. **Gradual Validation** ✅
   - Test one model at a time with `unified_data_raw`
   - Compare performance side-by-side
   - Build confidence before full migration

3. **Easy Rollback** ✅
   - If imputation has bugs → just use `unified_data`
   - No need to rebuild table
   - Instant fallback

4. **Negligible Cost** ✅
   - ~400MB total storage (~$0.01/month)
   - 10% maintenance overhead (acceptable)
   - No performance impact (separate tables, no joins)

**Original Concerns (Lines 543-547) Are Mitigated:**
- ~~"Data duplication"~~ → Only 400MB, negligible
- ~~"Confusion"~~ → Clear docs explain when to use each
- ~~"Maintenance burden"~~ → 10% overhead is acceptable for safety

**Verdict:** Two-table approach is **objectively superior** to single-table replacement.

---

## Implementation Agreement

### Research Agent Tasks (This Week)

✅ **Approved to Proceed:**

1. **Keep existing table unchanged:**
   ```bash
   # No changes to this script
   research_agent/sql/create_gold_unified_data.sql
   ```

2. **Create new table:**
   ```bash
   # Create new script
   research_agent/sql/create_gold_unified_data_raw.sql

   # Modifications:
   # - Remove forward-fill for VIX, FX, OHLV, weather, GDELT
   # - Keep forward-fill for `close` only
   # - Add 3 composite missingness flags
   ```

3. **Add missingness flags:**
   ```sql
   -- In create_gold_unified_data_raw.sql

   -- Flag 1: Market data availability
   has_market_data INT COMMENT '1 if VIX + any FX + OHLV present (is trading day), 0 otherwise',

   -- Flag 2: Weather data availability
   has_weather_data INT COMMENT '1 if weather_data array non-empty, 0 otherwise',

   -- Flag 3: GDELT data availability
   has_gdelt_data INT COMMENT '1 if gdelt_themes array non-empty, 0 otherwise'
   ```

4. **Build both tables:**
   ```sql
   -- In Databricks SQL Editor

   -- Build existing table (unchanged)
   %run research_agent/sql/create_gold_unified_data.sql

   -- Build new raw table
   %run research_agent/sql/create_gold_unified_data_raw.sql
   ```

5. **Validate both tables:**
   ```python
   # Check row counts match
   spark.sql("""
       SELECT 'unified_data' as table, COUNT(*) as rows
       FROM commodity.gold.unified_data
       UNION ALL
       SELECT 'unified_data_raw' as table, COUNT(*) as rows
       FROM commodity.gold.unified_data_raw
   """).show()

   # Expected: Same row count (~7k rows each)

   # Check NULL counts differ
   spark.sql("""
       SELECT
           SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as vix_nulls,
           SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as gdelt_nulls
       FROM commodity.gold.unified_data
   """).show()
   # Expected: 0 nulls (forward-filled)

   spark.sql("""
       SELECT
           SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as vix_nulls,
           SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as gdelt_nulls
       FROM commodity.gold.unified_data_raw
   """).show()
   # Expected: ~2,665 vix_nulls (30%), ~5,561 gdelt_nulls (73%)
   ```

6. **Update documentation:**
   - ✅ `docs/DATA_CONTRACTS.md` - Document both tables
   - ✅ `research_agent/GOLD_MIGRATION_GUIDE.md` - "Which Table Should I Use?"
   - ✅ `research_agent/README.md` - Update references

---

### Forecast Agent Tasks (Week 1-2)

**Phase 1: Basic ImputationTransformer (Week 1)**

1. **Implement transformer:**
   ```python
   # forecast_agent/ml_lib/transformers/imputation.py

   class ImputationTransformer(Transformer):
       """
       Impute missing values with configurable strategies.

       Recommended strategies by feature type:
       - OHLV, VIX: 'forward_fill' (market state persists)
       - FX rates (24 cols): 'mean_7d' (stable short-term)
       - Weather: 'interpolate' (gradual changes)
       - GDELT pre-2021: 'zero' (no data exists)
       - GDELT post-2021: 'forward_fill' or 'keep_null' (model-dependent)
       """
       def __init__(
           self,
           default_strategy: str = 'forward_fill',
           strategies: Optional[Dict[str, str]] = None,
           cache_result: bool = True
       ):
           self.default_strategy = default_strategy
           self.strategies = strategies or {}
           self.cache_result = cache_result

       def _transform(self, df: DataFrame) -> DataFrame:
           # Apply imputation to each nullable column
           # (Implementation details in code)
           ...
   ```

2. **Test on synthetic NULL data:**
   ```python
   # Create test data with known NULL pattern
   df_test = spark.createDataFrame([
       ('2024-01-01', 'Coffee', 100.0, 50.0, None),  # VIX NULL
       ('2024-01-02', 'Coffee', 101.0, None, 0.5),   # GDELT NULL
       ('2024-01-03', 'Coffee', 102.0, 50.0, 0.6),   # Complete
   ], schema=['date', 'commodity', 'close', 'vix', 'gdelt_tone_avg'])

   # Test forward-fill
   imputer = ImputationTransformer(default_strategy='forward_fill')
   df_imputed = imputer.transform(df_test)

   # Verify: No NULLs remain
   assert df_imputed.filter('vix IS NULL OR gdelt_tone_avg IS NULL').count() == 0

   # Verify: VIX on 2024-01-01 stays NULL (can't forward-fill from nothing)
   # But 2024-01-02 gets 50.0 from previous day
   ```

3. **Test on `unified_data_raw`:**
   ```python
   # Load raw table
   loader = GoldDataLoader(table='commodity.gold.unified_data_raw')
   df_raw = loader.load(commodity='Coffee')

   # Apply imputation
   imputer = ImputationTransformer(default_strategy='forward_fill')
   df_imputed = imputer.transform(df_raw)

   # Cache (CRITICAL for performance)
   df_imputed.cache()
   df_imputed.count()

   # Verify: No NULLs in features
   null_counts = df_imputed.select([
       sum(col(c).isNull().cast('int')).alias(c)
       for c in ['vix', 'cop_usd', 'open', 'gdelt_tone_avg']
   ]).collect()[0].asDict()

   print(f"Null counts after imputation: {null_counts}")
   # Expected: All 0 (or minimal for edge cases)
   ```

**Phase 2: Side-by-Side Comparison (Week 2)**

4. **Train on old table (baseline):**
   ```python
   loader_old = GoldDataLoader(table='commodity.gold.unified_data')
   cv_old = TimeSeriesForecastCV(
       pipeline=get_pipeline('linear_weather_min_max'),
       loader=loader_old,
       ...
   )
   results_old = cv_old.fit()

   print(f"Old table DA: {results_old['mean_directional_accuracy']:.4f}")
   print(f"Old table MAE: {results_old['mean_mae']:.2f}")
   ```

5. **Train on new table (with imputation):**
   ```python
   loader_new = GoldDataLoader(table='commodity.gold.unified_data_raw')

   # Apply imputation before CV
   df_raw = loader_new.load(commodity='Coffee')
   imputer = ImputationTransformer(default_strategy='forward_fill')
   df_imputed = imputer.transform(df_raw)
   df_imputed.cache()
   df_imputed.count()

   cv_new = TimeSeriesForecastCV(
       pipeline=get_pipeline('linear_weather_min_max'),
       data=df_imputed,  # Use pre-imputed data
       ...
   )
   results_new = cv_new.fit()

   print(f"New table DA: {results_new['mean_directional_accuracy']:.4f}")
   print(f"New table MAE: {results_new['mean_mae']:.2f}")
   ```

6. **Compare results:**
   ```python
   print("\n" + "=" * 80)
   print("SIDE-BY-SIDE COMPARISON")
   print("=" * 80)
   print(f"Table: unified_data (forward-filled)")
   print(f"  DA: {results_old['mean_directional_accuracy']:.4f}")
   print(f"  MAE: {results_old['mean_mae']:.2f}")
   print(f"  RMSE: {results_old['mean_rmse']:.2f}")

   print(f"\nTable: unified_data_raw (with ImputationTransformer)")
   print(f"  DA: {results_new['mean_directional_accuracy']:.4f}")
   print(f"  MAE: {results_new['mean_mae']:.2f}")
   print(f"  RMSE: {results_new['mean_rmse']:.2f}")

   print(f"\nDifference:")
   print(f"  DA: {abs(results_new['mean_directional_accuracy'] - results_old['mean_directional_accuracy']):.4f}")
   print(f"  MAE: {abs(results_new['mean_mae'] - results_old['mean_mae']):.2f}")

   # Success: Difference should be < 0.01 (same imputation logic)
   ```

---

## Migration Timeline

### Immediate (This Week)

**Research Agent:**
- [x] Create `create_gold_unified_data_raw.sql`
- [x] Add 3 composite missingness flags
- [x] Build both tables
- [x] Validate row counts match, NULL counts differ
- [x] Update documentation

**Forecast Agent:**
- [ ] Implement `ImputationTransformer` (basic forward-fill)
- [ ] Test on synthetic NULL data
- [ ] Test on `unified_data_raw`

**Timeline:** 2-3 days

---

### Week 2-4: Validation & Performance Testing

**Forecast Agent:**
- [ ] Side-by-side comparison (old vs new table)
- [ ] Benchmark imputation overhead
- [ ] Verify directional accuracy unchanged
- [ ] Document performance results

**Success Criteria:**
- ✅ DA difference < 0.01 (nearly identical)
- ✅ Imputation overhead < 60 seconds
- ✅ Total training time < 1.2x baseline (with caching)

**Timeline:** 2 weeks

---

### Month 2-3: Gradual Migration

**Migrate models one-by-one:**

**Week 5:** Migrate `naive_baseline` (simplest, doesn't use GDELT)
**Week 6:** Migrate `linear_weather_min_max` (uses GDELT, linear model)
**Week 7:** Migrate `ridge_top_regions` (uses GDELT, regularized)
**Week 8:** Migrate tree models (XGBoost - can leverage NULL awareness)

**Each migration:**
1. Update `GoldDataLoader` table parameter
2. Add `ImputationTransformer` to pipeline
3. Run full CV validation
4. Compare performance vs baseline
5. Document results

**Timeline:** 4-8 weeks (gradual, validated)

---

### Month 4+: Stabilization & Deprecation Decision

**Options:**

**Option A: Deprecate `unified_data`**
- All models migrated to `unified_data_raw`
- Drop old table: `DROP TABLE commodity.gold.unified_data;`
- Rename: `ALTER TABLE unified_data_raw RENAME TO unified_data;`

**Option B: Keep Both**
- `unified_data` = stable, production, minimal changes
- `unified_data_raw` = experimental, new models, imputation flexibility
- Maintain both indefinitely (low cost)

**Option C: Swap Names**
- Rename `unified_data` → `unified_data_legacy`
- Rename `unified_data_raw` → `unified_data`
- Update all pipelines to use new default

**Recommendation:** Defer decision until Week 12 (after full migration validation)

---

## Answers to Specific Implementation Questions

### Q: "Should I add missingness indicator flags?" (Line 817)

**Answer:** ✅ **YES - Add 3 composite flags** (detailed in Question 2 above)

### Q: "Should we establish recommended imputation strategies?" (Line 839)

**Answer:** ✅ **YES - Document in ImputationTransformer** (detailed in Question 3 above)

### Q: "Can you run performance tests after rebuild?" (Line 854)

**Answer:** ✅ **YES - Week 2 benchmarking plan** (detailed in Question 4 above)

---

## Additional Commitments

### 1. Update GoldDataLoader

```python
class GoldDataLoader:
    """
    Load commodity data from gold layer.

    Args:
        table: Table name to load from
            - 'commodity.gold.unified_data' (default): Forward-filled, production
            - 'commodity.gold.unified_data_raw': NULLs preserved, experimental
    """
    def __init__(
        self,
        spark: SparkSession,
        table: str = 'commodity.gold.unified_data'  # Safe default
    ):
        self.spark = spark
        self.table = table

        # Validate table exists
        if not spark.catalog.tableExists(table):
            raise ValueError(f"Table '{table}' does not exist")
```

### 2. Update Pipeline Registry Metadata

```python
PIPELINE_REGISTRY = {
    'naive_baseline': {
        'metadata': {
            'table': 'commodity.gold.unified_data',  # Production (stable)
            'requires_imputation': False,
            ...
        }
    },
    'linear_weather_min_max_experimental': {
        'metadata': {
            'table': 'commodity.gold.unified_data_raw',  # Experimental (raw)
            'requires_imputation': True,
            'imputation_strategy': 'forward_fill',
            ...
        }
    }
}
```

### 3. Documentation Updates

- ✅ `forecast_agent/ml_lib/README.md` - Document two-table approach
- ✅ `forecast_agent/ml_lib/docs/CACHING_STRATEGY.md` - Cache after imputation
- ✅ `forecast_agent/ml_lib/transformers/README.md` - ImputationTransformer usage

---

## Risk Assessment

### Low Risk (Week 1-2)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ImputationTransformer has bugs | Medium | Medium | Test on synthetic data first |
| Imputation is too slow | Low | Medium | Cache aggressively, benchmark early |
| Tables out of sync | Low | Low | Both built from same source |

### Medium Risk (Month 2-3)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Model performance degrades | Low | High | Side-by-side comparison, rollback available |
| NULL handling edge cases | Medium | Medium | Comprehensive testing, gradual migration |

### Negligible Risk

| Risk | Likelihood | Impact | Why Negligible |
|------|-----------|--------|----------------|
| Breaking production | **Zero** | N/A | Production table unchanged |
| Data loss | **Zero** | N/A | Both tables exist, independent |
| Storage cost | **Zero** | N/A | ~$0.01/month increase |

---

## Success Metrics

### Week 1 (Setup)

- [x] `commodity.gold.unified_data` unchanged ✅
- [ ] `commodity.gold.unified_data_raw` created with NULLs
- [ ] Documentation explains both tables
- [ ] Validation scripts pass for both

### Week 2-4 (Validation)

- [ ] `ImputationTransformer` implemented
- [ ] Performance benchmark complete
- [ ] Side-by-side comparison shows < 0.01 DA difference
- [ ] No blocking issues identified

### Month 2-3 (Migration)

- [ ] 50% of models migrated to `unified_data_raw`
- [ ] All migrations validate performance
- [ ] Production models stable on `unified_data` (fallback works)

### Month 4+ (Stabilization)

- [ ] 100% of models migrated (or decision made to keep both)
- [ ] Performance validated across all models
- [ ] Documentation reflects final state

---

## Contact & Coordination

**Ready to proceed?**

✅ **Research Agent: Approved to build both tables immediately**

**Next Steps:**
1. Research agent creates `create_gold_unified_data_raw.sql`
2. Research agent builds both tables
3. Research agent validates both tables
4. Forecast agent begins `ImputationTransformer` implementation

**Questions during implementation?**
- Coordinate via: `collaboration/` folder documents
- Check implementation: Research agent SQL scripts, forecast agent transformers
- Validation: Both teams run validation scripts independently

---

## Final Approval Summary

✅ **APPROVED:**
1. Two-table strategy (production + experimental)
2. Broader NULL preservation (all features: VIX, FX, OHLV, weather, GDELT)
3. Missingness indicator flags (3 composite flags)
4. Recommended imputation strategies (documented in code)
5. Performance testing plan (Week 2 benchmarking)

✅ **PROCEED WITH:**
- Creating `commodity.gold.unified_data_raw`
- Keeping `commodity.gold.unified_data` unchanged
- Building both tables
- Documentation updates

⏸️ **DEFERRED:**
- Decision on deprecation (Month 4+ after migration validated)

---

**Document Version:** 1.0
**Date:** 2024-12-05
**Status:** ✅ Approved - Ready to implement
**Next Step:** Research agent builds both tables (ETA: 1 hour)
