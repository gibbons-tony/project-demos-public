# GDELT Pipeline - Active Components

**Last Updated:** 2025-11-23 23:50 UTC

This document identifies which components are actively used in production vs. legacy/experimental.

**⚠️ CRITICAL:** Only 3 lambdas are active. gdelt-silver-transform is DEPRECATED.

---

## ✅ ACTIVE LAMBDA FUNCTIONS (Currently Used in Production)

### Daily Incremental Pipeline (Production)

1. **gdelt-daily-discovery** ✅ IN USE
   - **Location:** `lambda/functions/gdelt-daily-discovery/`
   - **Deployed Name:** `gdelt-daily-discovery`
   - **Purpose:** Discovers new GDELT files daily by streaming master list
   - **Trigger:** EventBridge schedule (2 AM UTC daily)
   - **Status:** ✅ PRODUCTION - Fixed Nov 22 (streaming optimization)
   - **Code:** `lambda_function.py`

2. **gdelt-csv-bronze-direct** ✅ IN USE
   - **Location:** `lambda/functions/gdelt-csv-bronze-direct/`
   - **Deployed Name:** `gdelt-bronze-transform`
   - **Purpose:** Downloads CSV from GDELT, filters, writes Bronze Parquet, queues dates to silver
   - **Trigger:** SQS queue `groundtruth-gdelt-backfill-queue`
   - **Status:** ✅ PRODUCTION - Updated Nov 22 (added silver queue loading)
   - **Code:** `lambda_function.py`
   - **Note:** Deployed to AWS function name `gdelt-bronze-transform`

3. **gdelt-silver-backfill** ✅ IN USE - ✅ **FIXED**
   - **Location:** `lambda/functions/gdelt-silver-backfill/`
   - **Deployed Name:** `gdelt-silver-backfill`
   - **Purpose:** ALL silver processing (Bronze → Silver wide format)
   - **Trigger:** SQS queue `groundtruth-gdelt-silver-backfill-queue`
   - **Status:** ✅ WORKING - Data type bug fixed 2025-11-23 23:45 UTC
   - **Code:** `lambda_function.py`
   - **Last Modified:** 2025-11-23 23:45:48 UTC
   - **Memory:** 3008 MB | **Timeout:** 900s
   - **Event Source Mapping:** ENABLED (batch_size=1)
   - **Chunking:** >30 files (lowered from 50)
   - **Fix Applied:** Changed `.astype('int64')` to `.astype(np.int64)` for numpy types
   - **Databricks:** Table recreated with BIGINT for counts, DOUBLE for tones
   - **Helper Scripts:** See `research_agent/infrastructure/scripts/README.md`

### ❌ DEPRECATED - No Longer Used

4. **gdelt-silver-transform** ❌ DEPRECATED
   - **Location:** `lambda/functions/gdelt-silver-transform/` (moved to legacy)
   - **Deployed Name:** `gdelt-silver-transform` (still deployed but NOT USED)
   - **Replaced By:** gdelt-silver-backfill
   - **Last Modified:** 2025-11-23 19:06 UTC
   - **Status:** ❌ **DO NOT USE** - Replaced by unified silver lambda
   - **Can Delete:** After 30-day observation period

5. **gdelt-silver-discovery** ❓ STATUS UNCLEAR
   - **Location:** `lambda/functions/gdelt-silver-discovery/`
   - **Deployed Name:** `gdelt-silver-discovery`
   - **Purpose:** Scans DynamoDB for bronze files without silver status, queues dates
   - **Last Modified:** 2025-11-22 21:21 UTC
   - **Status:** ❓ **NOT CURRENTLY USED** - No schedule configured
   - **Note:** Might be needed for backfill trigger

### ⏸️ COMPLETED - Historical Backfill

6. **gdelt-bronze-transform** (JSONL mode) ⏸️ COMPLETE
   - **Location:** `lambda/functions/gdelt-bronze-transform/`
   - **Deployed Name:** `gdelt-jsonl-bronze-transform`
   - **Purpose:** Historical backfill - JSONL → Bronze Parquet
   - **Status:** ⏸️  COMPLETE - Backfill finished (168,704 files processed)
   - **Code:** `lambda_function.py`
   - **Note:** Can be re-enabled if historical backfill needed

---

## ACTIVE EVENTBRIDGE SCHEDULES

| Rule Name | Schedule | Target Lambda | Status |
|-----------|----------|---------------|--------|
| `gdelt-daily-discovery-schedule` | `cron(0 2 * * ? *)` | gdelt-daily-discovery | ✅ ENABLED |
| `gdelt-daily-silver-transform` | `cron(0 3 * * ? *)` | gdelt-silver-transform | ✅ DISABLED (deprecated) |

---

## ACTIVE SQS QUEUES & TRIGGERS

| Queue Name | Triggered Lambda | Status | Purpose |
|------------|-----------------|--------|---------|
| `groundtruth-gdelt-backfill-queue` | gdelt-bronze-transform | ✅ ENABLED | Daily CSV→Bronze |
| `groundtruth-gdelt-silver-backfill-queue` | gdelt-silver-backfill | ✅ ENABLED | Backfill Bronze→Silver |

---

## LEGACY/EXPERIMENTAL COMPONENTS (Not in Production)

Moved to: `infrastructure/legacy/`

### Legacy Lambda Functions

1. **berkeley-datasci210-capstone-processor**
   - Old GDELT processor (replaced by modular pipeline)
   - Location: `legacy/lambda_functions/berkeley-datasci210-capstone-processor/`

2. **gdelt-csv-sqs-loader**
   - Experimental SQS loader (not used)
   - Location: `legacy/lambda_functions/gdelt-csv-sqs-loader/`

3. **gdelt-generate-date-batches**
   - Experimental batch date generator (not used)
   - Location: `legacy/lambda_functions/gdelt-generate-date-batches/`
   - Deployed in AWS but not actively used

4. **gdelt-jsonl-to-silver**
   - Old JSONL→Silver direct converter (replaced by gdelt-silver-transform)
   - Location: `legacy/lambda_functions/gdelt-jsonl-to-silver/`

5. **gdelt-queue-monitor**
   - Monitoring utility (not actively used)
   - Location: `legacy/lambda_functions/gdelt-queue-monitor/`
   - Deployed in AWS but not actively used

### Legacy Step Functions

All Step Functions are **DISABLED** in favor of EventBridge scheduled Lambdas:

1. **gdelt_bronze_silver_pipeline.json**
   - Old orchestration approach
   - Location: `legacy/step_functions/gdelt_bronze_silver_pipeline.json`

2. **gdelt_daily_incremental_pipeline.json**
   - Experimental daily orchestration
   - Location: `legacy/step_functions/gdelt_daily_incremental_pipeline.json`

3. **gdelt_daily_master_pipeline.json**
   - Experimental master pipeline
   - Location: `legacy/step_functions/gdelt_daily_master_pipeline.json`

4. **groundtruth_gdelt_backfill_sqs.json**
   - Old SQS backfill approach
   - Location: `legacy/step_functions/groundtruth_gdelt_backfill_sqs.json`

5. **groundtruth_gdelt_backfill_with_bronze_silver.json**
   - Old backfill orchestration
   - Location: `legacy/step_functions/groundtruth_gdelt_backfill_with_bronze_silver.json`

---

## DEPLOYMENT SCRIPTS (Active)

| Script | Purpose | Status |
|--------|---------|--------|
| `lambda/deploy_bronze_transform.sh` | Deploy CSV→Bronze Lambda | ✅ ACTIVE |
| `lambda/deploy_jsonl_bronze_transform.sh` | Deploy JSONL→Bronze Lambda | ⏸️  Used for backfill |
| `step_functions/deploy_gdelt_pipeline.sh` | Deploy Step Function | ❌ NOT USED |
| `step_functions/deploy_daily_master.sh` | Deploy daily master SF | ❌ NOT USED |

---

## CURRENT ARCHITECTURE (Active Production System)

```
┌─────────────────────────────────────────────────────────────────┐
│ DAILY INCREMENTAL PIPELINE (Active)                            │
└─────────────────────────────────────────────────────────────────┘

EventBridge (2 AM UTC)
    ↓
gdelt-daily-discovery
    ↓ (SQS: groundtruth-gdelt-backfill-queue)
gdelt-bronze-transform (CSV→Bronze)
    ↓ (1 hour gap)
EventBridge (3 AM UTC)
    ↓
gdelt-silver-transform (Bronze→Silver)


┌─────────────────────────────────────────────────────────────────┐
│ HISTORICAL BACKFILL PIPELINE (One-time, 98.9% complete)        │
└─────────────────────────────────────────────────────────────────┘

SQS Queue (groundtruth-gdelt-silver-backfill-queue)
    ↓
gdelt-silver-backfill (Bronze→Silver for 1,767 dates)
```

---

## FILES TO IGNORE

These files are in the repo but not actively used:

- `infrastructure/legacy/` - All legacy Lambda functions and Step Functions
- `lambda/functions/berkeley-datasci210-capstone-processor/` - Old processor
- Any Step Function JSON files (using EventBridge instead)

---

## FILES TO MAINTAIN

These are the core active components:

**Lambda Functions:**
- `lambda/functions/gdelt-daily-discovery/lambda_function.py`
- `lambda/functions/gdelt-csv-bronze-direct/lambda_function.py`
- `lambda/functions/gdelt-silver-backfill/lambda_function.py` (ALL silver processing)
- `lambda/functions/gdelt-bronze-transform/lambda_function.py` (JSONL mode for backfill)

**Helper Scripts:**
- `scripts/clear_test_environment.py`
- `scripts/test_lambda.py`
- `scripts/check_silver_dtypes.py`
- `scripts/query_databricks_dtypes.py`
- `scripts/create_table_simple.py`

**Deployment Scripts:**
- `lambda/deploy_bronze_transform.sh` (for CSV→Bronze)
- `lambda/deploy_jsonl_bronze_transform.sh` (for historical backfill)

**Documentation:**
- `docs/GDELT_LAMBDA_REFERENCE_GUIDE.md` - Lambda reference and testing procedures
- `docs/DATABRICKS_GDELT_QUERY_GUIDE.md` - Databricks query guide
- `scripts/README.md` - Helper scripts documentation
- `ACTIVE_COMPONENTS.md` - This file (active vs legacy components)

---

**Next Action:** Monitor tonight's daily pipeline run (2-3 AM UTC) to verify end-to-end operation
