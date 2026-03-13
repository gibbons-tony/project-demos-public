# GDELT Data Pipeline Orchestration (Step Functions)

## Overview

Automated pipeline orchestration for GDELT data processing through Bronze and Silver layers using AWS Step Functions. Supports both **daily incremental updates** and **historical backfill**.

## Architecture Options

### 1. Daily Master Pipeline (Recommended for Ongoing Operations)

Scheduled daily pipeline that orchestrates incremental GDELT downloads through Bronze and Silver transformations.

```
┌──────────────────────────────────────────┐
│  EventBridge Schedule (Daily @ 2am UTC)  │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  gdelt-daily-master-pipeline             │
│  (Master Orchestrator)                   │
└──────────────┬───────────────────────────┘
               │
               ├──► 1. GDELT Self-Healing Download
               │    └─ Lambda: gdelt-processor (mode=incremental)
               │       Checks DynamoDB & downloads ANY missing files
               │
               ├──► 2. Bronze → Silver Pipeline (if new files)
               │    └─ Nested: gdelt-bronze-silver-pipeline
               │       ├─ Bronze Transform (batched)
               │       └─ Silver Transform
               │
               └──► Complete (or skip if no new files)
```

**Key Features:**
- **Self-Healing**: GDELT processor checks DynamoDB and downloads ANY missing files, not just "yesterday's files"
  - If pipeline skipped a day due to failure, next run will automatically catch up
  - If individual files failed to download (404s, network errors), they'll be retried
  - Ensures complete data coverage without manual intervention
- Runs daily at 2am UTC via EventBridge schedule
- Only processes Bronze → Silver if new GDELT files were downloaded
- Uses `.sync:2` integration to wait for child pipeline completion
- Prevents thrashing by chaining sequentially

### 2. Bronze → Silver Pipeline (Child Pipeline)

Reusable pipeline for batch processing JSONL files to Bronze Parquet and Silver aggregations.

```
┌─────────────────────────────────────────┐
│  gdelt-bronze-silver-pipeline           │
└──────────────┬──────────────────────────┘
               │
               ├──► Bronze Transform (Loop)
               │    ├─ Convert JSONL → Parquet
               │    ├─ Process 100 files/batch
               │    ├─ Track with DynamoDB
               │    └─ Loop until all done
               │
               └──► Silver Transform
                    ├─ Read Bronze Parquet
                    ├─ Aggregate by theme
                    └─ Create wide format
```

### 3. Historical Backfill Pipeline (One-Time Use)

For initial historical data processing (2021-2025).

```
┌──────────────────────────────────────────┐
│  groundtruth-gdelt-backfill              │
│  (with Bronze → Silver chaining)         │
└──────────────┬───────────────────────────┘
               │
               ├──► GDELT Backfill (Parallel Map)
               │    ├─ Process date ranges in parallel
               │    ├─ MaxConcurrency: 5
               │    └─ Download historical JSONL files
               │
               └──► Trigger Bronze → Silver Pipeline
                    └─ Wait for completion (.sync:2)
```

## Components

### 1. State Machine
- **Name**: `gdelt-bronze-silver-pipeline`
- **ARN**: `arn:aws:states:us-west-2:534150427458:stateMachine:gdelt-bronze-silver-pipeline`
- **IAM Role**: `gdelt-stepfunctions-role`

### 2. Lambda Functions
- **Bronze**: `gdelt-bronze-transform` - Converts JSONL to Parquet (100 files per invocation)
- **Silver**: `gdelt-silver-transform` - Creates wide-format aggregations

### 3. DynamoDB Tracking
- **Table**: `groundtruth-capstone-bronze-tracking`
- **Purpose**: Track processed files to prevent reprocessing

## State Machine Flow

1. **BronzeTransformBatch** - Process batch of JSONL files
2. **CheckBronzeSuccess** - Verify Lambda succeeded
3. **CheckRemainingFiles** - Check if more files to process
4. **PrepareNextBatch** - Calculate next offset
5. **WaitBetweenBatches** - 5-second delay to avoid throttling
6. **Loop back** to step 1 if more files remain
7. **AllBronzeComplete** - All files processed
8. **SilverTransform** - Create wide-format aggregations
9. **CheckSilverSuccess** - Verify Silver succeeded
10. **PipelineSuccess** - Complete

## Input Parameters

```json
{
  "offset": 0,              // Starting file index
  "limit": 100,             // Files per batch
  "processed_so_far": 0,    // Running total of files
  "total_records": 0,       // Running total of records
  "silver_start_date": "2021-01-01",  // Silver date range start
  "silver_end_date": "2025-12-31"     // Silver date range end
}
```

## Usage

### Test with Small Batch (10 files)
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-west-2:534150427458:stateMachine:gdelt-bronze-silver-pipeline \
  --name test-bronze-10-$(date +%s) \
  --input '{"offset":0,"limit":10,"processed_so_far":0,"total_records":0,"silver_start_date":"2021-01-01","silver_end_date":"2021-01-31"}' \
  --region us-west-2
```

### Process All Files (21,267 files, ~3.5 hours)
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-west-2:534150427458:stateMachine:gdelt-bronze-silver-pipeline \
  --name backfill-full-bronze-$(date +%s) \
  --input '{"offset":0,"limit":100,"processed_so_far":0,"total_records":0,"silver_start_date":"2021-01-01","silver_end_date":"2025-12-31"}' \
  --region us-west-2
```

### Resume from Offset (if interrupted)
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-west-2:534150427458:stateMachine:gdelt-bronze-silver-pipeline \
  --name resume-bronze-$(date +%s) \
  --input '{"offset":5000,"limit":100,"processed_so_far":5000,"total_records":125000,"silver_start_date":"2021-01-01","silver_end_date":"2025-12-31"}' \
  --region us-west-2
```

## Monitoring

### List Recent Executions
```bash
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-west-2:534150427458:stateMachine:gdelt-bronze-silver-pipeline \
  --max-results 10 \
  --region us-west-2
```

### Get Execution Status
```bash
# Get execution ARN from list-executions, then:
aws stepfunctions describe-execution \
  --execution-arn <EXECUTION_ARN> \
  --region us-west-2
```

### View Execution History
```bash
aws stepfunctions get-execution-history \
  --execution-arn <EXECUTION_ARN> \
  --region us-west-2
```

### Monitor Lambda Logs
```bash
# Bronze Lambda
aws logs tail /aws/lambda/gdelt-bronze-transform --follow --region us-west-2

# Silver Lambda
aws logs tail /aws/lambda/gdelt-silver-transform --follow --region us-west-2
```

## Performance

- **Bronze Processing Rate**: ~100 files per minute
- **Total Files**: 21,267
- **Estimated Total Time**: ~3.5 hours for full backfill
- **Cost per Execution**:
  - Lambda: ~$5-10 (based on 15 min timeout × 213 invocations)
  - Step Functions: <$1 (state transitions)
  - DynamoDB: <$1 (tracking operations)

## Error Handling

### Automatic Retries
- Lambda failures retry 3 times with exponential backoff
- 5-second wait between batches prevents throttling

### Manual Recovery
If execution fails:
1. Check execution history for error details
2. Identify last successful offset
3. Resume from that offset using resume command above

### DynamoDB Tracking
Files are only marked as processed after successful Bronze transform. Failed files will be retried on next run.

## Output

### Bronze Layer
- **Location**: `s3://groundtruth-capstone/processed/gdelt/bronze/gdelt/`
- **Format**: Parquet (Snappy compressed)
- **Schema**:
  - `article_date` (DATE)
  - `source_url`, `themes`, `locations`, `all_names` (STRING)
  - `tone_avg`, `tone_positive`, `tone_negative`, `tone_polarity` (DOUBLE)
  - `has_coffee`, `has_sugar` (BOOLEAN)

### Silver Layer
- **Location**: `s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/`
- **Format**: Parquet (Snappy compressed), partitioned by `commodity`
- **Schema**: Wide format with 100+ columns for theme aggregations

## Files

- `gdelt_bronze_silver_pipeline.json` - State machine definition
- `deploy_gdelt_pipeline.sh` - Deployment script
- `README.md` - This file

## Related

- Bronze Lambda: `/Users/markgibbons/capstone/ucberkeley-capstone/research_agent/infrastructure/lambda/functions/gdelt-bronze-transform/`
- Silver Lambda: `/Users/markgibbons/capstone/ucberkeley-capstone/research_agent/infrastructure/lambda/functions/gdelt-silver-transform/`
- Databricks Tables: `/Users/markgibbons/capstone/ucberkeley-capstone/research_agent/infrastructure/databricks/`
