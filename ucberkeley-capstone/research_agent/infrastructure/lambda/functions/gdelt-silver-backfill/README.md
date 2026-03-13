# GDELT Silver Backfill Lambda

**AWS Function Name:** `gdelt-silver-backfill`
**Purpose:** Transforms Bronze parquet files into Silver wide-format aggregations
**Status:** ✅ PRODUCTION - Fixed 2025-11-23 23:45 UTC

---

## Overview

This lambda processes GDELT Bronze parquet files and creates Silver wide-format aggregations by date and commodity. It reads from S3 bronze storage, aggregates by article themes, and writes to S3 silver storage.

**Key Features:**
- Processes Bronze → Silver transformation
- Aggregates articles by 7 thematic groups (SUPPLY, DEMAND, PRICE, WEATHER, LOGISTICS, POLICY, MARKET)
- Calculates 5 metrics per group (count, tone_avg, tone_min, tone_max, tone_stddev)
- Chunks large date ranges (>30 files) for memory efficiency
- Updates DynamoDB tracking with SILVER_SUCCESS/SILVER_FAILED status

---

## Trigger

**SQS Queue:** `groundtruth-gdelt-silver-backfill-queue`
**Batch Size:** 1 message per invocation
**Message Format:**
```json
{
  "date": "2022-06-08",
  "commodity": "coffee"
}
```

---

## Critical Fix (2025-11-23)

**Bug:** Data type mismatch - count columns saved as pandas Int64 instead of numpy int64
**Error:** `[FAILED_READ_FILE.PARQUET_COLUMN_DATA_TYPE_MISMATCH] Expected Spark type double, actual Parquet type INT64`

**Fix Applied:**
```python
# Lines 652, 655, 722, 725
# Changed from:
df_wide[col] = df_wide[col].fillna(0).astype('int64')

# To:
df_wide[col] = df_wide[col].fillna(0).astype(np.int64)
```

**Result:** Count columns now properly saved as int64 (numpy), tone columns as float64

---

## Configuration

- **Memory:** 3008 MB
- **Timeout:** 900 seconds (15 minutes)
- **Runtime:** Python 3.11
- **Layers:** aws-sdk-pandas (awswrangler)
- **IAM Role:** Needs S3 read/write, DynamoDB read/write, SQS consume

---

## Helper Scripts

See `research_agent/infrastructure/scripts/` for testing and maintenance utilities:
- `clear_test_environment.py` - Clears S3/DynamoDB/SQS for testing
- `test_lambda.py` - Direct lambda invocation testing
- `check_silver_dtypes.py` - Verifies parquet data types
- `query_databricks_dtypes.py` - Checks Databricks schema
- `create_table_simple.py` - Recreates Databricks table

---

## Output Schema

**Table:** `commodity.silver.gdelt_wide`
**Columns:** 41 total (article_date, commodity, + 39 metrics)

| Column Type | Example | Data Type |
|-------------|---------|-----------|
| Partition keys | `article_date`, `commodity` | DATE, STRING |
| Count metrics | `group_SUPPLY_count` | BIGINT (int64) |
| Tone metrics | `group_SUPPLY_tone_avg` | DOUBLE (float64) |

**Groups:** SUPPLY, DEMAND, PRICE, WEATHER, LOGISTICS, POLICY, MARKET, ALL
**Metrics per group:** count, tone_avg, tone_min, tone_max, tone_stddev

---

## Testing Procedure

1. Clear test environment: `python scripts/clear_test_environment.py`
2. Test lambda: `python scripts/test_lambda.py`
3. Verify data types: `python scripts/check_silver_dtypes.py`
4. Check Databricks: `python scripts/query_databricks_dtypes.py`

See `research_agent/infrastructure/scripts/README.md` for complete workflow.

---

## Documentation

- **Reference Guide:** `research_agent/infrastructure/docs/GDELT_LAMBDA_REFERENCE_GUIDE.md`
- **Databricks Query Guide:** `research_agent/infrastructure/docs/DATABRICKS_GDELT_QUERY_GUIDE.md`
- **Active Components:** `research_agent/infrastructure/ACTIVE_COMPONENTS.md`

---

**Last Updated:** 2025-11-23
**Deployed Version:** 2025-11-23 23:45:48 UTC
