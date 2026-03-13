# Unified Data NULL Handling: Agent Collaboration

**Topic:** NULL handling strategy for `commodity.gold.unified_data`
**Date:** 2024-12-05
**Participants:** Forecast Agent (ML Pipeline), Research Agent (Data Infrastructure)
**Status:** ✅ **IMPLEMENTATION COMPLETE** - Both tables live in production

**See:** `IMPLEMENTATION_COMPLETE.md` for full delivery summary

---

## Quick Summary

**Decision:** Create TWO gold layer tables instead of one
- ✅ `commodity.gold.unified_data` - Forward-filled (production, stable)
- ✅ `commodity.gold.unified_data_raw` - NULLs preserved (experimental, imputation in ML)

**Key Outcomes:**
1. Zero-risk migration (production unchanged)
2. Broader NULL preservation (VIX, FX, OHLV, weather, GDELT - not just GDELT)
3. Missingness indicator flags (3 composite flags added)
4. Gradual model-by-model migration over 2-3 months

---

## Discussion Flow

### 1. Initial Proposal (Forecast Agent)
**File:** `FORECAST_AGENT_NULL_HANDLING_STRATEGY.md`

**Proposed:** Preserve NULLs in GDELT data, move imputation to ML pipelines

**Two Phases:**
- Phase 1: Add `gdelt_data_available` flag (keep forward-fill)
- Phase 2: Preserve NULLs, imputation in ML pipelines

**Rationale:** "Imputation is feature engineering, not data engineering"

### 2. Research Agent Response (In Same File)
**File:** `FORECAST_AGENT_NULL_HANDLING_STRATEGY.md` (lines 570-1320)

**Key Points:**
- ✅ **ALREADY IMPLEMENTED** broader scope (not just GDELT!)
- ✅ Removed forward-fill for VIX, FX (24 cols), OHLV, weather, GDELT
- ✅ Only `close` price remains forward-filled (target variable)
- ✅ Fixed GDELT commodity name bug (lowercase → capitalized)
- ⚠️ Initially planned single-table replacement (risky)

**Then Added:** Two-table strategy recommendation (lines 984-1320)
- Safer: Keep `unified_data` unchanged, create `unified_data_raw`
- Gradual migration, easy rollback
- Negligible storage cost (~$0.01/month)

### 3. Forecast Agent Approval
**File:** `FORECAST_AGENT_RESPONSE_TO_NULL_HANDLING.md`

**Approved:**
- ✅ Two-table strategy
- ✅ Broader NULL preservation (all features)
- ✅ 3 composite missingness flags
- ✅ Recommended imputation strategies documented
- ✅ Performance testing plan (Week 2)

**Next Steps:**
- Research agent builds both tables
- Forecast agent implements `ImputationTransformer`
- Side-by-side validation (Week 2-4)
- Gradual migration (Month 2-3)

---

## Key Technical Decisions

### 1. Scope: All Features (Not Just GDELT)

**NULL Preservation:**
| Feature | Count | NULL Rate | Imputation Strategy |
|---------|-------|-----------|---------------------|
| GDELT | 1 array | ~73% | Zero pre-2021, forward-fill post-2021 |
| VIX | 1 column | ~30% | Forward-fill |
| FX rates | 24 columns | ~30% | Mean (7-day window) |
| OHLV | 4 columns | ~30% | Forward-fill |
| Weather | Array fields | <5% | Interpolate |
| **close** | 1 column | **0%** | **Forward-fill (target)** |

### 2. Missingness Flags (3 Composite)

```sql
-- Added to commodity.gold.unified_data_raw
has_market_data INT   -- 1 if VIX + FX + OHLV present (is trading day)
has_weather_data INT  -- 1 if weather array non-empty
has_gdelt_data INT    -- 1 if GDELT array non-empty
```

**Why composite:** VIX, FX, OHLV always NULL together (weekends), so one flag captures this.

### 3. Two-Table Strategy

**Table 1: `commodity.gold.unified_data`** (Production)
- All features forward-filled (existing behavior)
- Zero breaking changes
- Stable, proven data source

**Table 2: `commodity.gold.unified_data_raw`** (Experimental)
- Only `close` forward-filled (target variable)
- All other features preserve NULLs
- Requires `ImputationTransformer` in ML pipelines

**Benefits:**
- ✅ Zero-risk migration
- ✅ Gradual validation
- ✅ Easy rollback
- ✅ A/B testing capability

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| **Week 1** | Setup | ✅ **COMPLETE** |
| Research agent builds both tables | 26.5s (total) | ✅ **DONE** (Dec 5, 2024) |
| Research agent validates tables | 6 tests | ✅ **DONE** (All passed) |
| Forecast agent implements ImputationTransformer | 2-3 days | ✅ **DONE** (Already implemented) |
| **Week 2-4** | Validation | 📅 **READY TO START** |
| Side-by-side comparison | 1 week | 📅 Upcoming |
| Performance benchmarking | 1 week | 📅 Upcoming |
| **Month 2-3** | Migration | 📅 Future |
| Gradual model-by-model migration | 4-8 weeks | 📅 Future |
| **Month 4+** | Stabilization | 📅 Future |
| Decision: deprecate, keep both, or swap | TBD | 📅 Future |

---

## Related Documentation

**Research Agent:**
- `research_agent/sql/create_gold_unified_data.sql` - Existing table (forward-filled)
- `research_agent/sql/create_gold_unified_data_raw.sql` - New table (NULLs preserved)
- `research_agent/docs/GOLD_MIGRATION_GUIDE.md` - "Which Table Should I Use?"
- `docs/DATA_CONTRACTS.md` - Input contract documentation

**Forecast Agent:**
- `forecast_agent/ml_lib/transformers/imputation.py` - ImputationTransformer implementation
- `forecast_agent/ml_lib/docs/CACHING_STRATEGY.md` - Cache after imputation
- `forecast_agent/ml_lib/docs/EDGE_CASE_HANDLING.md` - NULL handling edge cases
- `forecast_agent/ml_lib/cross_validation/data_loader.py` - GoldDataLoader (table parameter)

---

## Key Quotes

> "Imputation is feature engineering, not data engineering"
> — Forecast Agent Proposal

> "If this principle applies to GDELT, it applies to all features equally"
> — Research Agent Response

> "The risks cited (data duplication, confusion, maintenance) are minor compared to the benefit of zero breaking changes"
> — Research Agent Two-Table Recommendation

> "Two-table approach is objectively superior to single-table replacement"
> — Forecast Agent Approval

---

## Success Metrics

**Week 1:** ✅ **ALL COMPLETE**
- [x] Both tables exist with same row count (7,612 rows) ✅
- [x] `unified_data` has 0 NULLs (forward-filled) ✅
- [x] `unified_data_raw` has ~30% NULLs in VIX/FX/OHLV, ~73% in GDELT ✅
- [x] Documentation updated ✅
- [x] DRY architecture implemented (production derives from raw) ✅
- [x] Validation suite passes all 6 tests ✅

**Week 2-4:**
- [ ] ImputationTransformer works on both tables
- [ ] Directional accuracy difference < 0.01 (old vs new)
- [ ] Imputation overhead < 60 seconds
- [ ] Total training time < 1.2x baseline (with caching)

**Month 2-3:**
- [ ] 50% of models migrated to `unified_data_raw`
- [ ] All migrations validate performance
- [ ] Production models stable on `unified_data`

---

## Lessons Learned

1. **Start with low-risk approach** - Two tables better than single table replacement
2. **Extend principles consistently** - If GDELT gets NULL preservation, all features should
3. **Cache after imputation** - Critical for performance (2-3x speedup)
4. **Gradual migration** - Model-by-model validation builds confidence
5. **Document decisions** - Clear "which table?" guidance prevents confusion

---

**Last Updated:** December 5, 2024
**Status:** ✅ **IMPLEMENTATION COMPLETE - PRODUCTION READY**
**Next Action:** Forecast agent integrates tables and validates performance (Week 2-4)

**See:** `IMPLEMENTATION_COMPLETE.md` for comprehensive delivery summary
