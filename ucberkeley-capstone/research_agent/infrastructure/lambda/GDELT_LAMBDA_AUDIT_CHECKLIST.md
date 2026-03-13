# GDELT Lambda Configuration Audit Checklist

**Date**: 2025-11-18
**Account**: 534150427458 (groundtruth)
**Region**: us-west-2
**Lambda**: gdelt-processor

---

## Critical Issues Found

### 🔴 Issue 1: DynamoDB Table Name Mismatch
- **Lambda Code**: `TRACKING_TABLE = 'gdelt-file-tracking'`
- **Deployed Config**: `TRACKING_TABLE = 'groundtruth-capstone-file-tracking'`
- **Impact**: Lambda can't track which files it has processed
- **Fix**: Update Lambda environment variable OR update code

### 🔴 Issue 2: No EventBridge Schedule
- **Status**: NOT CONFIGURED
- **Impact**: Lambda only runs when manually triggered
- **Explains**: Why only Oct/Nov 2025 data exists (manual uploads)
- **Fix**: Set up EventBridge schedule for daily/hourly execution

### 🟡 Issue 3: Historical Data Missing
- **S3 has**: 214 files across 48 dates
- **Databricks has**: Only 32 dates loaded
- **Missing**: 1,003 days of historical data (Jan 2021 - Sep 2023)
- **Fix**: Trigger Lambda backfill

---

## Manual Verification Steps

Run these commands in your terminal with your AWS credentials:

### Step 1: Verify Lambda Function Exists

```bash
aws lambda get-function \
  --function-name gdelt-processor \
  --region us-west-2 \
  --query 'Configuration.{Runtime:Runtime,Memory:MemorySize,Timeout:Timeout,LastModified:LastModified}'
```

**Expected**: Function exists with:
- Runtime: python3.11
- Memory: 2048 MB
- Timeout: 900 seconds

### Step 2: Check Environment Variables

```bash
aws lambda get-function-configuration \
  --function-name gdelt-processor \
  --region us-west-2 \
  --query 'Environment.Variables'
```

**Expected**:
```json
{
  "S3_BUCKET": "groundtruth-capstone",
  "S3_RAW_PREFIX": "landing/gdelt/raw/",
  "S3_FILTERED_PREFIX": "landing/gdelt/filtered/",
  "TRACKING_TABLE": "groundtruth-capstone-file-tracking"
}
```

**Verify**: Does TRACKING_TABLE match this? If not, we need to fix it.

### Step 3: Check DynamoDB Table Exists

```bash
aws dynamodb describe-table \
  --table-name groundtruth-capstone-file-tracking \
  --region us-west-2 \
  --query 'Table.{Status:TableStatus,ItemCount:ItemCount,Size:TableSizeBytes}'
```

**If table doesn't exist**, create it:
```bash
aws dynamodb create-table \
  --table-name groundtruth-capstone-file-tracking \
  --attribute-definitions AttributeName=file_name,AttributeType=S \
  --key-schema AttributeName=file_name,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-west-2
```

### Step 4: Check EventBridge Schedule

```bash
aws events list-rules \
  --region us-west-2 \
  --name-prefix gdelt
```

**Expected**: Should show a rule (probably empty)

If empty, create schedule:
```bash
# Create rule for daily execution at midnight UTC
aws events put-rule \
  --name gdelt-processor-daily \
  --schedule-expression "cron(0 0 * * ? *)" \
  --state ENABLED \
  --region us-west-2

# Add Lambda as target
aws events put-targets \
  --rule gdelt-processor-daily \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-west-2:534150427458:function:gdelt-processor","Input"="{\"mode\":\"incremental\"}" \
  --region us-west-2

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name gdelt-processor \
  --statement-id gdelt-processor-daily-event \
  --action 'lambda:InvokeFunction' \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-west-2:534150427458:rule/gdelt-processor-daily \
  --region us-west-2
```

### Step 5: Test Lambda Invocation

```bash
# Test incremental mode (safe - processes latest files only)
aws lambda invoke \
  --function-name gdelt-processor \
  --region us-west-2 \
  --payload '{"mode":"incremental"}' \
  /tmp/gdelt-response.json

cat /tmp/gdelt-response.json
```

**Expected response**:
```json
{
  "statusCode": 200,
  "body": "{\"processed_files\": X, \"total_records\": Y, \"filtered_records\": Z}"
}
```

### Step 6: Check CloudWatch Logs

```bash
# Get latest log stream
aws logs describe-log-streams \
  --log-group-name /aws/lambda/gdelt-processor \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --region us-west-2 \
  --query 'logStreams[0].logStreamName'

# Replace LOG_STREAM_NAME with output from above
aws logs get-log-events \
  --log-group-name /aws/lambda/gdelt-processor \
  --log-stream-name LOG_STREAM_NAME \
  --region us-west-2 \
  --limit 50
```

---

## Fixing the TRACKING_TABLE Mismatch

### Option A: Update Lambda Environment Variable (EASIEST)

```bash
aws lambda update-function-configuration \
  --function-name gdelt-processor \
  --region us-west-2 \
  --environment "Variables={S3_BUCKET=groundtruth-capstone,S3_RAW_PREFIX=landing/gdelt/raw/,S3_FILTERED_PREFIX=landing/gdelt/filtered/,TRACKING_TABLE=groundtruth-capstone-file-tracking}"
```

### Option B: Update Code and Redeploy

1. Edit `lambda_function.py` line 29:
   ```python
   TRACKING_TABLE = 'groundtruth-capstone-file-tracking'  # Changed from 'gdelt-file-tracking'
   ```

2. Repackage and deploy:
   ```bash
   cd /Users/markgibbons/capstone/ucberkeley-capstone/research_agent/infrastructure/lambda/functions/berkeley-datasci210-capstone-processor
   zip -r ../../../updated/gdelt-processor.zip .

   aws lambda update-function-code \
     --function-name gdelt-processor \
     --zip-file fileb://../../../updated/gdelt-processor.zip \
     --region us-west-2
   ```

---

## Triggering Historical Backfill

⚠️ **WARNING**: This will download ~97,000 files (1,002 days × 96 files/day)

### Small Test First (1 day)

```bash
aws lambda invoke \
  --function-name gdelt-processor \
  --region us-west-2 \
  --invocation-type Event \
  --payload '{"mode":"backfill","start_date":"2021-01-02","end_date":"2021-01-02"}' \
  /tmp/backfill-test.json
```

Monitor in CloudWatch. If successful, proceed with larger backfill.

### Full Backfill (WARNING: Long-running)

Due to Lambda 15-minute timeout, you need to invoke multiple times:

```bash
# Backfill 2021-01-02 to 2021-12-31 (364 days)
aws lambda invoke \
  --function-name gdelt-processor \
  --region us-west-2 \
  --invocation-type Event \
  --payload '{"mode":"backfill","start_date":"2021-01-02","end_date":"2021-12-31"}' \
  /tmp/backfill-2021.json

# Backfill 2022 (365 days)
aws lambda invoke \
  --function-name gdelt-processor \
  --region us-west-2 \
  --invocation-type Event \
  --payload '{"mode":"backfill","start_date":"2022-01-01","end_date":"2022-12-31"}' \
  /tmp/backfill-2022.json

# Backfill 2023-01-01 to 2023-09-29 (272 days)
aws lambda invoke \
  --function-name gdelt-processor \
  --region us-west-2 \
  --invocation-type Event \
  --payload '{"mode":"backfill","start_date":"2023-01-01","end_date":"2023-09-29"}' \
  /tmp/backfill-2023.json
```

Each invocation processes max 50 files (hardcoded in lambda_function.py line 166). You'll need to invoke MANY times.

### Better Approach: Use Step Functions or Increase Batch Size

Edit `lambda_function.py` line 166-167:
```python
# Change from:
max_files_per_invocation = 50

# To:
max_files_per_invocation = 500  # Process more per invocation
```

Then redeploy before triggering backfill.

---

## Verification After Fixes

### 1. Check S3 File Count

```bash
aws s3 ls s3://groundtruth-capstone/landing/gdelt/filtered/ \
  --recursive \
  --region us-west-2 \
  | wc -l
```

### 2. Check Databricks Table

Run in Databricks SQL:
```sql
SELECT
  COUNT(DISTINCT TO_DATE(date, 'yyyyMMddHHmmss')) as unique_days,
  MIN(TO_DATE(date, 'yyyyMMddHHmmss')) as first_date,
  MAX(TO_DATE(date, 'yyyyMMddHHmmss')) as last_date,
  COUNT(*) as total_records
FROM commodity.bronze.gdelt
```

**Target**: Should see ~1,050 unique days after full backfill

---

## Summary Checklist

- [ ] Lambda function exists and has correct config
- [ ] Environment variable TRACKING_TABLE is set correctly
- [ ] DynamoDB tracking table exists
- [ ] EventBridge schedule is configured for daily execution
- [ ] Test Lambda invocation succeeds
- [ ] Historical backfill triggered
- [ ] Databricks table has continuous data coverage

---

## Next Steps After Audit

1. **If Lambda config is wrong**: Fix environment variables or redeploy
2. **If table doesn't exist**: Create DynamoDB table
3. **If no schedule exists**: Set up EventBridge daily trigger
4. **If test invocation works**: Trigger historical backfill
5. **After backfill completes**: Reload Databricks table to pick up new S3 files

Let me know what you find!
