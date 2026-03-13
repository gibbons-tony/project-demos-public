# Warnings & Critical Issues

Last Updated: 2025-11-07

## Active Warnings

### GDELT Data Coverage is Sparse (2025-11-07)

**Severity**: Medium

**Issue**: GDELT data has very limited coverage - only 32 unique days across 3 years:
- 2021: 1 day (Jan 1)
- 2023: 3 days (Sept 30, Oct 8, Oct 16)
- 2025: 28 days (Oct 5 - Nov 2)

**Impact**: GDELT sentiment/news data likely has minimal impact on forecasting models.

**Recommendation**: Consider whether to include GDELT in training data or exclude it entirely.

**Data Issues**:
- Date column is STRING type (`YYYYMMDDHHmmss`) instead of proper DATE
- Missing entire years (2022, 2024)
- Total: 114,221 events across 32 days

---

### CRITICAL: Weather v2 Backfill Bug Found (2025-11-08)

**Severity**: CRITICAL

**Status**: Bug fixed, re-backfill required

**Issue**: Discovered critical bug in weather v2 backfill script that caused data loss:
- Script processed regions sequentially and wrote each region's data to the same S3 path
- Each region OVERWROTE the previous region's data for the same date
- Result: Only 1 region's data per date instead of all 67 regions
- Current S3 data has only 3,775 records (1 per date) instead of 252,425 records (67 regions × 3,775 dates)

**Root Cause**:
- `backfill_region_date_range()` called `write_to_s3()` per region
- All regions wrote to `s3://.../year=X/month=Y/day=Z/data.jsonl` (same key)
- No append logic - each write overwrote previous data

**Fix Applied**:
- Modified script to collect ALL regions' data first
- Group by date across ALL regions
- Write once per date with all 67 regions included
- File: `research_agent/infrastructure/backfill_historical_weather_v2.py`

**Action Required**:
1. Clear bad S3 data: `s3://groundtruth-capstone/landing/weather_v2/`
2. Re-run backfill with fixed script (estimated 3-7 hours)
3. Create weather_v2 bronze table
4. Proceed with unified_data update

**Timeline**:
- Bug discovered: 2025-11-08
- Fix committed: 2025-11-08
- Re-backfill: Pending (waiting for confirmation)
- Bronze table creation: Blocked
- unified_data update: Blocked
- Model retraining: Blocked

**Impact**: All weather v2 work blocked until re-backfill completes. Bronze table created with bad data (only 3,775 rows with 4 regions).

---

## Resolved Warnings

(Archive resolved warnings here)
