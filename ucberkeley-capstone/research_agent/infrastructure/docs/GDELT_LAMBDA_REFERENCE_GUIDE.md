# GDELT Lambda Function Reference Guide

**CRITICAL**: READ THIS BEFORE UPDATING ANY LAMBDA FUNCTION

**Last Updated**: 2025-11-23 23:35 UTC

---

## ⚠️ THE PROBLEM

There are **11 deployed GDELT Lambda functions** in AWS, but only **3 are actively used**.

**THE CRITICAL ISSUE**:
- `gdelt-silver-transform` → ❌ **DEPRECATED** (no longer used)
- `gdelt-silver-backfill` → ✅ **ACTIVE** (ALL silver processing)

**THERE IS ONLY ONE ACTIVE SILVER LAMBDA**: `gdelt-silver-backfill`

---

## 🎯 ACTIVE LAMBDA FUNCTIONS (USE THESE)

**THERE ARE ONLY 3 ACTIVE LAMBDAS - ALL OTHERS ARE LEGACY**

###  1. gdelt-daily-discovery
**AWS Function Name**: `gdelt-daily-discovery`
**Source Code**: `research_agent/infrastructure/lambda/functions/gdelt-daily-discovery/lambda_function.py`
**Purpose**: Discovers new GDELT files daily by streaming master list
**Trigger**: EventBridge schedule (2 AM UTC daily)
**Memory**: 512 MB
**Timeout**: 300s
**Last Updated**: 2025-11-22
**Status**: ✅ PRODUCTION

**When to Update**:
- Changing discovery logic
- Adjusting date range scanning
- Fixing master list parsing

---

### 2. gdelt-bronze-transform
**AWS Function Name**: `gdelt-bronze-transform`
**Source Code**: `research_agent/infrastructure/lambda/functions/gdelt-csv-bronze-direct/lambda_function.py`
**Purpose**: Downloads CSV from GDELT, filters, writes Bronze Parquet
**Trigger**: SQS queue `groundtruth-gdelt-backfill-queue`
**Memory**: 2048 MB
**Timeout**: 900s
**Last Updated**: 2025-11-22
**Status**: ✅ PRODUCTION

**IMPORTANT NAMING**:
- Source folder is `gdelt-csv-bronze-direct/`
- Deployed AWS function is `gdelt-bronze-transform`
- This is the DAILY CSV→Bronze function

**When to Update**:
- Changing CSV download logic
- Modifying bronze schema
- Adjusting filtering logic

---

### 3. gdelt-silver-backfill (SILVER PROCESSING - ACTIVE)
**AWS Function Name**: `gdelt-silver-backfill`
**Source Code**: `research_agent/infrastructure/lambda/functions/gdelt-silver-backfill/lambda_function.py`
**Purpose**: Silver transformation - Bronze → Silver wide format (ALL dates)
**Trigger**: SQS queue `groundtruth-gdelt-silver-backfill-queue`
**Memory**: 3008 MB
**Timeout**: 900s
**Last Updated**: 2025-11-23 23:45:48 UTC
**Last Tested**: 2025-11-23 23:45 UTC (date 2022-06-08: 17,397 bronze → 2 silver rows ✓)
**Status**: ✅ PRODUCTION - Fixed data type bug

**CRITICAL**:
- **THIS IS THE ONLY ACTIVE SILVER LAMBDA**
- Processes ALL silver transformations (historical + daily)
- Uses chunked processing for large bronze sets (>30 files - lowered from 50)
- Triggered by SQS messages with date format: `{'date': 'YYYY-MM-DD'}`

**✅ FIXED** (2025-11-23 23:45 UTC):
- Data type bug resolved: Changed `.astype('int64')` to `.astype(np.int64)`
- Databricks table recreated with correct schema (BIGINT for counts, DOUBLE for tones)
- Verified working with test queries

**When to Update**:
- Changing silver schema (add columns, change aggregations)
- Modifying theme grouping logic
- Fixing data type issues
- Adjusting chunking logic

**DEPLOYMENT**:
```bash
cd research_agent/infrastructure/lambda/functions/gdelt-silver-backfill
zip deployment.zip lambda_function.py
aws lambda update-function-code \
  --function-name gdelt-silver-backfill \
  --zip-file fileb://deployment.zip \
  --region us-west-2
```

---

---

## ❌ LEGACY LAMBDA FUNCTIONS (DO NOT USE)

### MOVED TO LEGACY: gdelt-silver-transform
**AWS Function Name**: `gdelt-silver-transform` (still deployed but NOT USED)
**Source Code**: `research_agent/infrastructure/legacy/lambda_functions/gdelt-silver-transform/` (moved to legacy)
**Reason**: Replaced by `gdelt-silver-backfill` for ALL silver processing
**Last Updated**: 2025-11-23 19:06
**Status**: ⚠️ LEGACY - DO NOT USE OR UPDATE

**Why Deprecated**:
- `gdelt-silver-backfill` now handles BOTH historical AND daily silver processing
- Simpler architecture with single silver Lambda
- EventBridge trigger disabled in favor of SQS-based processing

**Can Delete?**: ✅ After 30-day observation period

---

### gdelt-jsonl-bronze-transform (BACKFILL COMPLETE)
**AWS Function Name**: `gdelt-jsonl-bronze-transform`
**Source Code**: `research_agent/infrastructure/lambda/functions/gdelt-bronze-transform/lambda_function.py`
**Purpose**: Historical backfill - JSONL → Bronze Parquet
**Trigger**: SQS queue (DISABLED)
**Memory**: 2048 MB
**Timeout**: 900s
**Last Updated**: 2025-11-21
**Status**: ⏸️ COMPLETE (168,704 files processed)

**When to Update**:
- Never - backfill is complete
- Can be re-enabled if historical backfill needed again

### Other Legacy Functions

| Function Name | Purpose | Status | Can Delete? |
|--------------|---------|---------|-------------|
| `gdelt-processor` | Old monolithic processor | LEGACY | ✅ After 30 days |
| `gdelt-generate-date-batches` | Experimental batch generator | LEGACY | ✅ After 30 days |
| `gdelt-queue-monitor` | Monitoring utility | LEGACY | ✅ After 30 days |
| `gdelt-sqs-loader` | Experimental SQS loader | LEGACY | ✅ After 30 days |
| `gdelt-sqs-trigger-manager` | SQS trigger utility | LEGACY | ✅ After 30 days |
| `gdelt-silver-discovery` | Silver date scanner | NOT USED | ✅ After testing |

---

## 🔄 DEPLOYMENT WORKFLOW

### Scenario 1: Update Silver Schema (e.g., add columns, change aggregations)

**Steps**:
1. ✅ Update `research_agent/infrastructure/lambda/functions/gdelt-silver-backfill/lambda_function.py`
2. ✅ Test locally with sample data
3. ✅ Deploy to `gdelt-silver-backfill`
4. ✅ Test with single date (verify Parquet data types)
5. ✅ If test passes, queue remaining dates in SQS

**IMPORTANT**: There is ONLY ONE active silver Lambda (`gdelt-silver-backfill`).
Do NOT update the legacy `gdelt-silver-transform` function.

---

### Scenario 2: Update Bronze Logic

**Steps**:
1. ✅ Update `research_agent/infrastructure/lambda/functions/gdelt-csv-bronze-direct/lambda_function.py`
2. ✅ Test locally
3. ✅ Deploy to `gdelt-bronze-transform` (AWS function name)
4. ✅ Test with small SQS batch (10 files)
5. ✅ Monitor CloudWatch logs

**Note**: Only ONE bronze function is active (daily CSV→Bronze)

---

### Scenario 3: Update Discovery Logic

**Steps**:
1. ✅ Update `research_agent/infrastructure/lambda/functions/gdelt-daily-discovery/lambda_function.py`
2. ✅ Test locally with master list streaming
3. ✅ Deploy to `gdelt-daily-discovery`
4. ✅ Trigger manually to verify SQS queue loading
5. ✅ Monitor next scheduled run (2 AM UTC)

---

## 📋 DEPLOYMENT COMMANDS

**ACTIVE FUNCTIONS ONLY - DO NOT DEPLOY LEGACY FUNCTIONS**

### Deploy gdelt-daily-discovery
```bash
cd research_agent/infrastructure/lambda/functions/gdelt-daily-discovery
zip -r deployment.zip lambda_function.py
aws lambda update-function-code \
  --function-name gdelt-daily-discovery \
  --zip-file fileb://deployment.zip \
  --region us-west-2
```

### Deploy gdelt-bronze-transform (CSV→Bronze)
```bash
cd research_agent/infrastructure/lambda/functions/gdelt-csv-bronze-direct
zip -r deployment.zip lambda_function.py
aws lambda update-function-code \
  --function-name gdelt-bronze-transform \
  --zip-file fileb://deployment.zip \
  --region us-west-2
```

### Deploy gdelt-silver-backfill (SILVER - ONLY ACTIVE SILVER LAMBDA)
```bash
cd research_agent/infrastructure/lambda/functions/gdelt-silver-backfill
zip deployment.zip lambda_function.py
aws lambda update-function-code \
  --function-name gdelt-silver-backfill \
  --zip-file fileb://deployment.zip \
  --region us-west-2
```

---

## ⚠️ COMMON MISTAKES TO AVOID

### ❌ Mistake 1: Updating the Wrong Silver Function
**Problem**: Try to update legacy `gdelt-silver-transform` thinking it's still active
**Result**: Wasted time - function is not used anymore
**Fix**: ONLY update `research_agent/infrastructure/lambda/functions/gdelt-silver-backfill/lambda_function.py` for silver changes

### ❌ Mistake 2: Wrong Function Name Mapping
**Problem**: Think `gdelt-csv-bronze-direct/` deploys to function with same name
**Reality**: It deploys to `gdelt-bronze-transform` (different name!)
**Fix**: Check this guide for AWS function name vs folder name mappings

### ❌ Mistake 3: Thinking There Are Two Silver Functions
**Problem**: Believe both `gdelt-silver-transform` and `gdelt-silver-backfill` are active
**Result**: Confusion about which one to update
**Fix**: There is ONLY ONE active silver Lambda: `gdelt-silver-backfill`

### ❌ Mistake 4: Forgetting to Test After Deployment
**Problem**: Deploy code without testing on real AWS data
**Result**: Errors discovered in production (failed Databricks queries)
**Fix**: Always test with single date after deployment:
```python
# IMPORTANT: Use 'gdelt-silver-backfill' (NOT 'gdelt-silver-transform')
# Date format must be 'YYYY-MM-DD'
lambda_client.invoke(
    FunctionName='gdelt-silver-backfill',
    Payload=json.dumps({'date': '2024-01-15'})
)
```

---

## 🔍 TROUBLESHOOTING

### "I updated the code but Lambda is still running old version"
1. Check LastModified timestamp: `aws lambda get-function --function-name <name>`
2. Verify deployment succeeded (no errors in CLI output)
3. Check CloudWatch logs - might be deployment issue

### "Databricks shows type mismatch errors"
1. Check if both silver functions have same schema
2. Verify `astype('int64', copy=False)` is used (not just `astype('int64')`)
3. Delete old S3 silver files and re-process with updated Lambda

### "SQS queue not draining"
1. Check Event Source Mapping is enabled
2. Verify Lambda has correct permissions
3. Check CloudWatch logs for Lambda errors
4. Verify queue visibility timeout matches Lambda timeout

---

## 📊 ARCHITECTURE SUMMARY

```
DAILY INCREMENTAL PIPELINE:
EventBridge (2 AM) → gdelt-daily-discovery → SQS → gdelt-bronze-transform → Bronze S3
EventBridge (3 AM) → gdelt-silver-transform → Silver S3 → Databricks

HISTORICAL BACKFILL PIPELINE:
Manual SQS Load → gdelt-jsonl-bronze-transform → Bronze S3  (COMPLETE)
Manual SQS Load → gdelt-silver-backfill → Silver S3 → Databricks  (ONGOING)
```

---

## 🎯 DECISION TREE: Which Lambda Should I Update?

**Q: Are you adding/changing silver columns or aggregations?**
→ YES: Update `research_agent/infrastructure/lambda/functions/gdelt-silver-backfill/lambda_function.py` and deploy to `gdelt-silver-backfill`

**Q: Are you fixing bronze schema or CSV download logic?**
→ YES: Update `gdelt-bronze-transform` (folder: gdelt-csv-bronze-direct)

**Q: Are you changing discovery or master list scanning?**
→ YES: Update `gdelt-daily-discovery`

**Q: Are you processing ANY silver data (historical OR daily)?**
→ YES: Queue date in SQS `groundtruth-gdelt-silver-backfill-queue`, triggers `gdelt-silver-backfill`

---

## 🧪 TESTING PROCEDURE: Silver Lambda

**✅ AUTOMATED SCRIPTS AVAILABLE**: See `research_agent/infrastructure/scripts/README.md`

**Helper Scripts:**
- `clear_test_environment.py` - Clears S3, DynamoDB, SQS
- `test_lambda.py` - Tests lambda with direct invocation
- `check_silver_dtypes.py` - Verifies parquet data types
- `create_table_simple.py` - Recreates Databricks table
- `query_databricks_dtypes.py` - Tests Databricks queries

**IMPORTANT**: Before loading dates into SQS, ALWAYS test the Lambda on a single date to verify:
1. Parquet data types (int64 for count, float64 for tone)
2. group_ALL columns exist
3. No Databricks type mismatch errors

**ARCHITECTURE NOTE**:
- **Production**: Lambda triggered by SQS queue `groundtruth-gdelt-silver-backfill-queue`
- **Testing**: Use direct invocation (simpler format)

### Step 1: Clear Test Environment

**Using helper script:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/clear_test_environment.py
```

**Manual (if needed):**
```python
import boto3
import awswrangler as wr

sqs = boto3.client('sqs', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('groundtruth-capstone-file-tracking')

# 1. Purge SQS queue
queue_url = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'
sqs.purge_queue(QueueUrl=queue_url)

# 2. Delete S3 silver files
wr.s3.delete_objects(path='s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/')

# 3. Delete DynamoDB SILVER_* entries
response = table.scan(FilterExpression='begins_with(file_name, :prefix)', ExpressionAttributeValues={':prefix': 'SILVER_'})
for item in response.get('Items', []):
    table.delete_item(Key={'file_name': item['file_name']})
```

### Step 2: Test Lambda with ONE Date

**Using helper script:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/test_lambda.py
```

**Manual (if needed):**
```python
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-west-2')

# IMPORTANT: Use YYYY-MM-DD format (e.g., '2022-06-08')
test_date = '2022-06-08'

response = lambda_client.invoke(
    FunctionName='gdelt-silver-backfill',
    InvocationType='RequestResponse',
    Payload=json.dumps({'date': test_date})
)

result = json.loads(response['Payload'].read())
body = json.loads(result['body'])
print(json.dumps(body, indent=2))
```

**Expected output**:
```json
{
  "status": "success",
  "date": "2022-06-08",
  "bronze_records": 17397,
  "wide_rows": 2,
  "wide_columns": 112
}
```

### Step 3: Verify Data Types

**Using helper script:**
```bash
source venv/bin/activate
python research_agent/infrastructure/scripts/check_silver_dtypes.py
```

**Manual (if needed):**
```python
import awswrangler as wr
import pandas as pd

# Read silver data
df = wr.s3.read_parquet('s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/', dataset=True)

# Check data types
count_cols = [c for c in df.columns if '_count' in c]
tone_cols = [c for c in df.columns if 'tone_' in c and '_count' not in c]
all_cols = [c for c in df_test.columns if 'group_ALL_' in c]

# Verify types
wrong_counts = [c for c in count_cols if str(df_test[c].dtype) != 'int64']
wrong_tones = [c for c in tone_cols if str(df_test[c].dtype) != 'float64']

if not wrong_counts and not wrong_tones and len(all_cols) > 0:
    print("✓ TEST PASSED - All types correct and group_ALL columns exist")
else:
    print("✗ TEST FAILED - Fix issues before SQS loading")
```

### Step 4: If Test Passes → Load Dates into SQS

**IMPORTANT**: Only load dates into SQS AFTER verifying the test passed.

**How production works**:
- Dates are loaded into SQS queue: `groundtruth-gdelt-silver-backfill-queue`
- Lambda is triggered automatically via Event Source Mapping
- Each SQS message contains: `{"date": "YYYY-MM-DD"}`
- Lambda processes date and writes to S3 silver layer

**Loading dates into SQS** (for full backfill):
```python
import boto3
import json

sqs = boto3.client('sqs', region_name='us-west-2')
queue_url = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'

# List of dates to process
dates_to_process = ['2021-01-01', '2021-01-02', '2021-01-03']  # etc.

for date_str in dates_to_process:
    sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({'date': date_str})
    )
    print(f"Queued: {date_str}")
```

The Lambda will process dates automatically from the queue.

---

**END OF REFERENCE GUIDE**

---

## ✅ VERIFIED WORKING PROCEDURES (2025-11-23 22:24 UTC)

### Test Environment Clearing
```python
# VERIFIED WORKING
import boto3
import awswrangler as wr

sqs = boto3.client('sqs', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('groundtruth-capstone-file-tracking')

queue_url = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'

# Successfully cleared:
# - SQS queue: Purged ✓
# - S3 silver files: 0 deleted (already empty) ✓
# - DynamoDB: 1 SILVER_* entry deleted ✓

sqs.purge_queue(QueueUrl=queue_url)
wr.s3.delete_objects(path='s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/')
response = table.scan(FilterExpression='begins_with(file_name, :prefix)', ExpressionAttributeValues={':prefix': 'SILVER_'})
for item in response.get('Items', []):
    table.delete_item(Key={'file_name': item['file_name']})
```

### Lambda Direct Invocation
```python
# VERIFIED WORKING - Test date 2022-06-08
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-west-2')

response = lambda_client.invoke(
    FunctionName='gdelt-silver-backfill',
    InvocationType='RequestResponse',
    Payload=json.dumps({'date': '2022-06-08'})
)

result = json.loads(response['Payload'].read())
body = json.loads(result['body'])

# Confirmed result:
# {
#   "status": "success",
#   "date": "2022-06-08",
#   "bronze_records": 17397,
#   "wide_rows": 2,
#   "wide_columns": 112
# }
```

### What's Confirmed Working

1. **Date Format**: `'YYYY-MM-DD'` works correctly (tested with '2022-06-08')
2. **Direct Invocation**: Lambda accepts `{'date': 'YYYY-MM-DD'}` format
3. **Date-to-File Matching**: Lambda correctly associates dates with bronze files
   - Input: '2022-06-08'  
   - Converts to: '20220608'
   - Matches files: `20220608*.gkg.parquet`
4. **Test Environment Clearing**: All 3 steps execute successfully
5. **Bronze File Lookup**: Successfully found 17,397 records for test date

### Bronze Column Schema
**Confirmed** (from reading actual bronze files):
```python
['date', 'source_url', 'themes', 'locations', 'persons', 'organizations', 'tone', 'all_names']
```
- `date` column contains raw GDELT timestamps like '20220608141500'
- No `article_date` column in bronze (Lambda converts date format internally)

---

**Last Updated**: 2025-11-23 22:26 UTC
