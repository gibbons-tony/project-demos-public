# Legacy Lambda Functions

**⚠️ DO NOT USE THESE FUNCTIONS - THEY ARE DEPRECATED**

## gdelt-silver-transform

**Moved to Legacy**: 2025-11-23  
**Reason**: Replaced by `gdelt-silver-backfill` for ALL silver processing

This function was previously used for daily incremental silver processing (EventBridge scheduled).  
It has been replaced by a unified approach where `gdelt-silver-backfill` handles BOTH:
- Historical backfill (1000+ dates)
- Daily incremental processing (via SQS)

**AWS Status**: Still deployed as `gdelt-silver-transform` but NOT USED  
**Can Delete**: After 30-day observation period

**If you need to update silver logic**:
- Update `/tmp/gdelt_silver_backfill_lambda.py`
- Deploy to `gdelt-silver-backfill`
- DO NOT update this legacy function

---

## Architecture Evolution

**Before (2025-11-22)**:
- `gdelt-silver-transform`: Daily incremental (EventBridge @ 3 AM UTC)
- `gdelt-silver-backfill`: Historical backfill only

**After (2025-11-23)**:
- `gdelt-silver-backfill`: ALL silver processing (SQS-triggered for both historical and daily)

**Benefits**:
- Single source of truth for silver logic
- Simpler deployment (one Lambda to maintain)
- Consistent processing for all dates
- Easier schema updates (only one function to update)
