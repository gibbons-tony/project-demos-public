# GDELT Infrastructure Helper Scripts

Utility scripts for testing, debugging, and maintaining GDELT infrastructure.

**Location:** `research_agent/infrastructure/scripts/`

---

## Lambda Testing & Deployment

### 1. `clear_test_environment.py`

**Purpose:** Clear test environment before testing silver lambda

**What it does:**
1. Deletes S3 silver files
2. Deletes DynamoDB SILVER_* tracking entries
3. Purges SQS queue

**Usage:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/clear_test_environment.py
```

**When to use:** Before testing silver lambda with a fresh test date

---

### 2. `test_lambda.py`

**Purpose:** Test gdelt-silver-backfill lambda with direct invocation

**What it does:**
- Invokes lambda with date parameter (direct mode, not SQS)
- Returns processing stats (bronze records, silver rows, columns)

**Usage:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/test_lambda.py
```

**Default test date:** 2022-06-08 (edit script to change)

**When to use:** After deploying lambda to verify it works

---

### 3. `check_silver_dtypes.py`

**Purpose:** Verify parquet file data types are correct

**What it does:**
- Reads silver parquet files from S3
- Checks count columns are int64
- Checks tone columns are float64
- Reports any type mismatches

**Usage:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/check_silver_dtypes.py
```

**Expected output:**
```
✅ TEST PASSED
  - All 22 count columns are int64
  - All 88 tone columns are float64
  - group_ALL columns exist (5 found)
```

**When to use:** After lambda processes data, to verify types before Databricks query

---

## Databricks Table Management

### 4. `query_databricks_dtypes.py`

**Purpose:** Check Databricks table schema and test queries

**What it does:**
- Connects to Databricks
- Shows table schema (column names and types)
- Attempts to query data
- Reports any type mismatch errors

**Usage:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/query_databricks_dtypes.py
```

**When to use:** To diagnose Databricks type mismatch errors

---

### 5. `create_table_simple.py`

**Purpose:** Create/recreate Databricks table with correct schema

**What it does:**
1. Drops existing `commodity.silver.gdelt_wide` table
2. Creates new table using PARQUET format (auto-discovers schema)
3. Verifies count columns are BIGINT
4. Tests query to confirm it works

**Usage:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/create_table_simple.py
```

**When to use:**
- After fixing lambda data type bug
- When Databricks table schema is wrong
- To recreate table from parquet files

---

### 6. `create_fillforward_table.py`

**Purpose:** Create forward-filled GDELT table with continuous daily data

**What it does:**
1. Reads SQL from `databricks/create_gdelt_fillforward.sql`
2. Creates `commodity.silver.gdelt_wide_fillforward` table with:
   - Every date-commodity combination (continuous daily series)
   - Count columns set to 0 for missing dates
   - Tone columns forward-filled from previous date
3. Verifies table creation with row count query

**Usage:**
```bash
source venv/bin/activate
export DATABRICKS_TOKEN=dapi...  # Set your Databricks token
python research_agent/infrastructure/scripts/create_fillforward_table.py
```

**When to use:**
- To create forecasting-ready continuous time series
- When you need gap-free daily data for each commodity

**SQL Location:** `research_agent/infrastructure/databricks/create_gdelt_fillforward.sql`

**Columns:**
- 2 metadata: article_date, commodity
- 22 count columns: COALESCE to 0 for missing dates
- 88 tone columns: Forward-filled using LAST_VALUE window function

---

## Complete Testing Workflow

**Scenario: Testing silver lambda after code changes**

```bash
# 1. Deploy lambda
cd /tmp
zip gdelt_silver_backfill.zip gdelt_silver_backfill_lambda.py
aws lambda update-function-code \
  --function-name gdelt-silver-backfill \
  --zip-file fileb://gdelt_silver_backfill.zip \
  --region us-west-2

# Wait for deployment
aws lambda wait function-updated \
  --function-name gdelt-silver-backfill \
  --region us-west-2

# 2. Clear test environment
source venv/bin/activate
python research_agent/infrastructure/scripts/clear_test_environment.py

# 3. Test lambda
python research_agent/infrastructure/scripts/test_lambda.py

# 4. Verify data types
python research_agent/infrastructure/scripts/check_silver_dtypes.py

# 5. Fix Databricks table (if needed)
python research_agent/infrastructure/scripts/create_table_simple.py

# 6. Verify Databricks works
python research_agent/infrastructure/scripts/query_databricks_dtypes.py
```

---

## Known Issues Fixed (2025-11-23)

### Issue: Pandas Int64 vs Numpy int64

**Problem:** Lambda code used `.astype('int64')` which creates pandas Int64 (nullable) instead of numpy int64

**Symptoms:**
- Pandas shows "Int64" dtype
- Databricks error: "Expected Spark type double, actual Parquet type INT64"

**Fix:** Changed to `.astype(np.int64)` in lambda code (lines 652, 655, 722, 725)

**Verification:** Run `check_silver_dtypes.py` - should show int64 (not Int64)

---

### Issue: Databricks Table Schema Wrong

**Problem:** Old table defined all columns as DOUBLE (including count columns)

**Symptoms:**
- Query fails with type mismatch
- Missing group_ALL_* columns

**Fix:** Recreate table using `create_table_simple.py`

**Result:** Count columns now BIGINT, tone columns DOUBLE

---

## Script Dependencies

All scripts require:
- Python 3.11+
- Virtual environment activated
- Packages: `boto3`, `awswrangler`, `pandas`, `databricks-sql-connector`

**Install:**
```bash
source venv/bin/activate
pip install boto3 awswrangler pandas databricks-sql-connector
```

---

## Configuration

Scripts use hardcoded values (from project defaults):

**AWS:**
- Region: `us-west-2`
- Lambda: `gdelt-silver-backfill`
- S3 Path: `s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/`
- DynamoDB: `groundtruth-capstone-file-tracking`
- SQS: `groundtruth-gdelt-silver-backfill-queue`

**Databricks:**
- Host: `dbc-5e4780f4-fcec.cloud.databricks.com`
- Warehouse: `d88ad009595327fd`
- Table: `commodity.silver.gdelt_wide`
- Token: Hardcoded (consider using env var)

**To change defaults:** Edit the script files directly

---

**Last Updated:** 2025-11-23
**Tested With:** Lambda last modified 2025-11-23 23:45:48 UTC
